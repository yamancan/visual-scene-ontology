import { error, text } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import type { SceneGraph } from '$lib/types';
import { toCypher, toDot, toGraphML, toMermaid } from '$lib/server/exporters';

interface Body {
	graph: SceneGraph;
	format: 'cypher' | 'graphml' | 'dot' | 'mermaid';
}

const MIME: Record<Body['format'], string> = {
	cypher: 'text/x-cypher',
	graphml: 'application/graphml+xml',
	dot: 'text/vnd.graphviz',
	mermaid: 'text/x-mermaid'
};

export const POST: RequestHandler = async ({ request }) => {
	const body = (await request.json().catch(() => null)) as Body | null;
	if (!body?.graph?.nodes || !body?.graph?.edges || !body.format)
		throw error(400, 'expected { graph, format }');

	let out = '';
	switch (body.format) {
		case 'cypher':
			out = toCypher(body.graph);
			break;
		case 'graphml':
			out = toGraphML(body.graph);
			break;
		case 'dot':
			out = toDot(body.graph);
			break;
		case 'mermaid':
			out = toMermaid(body.graph);
			break;
		default:
			throw error(400, `unknown format: ${body.format}`);
	}
	return text(out, { headers: { 'content-type': MIME[body.format] } });
};
