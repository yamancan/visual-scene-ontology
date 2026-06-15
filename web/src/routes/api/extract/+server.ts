import { json, error } from '@sveltejs/kit';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

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
	BARE_EXTRACT_USER,
	BARE_EXTRACT_USER_X,
	buildRepairPrompt,
	buildRepairXPrompt,
	isXSkillReady,
	promptVersionFor,
	systemPromptFor,
	type PromptVariant
} from '$lib/server/prompt';
import { DEFAULT_MODEL, OpenRouterError, chat } from '$lib/server/openrouter';
import { shortId } from '$lib/utils';

const MAX_BYTES = 5 * 1024 * 1024;
const MAX_REPAIR_RETRIES = 2;

interface ExtractBody {
	image_b64: string;
	mime: 'image/jpeg' | 'image/png';
	source_uri?: string;
	model?: string;
	sha256?: string;
	prompt?: 'skill' | 'skill-x' | 'full';
}

// Cached demo envelopes. SHA-256 of the bytes → envelope path. Loaded once,
// served instantly without an LLM call. Defends the cache path against `curl`
// callers who would otherwise bypass the client-side short-circuit.
const DEMO_DIR = resolve(process.cwd(), 'static/demos/envelopes');

function loadDemoMap(): Map<string, string> {
	try {
		const raw = readFileSync(resolve(DEMO_DIR, 'index.json'), 'utf8');
		const idx = JSON.parse(raw) as Record<string, string>;
		return new Map(Object.entries(idx));
	} catch {
		return new Map();
	}
}

const DEMO_MAP: Map<string, string> = loadDemoMap();

function tryServeDemo(sha: string | undefined): VsonEnvelope | null {
	if (!sha || !DEMO_MAP.has(sha)) return null;
	try {
		const file = DEMO_MAP.get(sha);
		if (!file) return null;
		const raw = readFileSync(resolve(DEMO_DIR, file), 'utf8');
		return JSON.parse(raw) as VsonEnvelope;
	} catch {
		return null;
	}
}

function extractPenman(text: string): string | null {
	// Be forgiving: some models wrap the doc in fences despite our instruction.
	const fenced = text.match(/```(?:\w+)?\s*\n([\s\S]*?)\n```/);
	const body = (fenced ? fenced[1] : text).trim();
	const start = body.indexOf('(');
	const end = body.lastIndexOf(')');
	if (start < 0 || end <= start) return null;
	return body.slice(start, end + 1).trim();
}

// Line-anchored extractor. Strips fences, finds the first `~` at column 0 of
// any line, returns the slice from there to end (including the trailing
// newline — line-significance matters for VSON-X).
function extractVsonX(text: string): string | null {
	const fenced = text.match(/```(?:\w+)?\s*\n([\s\S]*?)\n```/);
	const body = fenced ? fenced[1] : text;
	const m = body.match(/^[ \t]*~/m);
	if (!m || m.index === undefined) return null;
	const slice = body.slice(m.index).replace(/\s+$/, '');
	return slice ? slice + '\n' : null;
}

// Detect Penman drift in X mode: the model regressed to nested S-expressions.
function looksLikePenman(text: string): boolean {
	return /^\s*\(/.test(text);
}

function resolveVariant(bodyPrompt: string | undefined, urlPrompt: string | null): PromptVariant {
	const v = bodyPrompt ?? urlPrompt ?? 'skill';
	if (v === 'full') return 'full';
	if (v === 'skill-x') return 'skill-x';
	return 'skill';
}

export const POST: RequestHandler = async ({ request, url }) => {
	let body: ExtractBody;
	try {
		body = (await request.json()) as ExtractBody;
	} catch {
		throw error(400, 'invalid JSON body');
	}
	if (!body || typeof body.image_b64 !== 'string' || !body.mime) {
		throw error(400, 'expected { image_b64, mime }');
	}
	if (body.mime !== 'image/jpeg' && body.mime !== 'image/png') {
		throw error(400, 'mime must be image/jpeg or image/png');
	}
	const approxBytes = Math.floor((body.image_b64.length * 3) / 4);
	if (approxBytes > MAX_BYTES) throw error(400, 'image exceeds 5 MB cap');

	const sha256 = createHash('sha256').update(Buffer.from(body.image_b64, 'base64')).digest('hex');

	const variant: PromptVariant = resolveVariant(body.prompt, url.searchParams.get('prompt'));

	// Cached-demo short-circuit. Only fires when the requested variant matches
	// the variant the envelope was baked with — otherwise a `skill-x` request
	// on a `skill`-baked demo would silently serve the wrong notation. Compare
	// the version *name* (left of `@`): the `full` variant bakes as
	// `orchestrator-system@…`, not `full@…`, so a `${variant}@` prefix check
	// would never fire for the default variant and re-extract every time.
	const cached = tryServeDemo(body.sha256 ?? sha256);
	if (cached) {
		const bakedName = (cached.extraction?.prompt_version ?? '').split('@')[0];
		if (bakedName === promptVersionFor(variant).split('@')[0]) return json(cached);
	}
	if (variant === 'skill-x' && !isXSkillReady()) {
		throw error(503, 'VSON-X skill not yet shipped on this server');
	}
	const systemPrompt = systemPromptFor(variant);
	const promptVersion = promptVersionFor(variant);
	const userText = variant === 'skill-x' ? BARE_EXTRACT_USER_X : BARE_EXTRACT_USER;

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
				{
					role: 'user',
					content: [
						{
							type: 'image_url',
							image_url: { url: `data:${body.mime};base64,${body.image_b64}` }
						},
						{ type: 'text', text: userText }
					]
				}
			]
		});
		usage.input = initial.usage?.prompt_tokens ?? 0;
		usage.output = initial.usage?.completion_tokens ?? 0;
		raw = initial.choices[0]?.message?.content ?? '';
	} catch (e) {
		if (e instanceof OpenRouterError)
			throw error(e.status === 401 ? 502 : 502, `upstream: ${e.message}`);
		throw error(502, 'upstream error');
	}

	if (variant === 'skill-x') {
		return await runVsonXFlow({
			raw,
			model,
			systemPrompt,
			promptVersion,
			usage,
			t0,
			sha256,
			source_uri: body.source_uri
		});
	}

	return await runPenmanFlow({
		raw,
		model,
		systemPrompt,
		promptVersion,
		usage,
		t0,
		sha256,
		source_uri: body.source_uri
	});
};

// ──────────────────────────────────────────────────────────────────────────────
// Penman flow (unchanged behaviour from v1.0; only refactored).
// ──────────────────────────────────────────────────────────────────────────────

interface FlowCtx {
	raw: string;
	model: string | undefined;
	systemPrompt: string;
	promptVersion: string;
	usage: { input: number; output: number };
	t0: number;
	sha256: string;
	source_uri?: string;
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
		source: {
			kind: 'image',
			sha256: ctx.sha256,
			...(ctx.source_uri ? { uri: ctx.source_uri } : {})
		},
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

// ──────────────────────────────────────────────────────────────────────────────
// VSON-X flow. Drift state machine: if the model returns Penman, log it as a
// drift retry rather than silently switching notations. After two failed
// retries we ship an envelope with conforms=false so the UI can flag it.
// ──────────────────────────────────────────────────────────────────────────────

async function runVsonXFlow(ctx: FlowCtx) {
	let vsonXText = extractVsonX(ctx.raw);
	let drifted = vsonXText === null && looksLikePenman(ctx.raw);
	let driftCount = drifted ? 1 : 0;

	if (!vsonXText && !drifted) {
		throw error(422, 'model returned empty VSON-X');
	}

	// If the first call drifted, treat the empty X as the "failed doc" and
	// repair against the raw Penman text. The repair prompt re-anchors `~`.
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
		source: {
			kind: 'image',
			sha256: ctx.sha256,
			...(ctx.source_uri ? { uri: ctx.source_uri } : {})
		},
		// v1.1 X-mode sentinel: vson_p is empty until t2p ships in v1.2. The
		// schema's if/then rule allows this iff vson_x is non-empty.
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
