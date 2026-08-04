// The counterfactual behind the studio's keyless "see it fail" line.
//
// Every document the studio can show without a key is green by construction —
// the demo corpus and the gallery are baked from conformant sources — so a
// visitor with no key never watches a gate BITE, and a gate nobody has seen
// bite is a claim, not a demonstration. This module manufactures the moment
// honestly: it takes the VSON-T the loaded scene already carries, drops
// exactly ONE vso:viewer triple from one directional spatial fact, and hands
// the copy back for the same two browser gates to judge. C5 —
// vss:DirectionalNeedsViewerShape, `sh:targetSubjectsOf vso:directional`,
// `sh:minCount 1` on vso:viewer — then fires with its own published
// sh:message. Nothing here decides the verdict; pyshacl does.
//
// IN MEMORY ONLY. The input is a string and strings do not mutate; the caller
// renders the copy's verdict beside the real one and never writes it into the
// envelope, and no file is opened at all. `index` makes the reversal exact:
// splicing `line` back in at `index` reproduces the input byte for byte, which
// is what "restore" means and what the unit test asserts.
//
// Line-oriented on purpose. Every VSON-T the studio holds came out of the
// canonical emitter (tools/penman/vson_penman.py or the VSON-X parser, run in
// the Pyodide worker and byte-compared against the Rust CLI by `make
// cli-check`), and that emitter writes one triple per line ending in `.` —
// the same shape $lib/graph/walk.ts's Turtle reader documents. A line that
// does not fit (a `;` predicate list, an RDF-star quoted triple, a literal
// with spaces) is skipped rather than guessed at, and a document with no
// clean directional-plus-viewer subject yields null. The UI renders no
// affordance at all in that case, so a guess can never reach a visitor.

import { localName } from './report';

/** The VSON ontology namespace the emitter writes in full. */
const VSO = 'https://w3id.org/vson/v1/ontology#';

export interface ViewerRemoval {
	/** The tampered copy: the input with one vso:viewer triple line removed. */
	turtle: string;
	/** Local name of the spatial fact that lost its viewer, e.g. `sf1`. */
	fact: string;
	/** Local name of the viewer that was removed, e.g. `cam`. */
	viewer: string;
	/** The removed line, verbatim — the exact bytes taken out. */
	line: string;
	/** Its 0-based index in `turtle.split('\n')`; splice it back to restore. */
	index: number;
}

/** A predicate token written either as a full IRI or with the `vso:` prefix. */
function isVsoTerm(token: string, term: string): boolean {
	return token === `<${VSO}${term}>` || token === `vso:${term}`;
}

/** Subject / predicate / object of a single-line triple, or null if not one. */
function tripleOf(line: string): { s: string; p: string; o: string } | null {
	const body = line.trim();
	// Blank lines, comments, @prefix / @base directives.
	if (!body || body.startsWith('#') || body.startsWith('@')) return null;
	// Only a complete one-line triple. Anything continuing onto the next line,
	// or quoting a triple, is outside the emitter's shape.
	if (!body.endsWith('.') || body.includes('<<')) return null;
	const toks = body.slice(0, -1).trim().split(/\s+/);
	if (toks.length !== 3) return null;
	return { s: toks[0], p: toks[1], o: toks[2] };
}

/**
 * Remove the viewer of the first directional spatial fact in document order.
 *
 * Qualification is exactly C5's own target: a subject carrying both a
 * `vso:directional` triple and a `vso:viewer` triple. Returns null when the
 * document has no such subject — which is the studio's render condition, so
 * the affordance appears iff this transform can actually produce the copy.
 */
export function removeOneViewer(turtle: string): ViewerRemoval | null {
	const lines = turtle.split('\n');
	const directionalSubjects = new Set<string>();
	// Subject → index of its FIRST viewer line.
	const viewerLine = new Map<string, number>();

	for (let i = 0; i < lines.length; i++) {
		const t = tripleOf(lines[i]);
		if (!t) continue;
		if (isVsoTerm(t.p, 'directional')) directionalSubjects.add(t.s);
		else if (isVsoTerm(t.p, 'viewer') && !viewerLine.has(t.s)) viewerLine.set(t.s, i);
	}

	let index = -1;
	let subject = '';
	for (const [s, i] of viewerLine) {
		if (!directionalSubjects.has(s)) continue;
		if (index < 0 || i < index) {
			index = i;
			subject = s;
		}
	}
	if (index < 0) return null;

	const line = lines[index];
	const object = tripleOf(line)?.o ?? '';
	return {
		turtle: lines.filter((_, i) => i !== index).join('\n'),
		fact: localName(subject),
		viewer: localName(object),
		line,
		index
	};
}
