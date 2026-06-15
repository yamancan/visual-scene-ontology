import { json, error } from '@sveltejs/kit';
import { createHash } from 'node:crypto';

import type { RequestHandler } from './$types';
import type { VsonEnvelope } from '$lib/types';
import { walkPenmanToGraph, walkTurtleToGraph } from '$lib/server/graph-walk';
import {
	parseViolationReport,
	transpilePenmanToTurtle,
	transpileVsonXToTurtle,
	validateTurtle
} from '$lib/server/cli';
import {
	buildCorrectionPrompt,
	buildCorrectionXPrompt,
	buildRepairPrompt,
	buildRepairXPrompt,
	isXSkillReady,
	promptVersionFor,
	systemPromptFor,
	type CorrectionItem,
	type PromptVariant
} from '$lib/server/prompt';
import { DEFAULT_MODEL, OpenRouterError, chat } from '$lib/server/openrouter';
import { shortId } from '$lib/utils';

const MAX_BYTES = 5 * 1024 * 1024;
const MAX_REPAIR_RETRIES = 2;

interface CorrectBody {
	image_b64?: string;
	mime?: 'image/jpeg' | 'image/png';
	notation: 'p' | 'x';
	source: string;
	corrections: CorrectionItem[];
	sceneNote?: string;
	model?: string;
}

// ──────────────────────────────────────────────────────────────────────────────
// Local copies of the extractor's tolerant document extractors. Deliberately NOT
// imported from extract/+server.ts — this endpoint stays self-contained so the
// extract route can evolve without leaking a coupling.
// ──────────────────────────────────────────────────────────────────────────────

function extractPenman(text: string): string | null {
	const fenced = text.match(/```(?:\w+)?\s*\n([\s\S]*?)\n```/);
	const body = (fenced ? fenced[1] : text).trim();
	const start = body.indexOf('(');
	const end = body.lastIndexOf(')');
	if (start < 0 || end <= start) return null;
	return body.slice(start, end + 1).trim();
}

function extractVsonX(text: string): string | null {
	const fenced = text.match(/```(?:\w+)?\s*\n([\s\S]*?)\n```/);
	const body = fenced ? fenced[1] : text;
	const m = body.match(/^[ \t]*~/m);
	if (!m || m.index === undefined) return null;
	const slice = body.slice(m.index).replace(/\s+$/, '');
	return slice ? slice + '\n' : null;
}

function looksLikePenman(text: string): boolean {
	return /^\s*\(/.test(text);
}

export const POST: RequestHandler = async ({ request }) => {
	let body: CorrectBody;
	try {
		body = (await request.json()) as CorrectBody;
	} catch {
		throw error(400, 'invalid JSON body');
	}
	if (!body || typeof body.source !== 'string' || !body.source.trim()) {
		throw error(400, 'expected a non-empty source document');
	}
	if (!Array.isArray(body.corrections)) {
		throw error(400, 'corrections must be an array');
	}
	if (body.notation !== 'p' && body.notation !== 'x') {
		throw error(400, "notation must be 'p' or 'x'");
	}

	// Image is OPTIONAL (gallery scenes may lack it). Validate only when present.
	let sha256: string | undefined;
	if (body.image_b64) {
		if (body.mime !== 'image/jpeg' && body.mime !== 'image/png') {
			throw error(400, 'mime must be image/jpeg or image/png');
		}
		const approxBytes = Math.floor((body.image_b64.length * 3) / 4);
		if (approxBytes > MAX_BYTES) throw error(400, 'image exceeds 5 MB cap');
		sha256 = createHash('sha256').update(Buffer.from(body.image_b64, 'base64')).digest('hex');
	}

	const variant: PromptVariant = body.notation === 'x' ? 'skill-x' : 'skill';
	if (variant === 'skill-x' && !isXSkillReady()) {
		throw error(503, 'VSON-X skill not yet shipped on this server');
	}

	const systemPrompt = systemPromptFor(variant);
	const promptVersion = promptVersionFor(variant);
	const userText =
		body.notation === 'x'
			? buildCorrectionXPrompt(body.source, body.corrections, body.sceneNote)
			: buildCorrectionPrompt(body.source, body.corrections, body.sceneNote);

	const userContent = [
		...(body.image_b64
			? [
					{
						type: 'image_url' as const,
						image_url: { url: `data:${body.mime};base64,${body.image_b64}` }
					}
				]
			: []),
		{ type: 'text' as const, text: userText }
	];

	const t0 = Date.now();
	const model = body.model && body.model.includes('/') ? body.model : undefined;

	const usage = { input: 0, output: 0 };
	let raw = '';
	try {
		const initial = await chat({
			model,
			messages: [
				{
					role: 'system',
					content: [
						{
							type: 'text',
							text: systemPrompt,
							cache_control: { type: 'ephemeral' }
						}
					]
				},
				{ role: 'user', content: userContent }
			]
		});
		usage.input = initial.usage?.prompt_tokens ?? 0;
		usage.output = initial.usage?.completion_tokens ?? 0;
		raw = initial.choices[0]?.message?.content ?? '';
	} catch (e) {
		if (e instanceof OpenRouterError) throw error(502, `upstream: ${e.message}`);
		throw error(502, 'upstream error');
	}

	const ctx: FlowCtx = {
		raw,
		model,
		systemPrompt,
		promptVersion,
		usage,
		t0,
		sha256
	};

	return body.notation === 'x' ? runVsonXFlow(ctx) : runPenmanFlow(ctx);
};

// ──────────────────────────────────────────────────────────────────────────────
// Repair loops mirror extract/+server.ts: transpile → validate → repair, up to
// two retries, then ship an envelope (conforms flag tells the UI the outcome).
// ──────────────────────────────────────────────────────────────────────────────

interface FlowCtx {
	raw: string;
	model: string | undefined;
	systemPrompt: string;
	promptVersion: string;
	usage: { input: number; output: number };
	t0: number;
	sha256?: string;
}

function buildSource(sha256?: string): VsonEnvelope['source'] {
	return { kind: 'image', ...(sha256 ? { sha256 } : {}) };
}

async function runPenmanFlow(ctx: FlowCtx) {
	let penmanText = extractPenman(ctx.raw);
	if (!penmanText) throw error(422, 'model returned empty Penman');

	let transpile = await transpilePenmanToTurtle(penmanText);
	let conformance = transpile.ok ? await validateTurtle(transpile.turtle) : null;
	let retries = 0;

	while ((!transpile.ok || !conformance!.conforms) && retries < MAX_REPAIR_RETRIES) {
		retries++;
		const reason = !transpile.ok
			? `Penman parse error: ${(transpile as { ok: false; error: string }).error}`
			: `SHACL violations:\n${conformance!.report}`;
		try {
			const repair = await chat({
				model: ctx.model,
				messages: [
					{
						role: 'system',
						content: [
							{ type: 'text', text: ctx.systemPrompt, cache_control: { type: 'ephemeral' } }
						]
					},
					{
						role: 'user',
						content: [{ type: 'text', text: buildRepairPrompt(penmanText, reason) }]
					}
				]
			});
			ctx.usage.input += repair.usage?.prompt_tokens ?? 0;
			ctx.usage.output += repair.usage?.completion_tokens ?? 0;
			penmanText = extractPenman(repair.choices[0]?.message?.content ?? '') ?? penmanText;
		} catch {
			break;
		}
		transpile = await transpilePenmanToTurtle(penmanText);
		conformance = transpile.ok ? await validateTurtle(transpile.turtle) : null;
	}

	const turtle = transpile.ok ? transpile.turtle : '';
	const conforms = !!(transpile.ok && conformance?.conforms);
	const violations = conformance ? parseViolationReport(conformance.report) : [];

	const envelope: VsonEnvelope = {
		scene_id: shortId(),
		version: '1.0',
		source: buildSource(ctx.sha256),
		vson_p: penmanText,
		vson_t: turtle,
		graph: walkPenmanToGraph(penmanText),
		conformance: { conforms, ...(violations.length ? { violations } : {}) },
		extraction: {
			model: ctx.model ?? DEFAULT_MODEL,
			prompt_version: ctx.promptVersion,
			shacl_retries: retries,
			latency_ms: Date.now() - ctx.t0,
			input_tokens: ctx.usage.input,
			output_tokens: ctx.usage.output
		}
	};

	return json(envelope);
}

// VSON-X correction flow. Mirrors extract/+server.ts: when the model regresses
// to Penman during a correction round-trip, count the drift and downgrade
// confidence_overall so the UI can flag it the same way it flags drift at
// extraction time.
async function runVsonXFlow(ctx: FlowCtx) {
	let vsonXText = extractVsonX(ctx.raw);
	let drifted = vsonXText === null && looksLikePenman(ctx.raw);
	let driftCount = drifted ? 1 : 0;

	if (!vsonXText && !drifted) {
		throw error(422, 'model returned empty VSON-X');
	}

	let workingDoc = vsonXText ?? ctx.raw.trim();
	let transpile = vsonXText
		? await transpileVsonXToTurtle(vsonXText)
		: { ok: false as const, error: 'model emitted Penman, not VSON-X' };
	let conformance = transpile.ok ? await validateTurtle(transpile.turtle) : null;
	let retries = 0;

	while ((!transpile.ok || !conformance!.conforms) && retries < MAX_REPAIR_RETRIES) {
		retries++;
		const reason = !transpile.ok
			? `VSON-X parse error: ${(transpile as { ok: false; error: string }).error}${drifted ? ' (DRIFT: model emitted Penman; first character must be ~)' : ''}`
			: `SHACL violations:\n${conformance!.report}`;
		try {
			const repair = await chat({
				model: ctx.model,
				messages: [
					{
						role: 'system',
						content: [
							{ type: 'text', text: ctx.systemPrompt, cache_control: { type: 'ephemeral' } }
						]
					},
					{
						role: 'user',
						content: [{ type: 'text', text: buildRepairXPrompt(workingDoc, reason) }]
					}
				]
			});
			ctx.usage.input += repair.usage?.prompt_tokens ?? 0;
			ctx.usage.output += repair.usage?.completion_tokens ?? 0;
			const fixedRaw = repair.choices[0]?.message?.content ?? '';
			const fixed = extractVsonX(fixedRaw);
			if (fixed) {
				vsonXText = fixed;
				workingDoc = fixed;
				drifted = false;
			} else if (looksLikePenman(fixedRaw)) {
				driftCount++;
				drifted = true;
			}
		} catch {
			break;
		}
		transpile = vsonXText
			? await transpileVsonXToTurtle(vsonXText)
			: { ok: false as const, error: 'still no VSON-X after repair (drift)' };
		conformance = transpile.ok ? await validateTurtle(transpile.turtle) : null;
	}

	const turtle = transpile.ok ? transpile.turtle : '';
	const conforms = !!(transpile.ok && conformance?.conforms);
	const violations = conformance ? parseViolationReport(conformance.report) : [];
	const finalX = vsonXText ?? '';

	const envelope: VsonEnvelope = {
		scene_id: shortId(),
		version: '1.1',
		source: buildSource(ctx.sha256),
		vson_p: '',
		vson_t: turtle,
		vson_x: finalX,
		graph: turtle ? walkTurtleToGraph(turtle) : { nodes: [], edges: [] },
		conformance: { conforms, ...(violations.length ? { violations } : {}) },
		extraction: {
			model: ctx.model ?? DEFAULT_MODEL,
			prompt_version: ctx.promptVersion,
			shacl_retries: retries,
			latency_ms: Date.now() - ctx.t0,
			input_tokens: ctx.usage.input,
			output_tokens: ctx.usage.output,
			...(driftCount > 0 ? { confidence_overall: Math.max(0, 1 - 0.25 * driftCount) } : {})
		}
	};

	return json(envelope);
}
