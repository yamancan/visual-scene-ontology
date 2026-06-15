// Pure-text exporters from a SceneGraph projection. No deps.
// Canonical Cypher and Turtle live in the Rust CLI; these are convenience
// projections for the UI's "export" menu so users can paste into common
// graph tools (Neo4j browser, Gephi, Graphviz, mermaid.live).

import type { SceneGraph } from '../types';

const escId = (s: string) => s.replace(/[^A-Za-z0-9_]/g, '_');
const quoteCypher = (s: string) => `'${s.replace(/'/g, "\\'")}'`;
const quoteXml = (s: string) =>
	s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const quoteDot = (s: string) => `"${s.replace(/"/g, '\\"')}"`;

/** Cypher CREATE statements. Pasteable into the Neo4j browser. */
export function toCypher(graph: SceneGraph): string {
	const lines: string[] = [];
	for (const n of graph.nodes) {
		const id = escId(n.id);
		const props: string[] = [`id: '${id}'`];
		if (n.class) props.push(`class: ${quoteCypher(n.class)}`);
		if (n.properties)
			for (const [k, v] of Object.entries(n.properties))
				props.push(`${k}: ${typeof v === 'number' ? v : quoteCypher(String(v))}`);
		if (n.traits)
			for (const [k, v] of Object.entries(n.traits))
				if (Array.isArray(v)) props.push(`${k}: [${v.map((x) => quoteCypher(x)).join(', ')}]`);
				else if (v) props.push(`${k}: ${quoteCypher(String(v))}`);
		lines.push(`CREATE (${id}:${n.kind} {${props.join(', ')}});`);
	}
	for (const e of graph.edges)
		lines.push(`CREATE (${escId(e.from)})-[:${e.label}]->(${escId(e.to)});`);
	return lines.join('\n') + '\n';
}

/** GraphML — XML format consumed by Gephi, yEd, NetworkX. */
export function toGraphML(graph: SceneGraph): string {
	const head = `<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="kind" for="node" attr.name="kind" attr.type="string"/>
  <key id="class" for="node" attr.name="class" attr.type="string"/>
  <key id="label" for="edge" attr.name="label" attr.type="string"/>
  <graph id="vson" edgedefault="directed">`;
	const nodes = graph.nodes
		.map(
			(n) => `    <node id="${quoteXml(n.id)}">
      <data key="kind">${quoteXml(n.kind)}</data>${n.class ? `\n      <data key="class">${quoteXml(n.class)}</data>` : ''}
    </node>`
		)
		.join('\n');
	const edges = graph.edges
		.map(
			(e, i) =>
				`    <edge id="e${i}" source="${quoteXml(e.from)}" target="${quoteXml(e.to)}"><data key="label">${quoteXml(e.label)}</data></edge>`
		)
		.join('\n');
	return `${head}\n${nodes}\n${edges}\n  </graph>\n</graphml>\n`;
}

/** Graphviz DOT — best for static rendering with `dot -Tpng`. */
export function toDot(graph: SceneGraph): string {
	const lines = [
		'digraph vson {',
		'  rankdir=LR;',
		'  graph [bgcolor="#0d0d0d", fontname="Geist"];',
		'  node  [shape=ellipse, style=filled, fontname="Geist Mono", fontsize=10, color="#3a3a3a", fillcolor="#1d1d1d", fontcolor="#fafafa"];',
		'  edge  [color="#3a3a3a", fontname="Geist Mono", fontsize=9, fontcolor="#969696"];'
	];
	for (const n of graph.nodes) {
		const label = n.class ? `${n.id}\\n${n.kind}: ${n.class}` : `${n.id}\\n${n.kind}`;
		lines.push(`  ${escId(n.id)} [label=${quoteDot(label)}];`);
	}
	for (const e of graph.edges) {
		lines.push(`  ${escId(e.from)} -> ${escId(e.to)} [label=${quoteDot(e.label)}];`);
	}
	lines.push('}');
	return lines.join('\n') + '\n';
}

/** Mermaid graph — pasteable into mermaid.live, GitHub README, Notion. */
export function toMermaid(graph: SceneGraph): string {
	const lines = ['graph LR'];
	for (const n of graph.nodes) {
		const label = n.class ? `${n.id}<br/>${n.kind}: ${n.class}` : `${n.id}<br/>${n.kind}`;
		lines.push(`  ${escId(n.id)}["${label}"]`);
	}
	for (const e of graph.edges) {
		lines.push(`  ${escId(e.from)} -->|${e.label}| ${escId(e.to)}`);
	}
	return lines.join('\n') + '\n';
}
