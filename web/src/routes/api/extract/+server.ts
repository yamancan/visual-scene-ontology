import { json, error } from '@sveltejs/kit';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import type { RequestHandler } from './$types';
import type { VsonEnvelope } from '$lib/types';
import { walkPenmanToGraph } from '$lib/server/graph-walk';
import {
	parseViolationReport,
	transpilePenmanToTurtle,
	validateTurtle
} from '$lib/server/cli';
import {
	BARE_EXTRACT_USER,
	buildRepairPrompt,
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
	prompt?: 'skill' | 'full';
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

	// Cached-demo short-circuit. Trust either an explicit sha256 hint OR the
	// hash we just computed; either way we re-verify against the whitelist.
	const cached = tryServeDemo(body.sha256 ?? sha256);
	if (cached) return json(cached);

	const variant: PromptVariant =
		body.prompt === 'full' || url.searchParams.get('prompt') === 'full' ? 'full' : 'skill';
	const systemPrompt = systemPromptFor(variant);
	const promptVersion = promptVersionFor(variant);

	const t0 = Date.now();
	let penmanText: string | null = null;
	let inputTokens = 0;
	let outputTokens = 0;

	const model = body.model && body.model.includes('/') ? body.model : undefined;
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
						{ type: 'text', text: BARE_EXTRACT_USER }
					]
				}
			]
		});
		inputTokens = initial.usage?.prompt_tokens ?? 0;
		outputTokens = initial.usage?.completion_tokens ?? 0;
		penmanText = extractPenman(initial.choices[0]?.message?.content ?? '');
	} catch (e) {
		if (e instanceof OpenRouterError)
			throw error(e.status === 401 ? 502 : 502, `upstream: ${e.message}`);
		throw error(502, 'upstream error');
	}

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
						content: [{ type: 'text', text: buildRepairPrompt(penmanText, reason) }]
					}
				]
			});
			inputTokens += repair.usage?.prompt_tokens ?? 0;
			outputTokens += repair.usage?.completion_tokens ?? 0;
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
			sha256,
			...(body.source_uri ? { uri: body.source_uri } : {})
		},
		vson_p: penmanText,
		vson_t: turtle,
		graph: walkPenmanToGraph(penmanText),
		conformance: { conforms, ...(violations.length ? { violations } : {}) },
		extraction: {
			model: model ?? DEFAULT_MODEL,
			prompt_version: promptVersion,
			shacl_retries: retries,
			latency_ms: Date.now() - t0,
			input_tokens: inputTokens,
			output_tokens: outputTokens
		}
	};

	return json(envelope);
};
