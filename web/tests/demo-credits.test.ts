// Provenance gate for the pixels this studio actually ships.
//
// The demo photographs below the dropzone are third-party work. They were
// served for three releases with no recorded source, while every *derived*
// artifact in this repository carried an attribution file — the one place the
// project failed its own standard. This test is what stops that from
// recurring: an entry in `static/demos/manifest.json` without a photographer,
// a licence and a source URL fails `pnpm test`, which CI runs before the
// build, so an uncredited image cannot reach a deploy.
//
// It also refuses two specific false statements. Unsplash dropped CC0 in 2017
// and the Unsplash License is not a public-domain dedication: it is a licence
// from the photographer over the photograph, revocable in none of the ways
// CC0 is irrevocable, and it conveys no model or property release. Writing
// "CC0" or "public domain" beside one of these images would be a licence claim
// this project cannot support, so the strings are rejected wherever a licence
// is named — in the manifest, in CREDITS.md, and in NOTICE.
//
// What this test does NOT establish: that the named photographer is the
// photographer. That is a claim about the world, and the chain behind it
// (JPEG comment `Picsum ID: N` → picsum.photos/id/N/info → an unsplash.com
// photo page) is written down in CREDITS.md so a reader can walk it. This
// gate checks only that the claim is stated, stated consistently in all three
// places, and stated with a licence name that is not false on its face.

import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../..');
const DEMOS_DIR = resolve(__dirname, '../static/demos');
const MANIFEST = resolve(DEMOS_DIR, 'manifest.json');
const CREDITS = resolve(DEMOS_DIR, 'CREDITS.md');
const NOTICE = resolve(REPO_ROOT, 'NOTICE');

interface DemoEntry {
	path: string;
	label?: string;
	credit?: string;
	license?: string;
	license_url?: string;
	source_url?: string;
	served_via?: string;
}

const FORBIDDEN_LICENCE_CLAIMS = [/\bCC0\b/i, /public[\s-]+domain/i];

function entries(): DemoEntry[] {
	const manifest = JSON.parse(readFileSync(MANIFEST, 'utf8')) as { entries?: DemoEntry[] };
	return manifest.entries ?? [];
}

describe('demo image provenance', () => {
	const demos = entries();

	it('there is at least one demo to check', () => {
		expect(demos.length).toBeGreaterThan(0);
	});

	for (const entry of demos) {
		describe(entry.path, () => {
			it('names a photographer', () => {
				expect(entry.credit, `${entry.path} has no credit`).toBeTruthy();
				expect((entry.credit ?? '').trim().length).toBeGreaterThan(1);
			});

			it('names a licence', () => {
				expect(entry.license, `${entry.path} has no license`).toBeTruthy();
			});

			it('does not claim CC0 or public domain', () => {
				const claimed = [entry.license, entry.license_url].filter(Boolean).join(' ');
				for (const pattern of FORBIDDEN_LICENCE_CLAIMS) {
					expect(pattern.test(claimed), `${entry.path} licence claims ${pattern}`).toBe(false);
				}
			});

			it('points at the source it came from', () => {
				expect(entry.source_url, `${entry.path} has no source_url`).toBeTruthy();
				expect(entry.source_url ?? '').toMatch(/^https:\/\//);
			});

			it('ships the image it credits', () => {
				expect(existsSync(resolve(__dirname, '../static', entry.path.replace(/^\//, '')))).toBe(
					true
				);
			});
		});
	}

	it('CREDITS.md exists and covers every demo', () => {
		expect(existsSync(CREDITS), 'web/static/demos/CREDITS.md missing').toBe(true);
		const text = readFileSync(CREDITS, 'utf8');
		for (const entry of demos) {
			const file = entry.path.split('/').at(-1)!;
			expect(text, `CREDITS.md does not mention ${file}`).toContain(file);
			expect(text, `CREDITS.md does not credit ${entry.credit}`).toContain(entry.credit!);
			expect(text, `CREDITS.md does not link ${entry.source_url}`).toContain(entry.source_url!);
		}
	});

	it('NOTICE exists and covers every demo', () => {
		expect(existsSync(NOTICE), 'repository NOTICE missing').toBe(true);
		const text = readFileSync(NOTICE, 'utf8');
		for (const entry of demos) {
			const file = entry.path.split('/').at(-1)!;
			expect(text, `NOTICE does not mention ${file}`).toContain(file);
			expect(text, `NOTICE does not credit ${entry.credit}`).toContain(entry.credit!);
		}
	});

	it('neither CREDITS.md nor NOTICE calls an image CC0 or public domain', () => {
		for (const file of [CREDITS, NOTICE]) {
			const text = readFileSync(file, 'utf8');
			for (const pattern of FORBIDDEN_LICENCE_CLAIMS) {
				// The files are allowed to say what the licence is NOT, so the
				// rejection is scoped to lines that read as an assertion about one
				// of these images: a table row, or a "License:" line.
				const claiming = text
					.split('\n')
					.filter((line) => /^\s*\|/.test(line) || /licen[cs]e\s*[:=]/i.test(line));
				for (const line of claiming) {
					expect(pattern.test(line), `${file}: "${line.trim()}"`).toBe(false);
				}
			}
		}
	});
});
