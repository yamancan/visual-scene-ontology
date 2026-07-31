import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { listPickerModels } from '$lib/server/openrouter';

// The model list, its 10-minute cache and the vision-only shaping now live in
// $lib/server/openrouter so the extract and correct routes can validate a
// requested model id against the same catalog. This route is just the picker's
// view of it (narrowed by OPENROUTER_ALLOWED_MODELS when the operator set it).

export const GET: RequestHandler = async () => {
	const models = await listPickerModels();
	if (!models) throw error(502, 'openrouter /models unavailable');
	return json(models);
};
