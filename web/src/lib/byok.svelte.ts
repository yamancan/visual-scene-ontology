// BYOK — bring your own OpenRouter key.
//
// The key lives in module memory for the lifetime of the tab and nowhere else:
// no localStorage, no sessionStorage, no cookie, no URL. The OpenRouter client
// ($lib/openrouter/client) reads it to build its `Authorization: Bearer`
// header, so the key travels browser → openrouter.ai directly and never
// touches this site's host (never stored, never logged). A refresh or tab
// close forgets it, by design.
//
// The runes are created on FIRST ACCESS, not at module evaluation. Rolldown
// (vite 8) placed this module in a chunk the Svelte-runtime chunk circularly
// imports for its own `__exportAll` helper, so module-eval code here ran
// before the runtime's module-level vars were initialized — `$state()` then
// died inside push_reaction_value (undefined.push) and took the entire
// hydration down with it. First access happens from component init, when the
// runtime is guaranteed live.

function createByokState() {
	let key = $state('');

	// Monotonic signal: bumping it asks the model picker — the one place a key
	// is entered — to open and focus its key field. Plain state rather than a
	// DOM event so the picker can react with an ordinary $effect.
	let keyFocusSignal = $state(0);

	return {
		get key(): string {
			return key;
		},
		set(next: string) {
			key = next.trim();
		},
		get active(): boolean {
			return key.length > 0;
		},
		get keyFocusSignal(): number {
			return keyFocusSignal;
		},
		requestKeyFocus() {
			keyFocusSignal += 1;
		}
	};
}

let singleton: ReturnType<typeof createByokState> | undefined;

function inst(): ReturnType<typeof createByokState> {
	return (singleton ??= createByokState());
}

export const byok = {
	get key(): string {
		return inst().key;
	},
	set(next: string) {
		inst().set(next);
	},
	get active(): boolean {
		return inst().active;
	},
	get keyFocusSignal(): number {
		return inst().keyFocusSignal;
	},
	/** Open the model picker on its key field — used by the keyless-drop hint. */
	requestKeyFocus() {
		inst().requestKeyFocus();
	}
};
