// BYOK — bring your own OpenRouter key.
//
// The key lives in module memory for the lifetime of the tab and nowhere else:
// no localStorage, no sessionStorage, no cookie, no URL. The OpenRouter client
// ($lib/openrouter/client) reads it to build its `Authorization: Bearer`
// header, so the key travels browser → openrouter.ai directly and never
// touches this site's host (never stored, never logged). A refresh or tab
// close forgets it, by design.

let key = $state('');

// Monotonic signal: bumping it asks the model picker — the one place a key is
// entered — to open and focus its key field. Plain state rather than a DOM
// event so the picker can react with an ordinary $effect.
let keyFocusSignal = $state(0);

export const byok = {
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
	/** Open the model picker on its key field — used by the keyless-drop hint. */
	requestKeyFocus() {
		keyFocusSignal += 1;
	}
};
