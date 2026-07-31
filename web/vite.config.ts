import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';
import { fileURLToPath } from 'node:url';

// $lib/prompts/bodies ?raw-imports canonical files from the REPO ROOT
// (tools/extractor/prompts/*, skills/*/SKILL.md). The dev server refuses to
// serve files outside the project directory unless they are allow-listed, so
// widen the list to the repo root — a dev-only setting; `vite build` inlines
// the ?raw content into the bundle and never consults it.
const repoRoot = fileURLToPath(new URL('..', import.meta.url));

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
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
