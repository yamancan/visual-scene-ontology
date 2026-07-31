// Generate build/_headers for Cloudflare Pages from the ACTUAL build output.
//
// The studio is fully prerendered, so the only inline scripts in existence
// are SvelteKit's own per-page hydration bootstraps. This script scans every
// emitted HTML file, sha256-hashes every inline script it finds, and emits
// ONE real Content-Security-Policy response header covering every response —
// including static assets and the validation worker script, which the old
// adapter-node hook never reached. Because the hashes are recomputed from
// build output on every build, drift between the CSP and what SvelteKit
// emits is impossible by construction.
//
// A dedicated worker's CSP comes from its own script's response headers, so
// the /* rule below is also what licenses wasm compilation inside the
// Pyodide worker ('wasm-unsafe-eval'). COEP is deliberately absent:
// single-threaded Pyodide needs no SharedArrayBuffer.
//
// Exported as generateHeaders() so tests/security-headers.test.ts can pin
// hashing, the directive set, and the canary against synthetic HTML — CI
// runs `pnpm test` BEFORE `pnpm build`, so the test must never read build
// output. The build-output assertions (no server/ dir, no leftover
// %sveltekit.nonce%) live in the CLI half below, enforced by `pnpm build`.

import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Open tags of scripts with no src= — the ones whose body is inline and
// therefore needs a hash under script-src. Same shape the app.html hygiene
// test uses, extended to capture the body.
const INLINE_SCRIPT_RE = /<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;

/**
 * The constant response headers, carried over verbatim from the deleted
 * $lib/server/security-headers.ts. HSTS joins the constant set here because
 * Cloudflare Pages is always TLS — the dev-server concern that kept it
 * conditional in the hook no longer exists.
 * @type {ReadonlyArray<readonly [name: string, value: string]>}
 */
const SECURITY_HEADERS = [
	['X-Content-Type-Options', 'nosniff'],
	['Referrer-Policy', 'strict-origin-when-cross-origin'],
	['X-Frame-Options', 'DENY'],
	['Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=()'],
	['Cross-Origin-Opener-Policy', 'same-origin'],
	['Cross-Origin-Resource-Policy', 'same-origin'],
	['Strict-Transport-Security', 'max-age=31536000; includeSubDomains']
];

/**
 * Collect the sha256 CSP hash source for every inline script in the given
 * HTML documents, deduplicated, in first-seen order.
 * @param {string[]} htmlSources
 * @returns {string[]} e.g. ["'sha256-…base64…'"]
 */
function inlineScriptHashes(htmlSources) {
	/** @type {Set<string>} */
	const hashes = new Set();
	for (const html of htmlSources) {
		for (const match of html.matchAll(INLINE_SCRIPT_RE)) {
			const body = match[1];
			hashes.add(`'sha256-${createHash('sha256').update(body, 'utf8').digest('base64')}'`);
		}
	}
	return [...hashes];
}

/**
 * Build the complete Cloudflare Pages _headers file body from the emitted
 * HTML pages. Throws if no inline script is found anywhere — SvelteKit
 * always emits a per-page hydration bootstrap, so an empty scan means the
 * scan itself broke, and shipping its CSP would block hydration site-wide.
 * @param {string[]} htmlSources the text of every emitted HTML page
 * @returns {string} the _headers file body
 */
export function generateHeaders(htmlSources) {
	const hashes = inlineScriptHashes(htmlSources);
	if (hashes.length === 0) {
		throw new Error(
			'gen-headers: found zero inline scripts across ' +
				htmlSources.length +
				' HTML page(s). SvelteKit always emits an inline hydration bootstrap, ' +
				'so the scan is broken — refusing to emit a CSP that would block hydration.'
		);
	}

	// The baseline directives from the deleted svelte.config.js csp block,
	// with exactly two deltas: script-src gains 'wasm-unsafe-eval' (Pyodide)
	// plus the computed hashes, and connect-src gains https://openrouter.ai
	// (direct BYOK). Everything else is carried over unchanged.
	const csp = [
		"default-src 'self'",
		`script-src 'self' 'wasm-unsafe-eval' ${hashes.join(' ')}`,
		"connect-src 'self' https://openrouter.ai",
		"worker-src 'self'",
		"img-src 'self' data:",
		"style-src 'self' 'unsafe-inline'",
		"style-src-attr 'unsafe-inline'",
		"object-src 'none'",
		"base-uri 'self'",
		"form-action 'self'",
		"frame-ancestors 'none'"
	].join('; ');

	const lines = ['/*', `  Content-Security-Policy: ${csp}`];
	for (const [name, value] of SECURITY_HEADERS) {
		lines.push(`  ${name}: ${value}`);
	}
	// The 14MB Pyodide runtime is paid at most once per browser: the files
	// are only ever replaced wholesale by a new deploy, never edited.
	lines.push('', '/pyodide/*', '  Cache-Control: public, max-age=31536000, immutable', '');
	return lines.join('\n');
}

/**
 * CLI half: scan build/, assert the output is genuinely static, and write
 * build/_headers. Runs as the second step of `pnpm build`.
 * @returns {void}
 */
function main() {
	const buildDir = resolve(dirname(fileURLToPath(import.meta.url)), '../build');
	if (!existsSync(buildDir)) {
		throw new Error(`gen-headers: no build directory at ${buildDir} — run vite build first.`);
	}
	// adapter-static must not leave a server half behind; a server/ dir here
	// means the adapter swap regressed and the "static" deploy would silently
	// drop functionality.
	if (existsSync(join(buildDir, 'server'))) {
		throw new Error('gen-headers: build/server exists — the build output is not static.');
	}

	const htmlPaths = readdirSync(buildDir, { recursive: true, encoding: 'utf8' })
		.filter((p) => p.endsWith('.html'))
		.map((p) => join(buildDir, p))
		.sort();
	const htmlSources = htmlPaths.map((p) => {
		const html = readFileSync(p, 'utf8');
		// The nonce placeholder must never survive into emitted HTML: nothing
		// replaces it anymore, and a literal %sveltekit.nonce% attribute would
		// mean app.html regressed to an inline-script setup this CSP no longer
		// licenses.
		if (html.includes('%sveltekit.nonce%')) {
			throw new Error(`gen-headers: ${p} still contains %sveltekit.nonce%.`);
		}
		return html;
	});

	const body = generateHeaders(htmlSources);
	writeFileSync(join(buildDir, '_headers'), body, 'utf8');
	const hashCount = (body.match(/'sha256-/g) ?? []).length;
	console.log(
		`gen-headers: hashed ${hashCount} inline script(s) across ` +
			`${htmlPaths.length} page(s) -> build/_headers`
	);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
	main();
}
