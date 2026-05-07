import type { ExtractStatus, VsonEnvelope } from './types';

// Rune-based reactive container for the current scene. Imported directly
// where consumers need to read or mutate. Stateless across page reloads.
const DEFAULT_MODEL = 'google/gemini-2.5-flash';
const MODEL_KEY = 'vson:model';
const NOTATION_KEY = 'vson:notation';

function readStoredModel(): string {
	if (typeof localStorage === 'undefined') return DEFAULT_MODEL;
	try {
		return localStorage.getItem(MODEL_KEY) || DEFAULT_MODEL;
	} catch {
		return DEFAULT_MODEL;
	}
}

function readStoredNotation(): Notation {
	if (typeof localStorage === 'undefined') return 'p';
	try {
		const v = localStorage.getItem(NOTATION_KEY);
		return v === 'x' ? 'x' : 'p';
	} catch {
		return 'p';
	}
}

// 'source' is the dynamic-label tab whose body is VSON-P or VSON-X based on
// scene.notation. 'penman' is kept as a value alias only for backwards-compat
// during the rename window — new code should use 'source'.
export type RailTab = 'source' | 'turtle' | 'conformance';
export type Notation = 'p' | 'x';

function createSceneStore() {
	let envelope = $state<VsonEnvelope | null>(null);
	let status = $state<ExtractStatus>('idle');
	let errorMsg = $state<string | null>(null);
	let selectedNodeId = $state<string | null>(null);
	let imagePreview = $state<string | null>(null);
	let model = $state<string>(readStoredModel());
	let railTab = $state<RailTab>('source');
	let notation = $state<Notation>(readStoredNotation());

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
		get railTab() {
			return railTab;
		},
		get notation() {
			return notation;
		},
		setEnvelope(e: VsonEnvelope | null) {
			envelope = e;
			// Drop any selection from a previous scene — its var won't exist
			// in the new graph and we'd silently render a non-match.
			selectedNodeId = null;
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
		setRailTab(t: RailTab) {
			railTab = t;
		},
		setNotation(n: Notation) {
			notation = n;
			try {
				localStorage.setItem(NOTATION_KEY, n);
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
			railTab = 'source';
			// Don't clear `notation` — it's a sticky preference, like `model`.
		}
	};
}

export const scene = createSceneStore();
