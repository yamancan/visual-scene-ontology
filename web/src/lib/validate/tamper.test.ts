import { describe, it, expect } from 'vitest';
import { removeOneViewer } from './tamper';

const VSO = 'https://w3id.org/vson/v1/ontology#';

// Emitter-shaped VSON-T: one triple per line, full IRIs, terminating `.`.
const TWO_FACTS = [
	'@prefix vso:   <https://w3id.org/vson/v1/ontology#> .',
	'@prefix :      <https://example.org/scenes/anonymous#> .',
	'',
	`:scene a <${VSO}Composition> .`,
	`:cam a <${VSO}CameraView> .`,
	`:scene <${VSO}framedBy> :cam .`,
	`:scene <${VSO}viewedBy> :cam .`,
	`:sf1 a <${VSO}SpatialFact> .`,
	`:sf1 <${VSO}figure> :lamp .`,
	`:sf1 <${VSO}directional> <${VSO}left_of> .`,
	`:sf1 <${VSO}viewer> :cam .`,
	`:sf2 a <${VSO}SpatialFact> .`,
	`:sf2 <${VSO}directional> <${VSO}behind> .`,
	`:sf2 <${VSO}viewer> :cam .`,
	''
].join('\n');

describe('removeOneViewer', () => {
	it('removes exactly one viewer triple, from the first directional fact', () => {
		const out = removeOneViewer(TWO_FACTS);
		expect(out).not.toBeNull();
		expect(out!.fact).toBe('sf1');
		expect(out!.viewer).toBe('cam');
		expect(out!.line).toBe(`:sf1 <${VSO}viewer> :cam .`);

		const before = TWO_FACTS.split('\n');
		const after = out!.turtle.split('\n');
		expect(after).toHaveLength(before.length - 1);
		// Every other line survives byte-for-byte, in order.
		expect(after).toEqual(before.filter((_, i) => i !== out!.index));
		// One viewer triple gone, one left — the second fact is untouched.
		expect(after.filter((l) => l.includes(`<${VSO}viewer>`))).toEqual([
			`:sf2 <${VSO}viewer> :cam .`
		]);
	});

	it('leaves the tampered fact directional but viewerless — what C5 targets', () => {
		const out = removeOneViewer(TWO_FACTS);
		const lines = out!.turtle.split('\n').filter((l) => l.startsWith(':sf1 '));
		expect(lines.some((l) => l.includes(`<${VSO}directional>`))).toBe(true);
		expect(lines.some((l) => l.includes(`<${VSO}viewer>`))).toBe(false);
	});

	it('restores exactly: splicing the line back at index reproduces the input', () => {
		const out = removeOneViewer(TWO_FACTS)!;
		const restored = out.turtle.split('\n');
		restored.splice(out.index, 0, out.line);
		expect(restored.join('\n')).toBe(TWO_FACTS);
	});

	it('is pure: the source is unchanged and a second call agrees with the first', () => {
		const source = TWO_FACTS;
		const first = removeOneViewer(source);
		const second = removeOneViewer(source);
		expect(source).toBe(TWO_FACTS);
		expect(second).toEqual(first);
	});

	it('accepts the vso: prefixed form as well as the full IRI', () => {
		const prefixed = [
			'@prefix vso: <https://w3id.org/vson/v1/ontology#> .',
			':sf1 vso:directional vso:left_of .',
			':sf1 vso:viewer :cam .'
		].join('\n');
		const out = removeOneViewer(prefixed);
		expect(out!.line).toBe(':sf1 vso:viewer :cam .');
		expect(out!.turtle).not.toContain('vso:viewer');
	});

	it('returns null when no fact is directional', () => {
		const topologyOnly = [
			`:sf1 a <${VSO}SpatialFact> .`,
			`:sf1 <${VSO}figure> :lamp .`,
			`:sf1 <${VSO}rcc> <https://w3id.org/vson/v1/rcc8#DC> .`,
			`:scene <${VSO}viewedBy> :cam .`
		].join('\n');
		expect(removeOneViewer(topologyOnly)).toBeNull();
	});

	it('returns null when the directional fact carries no viewer', () => {
		const alreadyFailing = [
			`:sf1 a <${VSO}SpatialFact> .`,
			`:sf1 <${VSO}directional> <${VSO}left_of> .`
		].join('\n');
		expect(removeOneViewer(alreadyFailing)).toBeNull();
	});

	it('returns null on an empty document', () => {
		expect(removeOneViewer('')).toBeNull();
	});

	it('ignores viewer triples it cannot read as a whole line', () => {
		// A quoted triple and a predicate list are outside the emitter's shape;
		// guessing at them could remove the wrong bytes, so they are skipped.
		const notEmitterShaped = [
			`<< :sf1 <${VSO}viewer> :cam >> <${VSO}confidence> "0.9" .`,
			`:sf2 <${VSO}directional> <${VSO}behind> ;`,
			`     <${VSO}viewer> :cam .`
		].join('\n');
		expect(removeOneViewer(notEmitterShaped)).toBeNull();
	});
});
