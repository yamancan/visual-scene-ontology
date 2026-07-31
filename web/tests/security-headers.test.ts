// The response-header policy, asserted rather than assumed.
//
// None of this can be proven by reading a rendered page in a test — CSP is
// enforced by a browser, and there is no browser here. What a test CAN do is
// pin the three things that silently rot:
//
//   1. the CSP the app ships (a directive dropped in a refactor is invisible
//      until someone audits the live headers),
//   2. app.html carrying zero inline scripts (the theme guard is an external
//      static/theme-init.js licensed by script-src 'self'; a hand-written
//      inline script snuck back in would need nonce or hash plumbing again),
//   3. the constant header set (so adding one is a deliberate edit here, and
//      deleting one fails).

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import config from '../svelte.config.js';
import { SECURITY_HEADERS, HSTS_HEADER, HSTS_VALUE } from '../src/lib/server/security-headers';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP_HTML = resolve(__dirname, '../src/app.html');

describe('content-security-policy', () => {
	const csp = config.kit?.csp;

	it('uses nonce mode', () => {
		// Hash mode would hash only SvelteKit's own scripts, leaving the
		// hand-written app.html script with neither hash nor nonce.
		expect(csp?.mode).toBe('nonce');
	});

	it('declares exactly the intended directives', () => {
		expect(Object.keys(csp?.directives ?? {}).sort()).toEqual([
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
		const d = csp?.directives ?? {};
		expect(d['default-src']).toEqual(['self']);
		expect(d['script-src']).toEqual(['self']);
		expect(d['object-src']).toEqual(['none']);
		expect(d['base-uri']).toEqual(['self']);
		expect(d['form-action']).toEqual(['self']);
		expect(d['frame-ancestors']).toEqual(['none']);
		expect(d['worker-src']).toEqual(['self']);
	});

	it('never allows inline or evaluated script', () => {
		// The whole point of nonce mode. Styles are a separate, accepted
		// trade-off; script is not.
		const script = csp?.directives?.['script-src'] ?? [];
		expect(script).not.toContain('unsafe-inline');
		expect(script).not.toContain('unsafe-eval');
		expect(script).not.toContain('strict-dynamic');
	});

	it('allows the inline styles Svelte and the bbox overlay emit', () => {
		expect(csp?.directives?.['style-src']).toEqual(['self', 'unsafe-inline']);
		expect(csp?.directives?.['style-src-attr']).toEqual(['unsafe-inline']);
	});

	it('allows data: images for previews and crops, but not blob:', () => {
		expect(csp?.directives?.['img-src']).toEqual(['self', 'data:']);
	});

	it('restricts connect-src to this origin outside dev', () => {
		// Vitest does not set NODE_ENV=development, so this is the shipped shape.
		// The dev-only relaxation is the ws: HMR socket and nothing else.
		expect(process.env.NODE_ENV).not.toBe('development');
		expect(csp?.directives?.['connect-src']).toEqual(['self']);
	});
});

describe('app.html inline-script hygiene', () => {
	const html = readFileSync(APP_HTML, 'utf8');

	// Open tags of scripts with no src= — i.e. the ones whose body is inline
	// and would therefore need a nonce or hash under script-src 'self'.
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
		// The placeholder existed solely for the removed inline theme script.
		expect(html).not.toContain('%sveltekit.nonce%');
	});
});

describe('constant security headers', () => {
	it('is exactly the intended key set', () => {
		expect(Object.keys(SECURITY_HEADERS).sort()).toEqual([
			'cross-origin-opener-policy',
			'cross-origin-resource-policy',
			'permissions-policy',
			'referrer-policy',
			'x-content-type-options',
			'x-frame-options'
		]);
	});

	it('carries the intended values', () => {
		expect(SECURITY_HEADERS['x-content-type-options']).toBe('nosniff');
		expect(SECURITY_HEADERS['referrer-policy']).toBe('strict-origin-when-cross-origin');
		expect(SECURITY_HEADERS['x-frame-options']).toBe('DENY');
		expect(SECURITY_HEADERS['permissions-policy']).toBe(
			'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
		);
		expect(SECURITY_HEADERS['cross-origin-opener-policy']).toBe('same-origin');
		expect(SECURITY_HEADERS['cross-origin-resource-policy']).toBe('same-origin');
	});

	it('keeps HSTS out of the constant set', () => {
		// hooks.server.ts adds it only when the request arrived over https, so
		// that a dev server cannot pin localhost to HTTPS for a year.
		expect(Object.keys(SECURITY_HEADERS)).not.toContain(HSTS_HEADER);
		expect(HSTS_VALUE).toMatch(/^max-age=\d+/);
	});
});
