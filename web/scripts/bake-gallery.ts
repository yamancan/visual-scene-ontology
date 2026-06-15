// Bakes every hand-authored canonical fixture under examples/gallery/*.vson
// into a studio envelope (vson_p + vson_t + projected SceneGraph). These
// fixtures are SHACL-conformant ground truth — they exercise every VSON
// construct (Persona, Negation, BeliefState, Quantification, RDF-star
// Annotation, SpatialFact viewer, possession statives, mereology, etc.) and
// the studio reads them as "canonical" demos so the renderer is always
// validated against documents that conform to the spec, not just extractor
// output.
//
// Run with:  pnpm dlx tsx web/scripts/bake-gallery.ts
//
// Outputs:
//   web/static/demos/envelopes/gallery/<stem>.json  (one envelope per fixture)
//   web/static/demos/manifest-gallery.json          (index for studio picker)

import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { walkPenmanToGraph } from '../src/lib/server/graph-walk';
import type { VsonEnvelope } from '../src/lib/types';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = resolve(__dirname, '..');
const REPO_ROOT = resolve(WEB_ROOT, '..');
const VSON_BIN = resolve(REPO_ROOT, 'cli/target/release/vson');
const GALLERY_SRC = resolve(REPO_ROOT, 'examples/gallery');
const OUT_DIR = resolve(WEB_ROOT, 'static/demos/envelopes/gallery');
const MANIFEST_OUT = resolve(WEB_ROOT, 'static/demos/manifest-gallery.json');

interface GalleryEntry {
	stem: string;
	label: string;
	envelope_path: string;
	conforms: boolean;
	nodes: number;
	edges: number;
	covers: string[];
}

function run(args: string[]): { code: number; stdout: string; stderr: string } {
	const r = spawnSync(VSON_BIN, args, {
		cwd: REPO_ROOT,
		env: { ...process.env, VSON_HOME: REPO_ROOT },
		encoding: 'utf8'
	});
	return { code: r.status ?? -1, stdout: r.stdout, stderr: r.stderr };
}

function makeId(): string {
	const alpha = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
	let s = '';
	for (let i = 0; i < 12; i++) s += alpha[Math.floor(Math.random() * alpha.length)];
	return s;
}

function prettyLabel(stem: string): string {
	const m = stem.match(/^(\d+)_(.+)$/);
	const body = m ? m[2] : stem;
	return body.replace(/_/g, ' ').replace(/\b(\w)/g, (c) => c.toUpperCase());
}

// "Covers" tags — one or more VSON constructs each fixture exercises. Used by
// the studio sidebar to group/filter. Missing a tag is a soft warning.
const COVERS: Record<string, string[]> = {
	'01_minimal': ['minimal'],
	'02_quality': ['quality'],
	'03_spatial_topology': ['spatialfact', 'rcc'],
	'04_directional_with_viewer': ['spatialfact', 'directional', 'viewer'],
	'05_possession_stative': ['stative', 'possession'],
	'06_event_with_instrument': ['event', 'thematic-roles'],
	'07_ditransitive': ['event', 'ditransitive'],
	'08_collective': ['aggregate', 'countability'],
	'09_mass_substance': ['substance', 'mass'],
	'10_geometry_bbox': ['geometry', 'bbox2d'],
	'11_throne_room': ['composition', 'event', 'stative', 'spatialfact'],
	'12_persona': ['persona', 'embodies', 'hasInvariant'],
	'13_negation': ['negation', 'reified-annotation'],
	'14_belief_state': ['beliefstate', 'reified-annotation'],
	'15_quantification': ['quantification', 'reified-annotation'],
	'16_annotation': ['annotation', 'rdf-star', 'confidence']
};

async function main() {
	mkdirSync(OUT_DIR, { recursive: true });

	const files = readdirSync(GALLERY_SRC)
		.filter((f) => f.endsWith('.vson'))
		.sort();

	const entries: GalleryEntry[] = [];

	for (const f of files) {
		const stem = f.replace(/\.vson$/, '');
		const src = readFileSync(resolve(GALLERY_SRC, f), 'utf8');

		// Transpile via Rust CLI for parity with extractor output path.
		const t = run(['convert', 'p2t', resolve(GALLERY_SRC, f)]);
		if (t.code !== 0) {
			console.error(`[bake-gallery] ${stem}: transpile failed\n${t.stderr}`);
			process.exit(1);
		}
		const turtle = t.stdout;

		// Validate via the same CLI (writes to a temp .ttl file).
		const tmpTurtle = resolve(OUT_DIR, `__bake_${stem}.ttl`);
		writeFileSync(tmpTurtle, turtle);
		const v = run(['validate', tmpTurtle]);
		const conforms = v.code === 0;
		if (!conforms) {
			console.error(`[bake-gallery] ${stem}: SHACL FAILED\n${v.stdout}\n${v.stderr}`);
			process.exit(1);
		}

		const graph = walkPenmanToGraph(src);

		const env: VsonEnvelope = {
			scene_id: `gallery_${stem}_${makeId()}`,
			version: '1.0',
			source: { kind: 'hand_authored', uri: `examples/gallery/${f}` },
			vson_p: src,
			vson_t: turtle,
			graph,
			conformance: { conforms: true },
			extraction: {
				model: 'gallery-bake',
				prompt_version: 'canonical@1.0',
				shacl_retries: 0,
				latency_ms: 0,
				input_tokens: 0,
				output_tokens: 0
			}
		};

		const envFile = `${stem}.json`;
		writeFileSync(resolve(OUT_DIR, envFile), JSON.stringify(env, null, 2) + '\n');

		entries.push({
			stem,
			label: prettyLabel(stem),
			envelope_path: `/demos/envelopes/gallery/${envFile}`,
			conforms,
			nodes: graph.nodes.length,
			edges: graph.edges.length,
			covers: COVERS[stem] ?? []
		});

		console.log(
			`[bake-gallery] ${stem}: nodes=${graph.nodes.length} edges=${graph.edges.length} covers=[${(COVERS[stem] ?? []).join(', ')}]`
		);
	}

	// Cleanup tmp .ttl files.
	const fsp = await import('node:fs/promises');
	const tmps = await fsp.readdir(OUT_DIR);
	for (const f of tmps) {
		if (f.startsWith('__bake_')) await fsp.unlink(resolve(OUT_DIR, f));
	}

	const manifest = {
		_doc: 'Canonical hand-authored fixtures from examples/gallery/. Every entry is strict-SHACL-conformant. Studio picker reads this to populate the gallery section.',
		generated_at: new Date().toISOString(),
		entries
	};
	writeFileSync(MANIFEST_OUT, JSON.stringify(manifest, null, 2) + '\n');

	console.log(`[bake-gallery] wrote ${entries.length} envelopes + manifest-gallery.json`);
}

main().catch((e) => {
	console.error(e);
	process.exit(1);
});
