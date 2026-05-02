// TS mirror of tools/schema/vson-output.schema.json. Hand-written for clarity;
// kept in sync manually. If the schema changes, update both.

export type NodeKind =
	| 'Composition'
	| 'SceneContext'
	| 'VisualStyle'
	| 'CameraView'
	| 'PhysicalObject'
	| 'Aggregate'
	| 'Substance'
	| 'Event'
	| 'Process'
	| 'Stative'
	| 'Quality'
	| 'SpatialFact'
	| 'Annotation';

export interface NodeTraits {
	individuation?: 'Generic' | 'Named' | 'Kind' | 'Skolem';
	animacy?: 'Agentive' | 'Inert';
	countability?: 'Count' | 'Mass' | 'Collective';
	affordance?: string[];
}

export interface GraphNode {
	id: string;
	kind: NodeKind;
	class?: string;
	traits?: NodeTraits;
	properties?: Record<string, string | number | boolean | null>;
	bbox2d?: string;
}

export interface GraphEdge {
	from: string;
	to: string;
	label: string;
	qualifiers?: Record<string, string | number | boolean>;
}

export interface SceneGraph {
	nodes: GraphNode[];
	edges: GraphEdge[];
}

export interface Violation {
	message: string;
	shape: string;
	focus_node?: string;
	result_path?: string;
	severity?: 'Violation' | 'Warning' | 'Info';
}

export interface ConformanceReport {
	conforms: boolean;
	violations?: Violation[];
}

export interface ExtractionMeta {
	model?: string;
	prompt_version?: string;
	shacl_retries?: number;
	latency_ms?: number;
	input_tokens?: number;
	output_tokens?: number;
	confidence_overall?: number;
}

export interface SceneSource {
	kind: 'image' | 'video_frame' | 'synthetic' | 'hand_authored';
	uri?: string;
	sha256?: string;
	width_px?: number;
	height_px?: number;
	captured_at?: string;
}

export interface VsonEnvelope {
	scene_id: string;
	version: '1.0';
	source?: SceneSource;
	vson_p: string;
	vson_t: string;
	graph?: SceneGraph;
	conformance: ConformanceReport;
	extraction?: ExtractionMeta;
}

export type ExtractStatus = 'idle' | 'uploading' | 'calling' | 'validating' | 'rendering' | 'error';
