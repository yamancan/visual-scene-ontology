import type { ExtractStatus, VsonEnvelope } from './types';
// Type-only: erased at build, so the store costs zero Pyodide bytes.
import type { GateResult } from './validate/pyodide-ops';
import { DEFAULT_MODEL } from './openrouter/client';

// Rune-based reactive container for the current scene. Imported directly
// where consumers need to read or mutate. Stateless across page reloads.
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

// A staged, not-yet-applied correction to a single entity. Accumulated in the
// store while the user reviews a scene; flushed through the client correction
// orchestrator ($lib/extract/orchestrator) on submit.
export interface EntityEdit {
	klass?: string;
	qualities?: { dim: string; value: string }[];
	note?: string;
	remove?: boolean;
}

// A staged edit carries a real instruction iff it removes the entity, sets a
// class, sets at least one quality, or has a non-blank note. An edit that the
// user opened then cleared is a no-op: it must not count toward the badge nor
// burn an LLM round-trip. Shared by pendingCount and CorrectionBar.send().
export function isMeaningfulEdit(e: EntityEdit): boolean {
	return !!(e.remove || e.klass || e.qualities?.length || e.note?.trim());
}

function createSceneStore() {
	let envelope = $state<VsonEnvelope | null>(null);
	let status = $state<ExtractStatus>('idle');
	let errorMsg = $state<string | null>(null);
	let selectedNodeId = $state<string | null>(null);
	let imagePreview = $state<string | null>(null);
	let model = $state<string>(readStoredModel());
	let railTab = $state<RailTab>('source');
	let notation = $state<Notation>(readStoredNotation());
	let pendingEdits = $state<Record<string, EntityEdit>>({});
	let sceneNote = $state('');
	let hoveredNodeId = $state<string | null>(null);
	let correctionStatus = $state<'idle' | 'correcting' | 'error'>('idle');
	let correctionError = $state<string | null>(null);
	// Progressive verdict: the current round's Gate 1 SHACL result, delivered by
	// the orchestrator's onGate1 hook ~0.2s into each validation while Gate 2
	// (OWL RL, ~2.8s) is still running. Null outside an in-flight validation.
	let gate1 = $state<GateResult | null>(null);

	// Drop any staged corrections — a new scene makes prior edits stale (their
	// ids may not exist in the new graph). Shared by setEnvelope() and reset().
	function clearCorrections() {
		pendingEdits = {};
		sceneNote = '';
		correctionStatus = 'idle';
		correctionError = null;
	}

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
		// The notation that will actually render: honor the sticky `notation`
		// preference when the envelope carries that form, else transparently fall
		// back to whichever form has a body. When neither has a body, keep the
		// preference (the source pane shows its empty state). Single source of
		// truth — SourcePane (body + fallback chip) and TabsRail (tab label) both
		// read this so they can never disagree, including the both-empty case.
		get effectiveNotation(): Notation {
			const xBody = (envelope?.vson_x?.trim().length ?? 0) > 0;
			const pBody = (envelope?.vson_p?.trim().length ?? 0) > 0;
			if (notation === 'x') return xBody ? 'x' : pBody ? 'p' : 'x';
			return pBody ? 'p' : xBody ? 'x' : 'p';
		},
		get pendingEdits() {
			return pendingEdits;
		},
		get sceneNote() {
			return sceneNote;
		},
		get hoveredNodeId() {
			return hoveredNodeId;
		},
		get correctionStatus() {
			return correctionStatus;
		},
		get correctionError() {
			return correctionError;
		},
		get gate1() {
			return gate1;
		},
		// How many distinct corrections are staged — one per *meaningful* entity
		// edit (no-op edits the user opened then cleared don't count) plus one for
		// a non-blank scene note. Drives the submit-button badge.
		get pendingCount() {
			const edits = Object.values(pendingEdits).filter(isMeaningfulEdit).length;
			return edits + (sceneNote.trim() ? 1 : 0);
		},
		setEnvelope(e: VsonEnvelope | null) {
			envelope = e;
			// Drop any selection from a previous scene — its var won't exist
			// in the new graph and we'd silently render a non-match.
			selectedNodeId = null;
			// The envelope carries the final two-gate verdict; the interim Gate 1
			// line must not outlive the validation it narrated.
			gate1 = null;
			// New scene => any staged edits reference a graph that's gone.
			clearCorrections();
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
		setEntityEdit(id: string, patch: Partial<EntityEdit>) {
			pendingEdits = { ...pendingEdits, [id]: { ...(pendingEdits[id] ?? {}), ...patch } };
		},
		clearEntityEdit(id: string) {
			const { [id]: _removed, ...rest } = pendingEdits;
			pendingEdits = rest;
		},
		setSceneNote(s: string) {
			sceneNote = s;
		},
		setHovered(id: string | null) {
			hoveredNodeId = id;
		},
		setCorrectionStatus(s: 'idle' | 'correcting' | 'error', err?: string | null) {
			correctionStatus = s;
			correctionError = err ?? null;
		},
		setGate1(g: GateResult | null) {
			gate1 = g;
		},
		clearCorrections() {
			clearCorrections();
		},
		reset() {
			envelope = null;
			status = 'idle';
			errorMsg = null;
			selectedNodeId = null;
			imagePreview = null;
			railTab = 'source';
			hoveredNodeId = null;
			gate1 = null;
			clearCorrections();
			// Don't clear `notation` — it's a sticky preference, like `model`.
		}
	};
}

export const scene = createSceneStore();
