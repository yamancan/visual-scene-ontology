// Native fetch wrapper around the OpenRouter chat-completions endpoint.
// We use OpenRouter (not Anthropic direct) so the same code path works for
// claude-opus, claude-sonnet, gpt-5o, gemini, etc. by changing the model id.
//
// OpenRouter speaks OpenAI-format. For Anthropic models it forwards the
// `cache_control` hints on individual content blocks (only when routed via
// Anthropic).

import { env } from '$env/dynamic/private';

export const DEFAULT_MODEL = env.OPENROUTER_MODEL || 'google/gemini-2.5-flash';

export interface ChatTextBlock {
	type: 'text';
	text: string;
	cache_control?: { type: 'ephemeral'; ttl?: '5m' | '1h' };
}

export interface ChatImageBlock {
	type: 'image_url';
	image_url: { url: string; detail?: 'auto' | 'low' | 'high' };
}

export type ChatContent = ChatTextBlock | ChatImageBlock;

export interface ChatMessage {
	role: 'system' | 'user' | 'assistant';
	content: string | ChatContent[];
}

export interface ChatRequest {
	model?: string;
	messages: ChatMessage[];
	max_tokens?: number;
	temperature?: number;
	/** BYOK: caller-supplied key used for this request only, never stored. */
	apiKey?: string;
}

// BYOK header contract: printable ASCII, sane length. The value is read per
// request, passed down the call stack, and dropped — never logged, never
// persisted, never echoed back in a response.
const BYOK_HEADER = 'x-openrouter-key';
const BYOK_RE = /^[\x21-\x7e]{8,240}$/;

/**
 * Read the visitor's own OpenRouter key from the request headers.
 * `undefined` = header absent (use the server key); `null` = header present
 * but malformed (callers should 400 rather than silently bill the server key).
 */
export function byokKeyFrom(headers: Headers): string | undefined | null {
	const raw = headers.get(BYOK_HEADER);
	if (raw === null) return undefined;
	const key = raw.trim();
	return BYOK_RE.test(key) ? key : null;
}

export interface ChatResponse {
	id: string;
	model: string;
	choices: Array<{
		index: number;
		message: { role: 'assistant'; content: string };
		finish_reason: string;
	}>;
	usage?: {
		prompt_tokens: number;
		completion_tokens: number;
		total_tokens: number;
		cache_creation_input_tokens?: number;
		cache_read_input_tokens?: number;
	};
}

export class OpenRouterError extends Error {
	constructor(
		msg: string,
		public status: number,
		public body?: unknown
	) {
		super(msg);
	}
}

const ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions';

export async function chat(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
	const apiKey = req.apiKey ?? env.OPENROUTER_API_KEY;
	if (!apiKey) {
		throw new OpenRouterError('no API key: set OPENROUTER_API_KEY or supply your own', 500);
	}

	const body = JSON.stringify({
		model: req.model ?? DEFAULT_MODEL,
		messages: req.messages,
		max_tokens: req.max_tokens ?? 4096,
		temperature: req.temperature ?? 0.2
	});

	const res = await fetch(ENDPOINT, {
		method: 'POST',
		headers: {
			Authorization: `Bearer ${apiKey}`,
			'Content-Type': 'application/json',
			'HTTP-Referer': env.PUBLIC_BASE_URL || 'http://localhost:5173',
			'X-Title': 'vson'
		},
		body,
		signal
	});

	if (!res.ok) {
		const text = await res.text().catch(() => '');
		throw new OpenRouterError(`upstream ${res.status}: ${text.slice(0, 400)}`, res.status, text);
	}
	return (await res.json()) as ChatResponse;
}

// ──────────────────────────────────────────────────────────────────────────────
// Model catalog
//
// One process-wide cache of OpenRouter's model list, shared by three callers:
//   the models route  — shapes it into the picker rows
//   the extract route — validates the requested model id before relaying
//   the correct route — same
//
// Without the id check, `{"model": "anything/at-all"}` is forwarded verbatim to
// a paid upstream on our key. The catalog turns "any string with a slash" into
// "an id OpenRouter actually serves".
// ──────────────────────────────────────────────────────────────────────────────

/** Raw row from `GET https://openrouter.ai/api/v1/models`. */
interface OrModel {
	id: string;
	name: string;
	canonical_slug?: string;
	context_length?: number;
	architecture?: { input_modalities?: string[]; output_modalities?: string[] };
	pricing?: { prompt?: string; completion?: string; input_cache_read?: string };
	supported_parameters?: string[];
	top_provider?: { is_moderated?: boolean };
}

/** Vision-capable model as the client-side picker consumes it. */
export interface PickerModel {
	id: string;
	name: string;
	provider: string;
	context_length: number;
	prompt_per_mtok: number; // USD per 1M input tokens
	completion_per_mtok: number; // USD per 1M output tokens
	supports_cache: boolean;
}

export interface ModelCatalog {
	at: number;
	/** Every id OpenRouter serves — the allowlist the relay validates against. */
	ids: Set<string>;
	/** Image-input models only, sorted for the picker. */
	picker: PickerModel[];
}

const MODELS_ENDPOINT = 'https://openrouter.ai/api/v1/models';
const MODELS_TTL_MS = 10 * 60 * 1000; // 10 min — the model list rarely changes
const MODELS_RETRY_MS = 30 * 1000; // negative cache: don't hammer a failing upstream
const MODELS_TIMEOUT_MS = 5_000;

let catalog: ModelCatalog | null = null;
let inflight: Promise<ModelCatalog | null> | null = null;
let failedAt = 0;

function shapePickerModel(m: OrModel): PickerModel | null {
	const mods = m.architecture?.input_modalities ?? [];
	if (!mods.includes('image')) return null;
	const provider = (m.id.split('/')[0] ?? '').replace(/-/g, ' ');
	const promptUsd = parseFloat(m.pricing?.prompt ?? '0') * 1e6;
	const completionUsd = parseFloat(m.pricing?.completion ?? '0') * 1e6;
	return {
		id: m.id,
		name: m.name.replace(/^[^:]+:\s*/, ''), // drop provider prefix; we surface it separately
		provider,
		context_length: m.context_length ?? 0,
		prompt_per_mtok: Math.round(promptUsd * 100) / 100,
		completion_per_mtok: Math.round(completionUsd * 100) / 100,
		supports_cache: !!(m.pricing?.input_cache_read && parseFloat(m.pricing.input_cache_read) > 0)
	};
}

async function fetchCatalog(): Promise<ModelCatalog | null> {
	try {
		const res = await fetch(MODELS_ENDPOINT, { signal: AbortSignal.timeout(MODELS_TIMEOUT_MS) });
		if (!res.ok) throw new OpenRouterError(`openrouter /models → ${res.status}`, res.status);
		const body = (await res.json()) as { data?: OrModel[] };
		const rows = (body.data ?? []).filter((m) => typeof m?.id === 'string' && m.id);
		if (!rows.length) throw new OpenRouterError('openrouter /models returned no rows', 502);
		catalog = {
			at: Date.now(),
			ids: new Set(rows.map((m) => m.id)),
			picker: rows
				.map(shapePickerModel)
				.filter((m): m is PickerModel => m !== null)
				.sort((a, b) => {
					// Anthropic + OpenAI + Google to the top, then alphabetical.
					const rank = (p: string) =>
						p.startsWith('anthropic')
							? 0
							: p.startsWith('openai')
								? 1
								: p.startsWith('google')
									? 2
									: 3;
					const dr = rank(a.id) - rank(b.id);
					return dr !== 0 ? dr : a.id.localeCompare(b.id);
				})
		};
		failedAt = 0;
		return catalog;
	} catch {
		// Keep serving the stale catalog if we have one; otherwise report
		// "unavailable" and let callers decide (picker 502s, relay degrades).
		failedAt = Date.now();
		return catalog;
	}
}

/**
 * Cached model catalog. Never throws — returns `null` only when we have never
 * successfully fetched the list and the last attempt failed recently.
 */
export async function getModelCatalog(): Promise<ModelCatalog | null> {
	const now = Date.now();
	if (catalog && now - catalog.at < MODELS_TTL_MS) return catalog;
	if (now - failedAt < MODELS_RETRY_MS) return catalog;
	// Single-flight: concurrent misses share one upstream fetch.
	inflight ??= fetchCatalog().finally(() => {
		inflight = null;
	});
	return inflight;
}

/** Optional operator narrowing: `OPENROUTER_ALLOWED_MODELS=a/b,c/d`. */
function envAllowlist(): Set<string> | null {
	const raw = env.OPENROUTER_ALLOWED_MODELS?.trim();
	if (!raw) return null;
	const ids = raw
		.split(',')
		.map((s) => s.trim())
		.filter(Boolean);
	return ids.length ? new Set(ids) : null;
}

/** Picker rows, narrowed by OPENROUTER_ALLOWED_MODELS when the operator set it. */
export async function listPickerModels(): Promise<PickerModel[] | null> {
	const cat = await getModelCatalog();
	if (!cat) return null;
	const allowed = envAllowlist();
	return allowed ? cat.picker.filter((m) => allowed.has(m.id)) : cat.picker;
}

export type ModelCheck = { ok: true; model?: string } | { ok: false; reason: string };

// Cheap structural gate, used both as a pre-filter and as the fallback when the
// catalog is unavailable. OpenRouter ids look like `vendor/model[:variant]`.
const MODEL_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]*\/[A-Za-z0-9][A-Za-z0-9._:-]*$/;
const MAX_MODEL_ID_CHARS = 128;

/**
 * Validate a client-supplied model id against the catalog (and the optional env
 * allowlist). Returns `{ ok: true }` with no model when the caller sent nothing,
 * meaning "use DEFAULT_MODEL". Callers translate `{ ok: false }` into a 400.
 */
export async function resolveRequestedModel(requested: unknown): Promise<ModelCheck> {
	if (requested === undefined || requested === null) return { ok: true };
	if (typeof requested !== 'string') return { ok: false, reason: 'model must be a string' };
	const id = requested.trim();
	if (!id) return { ok: true };
	if (id.length > MAX_MODEL_ID_CHARS || !MODEL_ID_RE.test(id)) {
		return { ok: false, reason: `unknown model: ${id.slice(0, 64)}` };
	}
	const allowed = envAllowlist();
	if (allowed && !allowed.has(id)) {
		return { ok: false, reason: `model not enabled on this server: ${id.slice(0, 64)}` };
	}
	const cat = await getModelCatalog();
	// Catalog unavailable → fall back to the shape check so an OpenRouter blip
	// doesn't lock out legitimate users. Rate limiting still applies.
	if (!cat) return { ok: true, model: id };
	if (!cat.ids.has(id)) return { ok: false, reason: `unknown model: ${id.slice(0, 64)}` };
	return { ok: true, model: id };
}
