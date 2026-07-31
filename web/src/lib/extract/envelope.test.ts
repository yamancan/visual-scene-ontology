// Snapshot of the v1.2 envelope field contract. The client pipeline must
// emit envelopes byte-compatible with what the adapter-node routes emitted:
// same version string, same field SET and INSERTION ORDER (JSON.stringify
// preserves it, so order is part of byte compatibility), same X-mode
// vson_p:'' sentinel, same drift-derived confidence formula. These tests are
// the conscious-edit gate: change the wire shape and something here fails.

import { describe, it, expect } from 'vitest';

import {
	buildPenmanEnvelope,
	buildXEnvelope,
	driftConfidence,
	DRIFT_CONFIDENCE_STEP,
	EXPORT_MIME
} from './envelope';
import { DEFAULT_MODEL } from '../openrouter/client';
import { walkPenmanToGraph, walkTurtleToGraph } from '../graph/walk';

const PENMAN = '(s / Composition :hasParticipant (p / Persona))';
const TURTLE = 'vson:s a vso:Composition .\n';
const X_DOC = '~scene\n~ent p Persona\n';

const STATS = {
	model: 'anthropic/claude-sonnet-4.5',
	promptVersion: 'skill@1.0.0',
	shaclRetries: 1,
	latencyMs: 1234,
	inputTokens: 100,
	outputTokens: 50
};

describe('buildPenmanEnvelope — v1.2 field contract', () => {
	const envelope = buildPenmanEnvelope({
		penman: PENMAN,
		turtle: TURTLE,
		conformance: { conforms: true },
		source: { sha256: 'abc123', uri: 'https://example.org/img.jpg' },
		stats: STATS
	});

	it('pins the top-level field set and insertion order', () => {
		expect(Object.keys(envelope)).toEqual([
			'scene_id',
			'version',
			'source',
			'vson_p',
			'vson_t',
			'graph',
			'conformance',
			'extraction'
		]);
	});

	it('stays on wire version 1.2 with the server-era source shape', () => {
		expect(envelope.version).toBe('1.2');
		expect(envelope.source).toEqual({
			kind: 'image',
			sha256: 'abc123',
			uri: 'https://example.org/img.jpg'
		});
		expect(Object.keys(envelope.source!)).toEqual(['kind', 'sha256', 'uri']);
	});

	it('carries the notations and the graph walked from the Penman document', () => {
		expect(envelope.vson_p).toBe(PENMAN);
		expect(envelope.vson_t).toBe(TURTLE);
		expect(envelope.graph).toEqual(walkPenmanToGraph(PENMAN));
		expect(envelope.conformance).toEqual({ conforms: true });
	});

	it('pins the extraction metadata set, order, and values', () => {
		expect(envelope.extraction).toEqual({
			model: 'anthropic/claude-sonnet-4.5',
			prompt_version: 'skill@1.0.0',
			shacl_retries: 1,
			latency_ms: 1234,
			input_tokens: 100,
			output_tokens: 50
		});
		expect(Object.keys(envelope.extraction!)).toEqual([
			'model',
			'prompt_version',
			'shacl_retries',
			'latency_ms',
			'input_tokens',
			'output_tokens'
		]);
	});

	it('falls back to DEFAULT_MODEL when no model was requested', () => {
		const e = buildPenmanEnvelope({
			penman: PENMAN,
			turtle: TURTLE,
			conformance: { conforms: true },
			source: {},
			stats: { ...STATS, model: undefined }
		});
		expect(e.extraction?.model).toBe(DEFAULT_MODEL);
		expect(e.source).toEqual({ kind: 'image' });
	});

	it('never emits confidence_overall for the Penman flow', () => {
		expect('confidence_overall' in envelope.extraction!).toBe(false);
	});
});

describe('buildXEnvelope — v1.2 field contract', () => {
	const envelope = buildXEnvelope({
		vsonX: X_DOC,
		turtle: TURTLE,
		conformance: {
			conforms: false,
			violations: [{ message: 'm', shape: 'ClassConstraintComponent' }]
		},
		source: { sha256: 'abc123' },
		stats: { ...STATS, driftCount: 1 }
	});

	it('pins the top-level field order with vson_x after vson_t', () => {
		expect(Object.keys(envelope)).toEqual([
			'scene_id',
			'version',
			'source',
			'vson_p',
			'vson_t',
			'vson_x',
			'graph',
			'conformance',
			'extraction'
		]);
	});

	it('keeps the X-mode vson_p empty-string sentinel', () => {
		expect(envelope.vson_p).toBe('');
		expect(envelope.vson_x).toBe(X_DOC);
	});

	it('walks the graph from the Turtle, degrading to empty when transpile failed', () => {
		expect(envelope.graph).toEqual(walkTurtleToGraph(TURTLE));
		const failed = buildXEnvelope({
			vsonX: X_DOC,
			turtle: '',
			conformance: { conforms: false },
			source: {},
			stats: { ...STATS, driftCount: 2 }
		});
		expect(failed.graph).toEqual({ nodes: [], edges: [] });
	});

	it('downgrades confidence 0.25 per drift, only when drift happened', () => {
		expect(envelope.extraction?.confidence_overall).toBe(0.75);
		const noDrift = buildXEnvelope({
			vsonX: X_DOC,
			turtle: TURTLE,
			conformance: { conforms: true },
			source: {},
			stats: { ...STATS, driftCount: 0 }
		});
		expect('confidence_overall' in noDrift.extraction!).toBe(false);
	});
});

describe('driftConfidence — the 0.25/drift downgrade', () => {
	it('steps down by 0.25 per drift and floors at zero', () => {
		expect(DRIFT_CONFIDENCE_STEP).toBe(0.25);
		expect(driftConfidence(0)).toBe(1);
		expect(driftConfidence(1)).toBe(0.75);
		expect(driftConfidence(2)).toBe(0.5);
		expect(driftConfidence(4)).toBe(0);
		expect(driftConfidence(5)).toBe(0);
	});
});

describe('EXPORT_MIME — the export route MIME map, verbatim', () => {
	it('pins all six formats', () => {
		expect(EXPORT_MIME).toEqual({
			cypher: 'text/x-cypher',
			graphml: 'application/graphml+xml',
			dot: 'text/vnd.graphviz',
			mermaid: 'text/x-mermaid',
			caption: 'text/plain',
			fol: 'text/plain'
		});
	});
});
