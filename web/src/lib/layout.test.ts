// Contract tests for the layout store. Every UI component (ScenePanel,
// SceneFlow, LayoutSwitcher, MaxButton, TabsRail) reads these getters, so the
// names/signatures are load-bearing — these assertions pin them.
//
// The store is a module singleton, so tests mutate shared state. Each block
// resets to a known preset (resetLayout / setPreset) before asserting so order
// can't leak. localStorage is absent in the node env, so persist() is a no-op
// and the default preset falls back to 'image'.

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { layout, PRESET_ORDER, PRESET_META } from './layout.svelte';

const bodyCols = (editorFr: number, railFr: number) =>
	`minmax(0, ${editorFr}fr) minmax(340px, ${railFr}fr)`;

describe('layout store — defaults & metadata', () => {
	beforeEach(() => layout.resetLayout());

	it('defaults to the image preset with nothing maximized', () => {
		expect(layout.preset).toBe('image');
		expect(layout.maximized).toBeNull();
		expect(layout.anyMax).toBe(false);
	});

	it('exposes the three modes in order with metadata for each', () => {
		expect(PRESET_ORDER).toEqual(['image', 'graph', 'notation']);
		expect(PRESET_ORDER).toHaveLength(3);
		for (const p of PRESET_ORDER) {
			expect(PRESET_META[p].label).toBeTruthy();
			expect(PRESET_META[p].hint).toBeTruthy();
		}
		// User-facing relabel: Inspect / Graph / Source.
		expect(PRESET_META.image.label).toBe('Inspect');
		expect(PRESET_META.graph.label).toBe('Graph');
		expect(PRESET_META.notation.label).toBe('Source');
	});
});

describe('layout store — mode getter', () => {
	beforeEach(() => layout.resetLayout());

	it('maps each preset id to its user-facing mode', () => {
		layout.setPreset('image');
		expect(layout.mode).toBe('inspect');
		layout.setPreset('graph');
		expect(layout.mode).toBe('graph');
		layout.setPreset('notation');
		expect(layout.mode).toBe('source');
	});

	it('defaults to inspect mode', () => {
		expect(layout.preset).toBe('image');
		expect(layout.mode).toBe('inspect');
	});
});

describe('layout store — Inspect rail default', () => {
	beforeEach(() => layout.resetLayout());

	it('keeps the entity-list rail visible by default in Inspect (image) mode', () => {
		layout.setPreset('image');
		expect(layout.mode).toBe('inspect');
		// Notation is a MODE (Source), not the rail content, so the rail (entity
		// list) must stay open by default — it is not hidden for the image preset.
		expect(layout.railVisible).toBe(true);
	});
});

describe('layout store — bodyCols per preset (non-maximized)', () => {
	beforeEach(() => layout.resetLayout());

	it('image preset', () => {
		layout.setPreset('image');
		expect(layout.bodyCols).toBe(bodyCols(1.7, 0.9));
	});

	it('notation preset', () => {
		layout.setPreset('notation');
		expect(layout.bodyCols).toBe(bodyCols(0.75, 1.5));
	});

	it('graph preset', () => {
		layout.setPreset('graph');
		expect(layout.bodyCols).toBe(bodyCols(1.9, 0.55));
	});
});

describe('layout store — bodyCols under maximize', () => {
	beforeEach(() => layout.resetLayout());

	it('notation maximized => rail only (1fr, stage hidden)', () => {
		layout.toggleMax('notation');
		expect(layout.stageVisible).toBe(false);
		expect(layout.railVisible).toBe(true);
		expect(layout.bodyCols).toBe('1fr');
	});

	it('image maximized => stage only (1fr, rail hidden)', () => {
		layout.toggleMax('image');
		expect(layout.stageVisible).toBe(true);
		expect(layout.railVisible).toBe(false);
		expect(layout.bodyCols).toBe('1fr');
	});

	it('graph maximized => stage only (1fr, rail hidden)', () => {
		layout.toggleMax('graph');
		expect(layout.bodyCols).toBe('1fr');
	});

	it('facts maximized => stage only (1fr, rail hidden)', () => {
		layout.toggleMax('facts');
		expect(layout.bodyCols).toBe('1fr');
	});
});

describe('layout store — isMax / toggleMax round-trip', () => {
	beforeEach(() => layout.resetLayout());

	it('toggles a panel on then off', () => {
		expect(layout.isMax('graph')).toBe(false);
		layout.toggleMax('graph');
		expect(layout.isMax('graph')).toBe(true);
		expect(layout.maximized).toBe('graph');
		expect(layout.anyMax).toBe(true);
		layout.toggleMax('graph');
		expect(layout.isMax('graph')).toBe(false);
		expect(layout.maximized).toBeNull();
		expect(layout.anyMax).toBe(false);
	});

	it('toggling a different panel switches the maximized target', () => {
		layout.toggleMax('image');
		expect(layout.isMax('image')).toBe(true);
		layout.toggleMax('notation');
		expect(layout.isMax('image')).toBe(false);
		expect(layout.isMax('notation')).toBe(true);
	});

	it('clearMax drops any maximized panel', () => {
		layout.toggleMax('facts');
		expect(layout.anyMax).toBe(true);
		layout.clearMax();
		expect(layout.maximized).toBeNull();
		expect(layout.anyMax).toBe(false);
	});
});

describe('layout store — setPreset clears maximize + overrides', () => {
	beforeEach(() => layout.resetLayout());

	it('wipes maximize and per-panel overrides', () => {
		layout.toggleMax('graph');
		layout.togglePanel('facts');
		layout.setPreset('notation');
		expect(layout.preset).toBe('notation');
		expect(layout.maximized).toBeNull();
		expect(layout.anyMax).toBe(false);
		// overrides cleared => factsVisible falls back to the notation preset default (false)
		expect(layout.factsVisible).toBe(false);
	});
});

describe('layout store — visibility getters & overrides', () => {
	beforeEach(() => layout.resetLayout());

	it('graph is always visible in normal mode', () => {
		expect(layout.graphVisible).toBe(true);
	});

	it('rail defaults to visible and toggles off/on', () => {
		expect(layout.railVisible).toBe(true);
		layout.togglePanel('rail');
		expect(layout.railVisible).toBe(false);
		expect(layout.bodyCols).toBe('1fr');
		layout.togglePanel('rail');
		expect(layout.railVisible).toBe(true);
	});

	it('image visibility follows the preset default then the override', () => {
		layout.setPreset('image'); // imagePct 60 => visible
		expect(layout.imageVisible).toBe(true);
		layout.togglePanel('image');
		expect(layout.imageVisible).toBe(false);
		layout.setPreset('graph'); // imagePct 0 => collapsed by default
		expect(layout.imageVisible).toBe(false);
	});

	it('facts visibility follows the preset default', () => {
		layout.setPreset('image'); // factsOpen false
		expect(layout.factsVisible).toBe(false);
		layout.setPreset('graph'); // factsOpen true
		expect(layout.factsVisible).toBe(true);
	});
});

describe('layout store — stored-preset migration', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.resetModules();
	});

	const stub = (stored: string | null) => {
		const store = new Map<string, string>();
		if (stored !== null) store.set('vson:layout', stored);
		vi.stubGlobal('localStorage', {
			getItem: (k: string) => store.get(k) ?? null,
			setItem: (k: string, v: string) => void store.set(k, v),
			removeItem: (k: string) => void store.delete(k)
		});
	};

	it('migrates a stored "balanced" preset to image (Inspect)', async () => {
		stub('balanced');
		vi.resetModules();
		const { layout: fresh } = await import('./layout.svelte');
		expect(fresh.preset).toBe('image');
		expect(fresh.mode).toBe('inspect');
	});

	it('treats any unknown stored value as the image default', async () => {
		stub('nonsense');
		vi.resetModules();
		const { layout: fresh } = await import('./layout.svelte');
		expect(fresh.preset).toBe('image');
	});

	it('honours a valid stored preset', async () => {
		stub('graph');
		vi.resetModules();
		const { layout: fresh } = await import('./layout.svelte');
		expect(fresh.preset).toBe('graph');
		expect(fresh.mode).toBe('graph');
	});
});

describe('layout store — imagePct', () => {
	beforeEach(() => layout.resetLayout());

	it('reflects the image preset value', () => {
		layout.setPreset('image');
		expect(layout.imagePct).toBe(60);
	});

	it('is 0 on the graph preset (image collapsed)', () => {
		layout.setPreset('graph');
		expect(layout.imagePct).toBe(0);
	});

	it('is 100 when the image panel is maximized', () => {
		layout.setPreset('graph'); // even from a 0% preset
		layout.toggleMax('image');
		expect(layout.imagePct).toBe(100);
	});

	it('falls back to 44 when image is forced visible from a 0% preset', () => {
		layout.setPreset('graph'); // imagePct 0
		layout.togglePanel('image'); // force visible
		expect(layout.imageVisible).toBe(true);
		expect(layout.imagePct).toBe(44);
	});
});
