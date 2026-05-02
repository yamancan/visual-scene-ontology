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

// Original 18 KB orchestrator prompt — strongest first-try conformance, opt-in via ?prompt=full.
export const ORCHESTRATOR_SYSTEM_PROMPT = tryLoad(
	'tools/extractor/prompts/orchestrator-system.md'
);

// 4 KB distilled skill — default for studio. Same five hard rules, smaller token footprint.
export const SKILL_PROMPT = tryLoad('skills/vson-extractor/SKILL.md');

export const REPAIR_PROMPT_TEMPLATE = tryLoad('tools/extractor/prompts/specialized/repair.md');

export const BARE_EXTRACT_USER =
	'Emit the VSON-P document for this image. Output ONLY the Penman — start with `(`, end with `)`. No prose, no fences.';

export type PromptVariant = 'skill' | 'full';

export function systemPromptFor(variant: PromptVariant): string {
	return variant === 'full' ? ORCHESTRATOR_SYSTEM_PROMPT : SKILL_PROMPT;
}

export function promptVersionFor(variant: PromptVariant): string {
	return variant === 'full' ? 'orchestrator-system@1.0' : 'skill@1.0.0';
}

export function buildRepairPrompt(failedDoc: string, shaclReport: string): string {
	return REPAIR_PROMPT_TEMPLATE.replace('{{FAILED_DOCUMENT}}', failedDoc).replace(
		'{{SHACL_REPORT}}',
		shaclReport.slice(0, 4000)
	);
}
