// Prompt BODIES — the canonical text, inlined at build time via Vite ?raw
// imports of the exact repo-root files the old server-side prompt.ts read with
// readFileSync. Single-sourcing is preserved: edit tools/extractor/prompts/*
// or skills/*/SKILL.md and the next build ships it; rename one and the build
// fails loudly in the same checkout.
//
// This module is dynamic-imported by UI consumers so the ~36 KB of text stays
// out of first paint. ./meta must never import it statically.

import orchestratorSystem from '../../../../tools/extractor/prompts/orchestrator-system.md?raw';
import skillPrompt from '../../../../skills/vson-extractor/SKILL.md?raw';
import repairTemplate from '../../../../tools/extractor/prompts/specialized/repair.md?raw';
import repairXTemplate from '../../../../tools/extractor/prompts/specialized/repair-x.md?raw';

import { isXSkillReady, type PromptVariant, type SkillManifestEntry } from './meta';
import { SHACL_REPORT_SLICE_CHARS } from '../extract/limits';

const SKILL_X_FALLBACK =
	'# vson-extractor-x is not shipped on this server.\n\nVisit /prompts to see which skills are available.';

// Soft import: the X skill may not be present in every checkout. A plain ?raw
// import of a missing file breaks the build; import.meta.glob of the same path
// degrades to an empty result instead, and isXSkillReady() (computed from the
// same glob pattern in ./meta) flips to false with it.
const SKILL_X_MODULES = import.meta.glob('../../../../skills/vson-extractor-x/SKILL.md', {
	query: '?raw',
	import: 'default',
	eager: true
}) as Record<string, string>;

// Original 18 KB orchestrator prompt. No UI surface selects it today; it ships
// for the /prompts page and for API-level callers of systemPromptFor('full').
export const ORCHESTRATOR_SYSTEM_PROMPT: string = orchestratorSystem;

// ~5 KB distilled VSON-P skill — default for studio. Same five hard rules, smaller token footprint.
export const SKILL_PROMPT: string = skillPrompt;

// ~7 KB VSON-X skill — selected by the notation toggle. Soft-imported.
export const SKILL_X_PROMPT: string = Object.values(SKILL_X_MODULES)[0] ?? SKILL_X_FALLBACK;

export const REPAIR_PROMPT_TEMPLATE: string = repairTemplate;

export const REPAIR_X_PROMPT_TEMPLATE: string = repairXTemplate;

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

export function buildRepairPrompt(failedDoc: string, shaclReport: string): string {
	return REPAIR_PROMPT_TEMPLATE.replace('{{FAILED_DOCUMENT}}', failedDoc).replace(
		'{{SHACL_REPORT}}',
		shaclReport.slice(0, SHACL_REPORT_SLICE_CHARS)
	);
}

export function buildRepairXPrompt(failedDoc: string, shaclReport: string): string {
	return REPAIR_X_PROMPT_TEMPLATE.replace('{{FAILED_DOCUMENT}}', failedDoc).replace(
		'{{SHACL_REPORT}}',
		shaclReport.slice(0, SHACL_REPORT_SLICE_CHARS)
	);
}

// ──────────────────────────────────────────────────────────────────────────────
// Skill manifest — rendered on /prompts and behind ExportRow's system-prompt
// copy. Everything in it is a compile-time constant of this bundle.
// ──────────────────────────────────────────────────────────────────────────────

function byteLength(text: string): number {
	return new TextEncoder().encode(text).length;
}

export function loadSkillManifest(): SkillManifestEntry[] {
	return [
		{
			id: 'penman',
			notation: 'VSON-P (Penman)',
			output: 'vson_p',
			version: 'skill@1.0.0',
			body: SKILL_PROMPT,
			size_bytes: byteLength(SKILL_PROMPT),
			available: true
		},
		{
			id: 'vson-x',
			notation: 'VSON-X (compact)',
			output: 'vson_x',
			version: 'skill-x@1.0.0',
			body: SKILL_X_PROMPT,
			size_bytes: byteLength(SKILL_X_PROMPT),
			available: isXSkillReady()
		},
		{
			id: 'orchestrator',
			notation: 'VSON-P (full pipeline)',
			output: 'vson_p',
			version: 'orchestrator-system@1.0',
			body: ORCHESTRATOR_SYSTEM_PROMPT,
			size_bytes: byteLength(ORCHESTRATOR_SYSTEM_PROMPT),
			available: true
		}
	];
}
