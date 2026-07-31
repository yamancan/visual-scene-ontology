import { error, text } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import type { SceneGraph } from '$lib/types';
import { renderCaption, renderFol } from '$lib/server/cli';
import { toCypher, toDot, toGraphML, toMermaid } from '$lib/graph/exporters';

interface GraphBody {
	graph: SceneGraph;
	format: 'cypher' | 'graphml' | 'dot' | 'mermaid';
}

interface VsonBody {
	vson_p: string;
	format: 'caption' | 'fol';
}

type Body = GraphBody | VsonBody;

const MIME: Record<GraphBody['format'] | VsonBody['format'], string> = {
	cypher: 'text/x-cypher',
	graphml: 'application/graphml+xml',
	dot: 'text/vnd.graphviz',
	mermaid: 'text/x-mermaid',
	caption: 'text/plain',
	fol: 'text/plain'
};

// `caption` and `fol` shell out to the `vson` binary, so an unbounded document
// is an unbounded subprocess. Cap the notation fields before any spawn.
const MAX_DOC_CHARS = 64 * 1024;
const DOC_FIELDS = ['vson_p', 'vson_x'] as const;

export const POST: RequestHandler = async ({ request }) => {
	const body = (await request.json().catch(() => null)) as Body | null;
	if (!body || !body.format) throw error(400, 'expected { graph, format } or { vson_p, format }');

	for (const field of DOC_FIELDS) {
		const doc = (body as unknown as Record<string, unknown>)[field];
		if (typeof doc === 'string' && doc.length > MAX_DOC_CHARS) {
			throw error(400, `${field} exceeds 64 KB cap`);
		}
	}

	if (body.format === 'caption' || body.format === 'fol') {
		const vb = body as VsonBody;
		if (!vb.vson_p) throw error(400, `${vb.format} requires { vson_p, format }`);
		if (vb.format === 'caption') {
			const r = await renderCaption(vb.vson_p);
			if (!r.ok) throw error(500, `caption renderer failed: ${r.error}`);
			return text(r.caption, { headers: { 'content-type': MIME.caption } });
		}
		const r = await renderFol(vb.vson_p);
		if (!r.ok) throw error(500, `FOL renderer failed: ${r.error}`);
		return text(r.fol, { headers: { 'content-type': MIME.fol } });
	}

	const gb = body as GraphBody;
	if (!gb.graph?.nodes || !gb.graph?.edges)
		throw error(400, 'expected { graph, format } with nodes + edges');

	let out: string;
	switch (gb.format) {
		case 'cypher':
			out = toCypher(gb.graph);
			break;
		case 'graphml':
			out = toGraphML(gb.graph);
			break;
		case 'dot':
			out = toDot(gb.graph);
			break;
		case 'mermaid':
			out = toMermaid(gb.graph);
			break;
		default:
			throw error(400, `unknown format: ${gb.format}`);
	}
	return text(out, { headers: { 'content-type': MIME[gb.format] } });
};
