// Projection-only Penman walker. Extracts {nodes, edges} for the UI graph
// view. NOT a transpiler — it does NOT route to RCC/Allen/VSO namespaces.
// Canonical translation lives in cli/target/release/vson on the server.
//
// Signal vs. noise filter:
//  - Quality dimension/value pairs are folded into the parent's `properties`
//    rather than emitted as separate nodes (would explode the graph).
//  - Frame attachment edges and Entity/Perdurant relations are kept as edges.

import type { GraphEdge, GraphNode, NodeKind, SceneGraph } from '../types';

const KIND_VALUES = new Set<NodeKind>([
	'Composition',
	'SceneContext',
	'VisualStyle',
	'CameraView',
	'PhysicalObject',
	'Aggregate',
	'Substance',
	'Event',
	'Process',
	'Stative',
	'Quality',
	'SpatialFact',
	'Annotation'
]);

const TOKEN_RE =
	/(#[^\n]*)|(\()|(\))|"((?:[^"\\]|\\.)*)"|:([A-Za-z_][\w-]*)|(\/)|(-?\d+(?:\.\d+)?[A-Za-z_][\w-]*)|(-?\d+(?:\.\d+)?)|([A-Za-z_][\w-]*)|(\S)/g;

type Tok =
	| { k: '(' | ')' | '/' }
	| { k: 'role' | 'id'; v: string }
	| { k: 'str' | 'num' | 'unit'; v: string };

function tokenize(src: string): Tok[] {
	const out: Tok[] = [];
	for (const m of src.matchAll(TOKEN_RE)) {
		if (m[1]) continue; // comment
		if (m[2]) out.push({ k: '(' });
		else if (m[3]) out.push({ k: ')' });
		else if (m[4] !== undefined) out.push({ k: 'str', v: m[4] });
		else if (m[5]) out.push({ k: 'role', v: m[5] });
		else if (m[6]) out.push({ k: '/' });
		else if (m[7]) out.push({ k: 'unit', v: m[7] });
		else if (m[8]) out.push({ k: 'num', v: m[8] });
		else if (m[9]) out.push({ k: 'id', v: m[9] });
	}
	return out;
}

interface AstNode {
	var: string;
	concept: string | null;
	edges: Array<{ role: string; target: AstNode | { ref: string } | { lit: string; raw: string } }>;
}

class Walker {
	private i = 0;
	constructor(private toks: Tok[]) {}
	private peek() {
		return this.toks[this.i];
	}
	private bump() {
		return this.toks[this.i++];
	}
	parseNode(): AstNode {
		const open = this.bump();
		if (!open || open.k !== '(') throw new SyntaxError('expected (');
		const v = this.bump();
		if (!v || v.k !== 'id') throw new SyntaxError('expected var id');
		const node: AstNode = { var: v.v, concept: null, edges: [] };
		if (this.peek()?.k === '/') {
			this.bump();
			const c = this.bump();
			if (!c || c.k !== 'id') throw new SyntaxError('expected concept after /');
			node.concept = c.v;
		}
		while (true) {
			const t = this.peek();
			if (!t) throw new SyntaxError('EOF inside node');
			if (t.k === ')') {
				this.bump();
				return node;
			}
			if (t.k !== 'role') throw new SyntaxError('expected role or )');
			this.bump();
			const role = (t as Tok & { k: 'role' }).v;
			node.edges.push({ role, target: this.parseTerm() });
		}
	}
	private parseTerm(): AstNode | { ref: string } | { lit: string; raw: string } {
		const t = this.peek();
		if (!t) throw new SyntaxError('EOF in term');
		if (t.k === '(') return this.parseNode();
		if (t.k === 'str') {
			this.bump();
			return { lit: 'str', raw: (t as Tok & { k: 'str' }).v };
		}
		if (t.k === 'num') {
			this.bump();
			return { lit: 'num', raw: (t as Tok & { k: 'num' }).v };
		}
		if (t.k === 'unit') {
			this.bump();
			return { lit: 'unit', raw: (t as Tok & { k: 'unit' }).v };
		}
		if (t.k === 'id') {
			this.bump();
			return { ref: (t as Tok & { k: 'id' }).v };
		}
		throw new SyntaxError(`unexpected term ${JSON.stringify(t)}`);
	}
}

function asKind(concept: string | null): NodeKind | null {
	if (!concept) return null;
	return KIND_VALUES.has(concept as NodeKind) ? (concept as NodeKind) : null;
}

const TRAIT_KEYS = new Set(['individuation', 'animacy', 'countability', 'affordance']);

// Roles whose target is a property literal (camera/scene/style schemas, plus
// SpatialFact trait values rcc/directional/proximal which point at VSO IRIs
// in the canonical Turtle but render as scalar properties in the graph view).
const PROPERTY_ROLES = new Set([
	'venue',
	'atmosphere',
	'timeOfDay',
	'weather',
	'aesthetic',
	'palette',
	'medium',
	'angle',
	'focalLength',
	'framing',
	'cameraPosition',
	'manner',
	'lemma',
	'class',
	'bbox2d',
	'rcc',
	'directional',
	'proximal'
]);

export function walkPenmanToGraph(src: string): SceneGraph {
	let ast: AstNode;
	try {
		const toks = tokenize(src);
		ast = new Walker(toks).parseNode();
	} catch {
		return { nodes: [], edges: [] };
	}

	const nodes: GraphNode[] = [];
	const edges: GraphEdge[] = [];
	const seen = new Set<string>();

	function ensureNode(id: string, kind: NodeKind | null, concept: string | null): GraphNode {
		let existing = nodes.find((n) => n.id === id);
		if (existing) {
			if (kind && !existing.kind) existing.kind = kind;
			if (concept && !existing.class && !KIND_VALUES.has(concept as NodeKind))
				existing.class = concept;
			return existing;
		}
		const n: GraphNode = {
			id,
			kind: kind ?? 'PhysicalObject',
			...(concept && !KIND_VALUES.has(concept as NodeKind) ? { class: concept } : {})
		};
		nodes.push(n);
		return n;
	}

	function visit(n: AstNode): GraphNode {
		const kind = asKind(n.concept);
		const here = ensureNode(n.var, kind, n.concept);
		seen.add(n.var);

		for (const { role, target } of n.edges) {
			// Trait properties on the entity itself.
			if (TRAIT_KEYS.has(role) && 'ref' in (target as object)) {
				here.traits = here.traits ?? {};
				const v = (target as { ref: string }).ref;
				if (role === 'affordance') here.traits.affordance = [...(here.traits.affordance ?? []), v];
				else
					(here.traits as Record<string, string | string[]>)[role] = v as
						| 'Generic'
						| 'Named'
						| 'Kind'
						| 'Skolem'
						| 'Agentive'
						| 'Inert'
						| 'Count'
						| 'Mass'
						| 'Collective';
				continue;
			}

			// Property literals (lemma, venue, focalLength, etc.) → here.properties.
			if (PROPERTY_ROLES.has(role) && 'lit' in (target as object)) {
				here.properties = here.properties ?? {};
				const t = target as { lit: string; raw: string };
				here.properties[role] = t.lit === 'num' ? Number(t.raw) : t.raw;
				continue;
			}
			if (PROPERTY_ROLES.has(role) && 'ref' in (target as object)) {
				here.properties = here.properties ?? {};
				here.properties[role] = (target as { ref: string }).ref;
				if (role === 'class') here.class = (target as { ref: string }).ref;
				continue;
			}

			// Quality edges fold into properties (avoid graph explosion).
			if (role === 'hasQuality' && typeof target === 'object' && 'edges' in (target as object)) {
				const q = target as AstNode;
				let dim: string | null = null;
				let val: string | number | null = null;
				for (const e of q.edges) {
					const t = e.target;
					if (e.role === 'dimension' && 'ref' in (t as object)) dim = (t as { ref: string }).ref;
					else if (e.role === 'value') {
						if ('ref' in (t as object)) val = (t as { ref: string }).ref;
						else if ('lit' in (t as object))
							val =
								(t as { lit: string; raw: string }).lit === 'num'
									? Number((t as { lit: string; raw: string }).raw)
									: (t as { lit: string; raw: string }).raw;
					}
				}
				if (dim && val !== null) {
					here.properties = here.properties ?? {};
					here.properties[`q_${dim}`] = val;
				}
				continue;
			}

			// Otherwise: a real graph edge.
			let toId: string | null = null;
			if (typeof target === 'object' && 'edges' in (target as object)) {
				const child = visit(target as AstNode);
				toId = child.id;
			} else if ('ref' in (target as object)) {
				toId = (target as { ref: string }).ref;
				if (!seen.has(toId)) ensureNode(toId, null, null);
			}
			if (toId) edges.push({ from: here.id, to: toId, label: role });
		}

		return here;
	}

	visit(ast);
	return { nodes, edges };
}
