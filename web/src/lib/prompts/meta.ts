// Compile-time prompt METADATA. This module must stay tiny and free of any
// static dependency on the prompt bodies: it is imported by always-loaded UI
// (NotationToggle) and by the extraction routes, while the ~36 KB of canonical
// prompt text lives in ./bodies — a separate, lazily-imported chunk. Anything
// that needs the actual text imports ./bodies at the call site; a static
// import of ./bodies from here would chain the whole text into first paint.

export type PromptVariant = 'skill' | 'skill-x' | 'full';

export const PROMPT_VARIANTS: readonly PromptVariant[] = ['skill', 'skill-x', 'full'];

// Compile-time X-skill availability. import.meta.glob resolves its key set at
// build time, so a missing skills/vson-extractor-x/SKILL.md degrades this to
// `false` (and the notation toggle to "unavailable") instead of breaking the
// build. The non-eager form records only the file list — the body itself is
// never loaded through this glob.
const SKILL_X_FILES = import.meta.glob('../../../../skills/vson-extractor-x/SKILL.md', {
	query: '?raw'
});

/** True iff the VSON-X skill file was present in the checkout at build time. */
export function isXSkillReady(): boolean {
	return Object.keys(SKILL_X_FILES).length > 0;
}

export const BARE_EXTRACT_USER =
	'Emit the VSON-P document for this image. Output ONLY the Penman — start with `(`, end with `)`. No prose, no fences.';

export const BARE_EXTRACT_USER_X =
	'Emit the VSON-X document for this image. The first line MUST start with `~scene`. Output ONLY VSON-X — no prose, no fences, no Penman parens.';

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

// ──────────────────────────────────────────────────────────────────────────────
// Targeted correction prompts. Unlike extraction/repair these do NOT re-derive
// the scene from the image — they apply a small, enumerated list of human edits
// to an EXISTING document and return the COMPLETE corrected document with every
// other entity/quality/edge/frame/id preserved verbatim. They are pure string
// builders over their arguments, which is why they live here and not in
// ./bodies.
// ──────────────────────────────────────────────────────────────────────────────

export interface CorrectionItem {
	id: string;
	klass?: string;
	qualities?: { dim: string; value: string }[];
	note?: string;
	remove?: boolean;
}

// Render one correction item as a single human-readable instruction line.
function renderCorrectionItem(item: CorrectionItem): string {
	if (item.remove) {
		return `- entity @${item.id}: REMOVE this entity`;
	}
	const parts: string[] = [];
	if (item.klass) parts.push(`set class to ${item.klass}`);
	for (const q of item.qualities ?? []) {
		parts.push(`set quality ${q.dim} to ${q.value}`);
	}
	if (item.note) parts.push(`note: ${item.note}`);
	const body = parts.length ? parts.join('; ') : 'no-op';
	return `- entity @${item.id}: ${body}`;
}

function renderCorrectionList(items: CorrectionItem[], sceneNote?: string): string {
	const lines = items.map(renderCorrectionItem);
	if (sceneNote && sceneNote.trim()) {
		lines.push(`Scene note: ${sceneNote.trim()}`);
	}
	return lines.join('\n');
}

export function buildCorrectionPrompt(
	currentDoc: string,
	items: CorrectionItem[],
	sceneNote?: string
): string {
	return [
		'You are applying targeted corrections to an existing VSON-P (Penman) document.',
		'This is NOT a re-extraction. Apply ONLY the corrections listed below and return',
		'the COMPLETE corrected document in the same Penman notation. Preserve every other',
		'entity, quality, edge, frame, and id verbatim — do not re-derive, reorder, rename,',
		'or drop anything that is not explicitly corrected.',
		'',
		'Corrections to apply:',
		renderCorrectionList(items, sceneNote),
		'',
		'Current document:',
		currentDoc,
		'',
		'Return the complete corrected Penman document only, no prose, no fences.'
	].join('\n');
}

export function buildCorrectionXPrompt(
	currentDoc: string,
	items: CorrectionItem[],
	sceneNote?: string
): string {
	return [
		'You are applying targeted corrections to an existing VSON-X document.',
		'This is NOT a re-extraction. Apply ONLY the corrections listed below and return',
		'the COMPLETE corrected document in the same VSON-X notation. Preserve every other',
		'entity, quality, edge, frame, and id verbatim — do not re-derive, reorder, rename,',
		'or drop anything that is not explicitly corrected.',
		'',
		'Corrections to apply:',
		renderCorrectionList(items, sceneNote),
		'',
		'Current document:',
		currentDoc,
		'',
		'Return the complete corrected VSON-X document only; first character must be ~.'
	].join('\n');
}

// ──────────────────────────────────────────────────────────────────────────────
// Skill manifest shape — built by ./bodies (which holds the text), rendered on
// /prompts and behind ExportRow's system-prompt copy.
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
