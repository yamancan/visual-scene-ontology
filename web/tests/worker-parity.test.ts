// Offline parity gate for the Pyodide verification stack — the browser-side
// twin of `make cli-check`. Runs in Node with ZERO network: loadPyodide reads
// the exact-pinned npm runtime from node_modules/pyodide, and the wheels are
// installed from the COMMITTED files under static/pyodide/wheels/ (the same
// bytes the worker loads from /pyodide/wheels/, sha256-pinned by
// wheels-lock.test.ts). What passes here is what ships.
//
// Five pinned behaviors (the verified spike, now CI-enforced):
//   1. p2t over the throne-room scene byte-equals `vson convert p2t` output.
//      The committed golden is the vson_t of the BAKED gallery envelope
//      (web/static/demos/envelopes/gallery/11_throne_room.json): frozen Rust
//      CLI output whose bytes envelope-check and cached-envelopes already
//      guard. (examples/throne_room.ttl is a hand-authored worked example —
//      comment header, extra prefixes, prefixed-name style — and was never
//      emitter output, so it cannot serve as the byte golden.) Host-side,
//      `make cli-check --bytes` pins Rust==Python over the full corpus; this
//      test pins the in-Pyodide interpreter to those same bytes.
//   2. validate(examples/throne_room.ttl) passes BOTH gates (SHACL + OWL RL).
//   3. validate(bad_no_viewer.ttl) fails Gate 1 with the viewer message.
//   4. caption output byte-matches tests/fixtures/captions/11_throne_room.txt.
//   5. fol output byte-matches tests/fixtures/fol/11_throne_room.fol.

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { loadPyodide } from 'pyodide';

import {
	initVsonOps,
	toConformanceReport,
	WHEEL_FILENAMES,
	type GateResult,
	type VsonOps
} from '../src/lib/validate/pyodide-ops';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(__dirname, '../..');
const WHEELS_DIR = resolve(__dirname, '../static/pyodide/wheels');

const read = (repoRelative: string): string => readFileSync(resolve(REPO, repoRelative), 'utf8');

// Booting the runtime + installing eight wheels is seconds, and the first
// OWL 2 RL closure materializes the ontology fixpoint — generous timeouts,
// zero network.
const BOOT_TIMEOUT_MS = 300_000;
const OP_TIMEOUT_MS = 120_000;

let ops: VsonOps;

beforeAll(async () => {
	const pyodide = await loadPyodide();
	ops = await initVsonOps(pyodide, {
		// The committed wheel files themselves — same filenames the worker
		// resolves under /pyodide/wheels/, here as local paths for Node.
		wheelUrls: WHEEL_FILENAMES.map((f) => resolve(WHEELS_DIR, f))
	});
}, BOOT_TIMEOUT_MS);

describe('pyodide worker parity (offline)', () => {
	it(
		'p2t output is byte-identical to the committed CLI output for throne_room',
		() => {
			const envelope = JSON.parse(
				read('web/static/demos/envelopes/gallery/11_throne_room.json')
			) as { vson_p: string; vson_t: string };
			// The baked envelope's vson_p IS examples/gallery/11_throne_room.vson
			// and its vson_t IS `vson convert p2t` over it, byte-frozen at bake.
			expect(envelope.vson_p).toBe(read('examples/gallery/11_throne_room.vson'));
			expect(ops.p2t(envelope.vson_p)).toBe(envelope.vson_t);
		},
		OP_TIMEOUT_MS
	);

	it(
		'throne_room conforms through both gates, Gate 1 reported first',
		() => {
			let gate1Seen: GateResult | null = null;
			const verdict = ops.validate(read('examples/throne_room.ttl'), (gate1) => {
				gate1Seen = gate1;
			});

			expect(gate1Seen).not.toBeNull();
			expect(gate1Seen!.conforms).toBe(true);
			expect(verdict.gate1.conforms).toBe(true);
			expect(verdict.gate2).not.toBeNull();
			expect(verdict.gate2!.conforms).toBe(true);
			expect(verdict.conforms).toBe(true);
			expect(verdict.report).toBe('');
			expect(toConformanceReport(verdict)).toEqual({ conforms: true });
		},
		OP_TIMEOUT_MS
	);

	it(
		'bad_no_viewer fails Gate 1 with the viewer message',
		() => {
			const verdict = ops.validate(read('tests/fixtures/bad_no_viewer.ttl'));

			expect(verdict.conforms).toBe(false);
			expect(verdict.gate1.conforms).toBe(false);
			// The CLI short-circuit: Gate 2 never runs after a SHACL failure.
			expect(verdict.gate2).toBeNull();
			expect(verdict.report).toContain('viewer');

			const conformance = toConformanceReport(verdict);
			expect(conformance.conforms).toBe(false);
			expect(conformance.violations?.some((v) => v.message.includes('vso:viewer'))).toBe(true);
		},
		OP_TIMEOUT_MS
	);

	it(
		'caption byte-matches the committed CI fixture',
		() => {
			const turtle = ops.p2t(read('examples/gallery/11_throne_room.vson'));
			const caption = ops.caption(turtle);
			// The fixture is the renderer's output framed by print() — one
			// trailing newline (see tools/render/caption.py _main).
			expect(`${caption}\n`).toBe(read('tests/fixtures/captions/11_throne_room.txt'));
		},
		OP_TIMEOUT_MS
	);

	it(
		'fol byte-matches the committed CI fixture',
		() => {
			const turtle = ops.p2t(read('examples/gallery/11_throne_room.vson'));
			// fol.render() output already carries its final newline; the CLI
			// prints it with end="" (see tools/render/fol.py _main).
			expect(ops.fol(turtle)).toBe(read('tests/fixtures/fol/11_throne_room.fol'));
		},
		OP_TIMEOUT_MS
	);
});
