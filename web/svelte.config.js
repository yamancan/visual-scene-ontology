import adapter from '@sveltejs/adapter-node';

// Vite sets NODE_ENV before it loads this file: 'development' under `vite dev`,
// 'production' under `vite build`. Verified by probe, not assumed.
const dev = process.env.NODE_ENV === 'development';

// Content-Security-Policy. Nonce mode rather than hash mode: the FOUC guard in
// app.html is hand-written, and a hash would silently drift the moment someone
// edits it. A nonce is regenerated per response and carries no such coupling.
// Nonce mode is incompatible with prerendering — SvelteKit throws at build time
// if a page is ever marked prerenderable, which is the loud failure we want.

// SvelteKit does not export its CspDirectives interface, so the types are read
// back off the exported KitConfig. Worth the indirection: it means a typo in a
// directive name is a build error rather than a directive the browser ignores.
/** @typedef {NonNullable<NonNullable<import('@sveltejs/kit').KitConfig['csp']>['directives']>} CspDirectives */
/** @typedef {NonNullable<CspDirectives['connect-src']>[number]} CspSource */

// SvelteKit's scheme-source union stops at blob:/filesystem: and has no entry
// for ws:, so the one scheme source dev needs is cast rather than dropped or
// narrowed to a guessed hostname.
const HMR_WEBSOCKET = /** @type {CspSource} */ ('ws:');

/** @type {CspDirectives} */
const directives = {
	'default-src': ['self'],
	// SvelteKit appends 'nonce-…' here for its own bootstrap script and for the
	// app.html script that carries nonce="%sveltekit.nonce%".
	'script-src': ['self'],
	// Svelte emits component styles as inline <style> elements. 'unsafe-inline'
	// on styles buys an attacker markup injection, not script execution.
	'style-src': ['self', 'unsafe-inline'],
	// Belt and braces: style-src does not cover style="" attributes, and the
	// overlay positions bounding boxes that way. Declared explicitly so that
	// enabling inlineStyleThreshold later cannot quietly break the overlay.
	'style-src-attr': ['unsafe-inline'],
	// data: is required — the dropzone previews the uploaded file through
	// FileReader.readAsDataURL, and the bbox crops re-use that same data URL.
	// blob: is deliberately absent: download() navigates an <a download> to a
	// blob URL, which no fetch directive governs. Add it only if a real
	// violation is observed.
	'img-src': ['self', 'data:'],
	// The browser only ever talks to this origin; OpenRouter is called from the
	// server. ws: is added in dev for Vite's HMR socket and nowhere else.
	'connect-src': dev ? ['self', HMR_WEBSOCKET] : ['self'],
	'object-src': ['none'],
	'base-uri': ['self'],
	'form-action': ['self'],
	'frame-ancestors': ['none'],
	'worker-src': ['self']
};

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		adapter: adapter(),
		csp: { mode: 'nonce', directives }
	}
};

export default config;
