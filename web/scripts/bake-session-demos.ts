// Bake demo envelopes from a session-based extraction — the successor to the
// retired server-era bake-demos.ts, whose /api/extract endpoint no longer
// exists (the studio is static since v1.3).
//
// The extraction itself happens OUTSIDE this script: a vision-capable model
// reads the image and authors VSON-P against the extractor skill, and the
// document is validated by the real CLI gates (`vson validate`, three gates,
// plus `vson verify --geometry`) until it conforms. This script only does the
// deterministic assembly the studio itself would do: reference-transpiled
// Turtle in, `buildPenmanEnvelope` out — same walker, same field order, same
// wire version '1.2' as a live extraction in the browser.
//
// NEW FILES ONLY: this script refuses to overwrite an existing envelope.
// Frozen envelopes are genuine model output and are never regenerated.
//
//   pnpm --dir web exec tsx scripts/bake-session-demos.ts <job.json>
//
// job.json: { "model": "...", "prompt_version": "skill@1.0.0", "images": [
//   { "name": "cat", "penman": "/path/cat.vson", "turtle": "/path/cat.ttl",
//     "sha256": "...", "uri": "/demos/cat.jpg", "shacl_retries": 1 } ] }
// Unmetered runs carry latency_ms / input_tokens / output_tokens as 0; the
// meaning of that sentinel is documented in web/static/demos/CREDITS.md.

import { readFile, writeFile, access } from 'node:fs/promises';
import { resolve } from 'node:path';
import { buildPenmanEnvelope } from '../src/lib/extract/envelope';

interface JobImage {
	name: string;
	penman: string;
	turtle: string;
	sha256: string;
	uri: string;
	shacl_retries: number;
}

interface Job {
	model: string;
	prompt_version: string;
	images: JobImage[];
}

const ENVELOPES_DIR = resolve(import.meta.dirname, '../static/demos/envelopes');

async function main() {
	const jobPath = process.argv[2];
	if (!jobPath) throw new Error('usage: bake-session-demos.ts <job.json>');
	const job = JSON.parse(await readFile(jobPath, 'utf8')) as Job;

	for (const img of job.images) {
		const outPath = resolve(ENVELOPES_DIR, `${img.name}.json`);
		const exists = await access(outPath)
			.then(() => true)
			.catch(() => false);
		if (exists) throw new Error(`refusing to overwrite existing envelope: ${outPath}`);

		const penman = await readFile(img.penman, 'utf8');
		const turtle = await readFile(img.turtle, 'utf8');
		const env = buildPenmanEnvelope({
			penman: penman.trimEnd(),
			turtle,
			conformance: { conforms: true },
			source: { sha256: img.sha256, uri: img.uri },
			stats: {
				model: job.model,
				promptVersion: job.prompt_version,
				shaclRetries: img.shacl_retries,
				latencyMs: 0,
				inputTokens: 0,
				outputTokens: 0
			}
		});
		await writeFile(outPath, JSON.stringify(env, null, 2) + '\n');
		console.log(
			`[bake] ${img.name}.json nodes=${env.graph.nodes.length} edges=${env.graph.edges.length} scene_id=${env.scene_id}`
		);
	}
}

main().catch((e) => {
	console.error(e);
	process.exit(1);
});
