import prettier from 'eslint-config-prettier';
import path from 'node:path';
import { includeIgnoreFile } from '@eslint/compat';
import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import { defineConfig } from 'eslint/config';
import globals from 'globals';
import ts from 'typescript-eslint';
import svelteConfig from './svelte.config.js';

const gitignorePath = path.resolve(import.meta.dirname, '.gitignore');

export default defineConfig(
	includeIgnoreFile(gitignorePath),
	js.configs.recommended,
	ts.configs.recommended,
	svelte.configs.recommended,
	prettier,
	svelte.configs.prettier,
	{
		languageOptions: { globals: { ...globals.browser, ...globals.node } },
		rules: {
			// typescript-eslint strongly recommend that you do not use the no-undef lint rule on TypeScript projects.
			// see: https://typescript-eslint.io/troubleshooting/faqs/eslint/#i-get-errors-from-the-no-undef-rule-about-global-variables-not-being-defined-even-though-there-are-no-typescript-errors
			'no-undef': 'off'
		}
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: {
			parserOptions: {
				projectService: true,
				extraFileExtensions: ['.svelte'],
				parser: ts.parser,
				svelteConfig
			}
		}
	},
	{
		rules: {
			// The syntax highlighters (SourcePane / TurtlePane) escape every span
			// through escapeHtml() before interpolating, so {@html} is safe here;
			// the rule can't see the escaping and would force a noisier per-line
			// disable in each file.
			'svelte/no-at-html-tags': 'off',
			// The only Map/Set instances flagged are transient locals built inside
			// $derived.by() and immediately reduced to arrays — they are not
			// reactive state, so SvelteMap/SvelteSet would be wrong, not safer.
			'svelte/prefer-svelte-reactivity': 'off',
			// Internal nav uses plain static hrefs by design; the app has no base
			// path, so resolve() would add ceremony without behaviour change.
			'svelte/no-navigation-without-resolve': 'off',
			// Allow `_`-prefixed names to mark intentionally-unused bindings (e.g.
			// the rest-omit pattern `const { [id]: _x, ...rest } = obj`).
			'@typescript-eslint/no-unused-vars': [
				'error',
				{ argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }
			]
		}
	}
);
