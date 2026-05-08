// Pure projection from SceneGraph → SceneView (5-zone view-model).
// View-only: never mutates the graph, never persists. Driven by NodeKind +
// edge-label routing tables below. Adding a new label is the one-line change.

import type { GraphNode, NodeKind, SceneGraph } from '$lib/types';

export interface FrameSlot {
	id: string;
	kind: 'SceneContext' | 'VisualStyle' | 'CameraView';
	properties: Array<{ key: string; value: string }>;
}

export interface CompositionMeta {
	id: string;
	qualities: Array<{ dim: string; value: string }>;
}

export interface OutgoingRef {
	label: string;
	to: string;
}

// Axe-grouped traits: VSON spec §4.2 declares four orthogonal trait axes
// (individuation, animacy, countability, affordance). Flat string lists lose
// this structure — readers can't tell whether "Skolem" is an individuation
// kind or some open vocabulary token. Keep the axis label so the renderer
// can group with `indiv: Skolem · anim: Agentive` etc.
export interface TraitGroup {
	individuation?: string;
	animacy?: string;
	countability?: string;
	affordance: string[];
}

// Geometry layer (spec §14): bbox2d, position3d, scale3d, rotation,
// visibleFraction, occludes. The renderer surfaces all five so users see
// the complete VSO Geometry block, not just bbox2d.
export interface Geometry {
	bbox?: string;
	position3d?: string;
	scale3d?: string;
	rotation?: string;
	visibleFraction?: string;
	/** Outgoing vso:occludes edges to other entities. */
	occludes: string[];
}

export interface HasRef {
	label: string;
	to: string;
	klass?: string;
	traits: TraitGroup;
	qualities: Array<{ dim: string; value: string }>;
	geometry: Geometry;
}

export interface EntityCardModel {
	id: string;
	kind: NodeKind;
	klass?: string;
	traits: TraitGroup;
	qualities: Array<{ dim: string; value: string }>;
	geometry: Geometry;
	has: HasRef[];
	outgoing: OutgoingRef[];
}

export interface ActionFact {
	id: string;
	kind: 'Event' | 'Stative' | 'Process';
	lemma?: string;
	manner?: string;
	roles: Array<{ role: string; target: string }>;
}

export interface SpatialFactRow {
	id: string;
	figure?: string;
	ground?: string;
	viewer?: string;
	rcc?: string;
	directional?: string;
	proximal?: string;
}

export interface RelationRow {
	from: string;
	predicate: string;
	to: string;
}

export interface SceneView {
	composition: CompositionMeta | null;
	frame: FrameSlot[];
	entities: EntityCardModel[];
	actions: ActionFact[];
	spatial: SpatialFactRow[];
	temporal: RelationRow[];
}

// Edge-label routing — single source of truth. Adding a new predicate is one
// line. Order of checks in buildSceneView matches this typology.
const POSSESSION_LABELS = new Set([
	'wears',
	'carries',
	'holds',
	'hasPart',
	'partOf',
	'embodies'
]);
const PERDURANT_ROLE_LABELS = new Set([
	'agent',
	'patient',
	'theme',
	'instrument',
	'goal',
	'beneficiary',
	'experiencer',
	'stimulus',
	'holder',
	'cause',
	'recipient',
	'source',
	'destination'
]);
const SPATIAL_ROLE_LABELS = new Set(['figure', 'ground', 'viewer']);
// Spec §5.2 Allen interval algebra (13 base relations) + §5.4 causal group
// (causes, enables, prevents, triggers — the last absent from this set was
// silently dropped before the §5.4 audit). Full closure ensures no causal
// or temporal edge gets routed to outgoing-fallback.
const TEMPORAL_CAUSAL_LABELS = new Set([
	'causes',
	'enables',
	'prevents',
	'triggers',
	'before',
	'after',
	'meets',
	'metBy',
	'overlaps',
	'overlappedBy',
	'starts',
	'startedBy',
	'during',
	'contains',
	'finishes',
	'finishedBy',
	'equals'
]);
// Structural roles consumed by the layout itself (frame strip, implicit
// containment). Edges with these labels are intentionally not rendered.
// `depicts` is handled per-source: Composition→Entity is implicit containment
// (skipped), Entity→Entity is the extractor's possession misuse (routed to
// the Has chip-row).
const SKIP_LABELS = new Set([
	'framedBy',
	'rendersAs',
	'viewedBy',
	'hasQuality',
	'causal',
	'temporal'
]);

const FRAME_NODE_KINDS = new Set<NodeKind>(['SceneContext', 'VisualStyle', 'CameraView']);
const ENTITY_NODE_KINDS = new Set<NodeKind>(['PhysicalObject', 'Aggregate', 'Substance']);
const PERDURANT_KINDS = new Set<NodeKind>(['Event', 'Stative', 'Process']);

function pickQualities(node: GraphNode): Array<{ dim: string; value: string }> {
	if (!node.properties) return [];
	const out: Array<{ dim: string; value: string }> = [];
	for (const [k, v] of Object.entries(node.properties)) {
		if (k.startsWith('q_') && v !== null) {
			out.push({ dim: k.slice(2), value: String(v) });
		}
	}
	return out;
}

function pickFrameProps(node: GraphNode): Array<{ key: string; value: string }> {
	if (!node.properties) return [];
	return Object.entries(node.properties)
		.filter(([k, v]) => !k.startsWith('q_') && v !== null)
		.map(([k, v]) => ({ key: k, value: String(v) }));
}

function pickGeometry(node: GraphNode | undefined): Geometry {
	const out: Geometry = { occludes: [] };
	if (!node) return out;
	const props = node.properties ?? {};
	const bbox = props.bbox2d ?? node.bbox2d;
	if (bbox != null) out.bbox = String(bbox);
	if (props.position3d != null) out.position3d = String(props.position3d);
	if (props.scale3d != null) out.scale3d = String(props.scale3d);
	if (props.rotation != null) out.rotation = String(props.rotation);
	if (props.visibleFraction != null) out.visibleFraction = String(props.visibleFraction);
	return out;
}

function pickTraits(node: GraphNode): TraitGroup {
	const t = node.traits;
	const out: TraitGroup = { affordance: [] };
	if (!t) return out;
	if (t.individuation) out.individuation = t.individuation;
	if (t.animacy) out.animacy = t.animacy;
	if (t.countability) out.countability = t.countability;
	if (t.affordance?.length) out.affordance = [...t.affordance];
	return out;
}

const FRAME_ORDER: Record<string, number> = { SceneContext: 0, VisualStyle: 1, CameraView: 2 };

export function buildSceneView(graph: SceneGraph): SceneView {
	const byId = new Map<string, GraphNode>();
	for (const n of graph.nodes) byId.set(n.id, n);

	const compositionNode = graph.nodes.find((n) => n.kind === 'Composition') ?? null;
	const composition: CompositionMeta | null = compositionNode
		? { id: compositionNode.id, qualities: pickQualities(compositionNode) }
		: null;

	const frame: FrameSlot[] = graph.nodes
		.filter((n): n is GraphNode & { kind: 'SceneContext' | 'VisualStyle' | 'CameraView' } =>
			FRAME_NODE_KINDS.has(n.kind)
		)
		.map((n) => ({ id: n.id, kind: n.kind, properties: pickFrameProps(n) }))
		.sort((a, b) => (FRAME_ORDER[a.kind] ?? 99) - (FRAME_ORDER[b.kind] ?? 99));

	const hasByEntity = new Map<string, HasRef[]>();
	const outgoingByEntity = new Map<string, OutgoingRef[]>();
	const occludesByEntity = new Map<string, string[]>();
	const actionRoles = new Map<string, Array<{ role: string; target: string }>>();
	const spatialRoles = new Map<string, Map<string, string>>();
	const temporal: RelationRow[] = [];

	for (const e of graph.edges) {
		if (SKIP_LABELS.has(e.label)) continue;

		if (TEMPORAL_CAUSAL_LABELS.has(e.label)) {
			temporal.push({ from: e.from, predicate: e.label, to: e.to });
			continue;
		}

		const fromNode = byId.get(e.from);
		if (!fromNode) continue;

		if (PERDURANT_KINDS.has(fromNode.kind) && PERDURANT_ROLE_LABELS.has(e.label)) {
			const arr = actionRoles.get(e.from) ?? [];
			arr.push({ role: e.label, target: e.to });
			actionRoles.set(e.from, arr);
			continue;
		}

		if (fromNode.kind === 'SpatialFact' && SPATIAL_ROLE_LABELS.has(e.label)) {
			const m = spatialRoles.get(e.from) ?? new Map<string, string>();
			m.set(e.label, e.to);
			spatialRoles.set(e.from, m);
			continue;
		}

		// Composition→Entity `depicts` is implicit containment (the cards
		// already live inside the SceneFrame). Drop it.
		if (fromNode.kind === 'Composition' && e.label === 'depicts') continue;

		if (ENTITY_NODE_KINDS.has(fromNode.kind)) {
			// Geometry: vso:occludes belongs in the entity's geometry block,
			// not the outgoing fallback (spec §14).
			if (e.label === 'occludes') {
				const arr = occludesByEntity.get(e.from) ?? [];
				arr.push(e.to);
				occludesByEntity.set(e.from, arr);
				continue;
			}
			// Entity-sourced possession: VSO predicates plus the extractor's
			// `depicts` misuse (PhysicalObject→PhysicalObject in current
			// extractions means the source "has" the target as a component).
			if (POSSESSION_LABELS.has(e.label) || e.label === 'depicts') {
				const toNode = byId.get(e.to);
				const arr = hasByEntity.get(e.from) ?? [];
				arr.push({
					label: e.label,
					to: e.to,
					klass: toNode?.class,
					traits: toNode ? pickTraits(toNode) : { affordance: [] },
					qualities: toNode ? pickQualities(toNode) : [],
					geometry: pickGeometry(toNode)
				});
				hasByEntity.set(e.from, arr);
				continue;
			}
			// Fallback outgoing — custom labels (user-extended ontologies)
			// still surface instead of vanishing silently.
			const arr = outgoingByEntity.get(e.from) ?? [];
			arr.push({ label: e.label, to: e.to });
			outgoingByEntity.set(e.from, arr);
		}
	}

	const entities: EntityCardModel[] = graph.nodes
		.filter((n) => ENTITY_NODE_KINDS.has(n.kind))
		.map((n) => {
			const geometry = pickGeometry(n);
			geometry.occludes = occludesByEntity.get(n.id) ?? [];
			return {
				id: n.id,
				kind: n.kind,
				klass: n.class,
				traits: pickTraits(n),
				qualities: pickQualities(n),
				geometry,
				has: hasByEntity.get(n.id) ?? [],
				outgoing: outgoingByEntity.get(n.id) ?? []
			};
		});

	const actions: ActionFact[] = graph.nodes
		.filter((n): n is GraphNode & { kind: 'Event' | 'Stative' | 'Process' } =>
			PERDURANT_KINDS.has(n.kind)
		)
		.map((n) => ({
			id: n.id,
			kind: n.kind,
			lemma: n.properties?.lemma != null ? String(n.properties.lemma) : undefined,
			manner: n.properties?.manner != null ? String(n.properties.manner) : undefined,
			roles: actionRoles.get(n.id) ?? []
		}));

	const spatial: SpatialFactRow[] = graph.nodes
		.filter((n) => n.kind === 'SpatialFact')
		.map((n) => {
			const r = spatialRoles.get(n.id);
			return {
				id: n.id,
				figure: r?.get('figure'),
				ground: r?.get('ground'),
				viewer: r?.get('viewer'),
				rcc: n.properties?.rcc != null ? String(n.properties.rcc) : undefined,
				directional:
					n.properties?.directional != null ? String(n.properties.directional) : undefined,
				proximal: n.properties?.proximal != null ? String(n.properties.proximal) : undefined
			};
		});

	return { composition, frame, entities, actions, spatial, temporal };
}
