import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';
import { viteStaticCopy } from 'vite-plugin-static-copy';
import { fileURLToPath } from 'node:url';

// $lib/prompts/bodies ?raw-imports canonical files from the REPO ROOT
// (tools/extractor/prompts/*, skills/*/SKILL.md). The dev server refuses to
// serve files outside the project directory unless they are allow-listed, so
// widen the list to the repo root — a dev-only setting; `vite build` inlines
// the ?raw content into the bundle and never consults it.
const repoRoot = fileURLToPath(new URL('..', import.meta.url));

// Pyodide CORE RUNTIME, copied verbatim from the exact-pinned npm package
// (pyodide 314.0.3) into /pyodide/ — served by the dev server and emitted
// into the build. The validation WHEELS are deliberately NOT copied from
// node_modules: they are committed under static/pyodide/wheels/ with a
// sha256 lock (wheels.lock.json, enforced by tests/wheels-lock.test.ts) so
// every install is network-free and yank-immune. Note the ESM-era file set:
// pyodide ships pyodide.asm.mjs, not the pre-314 pyodide.asm.js.
const PYODIDE_RUNTIME_FILES = [
	'pyodide.mjs',
	'pyodide.asm.mjs',
	'pyodide.asm.wasm',
	'python_stdlib.zip',
	'pyodide-lock.json'
];

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit(),
		viteStaticCopy({
			targets: PYODIDE_RUNTIME_FILES.map((file) => ({
				src: `node_modules/pyodide/${file}`,
				dest: 'pyodide',
				// flatten: emit /pyodide/<file>, not /pyodide/node_modules/pyodide/<file>
				rename: { stripBase: true }
			}))
		})
	],
	server: {
		fs: {
			allow: [repoRoot]
		}
	},
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}', 'tests/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
