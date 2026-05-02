import type { ExtractStatus, VsonEnvelope } from './types';

// Rune-based reactive container for the current scene. Imported directly
// where consumers need to read or mutate. Stateless across page reloads.
const DEFAULT_MODEL = 'google/gemini-2.5-flash';
const MODEL_KEY = 'vson:model';

function readStoredModel(): string {
	if (typeof localStorage === 'undefined') return DEFAULT_MODEL;
	try {
		return localStorage.getItem(MODEL_KEY) || DEFAULT_MODEL;
	} catch {
		return DEFAULT_MODEL;
	}
}

function createSceneStore() {
	let envelope = $state<VsonEnvelope | null>(null);
	let status = $state<ExtractStatus>('idle');
	let errorMsg = $state<string | null>(null);
	let selectedNodeId = $state<string | null>(null);
	let imagePreview = $state<string | null>(null);
	let model = $state<string>(readStoredModel());

	return {
		get envelope() {
			return envelope;
		},
		get status() {
			return status;
		},
		get errorMsg() {
			return errorMsg;
		},
		get selectedNodeId() {
			return selectedNodeId;
		},
		get imagePreview() {
			return imagePreview;
		},
		get model() {
			return model;
		},
		setEnvelope(e: VsonEnvelope | null) {
			envelope = e;
		},
		setStatus(s: ExtractStatus) {
			status = s;
		},
		setError(msg: string | null) {
			errorMsg = msg;
			if (msg) status = 'error';
		},
		setSelected(id: string | null) {
			selectedNodeId = id;
		},
		setImagePreview(dataUrl: string | null) {
			imagePreview = dataUrl;
		},
		setModel(id: string) {
			model = id;
			try {
				localStorage.setItem(MODEL_KEY, id);
			} catch {
				/* ignore */
			}
		},
		reset() {
			envelope = null;
			status = 'idle';
			errorMsg = null;
			selectedNodeId = null;
			imagePreview = null;
		}
	};
}

export const scene = createSceneStore();
