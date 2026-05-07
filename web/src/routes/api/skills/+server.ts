import { json } from '@sveltejs/kit';
import { createHash } from 'node:crypto';
import type { RequestHandler } from './$types';
import { loadSkillManifest } from '$lib/server/prompt';

// Manifest is computed once at module load — skill files are read at server
// startup via tryLoad / tryLoadOptional, so the manifest is stable across
// requests. ETag is a content hash so clients can revalidate cheaply.
const manifest = loadSkillManifest();
const etag =
	'"' +
	createHash('sha256')
		.update(JSON.stringify(manifest))
		.digest('hex')
		.slice(0, 16) +
	'"';

export const GET: RequestHandler = ({ request }) => {
	if (request.headers.get('if-none-match') === etag) {
		return new Response(null, { status: 304, headers: { etag } });
	}
	return json(manifest, {
		headers: {
			'cache-control': 'public, max-age=300',
			etag
		}
	});
};
