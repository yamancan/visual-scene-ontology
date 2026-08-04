// Offline demo-envelope bake. Uses hand-authored vson_p per image so we can
// ship cached envelopes without a model call. The CLI does the heavy lifting:
//  - convert p2t for the canonical Turtle
//  - validate to confirm SHACL passes
// And the studio's own walker projects the graph for the UI. This keeps the
// fixture bake aligned with what the live extractor would produce.
//
// Run with:  pnpm dlx tsx web/scripts/bake-fixtures.ts

import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { walkPenmanToGraph } from '../src/lib/graph/walk';
import type { VsonEnvelope } from '../src/lib/types';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = resolve(__dirname, '..');
const REPO_ROOT = resolve(WEB_ROOT, '..');
const VSON_BIN = resolve(REPO_ROOT, 'cli/target/release/vson');
const DEMOS_DIR = resolve(WEB_ROOT, 'static/demos');
const ENVELOPES_DIR = resolve(DEMOS_DIR, 'envelopes');
const MANIFEST = resolve(DEMOS_DIR, 'manifest.json');

interface Fixture {
	image: string;
	label: string;
	mime: 'image/jpeg' | 'image/png';
	vson_p: string;
}

const FIXTURES: Fixture[] = [
	{
		image: 'kitchen.jpg',
		label: 'Kitchen',
		mime: 'image/jpeg',
		vson_p: `(c / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 35mm :framing medium_shot)
   :framedBy (ctx / SceneContext :venue kitchen :atmosphere domestic :timeOfDay day)
   :framedBy (style / VisualStyle :aesthetic photographic :palette warm :medium digital)
   :viewedBy cam
   :depicts (counter / PhysicalObject :class Counter
               :individuation Generic :animacy Inert :countability Count
               :bbox2d "0.00,0.55,1.00,0.45"
               :hasQuality (cq1 / Quality :dimension Material :value wood))
   :depicts (kettle / PhysicalObject :class Kettle
               :individuation Generic :animacy Inert :countability Count
               :affordance Container :affordance Holdable
               :bbox2d "0.18,0.32,0.20,0.38"
               :hasQuality (kq1 / Quality :dimension Material :value metal))
   :depicts (cup / PhysicalObject :class Cup
               :individuation Generic :animacy Inert :countability Count
               :affordance Container :affordance Holdable
               :bbox2d "0.52,0.50,0.10,0.18"
               :hasQuality (cq2 / Quality :dimension Material :value ceramic)
               :hasQuality (cq3 / Quality :dimension Color :value white))
   :depicts (bowl / PhysicalObject :class Bowl
               :individuation Generic :animacy Inert :countability Count
               :affordance Container
               :bbox2d "0.70,0.58,0.14,0.16"
               :hasQuality (bq1 / Quality :dimension Material :value ceramic))
   :depicts (sf1 / SpatialFact :figure cup :ground counter :rcc EC :directional above :viewer cam)
   :depicts (sf2 / SpatialFact :figure kettle :ground counter :rcc EC :directional above :viewer cam)
   :depicts (sf3 / SpatialFact :figure bowl :ground counter :rcc EC :directional above :viewer cam))`
	},
	// A fifth fixture stood here for street.jpg. The image was withdrawn on
	// 2026-08-04 (spec/CHANGELOG.md) and the fixture went with it, because a
	// fixture whose image is not on disk bakes an envelope no manifest entry
	// points at.
	{
		image: 'forest.jpg',
		label: 'Forest',
		mime: 'image/jpeg',
		vson_p: `(c / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing wide_shot)
   :framedBy (ctx / SceneContext :venue forest :atmosphere serene :timeOfDay day)
   :framedBy (style / VisualStyle :aesthetic photographic :palette green :medium digital)
   :viewedBy cam
   :depicts (canopy / Aggregate :class TreeCanopy
               :individuation Generic :animacy Inert :countability Collective
               :bbox2d "0.00,0.00,1.00,0.65"
               :hasQuality (gq1 / Quality :dimension Color :value green))
   :depicts (trunk1 / PhysicalObject :class Tree
               :individuation Generic :animacy Inert :countability Count
               :bbox2d "0.10,0.20,0.18,0.70"
               :hasQuality (tq1 / Quality :dimension Material :value bark))
   :depicts (trunk2 / PhysicalObject :class Tree
               :individuation Generic :animacy Inert :countability Count
               :bbox2d "0.55,0.18,0.20,0.72")
   :depicts (ground / Substance :class Soil
               :individuation Generic :animacy Inert :countability Mass
               :hasQuality (sq1 / Quality :dimension Color :value brown))
   :depicts (sf1 / SpatialFact :figure trunk1 :ground ground :rcc EC :directional above :viewer cam)
   :depicts (sf2 / SpatialFact :figure trunk2 :ground ground :rcc EC :directional above :viewer cam)
   :depicts (sf3 / SpatialFact :figure canopy :ground trunk1 :rcc PO :directional above :viewer cam))`
	},
	{
		image: 'books.jpg',
		label: 'Bookshelf',
		mime: 'image/jpeg',
		vson_p: `(c / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing close_up)
   :framedBy (ctx / SceneContext :venue library :atmosphere quiet :timeOfDay day)
   :framedBy (style / VisualStyle :aesthetic photographic :palette warm :medium digital)
   :viewedBy cam
   :depicts (shelf / PhysicalObject :class Shelf
               :individuation Generic :animacy Inert :countability Count
               :affordance Mountable
               :bbox2d "0.00,0.00,1.00,1.00"
               :hasQuality (shq1 / Quality :dimension Material :value wood))
   :depicts (books / Aggregate :class BookCollection
               :individuation Generic :animacy Inert :countability Collective
               :bbox2d "0.05,0.10,0.90,0.80"
               :hasQuality (bq1 / Quality :dimension Color :value mixed))
   :depicts (book1 / PhysicalObject :class Book
               :individuation Generic :animacy Inert :countability Count
               :affordance Holdable
               :bbox2d "0.10,0.15,0.06,0.40"
               :hasQuality (b1q1 / Quality :dimension Color :value red))
   :depicts (book2 / PhysicalObject :class Book
               :individuation Generic :animacy Inert :countability Count
               :affordance Holdable
               :bbox2d "0.18,0.15,0.06,0.42"
               :hasQuality (b2q1 / Quality :dimension Color :value blue))
   :depicts (sf1 / SpatialFact :figure books :ground shelf :rcc TPP :directional above :viewer cam)
   :depicts (sf2 / SpatialFact :figure book1 :ground books :rcc TPP :proximal adjacent :viewer cam)
   :depicts (sf3 / SpatialFact :figure book2 :ground books :rcc TPP :proximal adjacent :viewer cam))`
	},
	{
		image: 'lamp.jpg',
		label: 'Lamp',
		mime: 'image/jpeg',
		vson_p: `(c / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing close_up)
   :framedBy (ctx / SceneContext :venue interior :atmosphere intimate :timeOfDay night)
   :framedBy (style / VisualStyle :aesthetic photographic :palette warm :medium digital)
   :viewedBy cam
   :depicts (lamp / PhysicalObject :class Lamp
               :individuation Generic :animacy Inert :countability Count
               :bbox2d "0.30,0.10,0.40,0.80"
               :hasQuality (lq1 / Quality :dimension Material :value brass)
               :hasQuality (lq2 / Quality :dimension ActionState :value glowing))
   :depicts (shade / PhysicalObject :class Lampshade
               :individuation Generic :animacy Inert :countability Count
               :bbox2d "0.30,0.10,0.40,0.30"
               :hasQuality (sq1 / Quality :dimension Color :value beige)
               :hasQuality (sq2 / Quality :dimension Material :value fabric))
   :depicts (table / PhysicalObject :class Table
               :individuation Generic :animacy Inert :countability Count
               :affordance Mountable
               :bbox2d "0.00,0.85,1.00,0.15"
               :hasQuality (tq1 / Quality :dimension Material :value wood))
   :depicts (sf1 / SpatialFact :figure shade :ground lamp :rcc TPPi :directional above :viewer cam)
   :depicts (sf2 / SpatialFact :figure lamp :ground table :rcc EC :directional above :viewer cam))`
	}
];

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

interface Manifest {
	_doc?: string;
	entries: Array<{
		path: string;
		label?: string;
		mime?: 'image/jpeg' | 'image/png';
		envelope_path?: string;
		model_used?: string;
	}>;
}

async function main() {
	mkdirSync(ENVELOPES_DIR, { recursive: true });

	const manifest = JSON.parse(readFileSync(MANIFEST, 'utf8')) as Manifest;
	const updatedEntries = [...manifest.entries];
	const shaIndex: Record<string, string> = {};

	for (const fx of FIXTURES) {
		const imagePath = resolve(DEMOS_DIR, fx.image);
		const imageBytes = readFileSync(imagePath);
		const sha256 = createHash('sha256').update(imageBytes).digest('hex');

		// Write Penman to a temp file and run vson convert + validate.
		const tmpPenman = resolve(ENVELOPES_DIR, `__bake_${fx.image}.vson`);
		writeFileSync(tmpPenman, fx.vson_p);

		const t = run(['convert', 'p2t', tmpPenman]);
		if (t.code !== 0) {
			console.error(`[bake] ${fx.label}: transpile failed\n${t.stderr}`);
			process.exit(1);
		}
		const turtle = t.stdout;

		// validate expects a .ttl file path.
		const tmpTurtle = resolve(ENVELOPES_DIR, `__bake_${fx.image}.ttl`);
		writeFileSync(tmpTurtle, turtle);
		const v = run(['validate', tmpTurtle]);
		const conforms = v.code === 0;
		if (!conforms) {
			console.error(`[bake] ${fx.label}: SHACL FAILED\n${v.stdout}\n${v.stderr}`);
			process.exit(1);
		}

		const graph = walkPenmanToGraph(fx.vson_p);

		const env: VsonEnvelope = {
			scene_id: `demo_${fx.image.replace(/\.[^.]+$/, '')}_${makeId()}`,
			version: '1.0',
			source: { kind: 'image', sha256, uri: `/demos/${fx.image}` },
			vson_p: fx.vson_p,
			vson_t: turtle,
			graph,
			conformance: { conforms: true },
			extraction: {
				model: 'fixture-bake',
				prompt_version: 'skill@1.0.0',
				shacl_retries: 0,
				latency_ms: 0,
				input_tokens: 0,
				output_tokens: 0
			}
		};

		const stem = fx.image.replace(/\.[^.]+$/, '');
		const envFile = `${stem}.json`;
		writeFileSync(resolve(ENVELOPES_DIR, envFile), JSON.stringify(env, null, 2) + '\n');
		shaIndex[sha256] = envFile;

		// Update manifest.
		const idx = updatedEntries.findIndex((e) => e.path === `/demos/${fx.image}`);
		if (idx >= 0) {
			updatedEntries[idx] = {
				...updatedEntries[idx],
				envelope_path: `/demos/envelopes/${envFile}`,
				model_used: 'fixture-bake'
			};
		}

		console.log(
			`[bake] ${fx.label}: nodes=${graph.nodes.length} edges=${graph.edges.length} sha=${sha256.slice(0, 8)}…`
		);
	}

	// cleanup temp files
	const fsp = await import('node:fs/promises');
	const tmps = await fsp.readdir(ENVELOPES_DIR);
	for (const f of tmps) {
		if (f.startsWith('__bake_')) {
			await fsp.unlink(resolve(ENVELOPES_DIR, f));
		}
	}

	writeFileSync(resolve(ENVELOPES_DIR, 'index.json'), JSON.stringify(shaIndex, null, 2) + '\n');
	writeFileSync(MANIFEST, JSON.stringify({ ...manifest, entries: updatedEntries }, null, 2) + '\n');
	console.log(`[bake] wrote ${Object.keys(shaIndex).length} envelopes + index + manifest`);
}

main().catch((e) => {
	console.error(e);
	process.exit(1);
});
