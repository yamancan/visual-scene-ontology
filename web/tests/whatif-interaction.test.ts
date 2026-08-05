// The keyless "see it fail" interaction, pinned end to end minus the runtime.
//
// The studio can show a gate BITING with no key, no model call and no image
// read: it drops one vso:viewer triple from an in-memory copy of the loaded
// document and runs the same two browser gates over the copy. Three things
// have to stay true for that to be a demonstration rather than a claim, and
// none of them is checked by the transform's own unit tests
// (src/lib/validate/tamper.test.ts):
//
//   1. the shipped corpus still contains scenes that qualify — an affordance
//      that never renders demonstrates nothing;
//   2. the transform touches NO file — the baked envelopes are byte-frozen,
//      and "in memory only" is the whole safety claim of the interaction;
//   3. the pane renders the affordance only for a qualifying document, and
//      never writes the tampered verdict back into the envelope.
//
// The Pyodide path itself is deliberately not re-tested here: tests/
// worker-parity.test.ts already boots the runtime offline and pins both
// gates' verdicts. What IS pinned is the published shape whose sh:message the
// interaction promises a visitor will see — if C5 is renamed or relaxed, the
// promise breaks silently, and this fails instead.

import { describe, it, expect } from 'vitest';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

import { removeOneViewer } from '../src/lib/validate/tamper';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../..');
const ENVELOPES_DIR = resolve(__dirname, '../static/demos/envelopes');
const GALLERY_DIR = resolve(ENVELOPES_DIR, 'gallery');
const PANE = resolve(__dirname, '../src/lib/components/ConformancePane.svelte');
const SHAPES = resolve(REPO_ROOT, 'shapes/vson-shapes.ttl');

const VSO = 'https://w3id.org/vson/v1/ontology#';

function envelopeFiles(): string[] {
	const out: string[] = [];
	for (const dir of [ENVELOPES_DIR, GALLERY_DIR]) {
		if (!existsSync(dir) || !statSync(dir).isDirectory()) continue;
		for (const f of readdirSync(dir)) {
			if (f.endsWith('.json') && f !== 'index.json') out.push(resolve(dir, f));
		}
	}
	return out.sort();
}

function turtleOf(file: string): string {
	return (JSON.parse(readFileSync(file, 'utf8')) as { vson_t?: string }).vson_t ?? '';
}

/**
 * Does this document have what C5 targets — a subject carrying both
 * vso:directional and vso:viewer? Written independently of the transform (a
 * regex per predicate, not the transform's line reader) so the two can
 * disagree.
 */
function hasDirectionalWithViewer(turtle: string): boolean {
	const subjectsWith = (term: string) =>
		new Set(
			[...turtle.matchAll(new RegExp(`^(\\S+)\\s+<${VSO}${term}>\\s`, 'gm'))].map((m) => m[1])
		);
	const viewers = subjectsWith('viewer');
	return [...subjectsWith('directional')].some((s) => viewers.has(s));
}

describe('what-if corpus', () => {
	const files = envelopeFiles();

	it('the shipped corpus still contains scenes the interaction can run on', () => {
		const qualifying = files
			.filter((f) => removeOneViewer(turtleOf(f)) !== null)
			.map((f) => basename(f));
		// Every photographic demo, plus the two gallery scenes built around
		// directional construal. If a bake ever drops these, the affordance
		// quietly disappears from the studio — so name them.
		expect(qualifying).toEqual(
			expect.arrayContaining([
				'kitchen.json',
				'cat.json',
				'chess.json',
				'blocks.json',
				'table.json',
				'bicycle.json',
				'04_directional_with_viewer.json',
				'11_throne_room.json'
			])
		);
	});

	it('qualifies exactly the documents whose facts are directional with a viewer', () => {
		for (const file of files) {
			const turtle = turtleOf(file);
			expect({ file: basename(file), qualifies: removeOneViewer(turtle) !== null }).toEqual({
				file: basename(file),
				qualifies: hasDirectionalWithViewer(turtle)
			});
		}
	});

	it('scenes without a directional fact offer nothing to remove', () => {
		const plain = files.filter((f) => !hasDirectionalWithViewer(turtleOf(f)));
		expect(plain.length).toBeGreaterThan(0);
		for (const file of plain) expect(removeOneViewer(turtleOf(file))).toBeNull();
	});

	it('leaves every envelope on disk byte-identical', () => {
		const digest = (f: string) => createHash('sha256').update(readFileSync(f)).digest('hex');
		const before = files.map(digest);
		for (const file of files) {
			const removal = removeOneViewer(turtleOf(file));
			// Use the copy the way the pane does, then drop it.
			if (removal) expect(removal.turtle).not.toBe(turtleOf(file));
		}
		expect(files.map(digest)).toEqual(before);
	});
});

describe('what-if affordance', () => {
	const pane = readFileSync(PANE, 'utf8');

	it('renders only when the transform yields a copy', () => {
		expect(pane).toContain("import { removeOneViewer } from '$lib/validate/tamper'");
		expect(pane).toMatch(/whatIfSource = \$derived\(/);
		expect(pane).toContain('removeOneViewer(env.vson_t)');
		// One guard around the whole block: no copy, no markup at all — and
		// inside it, never a disabled control.
		const block = pane.slice(pane.indexOf('{#if whatIfSource}'), pane.indexOf('<style>'));
		expect(block).toContain('what if the viewer were removed?');
		expect(block).not.toContain('disabled');
	});

	it('never writes the tampered document into the envelope', () => {
		expect(pane).not.toContain('setEnvelope');
	});

	it('says what ran, keylessly, without claiming the image was read', () => {
		expect(pane).toContain('no key, no model, no image read');
		expect(pane).toContain('the loaded document is untouched');
	});
});

describe('the shape the interaction promises', () => {
	const shapes = readFileSync(SHAPES, 'utf8');

	it('C5 still requires a viewer on subjects of vso:directional', () => {
		expect(shapes).toContain('vss:DirectionalNeedsViewerShape a sh:NodeShape');
		const block = shapes.slice(shapes.indexOf('vss:DirectionalNeedsViewerShape a sh:NodeShape'));
		const decl = block.slice(0, block.indexOf('\n\n'));
		expect(decl).toContain('sh:targetSubjectsOf vso:directional');
		expect(decl).toContain('sh:path vso:viewer');
		expect(decl).toContain('sh:minCount 1');
		expect(decl).toMatch(/sh:message "[^"]*\(C5\)/);
	});
});
