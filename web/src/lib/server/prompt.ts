import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Resolve repo files. In dev cwd is web/; in node-adapter prod cwd is web/build.
const REPO_ROOT = resolve(process.cwd(), '..');

function tryLoad(rel: string): string {
	try {
		return readFileSync(resolve(REPO_ROOT, rel), 'utf8');
	} catch {
		return readFileSync(resolve(process.cwd(), '../..', rel), 'utf8');
	}
}

// Soft variant. Returns fallback when the file is missing — used for skills that
// may not yet be shipped (e.g. vson-extractor-x before D.1 lands). Hard-failing
// here would crash server startup and block the rest of the app.
function tryLoadOptional(rel: string, fallback: string): string {
	try {
		return tryLoad(rel);
	} catch {
		return fallback;
	}
}

const SKILL_X_FALLBACK =
	'# vson-extractor-x is not shipped on this server.\n\nVisit /prompts to see which skills are available.';

// Original 18 KB orchestrator prompt — strongest first-try conformance, opt-in via ?prompt=full.
export const ORCHESTRATOR_SYSTEM_PROMPT = tryLoad(
	'tools/extractor/prompts/orchestrator-system.md'
);

// 4 KB distilled VSON-P skill — default for studio. Same five hard rules, smaller token footprint.
export const SKILL_PROMPT = tryLoad('skills/vson-extractor/SKILL.md');

// 7 KB VSON-X skill — opt-in via ?prompt=skill-x. Soft-loaded.
export const SKILL_X_PROMPT = tryLoadOptional(
	'skills/vson-extractor-x/SKILL.md',
	SKILL_X_FALLBACK
);

export const REPAIR_PROMPT_TEMPLATE = tryLoad('tools/extractor/prompts/specialized/repair.md');

export const REPAIR_X_PROMPT_TEMPLATE = tryLoadOptional(
	'tools/extractor/prompts/specialized/repair-x.md',
	'# repair-x not shipped\n\nThe failed VSON-X document was:\n\n{{FAILED_DOCUMENT}}\n\nReport:\n\n{{SHACL_REPORT}}\n\nFix and re-emit. The first character MUST be `~`.'
);

export const BARE_EXTRACT_USER =
	'Emit the VSON-P document for this image. Output ONLY the Penman — start with `(`, end with `)`. No prose, no fences.';

export const BARE_EXTRACT_USER_X =
	'Emit the VSON-X document for this image. The first line MUST start with `~scene`. Output ONLY VSON-X — no prose, no fences, no Penman parens.';

export type PromptVariant = 'skill' | 'skill-x' | 'full';

export function systemPromptFor(variant: PromptVariant): string {
	switch (variant) {
		case 'full':
			return ORCHESTRATOR_SYSTEM_PROMPT;
		case 'skill-x':
			return SKILL_X_PROMPT;
		case 'skill':
		default:
			return SKILL_PROMPT;
	}
}

export function promptVersionFor(variant: PromptVariant): string {
	switch (variant) {
		case 'full':
			return 'orchestrator-system@1.0';
		case 'skill-x':
			return 'skill-x@1.0.0';
		case 'skill':
		default:
			return 'skill@1.0.0';
	}
}

export function userPromptFor(variant: PromptVariant): string {
	return variant === 'skill-x' ? BARE_EXTRACT_USER_X : BARE_EXTRACT_USER;
}

/** True iff the VSON-X skill body was loaded from disk (not the fallback stub). */
export function isXSkillReady(): boolean {
	return SKILL_X_PROMPT !== SKILL_X_FALLBACK && SKILL_X_PROMPT.length > 100;
}

export function buildRepairPrompt(failedDoc: string, shaclReport: string): string {
	return REPAIR_PROMPT_TEMPLATE.replace('{{FAILED_DOCUMENT}}', failedDoc).replace(
		'{{SHACL_REPORT}}',
		shaclReport.slice(0, 4000)
	);
}

export function buildRepairXPrompt(failedDoc: string, shaclReport: string): string {
	return REPAIR_X_PROMPT_TEMPLATE.replace('{{FAILED_DOCUMENT}}', failedDoc).replace(
		'{{SHACL_REPORT}}',
		shaclReport.slice(0, 4000)
	);
}

// ──────────────────────────────────────────────────────────────────────────────
// Skill manifest — surfaced via /api/skills and rendered on /prompts.
// ──────────────────────────────────────────────────────────────────────────────

export interface SkillManifestEntry {
	id: 'penman' | 'vson-x' | 'orchestrator';
	notation: string;
	output: 'vson_p' | 'vson_x';
	version: string;
	body: string;
	size_bytes: number;
	available: boolean;
}

export function loadSkillManifest(): SkillManifestEntry[] {
	return [
		{
			id: 'penman',
			notation: 'VSON-P (Penman)',
			output: 'vson_p',
			version: 'skill@1.0.0',
			body: SKILL_PROMPT,
			size_bytes: Buffer.byteLength(SKILL_PROMPT, 'utf8'),
			available: true
		},
		{
			id: 'vson-x',
			notation: 'VSON-X (compact)',
			output: 'vson_x',
			version: 'skill-x@1.0.0',
			body: SKILL_X_PROMPT,
			size_bytes: Buffer.byteLength(SKILL_X_PROMPT, 'utf8'),
			available: isXSkillReady()
		},
		{
			id: 'orchestrator',
			notation: 'VSON-P (full pipeline)',
			output: 'vson_p',
			version: 'orchestrator-system@1.0',
			body: ORCHESTRATOR_SYSTEM_PROMPT,
			size_bytes: Buffer.byteLength(ORCHESTRATOR_SYSTEM_PROMPT, 'utf8'),
			available: true
		}
	];
}
