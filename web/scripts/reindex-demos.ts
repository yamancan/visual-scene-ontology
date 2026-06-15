// Regenerate static/demos/envelopes/index.json from the on-disk manifest +
// envelope files. Pure SHA computation — no LLM calls, no cost.
//
// Use this when:
//   - bake-demos.ts was run with --only=X and overwrote the index with one entry
//   - you want the cache short-circuit to fire for every demo without re-baking
//
//   pnpm dlx tsx web/scripts/reindex-demos.ts

import { createHash } from 'node:crypto';
import { readFile, writeFile, access } from 'node:fs/promises';
import { resolve, basename, extname } from 'node:path';

interface ManifestEntry {
	path: string;
	envelope_path?: string;
}

const ROOT = resolve(import.meta.dirname, '..');
const DEMOS_DIR = resolve(ROOT, 'static/demos');
const ENVELOPES_DIR = resolve(DEMOS_DIR, 'envelopes');
const MANIFEST = resolve(DEMOS_DIR, 'manifest.json');

async function exists(p: string): Promise<boolean> {
	try {
		await access(p);
		return true;
	} catch {
		return false;
	}
}

async function main() {
	const manifest = JSON.parse(await readFile(MANIFEST, 'utf8')) as { entries: ManifestEntry[] };
	const index: Record<string, string> = {};
	const skipped: string[] = [];

	for (const entry of manifest.entries) {
		const imagePath = resolve(DEMOS_DIR, basename(entry.path));
		const envelopeFile = `${basename(imagePath, extname(imagePath))}.json`;
		const envelopePath = resolve(ENVELOPES_DIR, envelopeFile);

		if (!(await exists(imagePath))) {
			skipped.push(`${entry.path} (image missing)`);
			continue;
		}
		if (!(await exists(envelopePath))) {
			skipped.push(`${entry.path} (envelope ${envelopeFile} missing — bake first)`);
			continue;
		}

		const bytes = await readFile(imagePath);
		const sha = createHash('sha256').update(bytes).digest('hex');
		index[sha] = envelopeFile;
		console.log(`[reindex] ${entry.path} sha=${sha.slice(0, 8)}… → ${envelopeFile}`);
	}

	await writeFile(resolve(ENVELOPES_DIR, 'index.json'), JSON.stringify(index, null, 2) + '\n');
	console.log(`[reindex] wrote index.json (${Object.keys(index).length} entries)`);
	if (skipped.length) {
		console.log(`[reindex] skipped: ${skipped.join(', ')}`);
	}
}

main().catch((e) => {
	console.error(e);
	process.exit(1);
});
