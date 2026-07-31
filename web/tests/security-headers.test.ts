// The response-header policy, asserted rather than assumed.
//
// The CSP is no longer SvelteKit config: scripts/gen-headers.js derives it
// from the actual build output and writes build/_headers for Cloudflare
// Pages. None of that can be proven by reading a rendered page in a test —
// CSP is enforced by a browser, and there is no browser here. What a test
// CAN do is pin the three things that silently rot:
//
//   1. the generator's contract (every inline script hashed, the exact
//      directive set, the zero-inline-scripts canary that refuses to emit a
//      hydration-blocking policy),
//   2. app.html carrying zero inline scripts (the theme guard is an external
//      static/theme-init.js licensed by script-src 'self'; a hand-written
//      inline script snuck back in would need nonce or hash plumbing again),
//   3. the constant header set (so adding one is a deliberate edit here, and
//      deleting one fails).
//
// Everything runs against SYNTHETIC HTML, never build output: CI runs
// `pnpm test` before `pnpm build` (ci.yml), so build/ does not exist yet.
// The build-output assertions (no server/ dir, no leftover nonce
// placeholder) live inside gen-headers.js itself, enforced by `pnpm build`.

import { describe, it, expect } from 'vitest';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { generateHeaders } from '../scripts/gen-headers.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP_HTML = resolve(__dirname, '../src/app.html');

// Stand-ins for SvelteKit's per-page hydration bootstrap — the only inline
// scripts that exist in real build output after app.html went inline-free.
const BOOTSTRAP_A = '{\n\t__sveltekit_1abc = {};\n\timport("/_app/immutable/entry/start.js");\n}';
const BOOTSTRAP_B = '{\n\t__sveltekit_1abc = {};\n\timport("/_app/immutable/entry/other.js");\n}';

function pageWith(inlineBody: string): string {
	// Includes an external script tag to prove src= scripts are never hashed.
	return (
		'<!doctype html><html><head><script src="/theme-init.js"></script></head>' +
		`<body><script>${inlineBody}</script></body></html>`
	);
}

function cspHashOf(body: string): string {
	return `'sha256-${createHash('sha256').update(body, 'utf8').digest('base64')}'`;
}

/** Extract the indented header lines of one rule block from a _headers body. */
function ruleBlock(headers: string, rule: string): string[] {
	const lines = headers.split('\n');
	const start = lines.indexOf(rule);
	expect(start).toBeGreaterThanOrEqual(0);
	const block: string[] = [];
	for (let i = start + 1; i < lines.length && lines[i].startsWith('  '); i++) {
		block.push(lines[i].trim());
	}
	return block;
}

/** Parse the Content-Security-Policy value of the /* rule into a map. */
function cspDirectives(headers: string): Map<string, string> {
	const line = ruleBlock(headers, '/*').find((l) => l.startsWith('Content-Security-Policy:'));
	expect(line).toBeDefined();
	const value = (line as string).slice('Content-Security-Policy:'.length).trim();
	const directives = new Map<string, string>();
	for (const part of value.split(';')) {
		const p = part.trim();
		const space = p.indexOf(' ');
		expect(space).toBeGreaterThan(0); // every directive here carries a value
		directives.set(p.slice(0, space), p.slice(space + 1));
	}
	return directives;
}

describe('generated content-security-policy', () => {
	const headers = generateHeaders([pageWith(BOOTSTRAP_A), pageWith(BOOTSTRAP_B)]);
	const csp = cspDirectives(headers);

	it('hashes every inline script and nothing else', () => {
		const script = csp.get('script-src') ?? '';
		expect(script).toContain(cspHashOf(BOOTSTRAP_A));
		expect(script).toContain(cspHashOf(BOOTSTRAP_B));
		// The src= theme-init script must not be hashed: exactly two sources.
		expect(headers.match(/'sha256-/g)).toHaveLength(2);
	});

	it('deduplicates identical bootstraps across pages', () => {
		const one = generateHeaders([pageWith(BOOTSTRAP_A), pageWith(BOOTSTRAP_A)]);
		expect(one.match(/'sha256-/g)).toHaveLength(1);
	});

	it('declares exactly the intended directives', () => {
		expect([...csp.keys()].sort()).toEqual([
			'base-uri',
			'connect-src',
			'default-src',
			'form-action',
			'frame-ancestors',
			'img-src',
			'object-src',
			'script-src',
			'style-src',
			'style-src-attr',
			'worker-src'
		]);
	});

	it('locks down the directives that matter', () => {
		expect(csp.get('default-src')).toBe("'self'");
		expect(csp.get('object-src')).toBe("'none'");
		expect(csp.get('base-uri')).toBe("'self'");
		expect(csp.get('form-action')).toBe("'self'");
		// Delivered as a real response header, so frame-ancestors is
		// spec-effective — kit's meta-delivered CSP never could enforce it.
		expect(csp.get('frame-ancestors')).toBe("'none'");
		expect(csp.get('worker-src')).toBe("'self'");
	});

	it('adds exactly two deltas over the old baseline: wasm and openrouter', () => {
		// script-src: 'self' + 'wasm-unsafe-eval' (Pyodide compiles wasm inside
		// the worker; a dedicated worker's CSP comes from its own script's
		// response headers, which this /* rule covers) + the hashes.
		expect(csp.get('script-src')).toMatch(/^'self' 'wasm-unsafe-eval' 'sha256-/);
		// connect-src: the visitor's own key rides browser -> OpenRouter.
		expect(csp.get('connect-src')).toBe("'self' https://openrouter.ai");
	});

	it('never allows inline or evaluated script', () => {
		// Matched as quoted CSP tokens: 'wasm-unsafe-eval' licenses wasm
		// compilation only and must not be confused with 'unsafe-eval'.
		const script = csp.get('script-src') ?? '';
		expect(script).not.toContain("'unsafe-inline'");
		expect(script).not.toContain("'unsafe-eval'");
		expect(script).not.toContain("'strict-dynamic'");
	});

	it('allows the inline styles Svelte and the bbox overlay emit', () => {
		expect(csp.get('style-src')).toBe("'self' 'unsafe-inline'");
		expect(csp.get('style-src-attr')).toBe("'unsafe-inline'");
	});

	it('allows data: images for previews and crops, but not blob:', () => {
		expect(csp.get('img-src')).toBe("'self' data:");
	});

	it('refuses to emit when the scan finds zero inline scripts', () => {
		// SvelteKit always emits a hydration bootstrap; an empty scan means the
		// scan broke, and its CSP would block hydration site-wide.
		expect(() => generateHeaders([])).toThrow(/zero inline scripts/);
		expect(() =>
			generateHeaders(['<html><head><script src="/a.js"></script></head></html>'])
		).toThrow(/zero inline scripts/);
	});
});

describe('constant security headers', () => {
	const block = ruleBlock(generateHeaders([pageWith(BOOTSTRAP_A)]), '/*');
	const names = block.map((l) => l.slice(0, l.indexOf(':')));

	it('is exactly the intended header set', () => {
		expect([...names].sort()).toEqual([
			'Content-Security-Policy',
			'Cross-Origin-Opener-Policy',
			'Cross-Origin-Resource-Policy',
			'Permissions-Policy',
			'Referrer-Policy',
			'Strict-Transport-Security',
			'X-Content-Type-Options',
			'X-Frame-Options'
		]);
	});

	it('carries the intended values', () => {
		expect(block).toContain('X-Content-Type-Options: nosniff');
		expect(block).toContain('Referrer-Policy: strict-origin-when-cross-origin');
		expect(block).toContain('X-Frame-Options: DENY');
		expect(block).toContain(
			'Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()'
		);
		expect(block).toContain('Cross-Origin-Opener-Policy: same-origin');
		expect(block).toContain('Cross-Origin-Resource-Policy: same-origin');
	});

	it('pins HSTS now that every response is TLS', () => {
		// Cloudflare Pages is always HTTPS, so the was-it-https conditional the
		// old server hook needed is gone: HSTS joins the constant set.
		expect(block).toContain('Strict-Transport-Security: max-age=31536000; includeSubDomains');
	});
});

describe('caching', () => {
	it('serves the pyodide runtime immutable', () => {
		// 14MB, content only ever replaced wholesale by a deploy: pay once.
		const block = ruleBlock(generateHeaders([pageWith(BOOTSTRAP_A)]), '/pyodide/*');
		expect(block).toEqual(['Cache-Control: public, max-age=31536000, immutable']);
	});
});

describe('app.html inline-script hygiene', () => {
	const html = readFileSync(APP_HTML, 'utf8');

	// Open tags of scripts with no src= — i.e. the ones whose body is inline
	// and would therefore need a hash under script-src.
	const inlineScripts = html.match(/<script\b(?![^>]*\bsrc=)[^>]*>/g) ?? [];

	it('carries zero inline scripts', () => {
		// The theme guard lives in static/theme-init.js, loaded as a blocking
		// external script that script-src 'self' licenses with no per-script
		// plumbing. An inline script reappearing here would ship blocked.
		expect(inlineScripts.length).toBe(0);
	});

	it('loads the external theme guard as a blocking head script', () => {
		expect(html).toContain('<script src="/theme-init.js"></script>');
	});

	it('has no nonce placeholder left behind', () => {
		// Nothing replaces the placeholder anymore; gen-headers.js also fails
		// the build if it ever reappears in emitted HTML.
		expect(html).not.toContain('%sveltekit.nonce%');
	});
});
