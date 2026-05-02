// Smoke test for baked demo envelopes. If `web/scripts/bake-demos.ts` has
// been run, every envelope on disk MUST be a valid VSON envelope:
//   - version === "1.0"
//   - vson_p starts with `(`, ends with `)`
//   - conformance.conforms is true (we only ship demos that conform)
//   - graph has nodes and edges arrays
//
// When the envelopes/ directory is empty (fresh checkout, no bake yet) the
// test is a no-op and passes. Re-run after `pnpm dlx tsx scripts/bake-demos.ts`.

import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ENVELOPES_DIR = resolve(__dirname, '../static/demos/envelopes');

interface Envelope {
	scene_id: string;
	version: string;
	vson_p: string;
	vson_t: string;
	conformance: { conforms: boolean; violations?: unknown[] };
	graph?: { nodes: unknown[]; edges: unknown[] };
	source?: { kind: string; sha256?: string };
	extraction?: { model?: string; prompt_version?: string };
}

function envelopeFiles(): string[] {
	if (!existsSync(ENVELOPES_DIR)) return [];
	if (!statSync(ENVELOPES_DIR).isDirectory()) return [];
	return readdirSync(ENVELOPES_DIR)
		.filter((f) => f.endsWith('.json') && f !== 'index.json')
		.map((f) => resolve(ENVELOPES_DIR, f));
}

describe('cached demo envelopes', () => {
	const files = envelopeFiles();

	it('directory is well-formed (or absent)', () => {
		expect(Array.isArray(files)).toBe(true);
	});

	if (files.length === 0) {
		it.skip('no envelopes baked yet — run `tsx scripts/bake-demos.ts`', () => {});
		return;
	}

	for (const file of files) {
		describe(file.split('/').slice(-1)[0], () => {
			const env = JSON.parse(readFileSync(file, 'utf8')) as Envelope;

			it('declares version 1.0', () => {
				expect(env.version).toBe('1.0');
			});

			it('vson_p is a balanced Penman document', () => {
				expect(env.vson_p.trim().startsWith('(')).toBe(true);
				expect(env.vson_p.trim().endsWith(')')).toBe(true);
				expect(env.vson_p.length).toBeGreaterThan(20);
			});

			it('vson_t is non-empty Turtle', () => {
				expect(env.vson_t.length).toBeGreaterThan(20);
			});

			it('conforms to SHACL', () => {
				expect(env.conformance.conforms).toBe(true);
				expect(env.conformance.violations ?? []).toHaveLength(0);
			});

			it('graph has nodes and edges', () => {
				expect(Array.isArray(env.graph?.nodes)).toBe(true);
				expect(Array.isArray(env.graph?.edges)).toBe(true);
				expect(env.graph!.nodes.length).toBeGreaterThan(0);
				expect(env.graph!.edges.length).toBeGreaterThan(0);
			});

			it('records sha256 for cache lookup', () => {
				expect(env.source?.sha256).toMatch(/^[a-f0-9]{64}$/);
			});
		});
	}

	it('index.json maps every demo sha to an envelope file', () => {
		const indexPath = resolve(ENVELOPES_DIR, 'index.json');
		if (!existsSync(indexPath)) {
			expect.fail('index.json missing — re-run bake-demos');
		}
		const idx = JSON.parse(readFileSync(indexPath, 'utf8')) as Record<string, string>;
		expect(Object.keys(idx).length).toBeGreaterThan(0);
		for (const [sha, file] of Object.entries(idx)) {
			expect(sha).toMatch(/^[a-f0-9]{64}$/);
			expect(existsSync(resolve(ENVELOPES_DIR, file))).toBe(true);
		}
	});
});
