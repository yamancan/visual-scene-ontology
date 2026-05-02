// One-shot script to pre-extract envelopes for the 5 curated demo images and
// commit them as static JSON. The studio short-circuits to these on click —
// $0 to serve and instant-render even with no API key.
//
// Run when the prompt or demo set changes:
//   pnpm dlx tsx web/scripts/bake-demos.ts            # bake all demos
//   pnpm dlx tsx web/scripts/bake-demos.ts --validate # bake + assert conformance
//
// Requires a running dev server (`pnpm dev` in another shell) and OPENROUTER_API_KEY.

import { createHash } from 'node:crypto';
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { resolve, basename, extname } from 'node:path';

interface ManifestEntry {
	path: string;
	label?: string;
	mime?: 'image/jpeg' | 'image/png';
	envelope_path?: string;
	model_used?: string;
}

interface Manifest {
	_doc?: string;
	entries: ManifestEntry[];
}

const ROOT = resolve(import.meta.dirname, '..');
const DEMOS_DIR = resolve(ROOT, 'static/demos');
const ENVELOPES_DIR = resolve(DEMOS_DIR, 'envelopes');
const MANIFEST = resolve(DEMOS_DIR, 'manifest.json');
const ENDPOINT = process.env.STUDIO_URL ?? 'http://127.0.0.1:5173';
const MODEL = process.env.MODEL ?? 'google/gemini-2.5-flash';

function mimeOf(ext: string): 'image/jpeg' | 'image/png' {
	return ext.toLowerCase() === '.png' ? 'image/png' : 'image/jpeg';
}

async function bakeOne(entry: ManifestEntry, validate: boolean): Promise<{ entry: ManifestEntry; sha: string }> {
	const filePath = resolve(DEMOS_DIR, basename(entry.path));
	const bytes = await readFile(filePath);
	const sha = createHash('sha256').update(bytes).digest('hex');
	const b64 = bytes.toString('base64');
	const mime = entry.mime ?? mimeOf(extname(filePath));

	console.log(`[bake] ${entry.label ?? basename(filePath)} sha=${sha.slice(0, 8)}…`);

	const t0 = Date.now();
	const res = await fetch(`${ENDPOINT}/api/extract`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({
			image_b64: b64,
			mime,
			source_uri: entry.path,
			model: MODEL,
			prompt: 'skill'
		})
	});
	if (!res.ok) {
		const t = await res.text().catch(() => '');
		throw new Error(`extract failed (${res.status}): ${t.slice(0, 200)}`);
	}
	const env = (await res.json()) as Record<string, unknown> & {
		conformance?: { conforms?: boolean; violations?: unknown[] };
		graph?: { nodes: unknown[]; edges: unknown[] };
		extraction?: { latency_ms?: number; shacl_retries?: number };
	};

	const conforms = env.conformance?.conforms === true;
	const nodes = env.graph?.nodes?.length ?? 0;
	const edges = env.graph?.edges?.length ?? 0;
	const ms = Date.now() - t0;
	console.log(`       conforms=${conforms} nodes=${nodes} edges=${edges} retries=${env.extraction?.shacl_retries ?? 0} ${ms}ms`);

	if (validate && !conforms) {
		throw new Error(`${entry.label}: did not conform after retries`);
	}

	const outFile = `${basename(filePath, extname(filePath))}.json`;
	await writeFile(resolve(ENVELOPES_DIR, outFile), JSON.stringify(env, null, 2) + '\n');

	return {
		entry: { ...entry, envelope_path: `/demos/envelopes/${outFile}`, model_used: MODEL },
		sha
	};
}

async function main() {
	const validate = process.argv.includes('--validate');
	const onlyArg = process.argv.find((a) => a.startsWith('--only='));
	const only = onlyArg ? onlyArg.slice('--only='.length) : null;

	const manifest = JSON.parse(await readFile(MANIFEST, 'utf8')) as Manifest;
	const entries = only
		? manifest.entries.filter((e) => e.path.includes(only))
		: manifest.entries;

	const baked: { entry: ManifestEntry; sha: string }[] = [];
	for (const e of entries) {
		try {
			baked.push(await bakeOne(e, validate));
		} catch (err) {
			console.error(`[bake] FAILED ${e.label}: ${(err as Error).message}`);
			if (validate) process.exit(1);
		}
	}

	// Write SHA index so the server can reverse-lookup demo bytes → envelope.
	const shaIndex: Record<string, string> = {};
	for (const b of baked) shaIndex[b.sha] = `${basename(b.entry.path, extname(b.entry.path))}.json`;
	await writeFile(
		resolve(ENVELOPES_DIR, 'index.json'),
		JSON.stringify(shaIndex, null, 2) + '\n'
	);
	console.log(`[bake] wrote index.json (${Object.keys(shaIndex).length} entries)`);

	// Update manifest.json with envelope_path + model_used.
	const updated: Manifest = {
		...manifest,
		entries: manifest.entries.map((orig) => {
			const hit = baked.find((b) => b.entry.path === orig.path);
			return hit ? hit.entry : orig;
		})
	};
	await writeFile(MANIFEST, JSON.stringify(updated, null, 2) + '\n');
	console.log(`[bake] updated manifest.json`);

	// Sanity: list files in envelopes dir.
	const files = await readdir(ENVELOPES_DIR);
	console.log(`[bake] envelopes/ contains: ${files.sort().join(', ')}`);
}

main().catch((e) => {
	console.error(e);
	process.exit(1);
});
