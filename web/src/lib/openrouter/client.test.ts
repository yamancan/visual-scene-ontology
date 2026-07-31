// Contract tests for the direct BYOK OpenRouter client.
//
// Everything here runs against a mocked global fetch — no network. The three
// load-bearing contracts:
//   1. chat() builds Authorization internally from the byok store and sends
//      the literal vson-studio referer — no relay header, no server key;
//   2. failures map onto the fixed taxonomy the dropzone renders verbatim
//      (401 key / 402 credits / 429 rate limit / network);
//   3. models() is lazy (nothing at import time), cached per tab after one
//      success, and a failure resolves null WITHOUT being cached.
//
// Module state (byok key, catalog cache) is reset per test via a fresh module
// registry, so tests cannot leak into each other.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

type ClientModule = typeof import('./client');
type ByokModule = typeof import('../byok.svelte');

let client: ClientModule;
let byok: ByokModule['byok'];
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(async () => {
	fetchMock = vi.fn();
	vi.stubGlobal('fetch', fetchMock);
	vi.resetModules();
	client = await import('./client');
	({ byok } = await import('../byok.svelte'));
});

afterEach(() => {
	vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});
}

function chatOk(content = 'ok'): unknown {
	return {
		id: 'gen-1',
		model: 'google/gemini-2.5-flash',
		choices: [{ index: 0, message: { role: 'assistant', content }, finish_reason: 'stop' }],
		usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 }
	};
}

async function caught(p: Promise<unknown>): Promise<InstanceType<ClientModule['OpenRouterError']>> {
	try {
		await p;
	} catch (e) {
		return e as InstanceType<ClientModule['OpenRouterError']>;
	}
	throw new Error('expected the promise to reject');
}

describe('chat() — auth header shape', () => {
	it('builds Authorization: Bearer from the byok store and sends the literal referer', async () => {
		byok.set('sk-or-v1-test-key');
		fetchMock.mockResolvedValueOnce(jsonResponse(chatOk()));

		await client.chat({ messages: [{ role: 'user', content: 'hi' }] });

		expect(fetchMock).toHaveBeenCalledTimes(1);
		const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(url).toBe('https://openrouter.ai/api/v1/chat/completions');
		expect(init.method).toBe('POST');
		expect(init.headers).toEqual({
			Authorization: 'Bearer sk-or-v1-test-key',
			'Content-Type': 'application/json',
			'HTTP-Referer': 'https://vson-studio.pages.dev',
			'X-Title': 'vson'
		});
	});

	it('defaults model, max_tokens, and temperature in the request body', async () => {
		byok.set('sk-or-v1-test-key');
		fetchMock.mockResolvedValueOnce(jsonResponse(chatOk()));

		await client.chat({ messages: [{ role: 'user', content: 'hi' }] });

		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(JSON.parse(init.body as string)).toEqual({
			model: client.DEFAULT_MODEL,
			messages: [{ role: 'user', content: 'hi' }],
			max_tokens: 4096,
			temperature: 0.2
		});
	});

	it('honors an explicit model and passes messages through verbatim', async () => {
		byok.set('sk-or-v1-test-key');
		fetchMock.mockResolvedValueOnce(jsonResponse(chatOk()));
		const messages = [
			{
				role: 'system' as const,
				content: [
					{ type: 'text' as const, text: 'sys', cache_control: { type: 'ephemeral' as const } }
				]
			},
			{ role: 'user' as const, content: 'go' }
		];

		await client.chat({ model: 'anthropic/claude-sonnet-4.5', messages, max_tokens: 512 });

		const body = JSON.parse((fetchMock.mock.calls[0] as [string, RequestInit])[1].body as string);
		expect(body.model).toBe('anthropic/claude-sonnet-4.5');
		expect(body.max_tokens).toBe(512);
		expect(body.messages).toEqual(messages);
	});

	it('returns the parsed ChatResponse on success', async () => {
		byok.set('sk-or-v1-test-key');
		fetchMock.mockResolvedValueOnce(jsonResponse(chatOk('(s / Scene)')));

		const res = await client.chat({ messages: [{ role: 'user', content: 'hi' }] });

		expect(res.choices[0].message.content).toBe('(s / Scene)');
		expect(res.usage?.prompt_tokens).toBe(10);
	});
});

describe('chat() — error taxonomy', () => {
	it('rejects with no-key before any fetch when the byok store is empty', async () => {
		byok.set('');

		const err = await caught(client.chat({ messages: [{ role: 'user', content: 'hi' }] }));

		expect(err).toBeInstanceOf(client.OpenRouterError);
		expect(err.kind).toBe('no-key');
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('maps 401 to key-not-accepted', async () => {
		byok.set('sk-or-v1-bad-key');
		fetchMock.mockResolvedValueOnce(new Response('unauthorized', { status: 401 }));

		const err = await caught(client.chat({ messages: [{ role: 'user', content: 'hi' }] }));

		expect(err.kind).toBe('key-not-accepted');
		expect(err.message).toBe('key not accepted');
		expect(err.status).toBe(401);
	});

	it('maps 402 to out-of-credits', async () => {
		byok.set('sk-or-v1-broke-key');
		fetchMock.mockResolvedValueOnce(new Response('payment required', { status: 402 }));

		const err = await caught(client.chat({ messages: [{ role: 'user', content: 'hi' }] }));

		expect(err.kind).toBe('out-of-credits');
		expect(err.message).toBe('out of credits');
	});

	it('maps 429 to rate-limited', async () => {
		byok.set('sk-or-v1-test-key');
		fetchMock.mockResolvedValueOnce(new Response('slow down', { status: 429 }));

		const err = await caught(client.chat({ messages: [{ role: 'user', content: 'hi' }] }));

		expect(err.kind).toBe('rate-limited');
		expect(err.message).toBe('provider rate limit');
	});

	it('maps any other non-2xx to upstream, keeping the status and body slice', async () => {
		byok.set('sk-or-v1-test-key');
		fetchMock.mockResolvedValueOnce(new Response('boom', { status: 500 }));

		const err = await caught(client.chat({ messages: [{ role: 'user', content: 'hi' }] }));

		expect(err.kind).toBe('upstream');
		expect(err.status).toBe(500);
		expect(err.body).toBe('boom');
	});

	it('maps a failed fetch (offline, DNS, CORS) to network', async () => {
		byok.set('sk-or-v1-test-key');
		fetchMock.mockRejectedValueOnce(new TypeError('fetch failed'));

		const err = await caught(client.chat({ messages: [{ role: 'user', content: 'hi' }] }));

		expect(err.kind).toBe('network');
	});
});

// A minimal raw catalog: one text-only row (must be filtered out) and four
// vision rows across providers (must be shaped and rank-sorted).
const RAW_CATALOG = {
	data: [
		{
			id: 'zeta/vision-z',
			name: 'Zeta: Vision Z',
			architecture: { input_modalities: ['image', 'text'] },
			context_length: 32000,
			pricing: { prompt: '0.000001', completion: '0.000002' }
		},
		{
			id: 'openai/text-only',
			name: 'OpenAI: Text Only',
			architecture: { input_modalities: ['text'] },
			pricing: { prompt: '0.000001', completion: '0.000001' }
		},
		{
			id: 'google/gemini-2.5-flash',
			name: 'Google: Gemini 2.5 Flash',
			architecture: { input_modalities: ['image', 'text'] },
			context_length: 1048576,
			pricing: { prompt: '0.0000003', completion: '0.0000025' }
		},
		{
			id: 'openai/gpt-5o',
			name: 'OpenAI: GPT-5o',
			architecture: { input_modalities: ['image', 'text'] },
			context_length: 128000,
			pricing: { prompt: '0.0000025', completion: '0.00001' }
		},
		{
			id: 'anthropic/claude-sonnet-4.5',
			name: 'Anthropic: Claude Sonnet 4.5',
			architecture: { input_modalities: ['image', 'text'] },
			context_length: 200000,
			pricing: { prompt: '0.000003', completion: '0.000015', input_cache_read: '0.0000003' }
		}
	]
};

describe('models() — lazy catalog with in-tab cache', () => {
	it('fetches nothing at import time', () => {
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('shapes vision-only rows and sorts anthropic → openai → google → rest', async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse(RAW_CATALOG));

		const rows = await client.models();

		expect(fetchMock).toHaveBeenCalledWith(
			'https://openrouter.ai/api/v1/models',
			expect.objectContaining({ signal: expect.anything() })
		);
		expect(rows?.map((m) => m.id)).toEqual([
			'anthropic/claude-sonnet-4.5',
			'openai/gpt-5o',
			'google/gemini-2.5-flash',
			'zeta/vision-z'
		]);
		expect(rows?.[0]).toEqual({
			id: 'anthropic/claude-sonnet-4.5',
			name: 'Claude Sonnet 4.5', // provider prefix stripped
			provider: 'anthropic',
			context_length: 200000,
			prompt_per_mtok: 3,
			completion_per_mtok: 15,
			supports_cache: true
		});
		expect(rows?.[2].prompt_per_mtok).toBe(0.3);
		expect(rows?.[2].supports_cache).toBe(false);
	});

	it('caches a successful catalog for the tab: one upstream fetch across calls', async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse(RAW_CATALOG));

		const first = await client.models();
		const second = await client.models();

		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(second).toBe(first);
	});

	it('shares one in-flight fetch between concurrent first calls', async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse(RAW_CATALOG));

		const [a, b] = await Promise.all([client.models(), client.models()]);

		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(b).toBe(a);
	});

	it('resolves null on upstream failure and does NOT cache it — the next call retries', async () => {
		fetchMock.mockResolvedValueOnce(new Response('nope', { status: 500 }));
		expect(await client.models()).toBeNull();

		fetchMock.mockResolvedValueOnce(jsonResponse(RAW_CATALOG));
		const retry = await client.models();

		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(retry?.length).toBe(4);
	});

	it('resolves null on a network error and an empty catalog', async () => {
		fetchMock.mockRejectedValueOnce(new TypeError('fetch failed'));
		expect(await client.models()).toBeNull();

		fetchMock.mockResolvedValueOnce(jsonResponse({ data: [] }));
		expect(await client.models()).toBeNull();
	});
});

describe('isPlausibleModelId — advisory only', () => {
	it('accepts vendor/model[:variant] shapes', () => {
		expect(client.isPlausibleModelId('google/gemini-2.5-flash')).toBe(true);
		expect(client.isPlausibleModelId('meta-llama/llama-4-maverick:free')).toBe(true);
	});

	it('rejects empty, slashless, and oversized ids', () => {
		expect(client.isPlausibleModelId('')).toBe(false);
		expect(client.isPlausibleModelId('not-a-model-id')).toBe(false);
		expect(client.isPlausibleModelId(`vendor/${'x'.repeat(140)}`)).toBe(false);
	});
});
