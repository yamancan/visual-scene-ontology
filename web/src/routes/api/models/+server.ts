import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

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

export interface PickerModel {
	id: string;
	name: string;
	provider: string;
	context_length: number;
	prompt_per_mtok: number; // USD per 1M input tokens
	completion_per_mtok: number; // USD per 1M output tokens
	supports_cache: boolean;
}

const TTL_MS = 10 * 60 * 1000; // 10 min — model list rarely changes
let cache: { at: number; data: PickerModel[] } | null = null;

function shape(m: OrModel): PickerModel | null {
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

export const GET: RequestHandler = async () => {
	const now = Date.now();
	if (cache && now - cache.at < TTL_MS) return json(cache.data);

	const res = await fetch('https://openrouter.ai/api/v1/models');
	if (!res.ok) throw error(502, `openrouter /models → ${res.status}`);
	const body = (await res.json()) as { data: OrModel[] };
	const data = body.data
		.map(shape)
		.filter((m): m is PickerModel => m !== null)
		.sort((a, b) => {
			// Anthropic + OpenAI + Google to the top, then alphabetical.
			const rank = (p: string) =>
				p.startsWith('anthropic') ? 0 : p.startsWith('openai') ? 1 : p.startsWith('google') ? 2 : 3;
			const dr = rank(a.id) - rank(b.id);
			return dr !== 0 ? dr : a.id.localeCompare(b.id);
		});
	cache = { at: now, data };
	return json(data);
};
