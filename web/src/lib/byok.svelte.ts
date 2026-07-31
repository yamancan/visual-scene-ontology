// BYOK — bring your own OpenRouter key.
//
// The key lives in module memory for the lifetime of the tab and nowhere else:
// no localStorage, no sessionStorage, no cookie, no URL. It is attached as an
// `x-openrouter-key` header to /api/extract and /api/correct requests, where
// the server uses it for that one upstream call instead of its own key and
// then drops it (never stored, never logged — see lib/server/openrouter.ts).
// A refresh or tab close forgets it, by design.

let key = $state('');

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
	/** Spread into a fetch `headers` object; empty when no key is set. */
	headers(): Record<string, string> {
		return key ? { 'x-openrouter-key': key } : {};
	}
};
