// Response headers that are the same on every response, whatever it is.
//
// Kept as plain data in one place so the set is auditable at a glance and so a
// test can assert the exact key set rather than re-deriving it. The
// Content-Security-Policy is NOT here: SvelteKit builds it per response (it has
// to splice in the nonce), so it is configured in svelte.config.js instead.
//
// hooks.server.ts applies these. Anything adapter-node's static file server
// answers before hooks run — everything under static/ — does not get them; see
// the "Response headers" section of web/README.md.

export const SECURITY_HEADERS: Readonly<Record<string, string>> = Object.freeze({
	// Never let a browser second-guess our content-type. Turtle and JSON-LD
	// bodies are the ones that would sniff into something executable.
	'x-content-type-options': 'nosniff',
	// Send the full URL same-origin, bare origin cross-origin, nothing when
	// downgrading. Image paths and scene ids stay off third-party referers.
	'referrer-policy': 'strict-origin-when-cross-origin',
	// frame-ancestors 'none' in the CSP is the modern spelling; this is the
	// legacy one, for the browsers that only understand the legacy one.
	'x-frame-options': 'DENY',
	// The studio reads files the user hands it and nothing else. No camera, no
	// microphone, no location, no payment handler, no USB.
	'permissions-policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
	// Break the opener relationship with any cross-origin window, so a page that
	// opens the studio cannot reach into it.
	'cross-origin-opener-policy': 'same-origin',
	// Refuse to be embedded as a subresource by another origin.
	'cross-origin-resource-policy': 'same-origin'
});

/**
 * HSTS is conditional, not part of the constant set: sending it over plain HTTP
 * is meaningless (browsers ignore it), and sending it from a local dev server
 * would pin localhost to HTTPS in the developer's browser for a year.
 */
export const HSTS_HEADER = 'strict-transport-security';
export const HSTS_VALUE = 'max-age=31536000; includeSubDomains';
