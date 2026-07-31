// The compile-time skill manifest, asserted against the canonical files.
//
// $lib/prompts/bodies inlines repo-root prompt files via Vite ?raw imports at
// build time. This test re-reads the same files with node:fs and pins that
// what the bundle ships is exactly what the checkout holds:
//
//   1. every manifest body is byte-identical to its canonical file,
//   2. every size_bytes matches the canonical file's UTF-8 byte length,
//   3. the compile-time availability flag tracks the X skill's presence on
//      disk (and degrades — never breaks — when the file is absent),
//   4. the repair templates ride along unmodified.
//
// A renamed canonical file fails the ?raw import at transform time, so this
// suite doubles as the loud in-checkout error the old readFileSync gave us.

import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
	loadSkillManifest,
	ORCHESTRATOR_SYSTEM_PROMPT,
	REPAIR_PROMPT_TEMPLATE,
	REPAIR_X_PROMPT_TEMPLATE,
	SKILL_PROMPT,
	SKILL_X_PROMPT
} from '../src/lib/prompts/bodies';
import { isXSkillReady } from '../src/lib/prompts/meta';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '../..');

const CANONICAL: Record<'penman' | 'vson-x' | 'orchestrator', string> = {
	penman: resolve(REPO_ROOT, 'skills/vson-extractor/SKILL.md'),
	'vson-x': resolve(REPO_ROOT, 'skills/vson-extractor-x/SKILL.md'),
	orchestrator: resolve(REPO_ROOT, 'tools/extractor/prompts/orchestrator-system.md')
};

const X_ON_DISK = existsSync(CANONICAL['vson-x']);

function bytesOf(text: string): number {
	return new TextEncoder().encode(text).length;
}

describe('skill manifest vs canonical files', () => {
	const manifest = loadSkillManifest();

	it('carries exactly the three known skills, in order', () => {
		expect(manifest.map((s) => s.id)).toEqual(['penman', 'vson-x', 'orchestrator']);
	});

	it('penman body and size match skills/vson-extractor/SKILL.md', () => {
		const entry = manifest.find((s) => s.id === 'penman')!;
		const onDisk = readFileSync(CANONICAL.penman, 'utf8');
		expect(entry.body).toBe(onDisk);
		expect(entry.size_bytes).toBe(bytesOf(onDisk));
		expect(entry.available).toBe(true);
	});

	it('orchestrator body and size match tools/extractor/prompts/orchestrator-system.md', () => {
		const entry = manifest.find((s) => s.id === 'orchestrator')!;
		const onDisk = readFileSync(CANONICAL.orchestrator, 'utf8');
		expect(entry.body).toBe(onDisk);
		expect(entry.size_bytes).toBe(bytesOf(onDisk));
		expect(entry.available).toBe(true);
	});

	it('vson-x availability tracks the file on disk, body follows', () => {
		const entry = manifest.find((s) => s.id === 'vson-x')!;
		expect(entry.available).toBe(X_ON_DISK);
		if (X_ON_DISK) {
			const onDisk = readFileSync(CANONICAL['vson-x'], 'utf8');
			expect(entry.body).toBe(onDisk);
		} else {
			// Soft-import fallback: a stub that names the situation, not a crash.
			expect(entry.body).toContain('not shipped');
		}
		expect(entry.size_bytes).toBe(bytesOf(entry.body));
	});

	it('every size_bytes is the UTF-8 byte length of its own body', () => {
		for (const entry of manifest) {
			expect(entry.size_bytes).toBe(bytesOf(entry.body));
		}
	});
});

describe('compile-time X availability', () => {
	it('isXSkillReady() agrees with the checkout', () => {
		expect(isXSkillReady()).toBe(X_ON_DISK);
	});

	it('exported constants mirror the manifest bodies', () => {
		const byId = Object.fromEntries(loadSkillManifest().map((s) => [s.id, s.body]));
		expect(byId['penman']).toBe(SKILL_PROMPT);
		expect(byId['vson-x']).toBe(SKILL_X_PROMPT);
		expect(byId['orchestrator']).toBe(ORCHESTRATOR_SYSTEM_PROMPT);
	});
});

describe('repair templates vs canonical files', () => {
	it('repair.md is inlined byte-identical', () => {
		const onDisk = readFileSync(
			resolve(REPO_ROOT, 'tools/extractor/prompts/specialized/repair.md'),
			'utf8'
		);
		expect(REPAIR_PROMPT_TEMPLATE).toBe(onDisk);
	});

	it('repair-x.md is inlined byte-identical', () => {
		const onDisk = readFileSync(
			resolve(REPO_ROOT, 'tools/extractor/prompts/specialized/repair-x.md'),
			'utf8'
		);
		expect(REPAIR_X_PROMPT_TEMPLATE).toBe(onDisk);
	});
});
