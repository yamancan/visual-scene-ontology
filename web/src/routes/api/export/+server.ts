import { error, text } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import type { SceneGraph } from '$lib/types';
import { renderCaption, renderFol } from '$lib/server/cli';
import { toCypher, toDot, toGraphML, toMermaid } from '$lib/server/exporters';

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

export const POST: RequestHandler = async ({ request }) => {
	const body = (await request.json().catch(() => null)) as Body | null;
	if (!body || !body.format) throw error(400, 'expected { graph, format } or { vson_p, format }');

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

	let out = '';
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
