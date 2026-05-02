import type { ExtractStatus, VsonEnvelope } from './types';

// Rune-based reactive container for the current scene. Imported directly
// where consumers need to read or mutate. Stateless across page reloads.
function createSceneStore() {
	let envelope = $state<VsonEnvelope | null>(null);
	let status = $state<ExtractStatus>('idle');
	let errorMsg = $state<string | null>(null);
	let selectedNodeId = $state<string | null>(null);
	let imagePreview = $state<string | null>(null);

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
