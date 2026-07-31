import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// Strict prerender, no fallback: every route is static HTML or the build
		// fails. The Content-Security-Policy is no longer configured here — it is
		// generated from the actual build output by scripts/gen-headers.js and
		// delivered as a real response header via build/_headers, which covers
		// static assets and the worker script that kit's meta/nonce CSP never
		// reached.
		adapter: adapter()
	}
};

export default config;
