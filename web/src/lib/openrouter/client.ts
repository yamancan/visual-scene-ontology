// Direct browser client for OpenRouter — the zero-backend replacement for
// lib/server/openrouter.ts. The visitor's own key rides every request as
// `Authorization: Bearer`, built INTERNALLY from the byok store, so the key
// goes browser → openrouter.ai and never touches this site's host.
//
// Deliberately NOT ported from the server wrapper:
//   - server-key fallback (env.OPENROUTER_API_KEY) — there is no server key;
//   - byokKeyFrom relay-header parsing (x-openrouter-key) — there is no relay;
//   - the OPENROUTER_ALLOWED_MODELS allowlist and catalog id gate — they
//     defended the operator's paid key, and the operator key is gone. The
//     structural MODEL_ID_RE check survives as ADVISORY only.
//
// Nothing in this module runs at import time: chat() fires on demand and the
// model catalog is fetched lazily on the first models() call (first picker
// interaction — never onMount), then cached for the lifetime of the tab.

import { byok } from '../byok.svelte';

/** Default extraction model; was env.OPENROUTER_MODEL on the server. */
export const DEFAULT_MODEL = 'google/gemini-2.5-flash';

// Literal, build-time referer (retires PUBLIC_BASE_URL): OpenRouter uses it to
// attribute traffic to the app, nothing more.
const REFERER = 'https://vson-studio.pages.dev';

const CHAT_ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions';
const MODELS_ENDPOINT = 'https://openrouter.ai/api/v1/models';
const MODELS_TIMEOUT_MS = 5_000;

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

// ── error taxonomy ─────────────────────────────────────────────────────────
// The UI-facing contract: every chat() failure is one of these kinds, each
// with a short human-readable message the dropzone can show verbatim.

export type OpenRouterFailure =
	/** No key in the byok store — live extraction needs the visitor's key. */
	| 'no-key'
	/** 401 — OpenRouter rejected the key. */
	| 'key-not-accepted'
	/** 402 — the key's account has no credit left. */
	| 'out-of-credits'
	/** 429 — provider-side rate limit on the visitor's key. */
	| 'rate-limited'
	/** fetch itself failed: offline, DNS, CORS, firewall. */
	| 'network'
	/** any other non-2xx upstream response. */
	| 'upstream';

export class OpenRouterError extends Error {
	readonly kind: OpenRouterFailure;
	readonly status: number | null;
	readonly body?: string;

	constructor(
		kind: OpenRouterFailure,
		message: string,
		status: number | null = null,
		body?: string
	) {
		super(message);
		this.name = 'OpenRouterError';
		this.kind = kind;
		this.status = status;
		this.body = body;
	}
}

function failureFor(status: number): { kind: OpenRouterFailure; message: string } {
	switch (status) {
		case 401:
			return { kind: 'key-not-accepted', message: 'key not accepted' };
		case 402:
			return { kind: 'out-of-credits', message: 'out of credits' };
		case 429:
			return { kind: 'rate-limited', message: 'provider rate limit' };
		default:
			return { kind: 'upstream', message: `upstream error (${status})` };
	}
}

// ── chat ───────────────────────────────────────────────────────────────────

/**
 * One chat-completions round-trip on the visitor's own key. Throws
 * OpenRouterError with the taxonomy above; an AbortError from `signal`
 * propagates unchanged so callers can distinguish cancel from failure.
 */
export async function chat(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
	const key = byok.key;
	if (!key) {
		throw new OpenRouterError('no-key', 'no OpenRouter key — add yours in the model picker');
	}

	const body = JSON.stringify({
		model: req.model ?? DEFAULT_MODEL,
		messages: req.messages,
		max_tokens: req.max_tokens ?? 4096,
		temperature: req.temperature ?? 0.2
	});

	let res: Response;
	try {
		res = await fetch(CHAT_ENDPOINT, {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${key}`,
				'Content-Type': 'application/json',
				'HTTP-Referer': REFERER,
				'X-Title': 'vson'
			},
			body,
			signal
		});
	} catch (e) {
		if (e instanceof Error && e.name === 'AbortError') throw e;
		throw new OpenRouterError('network', 'network unreachable — could not reach openrouter.ai');
	}

	if (!res.ok) {
		const text = await res.text().catch(() => '');
		const { kind, message } = failureFor(res.status);
		throw new OpenRouterError(kind, message, res.status, text.slice(0, 400));
	}
	return (await res.json()) as ChatResponse;
}

// ── model catalog ──────────────────────────────────────────────────────────
// Live only — no snapshot ships, so there is no staleness to communicate.
// Fetched once per tab on the first models() call; a failed fetch resolves to
// null (the picker degrades exactly as before and extraction never blocks on
// the catalog) and is NOT cached, so the next interaction retries.

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

/** Vision-capable model as the picker consumes it. */
export interface PickerModel {
	id: string;
	name: string;
	provider: string;
	context_length: number;
	prompt_per_mtok: number; // USD per 1M input tokens
	completion_per_mtok: number; // USD per 1M output tokens
	supports_cache: boolean;
}

let picker: PickerModel[] | null = null;
let inflight: Promise<PickerModel[] | null> | null = null;

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

async function fetchPicker(): Promise<PickerModel[] | null> {
	try {
		const res = await fetch(MODELS_ENDPOINT, { signal: AbortSignal.timeout(MODELS_TIMEOUT_MS) });
		if (!res.ok) return null;
		const body = (await res.json()) as { data?: OrModel[] };
		const rows = (body.data ?? []).filter((m) => typeof m?.id === 'string' && m.id);
		if (!rows.length) return null;
		picker = rows
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
			});
		return picker;
	} catch {
		return null;
	}
}

/**
 * Vision-only picker rows, straight from openrouter.ai. Null when the catalog
 * is unreachable — callers already tolerate that (the picker shows its empty
 * state and the default model still extracts).
 */
export async function models(): Promise<PickerModel[] | null> {
	if (picker) return picker;
	// Single-flight: concurrent first interactions share one upstream fetch.
	inflight ??= fetchPicker().finally(() => {
		inflight = null;
	});
	return inflight;
}

// ── advisory model-id check ────────────────────────────────────────────────
// The catalog gate died with the operator key (a bad id now only wastes the
// visitor's own request, and OpenRouter answers with its own 400). This cheap
// structural check survives for UI hints only. OpenRouter ids look like
// `vendor/model[:variant]`.

export const MODEL_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]*\/[A-Za-z0-9][A-Za-z0-9._:-]*$/;
const MAX_MODEL_ID_CHARS = 128;

/** Advisory: does this look like an OpenRouter model id? Never blocks a call. */
export function isPlausibleModelId(id: string): boolean {
	const trimmed = id.trim();
	return trimmed.length > 0 && trimmed.length <= MAX_MODEL_ID_CHARS && MODEL_ID_RE.test(trimmed);
}
