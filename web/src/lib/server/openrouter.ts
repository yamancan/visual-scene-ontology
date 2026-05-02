// Native fetch wrapper around the OpenRouter chat-completions endpoint.
// We use OpenRouter (not Anthropic direct) so the same code path works for
// claude-opus, claude-sonnet, gpt-5o, gemini, etc. by changing the model id.
//
// OpenRouter speaks OpenAI-format. For Anthropic models it forwards the
// `cache_control` hints on individual content blocks (only when routed via
// Anthropic).

import { env } from '$env/dynamic/private';

export const DEFAULT_MODEL = env.OPENROUTER_MODEL || 'anthropic/claude-opus-4.6';

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
	const apiKey = env.OPENROUTER_API_KEY;
	if (!apiKey) throw new OpenRouterError('OPENROUTER_API_KEY not set', 500);

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
