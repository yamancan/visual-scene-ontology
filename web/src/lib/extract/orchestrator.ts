// Browser-side extraction and correction orchestration — the client home of
// the flow the adapter-node routes ran: sha256 demo short-circuit, then
// chat → worker p2t/x2t → two-gate validate → repair loop (bounded by
// limits.ts), then v1.2-byte-compatible envelope assembly (envelope.ts).
//
// Dependencies (the OpenRouter chat client, the Pyodide worker ops, fetch)
// are injected so unit tests run with mocks and zero network; the default
// wiring dynamic-imports the real modules on first use, preserving the core
// payload invariant — importing this module costs neither the prompt-bodies
// chunk nor a single Pyodide byte.
//
// Nothing here parses env or headers: the key lives in the byok store (read
// internally by the chat client) and every bound is a named constant.

import type { ChatMessage, ChatRequest, ChatResponse } from '../openrouter/client';
import type { GateResult, ValidateResult } from '../validate/pyodide-ops';
import type { ConformanceReport, VsonEnvelope } from '../types';
import {
	BARE_EXTRACT_USER,
	BARE_EXTRACT_USER_X,
	buildCorrectionPrompt,
	buildCorrectionXPrompt,
	isXSkillReady,
	promptVersionFor,
	type CorrectionItem,
	type PromptVariant
} from '../prompts/meta';
import { parseViolationReport } from '../validate/report';
import { buildPenmanEnvelope, buildXEnvelope, type EnvelopeSource } from './envelope';
import {
	MAX_CORRECTION_CHARS,
	MAX_CORRECTIONS,
	MAX_REPAIR_RETRIES,
	MAX_SOURCE_CHARS
} from './limits';

// ── errors ─────────────────────────────────────────────────────────────────

export type OrchestratorErrorKind =
	/** A request-shape or cap violation — nothing was sent anywhere. */
	| 'input'
	/** The model's reply contained no extractable document. */
	| 'empty-output'
	/** VSON-X was requested but the X skill was absent at build time. */
	| 'x-unavailable';

export class OrchestratorError extends Error {
	readonly kind: OrchestratorErrorKind;
	constructor(kind: OrchestratorErrorKind, message: string) {
		super(message);
		this.name = 'OrchestratorError';
		this.kind = kind;
	}
}

// ── dependencies ───────────────────────────────────────────────────────────

/** The worker surface the flows need — matches ValidationClient's methods. */
export interface TranspileValidateOps {
	p2t(vsonP: string): Promise<string>;
	x2t(vsonX: string): Promise<string>;
	validate(turtle: string, onGate1?: (gate1: GateResult) => void): Promise<ValidateResult>;
}

export interface OrchestratorDeps {
	chat(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse>;
	ops: TranspileValidateOps;
	fetchFn: typeof fetch;
	/**
	 * Fire-and-forget Pyodide prefetch. Called the moment a live model call is
	 * certain, so the ~16 MB runtime download overlaps the model's latency
	 * instead of serializing after it. Failures stay silent here — the designed
	 * validation-unavailable state surfaces at validate time.
	 */
	warmup?(): void;
}

/** Real wiring, loaded lazily: OpenRouter client + the Pyodide worker singleton. */
async function defaultDeps(): Promise<OrchestratorDeps> {
	const [{ chat }, { validationClient }] = await Promise.all([
		import('../openrouter/client'),
		import('../validate/client')
	]);
	const worker = validationClient();
	return {
		chat,
		ops: {
			p2t: (vsonP) => worker.p2t(vsonP),
			x2t: (vsonX) => worker.x2t(vsonX),
			validate: (turtle, onGate1) => worker.validate(turtle, onGate1)
		},
		fetchFn: (input, init) => fetch(input, init),
		warmup: () => {
			worker.warmup().catch(() => {});
		}
	};
}

// ── sha256 demo short-circuit ──────────────────────────────────────────────
// The keyless $0 path: a byte-exact re-upload of a bundled demo image hashes
// to a key in /demos/envelopes/index.json and renders the baked envelope
// instantly — no model call, no key, no Pyodide.

const DEMO_INDEX_URL = '/demos/envelopes/index.json';

export function base64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
	const bin = atob(b64);
	const bytes = new Uint8Array(bin.length);
	for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
	return bytes;
}

export async function sha256Hex(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
	const digest = await crypto.subtle.digest('SHA-256', bytes);
	return Array.from(new Uint8Array(digest))
		.map((b) => b.toString(16).padStart(2, '0'))
		.join('');
}

/**
 * Baked envelope for a sha256, or null. Only fires when the requested variant
 * matches the variant the envelope was baked with — otherwise a `skill-x`
 * request on a `skill`-baked demo would silently serve the wrong notation.
 * Compare the version *name* (left of `@`): the `full` variant bakes as
 * `orchestrator-system@…`, not `full@…`, so a `${variant}@` prefix check
 * would never fire for the default variant and re-extract every time.
 * Any fetch/parse failure degrades to the live path, never to an error.
 */
export async function demoEnvelopeForSha(
	sha256: string,
	variant: PromptVariant,
	fetchFn: typeof fetch
): Promise<VsonEnvelope | null> {
	try {
		const indexRes = await fetchFn(DEMO_INDEX_URL);
		if (!indexRes.ok) return null;
		const index = (await indexRes.json()) as Record<string, string>;
		const file = index[sha256];
		if (!file) return null;
		const envelopeRes = await fetchFn(`/demos/envelopes/${file}`);
		if (!envelopeRes.ok) return null;
		const cached = (await envelopeRes.json()) as VsonEnvelope;
		const bakedName = (cached.extraction?.prompt_version ?? '').split('@')[0];
		return bakedName === promptVersionFor(variant).split('@')[0] ? cached : null;
	} catch {
		return null;
	}
}

// ── tolerant document extractors (shared by extract and correct) ───────────

export function extractPenman(text: string): string | null {
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
export function extractVsonX(text: string): string | null {
	const fenced = text.match(/```(?:\w+)?\s*\n([\s\S]*?)\n```/);
	const body = fenced ? fenced[1] : text;
	const m = body.match(/^[ \t]*~/m);
	if (!m || m.index === undefined) return null;
	const slice = body.slice(m.index).replace(/\s+$/, '');
	return slice ? slice + '\n' : null;
}

// Detect Penman drift in X mode: the model regressed to nested S-expressions.
export function looksLikePenman(text: string): boolean {
	return /^\s*\(/.test(text);
}

// ── chat plumbing ──────────────────────────────────────────────────────────

function systemMessage(systemPrompt: string): ChatMessage {
	return {
		role: 'system',
		content: [{ type: 'text', text: systemPrompt, cache_control: { type: 'ephemeral' } }]
	};
}

type Transpile = { ok: true; turtle: string } | { ok: false; error: string };

async function tryTranspile(run: () => Promise<string>): Promise<Transpile> {
	try {
		return { ok: true, turtle: await run() };
	} catch (e) {
		return { ok: false, error: e instanceof Error ? e.message : String(e) };
	}
}

function conformanceOf(transpileOk: boolean, verdict: ValidateResult | null): ConformanceReport {
	const conforms = !!(transpileOk && verdict?.conforms);
	const violations = verdict ? parseViolationReport(verdict.report) : [];
	return { conforms, ...(violations.length ? { violations } : {}) };
}

// ── shared flow context ────────────────────────────────────────────────────

interface FlowCtx {
	raw: string;
	model: string | undefined;
	systemPrompt: string;
	promptVersion: string;
	usage: { input: number; output: number };
	t0: number;
	source: EnvelopeSource;
	onGate1?: (gate1: GateResult) => void;
}

// ── Penman flow (behaviour ported verbatim from the extract route) ─────────

async function runPenmanFlow(
	ctx: FlowCtx,
	deps: OrchestratorDeps,
	buildRepair: (failedDoc: string, reason: string) => string
): Promise<VsonEnvelope> {
	let penmanText = extractPenman(ctx.raw);
	if (!penmanText) throw new OrchestratorError('empty-output', 'model returned empty Penman');

	let transpile = await tryTranspile(() => deps.ops.p2t(penmanText!));
	let verdict = transpile.ok ? await deps.ops.validate(transpile.turtle, ctx.onGate1) : null;
	let retries = 0;

	while ((!transpile.ok || !verdict!.conforms) && retries < MAX_REPAIR_RETRIES) {
		retries++;
		const reason = !transpile.ok
			? `Penman parse error: ${(transpile as { ok: false; error: string }).error}`
			: `SHACL violations:\n${verdict!.report}`;
		try {
			const repair = await deps.chat({
				model: ctx.model,
				messages: [
					systemMessage(ctx.systemPrompt),
					{ role: 'user', content: [{ type: 'text', text: buildRepair(penmanText, reason) }] }
				]
			});
			ctx.usage.input += repair.usage?.prompt_tokens ?? 0;
			ctx.usage.output += repair.usage?.completion_tokens ?? 0;
			penmanText = extractPenman(repair.choices[0]?.message?.content ?? '') ?? penmanText;
		} catch {
			break;
		}
		transpile = await tryTranspile(() => deps.ops.p2t(penmanText!));
		verdict = transpile.ok ? await deps.ops.validate(transpile.turtle, ctx.onGate1) : null;
	}

	return buildPenmanEnvelope({
		penman: penmanText,
		turtle: transpile.ok ? transpile.turtle : '',
		conformance: conformanceOf(transpile.ok, verdict),
		source: ctx.source,
		stats: {
			model: ctx.model,
			promptVersion: ctx.promptVersion,
			shaclRetries: retries,
			latencyMs: Date.now() - ctx.t0,
			inputTokens: ctx.usage.input,
			outputTokens: ctx.usage.output
		}
	});
}

// ── VSON-X flow ────────────────────────────────────────────────────────────
// Drift state machine: if the model returns Penman, log it as a drift retry
// rather than silently switching notations. After two failed retries we ship
// an envelope with conforms=false (and a drift-downgraded confidence) so the
// UI can flag it.

async function runVsonXFlow(
	ctx: FlowCtx,
	deps: OrchestratorDeps,
	buildRepair: (failedDoc: string, reason: string) => string
): Promise<VsonEnvelope> {
	let vsonXText = extractVsonX(ctx.raw);
	let drifted = vsonXText === null && looksLikePenman(ctx.raw);
	let driftCount = drifted ? 1 : 0;

	if (!vsonXText && !drifted) {
		throw new OrchestratorError('empty-output', 'model returned empty VSON-X');
	}

	// If the first call drifted, treat the empty X as the "failed doc" and
	// repair against the raw Penman text. The repair prompt re-anchors `~`.
	let workingDoc = vsonXText ?? ctx.raw.trim();
	let transpile: Transpile = vsonXText
		? await tryTranspile(() => deps.ops.x2t(vsonXText!))
		: { ok: false, error: 'model emitted Penman, not VSON-X' };
	let verdict = transpile.ok ? await deps.ops.validate(transpile.turtle, ctx.onGate1) : null;
	let retries = 0;

	while ((!transpile.ok || !verdict!.conforms) && retries < MAX_REPAIR_RETRIES) {
		retries++;
		const reason = !transpile.ok
			? `VSON-X parse error: ${(transpile as { ok: false; error: string }).error}${drifted ? ' (DRIFT: model emitted Penman; first character must be ~)' : ''}`
			: `SHACL violations:\n${verdict!.report}`;
		try {
			const repair = await deps.chat({
				model: ctx.model,
				messages: [
					systemMessage(ctx.systemPrompt),
					{ role: 'user', content: [{ type: 'text', text: buildRepair(workingDoc, reason) }] }
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
			? await tryTranspile(() => deps.ops.x2t(vsonXText!))
			: { ok: false, error: 'still no VSON-X after repair (drift)' };
		verdict = transpile.ok ? await deps.ops.validate(transpile.turtle, ctx.onGate1) : null;
	}

	return buildXEnvelope({
		vsonX: vsonXText ?? '',
		turtle: transpile.ok ? transpile.turtle : '',
		conformance: conformanceOf(transpile.ok, verdict),
		source: ctx.source,
		stats: {
			model: ctx.model,
			promptVersion: ctx.promptVersion,
			shaclRetries: retries,
			latencyMs: Date.now() - ctx.t0,
			inputTokens: ctx.usage.input,
			outputTokens: ctx.usage.output,
			driftCount
		}
	});
}

// ── extraction ─────────────────────────────────────────────────────────────

export interface ExtractRequest {
	image_b64: string;
	mime: 'image/jpeg' | 'image/png';
	source_uri?: string;
	model?: string;
	variant?: PromptVariant;
	/** Progressive verdict hook: fires with each round's Gate 1 SHACL result. */
	onGate1?: (gate1: GateResult) => void;
}

/**
 * Image → VsonEnvelope, entirely in the browser. A byte-exact demo upload
 * short-circuits to the baked envelope ($0, keyless); anything else runs the
 * live chat → transpile → validate → repair pipeline on the visitor's key.
 */
export async function extractScene(
	req: ExtractRequest,
	deps?: OrchestratorDeps
): Promise<VsonEnvelope> {
	if (req.mime !== 'image/jpeg' && req.mime !== 'image/png') {
		throw new OrchestratorError('input', 'mime must be image/jpeg or image/png');
	}
	const d = deps ?? (await defaultDeps());
	const variant: PromptVariant = req.variant ?? 'skill';

	const sha256 = await sha256Hex(base64ToBytes(req.image_b64));
	const cached = await demoEnvelopeForSha(sha256, variant, d.fetchFn);
	if (cached) return cached;

	if (variant === 'skill-x' && !isXSkillReady()) {
		throw new OrchestratorError('x-unavailable', 'VSON-X skill not shipped in this build');
	}

	// A live model call is now certain: pull the prompt bodies (lazily-imported
	// chunk) and start the Pyodide download under the model's latency.
	d.warmup?.();
	const bodies = await import('../prompts/bodies');
	const systemPrompt = bodies.systemPromptFor(variant);
	const userText = variant === 'skill-x' ? BARE_EXTRACT_USER_X : BARE_EXTRACT_USER;

	const t0 = Date.now();
	const usage = { input: 0, output: 0 };
	const initial = await d.chat({
		model: req.model,
		messages: [
			systemMessage(systemPrompt),
			{
				role: 'user',
				content: [
					{ type: 'image_url', image_url: { url: `data:${req.mime};base64,${req.image_b64}` } },
					{ type: 'text', text: userText }
				]
			}
		]
	});
	usage.input = initial.usage?.prompt_tokens ?? 0;
	usage.output = initial.usage?.completion_tokens ?? 0;

	const ctx: FlowCtx = {
		raw: initial.choices[0]?.message?.content ?? '',
		model: req.model,
		systemPrompt,
		promptVersion: promptVersionFor(variant),
		usage,
		t0,
		source: { sha256, ...(req.source_uri ? { uri: req.source_uri } : {}) },
		onGate1: req.onGate1
	};

	return variant === 'skill-x'
		? runVsonXFlow(ctx, d, bodies.buildRepairXPrompt)
		: runPenmanFlow(ctx, d, bodies.buildRepairPrompt);
}

// ── correction ─────────────────────────────────────────────────────────────

export interface CorrectRequest {
	notation: 'p' | 'x';
	source: string;
	corrections: CorrectionItem[];
	sceneNote?: string;
	/** Optional — gallery scenes may lack the original image. */
	image_b64?: string;
	mime?: 'image/jpeg' | 'image/png';
	model?: string;
	onGate1?: (gate1: GateResult) => void;
}

function assertCorrectionCaps(req: CorrectRequest): void {
	if (typeof req.source !== 'string' || !req.source.trim()) {
		throw new OrchestratorError('input', 'expected a non-empty source document');
	}
	if (req.source.length > MAX_SOURCE_CHARS) {
		throw new OrchestratorError('input', 'source exceeds 64 KB cap');
	}
	if (!Array.isArray(req.corrections)) {
		throw new OrchestratorError('input', 'corrections must be an array');
	}
	if (req.corrections.length > MAX_CORRECTIONS) {
		throw new OrchestratorError('input', `too many corrections (max ${MAX_CORRECTIONS})`);
	}
	for (const item of req.corrections) {
		if (JSON.stringify(item ?? null).length > MAX_CORRECTION_CHARS) {
			throw new OrchestratorError('input', 'correction item exceeds 2 KB cap');
		}
	}
	if (typeof req.sceneNote === 'string' && req.sceneNote.length > MAX_CORRECTION_CHARS) {
		throw new OrchestratorError('input', 'sceneNote exceeds 2 KB cap');
	}
	if (req.notation !== 'p' && req.notation !== 'x') {
		throw new OrchestratorError('input', "notation must be 'p' or 'x'");
	}
}

/**
 * Targeted human corrections → new envelope: one correction-prompt chat call,
 * then the same transpile → validate → repair loop as extraction.
 */
export async function correctScene(
	req: CorrectRequest,
	deps?: OrchestratorDeps
): Promise<VsonEnvelope> {
	assertCorrectionCaps(req);
	if (req.image_b64 && req.mime !== 'image/jpeg' && req.mime !== 'image/png') {
		throw new OrchestratorError('input', 'mime must be image/jpeg or image/png');
	}
	const d = deps ?? (await defaultDeps());

	const variant: PromptVariant = req.notation === 'x' ? 'skill-x' : 'skill';
	if (variant === 'skill-x' && !isXSkillReady()) {
		throw new OrchestratorError('x-unavailable', 'VSON-X skill not shipped in this build');
	}

	// Same overlap as extraction — though in practice the worker is usually
	// already warm here, since a correction follows a validated extraction.
	d.warmup?.();
	const bodies = await import('../prompts/bodies');
	const systemPrompt = bodies.systemPromptFor(variant);
	const userText =
		req.notation === 'x'
			? buildCorrectionXPrompt(req.source, req.corrections, req.sceneNote)
			: buildCorrectionPrompt(req.source, req.corrections, req.sceneNote);

	const sha256 = req.image_b64 ? await sha256Hex(base64ToBytes(req.image_b64)) : undefined;

	const t0 = Date.now();
	const usage = { input: 0, output: 0 };
	const initial = await d.chat({
		model: req.model,
		messages: [
			systemMessage(systemPrompt),
			{
				role: 'user',
				content: [
					...(req.image_b64
						? [
								{
									type: 'image_url' as const,
									image_url: { url: `data:${req.mime};base64,${req.image_b64}` }
								}
							]
						: []),
					{ type: 'text' as const, text: userText }
				]
			}
		]
	});
	usage.input = initial.usage?.prompt_tokens ?? 0;
	usage.output = initial.usage?.completion_tokens ?? 0;

	const ctx: FlowCtx = {
		raw: initial.choices[0]?.message?.content ?? '',
		model: req.model,
		systemPrompt,
		promptVersion: promptVersionFor(variant),
		usage,
		t0,
		source: sha256 ? { sha256 } : {},
		onGate1: req.onGate1
	};

	return req.notation === 'x'
		? runVsonXFlow(ctx, d, bodies.buildRepairXPrompt)
		: runPenmanFlow(ctx, d, bodies.buildRepairPrompt);
}
