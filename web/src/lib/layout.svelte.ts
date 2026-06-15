// Single source of truth for the studio layout. Replaces the old
// fixed-fraction grids (ScenePanel .body / .split, SceneFlow .image-band) with
// a reactive store that powers four one-click presets, per-panel maximize, and
// a sticky preset preference. No drag gutters — the user picks a shape and we
// translate it into grid-template strings + flex bases via getters.
//
// Follows the createXStore() pattern in scene.svelte.ts: $state locals behind a
// returned bag of getters/methods, with localStorage reads guarded by a
// typeof check so the module is safe to import during SSR and unit tests.

export type LayoutPreset = 'image' | 'balanced' | 'notation' | 'graph';
export type PanelId = 'image' | 'graph' | 'facts' | 'notation';

export const PRESET_ORDER: readonly LayoutPreset[] = ['image', 'balanced', 'notation', 'graph'];

export const PRESET_META: Record<LayoutPreset, { label: string; hint: string }> = {
	image: { label: 'image', hint: 'Image-forward — large preview' },
	balanced: { label: 'balanced', hint: 'Editor and notation balanced' },
	notation: { label: 'notation', hint: 'Notation-forward — wide source' },
	graph: { label: 'graph', hint: 'Graph focus — image collapsed' }
};

// The actual shape behind each preset. Private on purpose — UI components read
// the derived getters (bodyCols, imagePct, *Visible), never these raw numbers,
// so the translation from "shape" to CSS stays in one place.
//   editorFr/railFr — the two columns of ScenePanel .body
//   imagePct        — SceneFlow .image-band flex-basis (0 => band collapsed by default)
//   factsOpen       — whether the FactsStrip starts open (callers also gate on spatialCount>0)
const PRESETS: Record<
	LayoutPreset,
	{ editorFr: number; railFr: number; imagePct: number; factsOpen: boolean }
> = {
	image: { editorFr: 1.7, railFr: 0.7, imagePct: 60, factsOpen: false },
	balanced: { editorFr: 1.4, railFr: 0.95, imagePct: 44, factsOpen: true },
	notation: { editorFr: 0.75, railFr: 1.5, imagePct: 40, factsOpen: false },
	graph: { editorFr: 1.9, railFr: 0.55, imagePct: 0, factsOpen: true }
};

const LAYOUT_KEY = 'vson:layout';
const DEFAULT_PRESET: LayoutPreset = 'image';

function isPreset(v: unknown): v is LayoutPreset {
	return v === 'image' || v === 'balanced' || v === 'notation' || v === 'graph';
}

function readStoredPreset(): LayoutPreset {
	if (typeof localStorage === 'undefined') return DEFAULT_PRESET;
	try {
		const v = localStorage.getItem(LAYOUT_KEY);
		return isPreset(v) ? v : DEFAULT_PRESET;
	} catch {
		return DEFAULT_PRESET;
	}
}

// Per-panel show/hide overrides layered on top of the active preset. Session
// only (not persisted) — flipped by togglePanel, wiped on setPreset/reset.
interface LayoutOverrides {
	image?: boolean;
	facts?: boolean;
	rail?: boolean;
}

function createLayoutStore() {
	let preset = $state<LayoutPreset>(readStoredPreset());
	let maximized = $state<PanelId | null>(null);
	let overrides = $state<LayoutOverrides>({});

	function persist() {
		try {
			localStorage.setItem(LAYOUT_KEY, preset);
		} catch {
			/* ignore */
		}
	}

	const api = {
		get preset() {
			return preset;
		},
		get maximized() {
			return maximized;
		},
		get anyMax() {
			return maximized !== null;
		},
		isMax(p: PanelId) {
			return maximized === p;
		},
		// The notation pane lives in the rail; maximizing it drops the whole stage.
		get stageVisible() {
			return !api.isMax('notation');
		},
		// In maximize mode only the notation rail survives; otherwise the rail
		// follows its override (defaulting to shown).
		get railVisible() {
			return maximized ? api.isMax('notation') : (overrides.rail ?? true);
		},
		get imageVisible() {
			return maximized ? api.isMax('image') : (overrides.image ?? PRESETS[preset].imagePct > 0);
		},
		get graphVisible() {
			return maximized ? api.isMax('graph') : true;
		},
		// Callers ALSO gate this on spatialCount>0 — a scene with no spatial facts
		// has nothing to show in the FactsStrip regardless of this flag.
		get factsVisible() {
			return maximized ? api.isMax('facts') : (overrides.facts ?? PRESETS[preset].factsOpen);
		},
		get imagePct() {
			if (api.isMax('image')) return 100;
			return api.imageVisible ? PRESETS[preset].imagePct || 44 : 0;
		},
		// grid-template-columns for ScenePanel .body.
		get bodyCols() {
			if (!api.stageVisible) return '1fr'; // notation maximized -> rail only
			if (!api.railVisible) return '1fr'; // a non-notation panel maximized, or rail collapsed -> stage only
			const { editorFr, railFr } = PRESETS[preset];
			return 'minmax(0, ' + editorFr + 'fr) minmax(340px, ' + railFr + 'fr)';
		},
		setPreset(p: LayoutPreset) {
			preset = p;
			maximized = null;
			overrides = {};
			persist();
		},
		toggleMax(p: PanelId) {
			maximized = maximized === p ? null : p;
		},
		clearMax() {
			maximized = null;
		},
		// Flip a panel's override to the negation of its CURRENT visibility, so the
		// first click always does the opposite of what's on screen right now.
		// Clear any maximize FIRST: while a panel is maximized the *Visible getters
		// return the maximize state and ignore overrides, so writing an override
		// then would be a silent no-op (and a stale value). Dropping maximize makes
		// the toggle take effect immediately and reads `current` from the real
		// (non-maximized) preset+override visibility.
		togglePanel(p: 'image' | 'facts' | 'rail') {
			if (maximized !== null) maximized = null;
			const current = p === 'image' ? api.imageVisible : p === 'facts' ? api.factsVisible : api.railVisible;
			overrides = { ...overrides, [p]: !current };
		},
		resetLayout() {
			preset = DEFAULT_PRESET;
			maximized = null;
			overrides = {};
			persist();
		}
	};

	return api;
}

export const layout = createLayoutStore();
