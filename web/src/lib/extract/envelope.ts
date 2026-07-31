// Envelope assembly for the client pipeline — BYTE-COMPATIBLE with the v1.2
// envelopes the adapter-node routes emitted. v1.3 changes WHERE computation
// runs, not what an envelope asserts: same version '1.2' wire format, same
// field set and insertion order, same shacl_retries/token/latency metadata,
// same vson_p:'' sentinel in X mode, same drift-derived confidence. The
// baked 1.0-1.2 demo corpus and live output stay interchangeable.

import type { ConformanceReport, VsonEnvelope } from '../types';
import { walkPenmanToGraph, walkTurtleToGraph } from '../graph/walk';
import { DEFAULT_MODEL } from '../openrouter/client';
import { shortId } from '../utils';

/** Optional provenance of the extracted scene's source image. */
export interface EnvelopeSource {
	sha256?: string;
	uri?: string;
}

export interface ExtractionStats {
	/** Model id the caller requested; undefined falls back to DEFAULT_MODEL. */
	model: string | undefined;
	promptVersion: string;
	shaclRetries: number;
	latencyMs: number;
	inputTokens: number;
	outputTokens: number;
	/** X mode only: times the model regressed to Penman. */
	driftCount?: number;
}

// X-mode drift downgrade: each drift retry costs a quarter of confidence,
// floored at zero — identical to the server-era formula.
export const DRIFT_CONFIDENCE_STEP = 0.25;

export function driftConfidence(driftCount: number): number {
	return Math.max(0, 1 - DRIFT_CONFIDENCE_STEP * driftCount);
}

function buildSource(source: EnvelopeSource): VsonEnvelope['source'] {
	return {
		kind: 'image',
		...(source.sha256 ? { sha256: source.sha256 } : {}),
		...(source.uri ? { uri: source.uri } : {})
	};
}

function buildExtraction(stats: ExtractionStats): VsonEnvelope['extraction'] {
	const driftCount = stats.driftCount ?? 0;
	return {
		model: stats.model ?? DEFAULT_MODEL,
		prompt_version: stats.promptVersion,
		shacl_retries: stats.shaclRetries,
		latency_ms: stats.latencyMs,
		input_tokens: stats.inputTokens,
		output_tokens: stats.outputTokens,
		...(driftCount > 0 ? { confidence_overall: driftConfidence(driftCount) } : {})
	};
}

/** Penman-flow envelope: graph walked from the Penman document itself. */
export function buildPenmanEnvelope(args: {
	penman: string;
	turtle: string;
	conformance: ConformanceReport;
	source: EnvelopeSource;
	stats: ExtractionStats;
}): VsonEnvelope {
	return {
		scene_id: shortId(),
		version: '1.2',
		source: buildSource(args.source),
		vson_p: args.penman,
		vson_t: args.turtle,
		graph: walkPenmanToGraph(args.penman),
		conformance: args.conformance,
		extraction: buildExtraction(args.stats)
	};
}

/**
 * X-flow envelope. vson_p stays the empty-string sentinel until t2p ships —
 * the schema's if/then rule allows this iff vson_x is non-empty. The graph is
 * walked from the Turtle (empty when transpilation never succeeded).
 */
export function buildXEnvelope(args: {
	vsonX: string;
	turtle: string;
	conformance: ConformanceReport;
	source: EnvelopeSource;
	stats: ExtractionStats;
}): VsonEnvelope {
	return {
		scene_id: shortId(),
		version: '1.2',
		source: buildSource(args.source),
		vson_p: '',
		vson_t: args.turtle,
		vson_x: args.vsonX,
		graph: args.turtle ? walkTurtleToGraph(args.turtle) : { nodes: [], edges: [] },
		conformance: args.conformance,
		extraction: buildExtraction(args.stats)
	};
}

// Per-format MIME types for client-side Blob construction, ported verbatim
// from the export route's response headers.
export const EXPORT_MIME = {
	cypher: 'text/x-cypher',
	graphml: 'application/graphml+xml',
	dot: 'text/vnd.graphviz',
	mermaid: 'text/x-mermaid',
	caption: 'text/plain',
	fol: 'text/plain'
} as const;

export type ExportFormat = keyof typeof EXPORT_MIME;
