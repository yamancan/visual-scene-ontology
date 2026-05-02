import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Load orchestrator-system.md once on module init. The repo root is two
// levels up from web/. In dev cwd is web/; in node-adapter prod the build is
// in web/build, so resolution still works.
const REPO_ROOT = resolve(process.cwd(), '..');

function tryLoad(rel: string): string {
	try {
		return readFileSync(resolve(REPO_ROOT, rel), 'utf8');
	} catch {
		return readFileSync(resolve(process.cwd(), '../..', rel), 'utf8');
	}
}

export const ORCHESTRATOR_SYSTEM_PROMPT = tryLoad(
	'tools/extractor/prompts/orchestrator-system.md'
);

export const REPAIR_PROMPT_TEMPLATE = tryLoad('tools/extractor/prompts/specialized/repair.md');

export const BARE_EXTRACT_USER =
	'No upstream tool evidence is available for this image. Emit your best VSON-P document directly from the image. Output ONLY the Penman document — start with `(` and end with `)`. No prose, no markdown fences.';

export function buildRepairPrompt(failedDoc: string, shaclReport: string): string {
	return REPAIR_PROMPT_TEMPLATE.replace('{{FAILED_DOCUMENT}}', failedDoc).replace(
		'{{SHACL_REPORT}}',
		shaclReport.slice(0, 4000)
	);
}
