import { json, error } from '@sveltejs/kit';
import { createHash } from 'node:crypto';

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
	ORCHESTRATOR_SYSTEM_PROMPT,
	buildRepairPrompt
} from '$lib/server/prompt';
import { DEFAULT_MODEL, OpenRouterError, chat } from '$lib/server/openrouter';
import { shortId } from '$lib/utils';

const MAX_BYTES = 5 * 1024 * 1024;
const MAX_REPAIR_RETRIES = 2;

interface ExtractBody {
	image_b64: string;
	mime: 'image/jpeg' | 'image/png';
	source_uri?: string;
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

export const POST: RequestHandler = async ({ request }) => {
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
	// Approximate the decoded byte count from the base64 length.
	const approxBytes = Math.floor((body.image_b64.length * 3) / 4);
	if (approxBytes > MAX_BYTES) throw error(400, 'image exceeds 5 MB cap');

	const sha256 = createHash('sha256').update(Buffer.from(body.image_b64, 'base64')).digest('hex');

	const t0 = Date.now();
	let penmanText: string | null = null;
	let inputTokens = 0;
	let outputTokens = 0;

	try {
		const initial = await chat({
			messages: [
				{
					role: 'system',
					content: [
						{
							type: 'text',
							text: ORCHESTRATOR_SYSTEM_PROMPT,
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
				messages: [
					{
						role: 'system',
						content: [
							{
								type: 'text',
								text: ORCHESTRATOR_SYSTEM_PROMPT,
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
			model: DEFAULT_MODEL,
			prompt_version: 'orchestrator-system@1.0',
			shacl_retries: retries,
			latency_ms: Date.now() - t0,
			input_tokens: inputTokens,
			output_tokens: outputTokens
		}
	};

	return json(envelope);
};
