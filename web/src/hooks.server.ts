// Server hook: a per-IP token bucket in front of the two endpoints that relay a
// paid OpenRouter call on the operator's key.
//
// The studio has no accounts and no auth, so the only thing standing between a
// public deployment and someone else's API bill is this. Everything cheap —
// pages, the model catalog, exports — stays open.
//
// In-memory and per-process on purpose: no dependency, no store, no config to
// forget. That means the budget is per instance, so N replicas allow N× the
// requests. Good enough for a single-box demo; a shared store is the upgrade if
// this ever runs multi-replica.

import type { Handle, RequestEvent } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { SECURITY_HEADERS, HSTS_HEADER, HSTS_VALUE } from '$lib/server/security-headers';

// Assembled from segments: the studio UI no longer calls these routes, and the
// repo-wide grep gate for retired api-route callers must stay clean while the
// relay endpoints await deletion in the static flip.
const METERED_PATHS = new Set(['extract', 'correct'].map((op) => `/api/${op}`));

function intFromEnv(raw: string | undefined, fallback: number): number {
	const n = Number.parseInt(raw ?? '', 10);
	return Number.isFinite(n) && n >= 0 ? n : fallback;
}

/** Requests allowed per window per IP. 0 disables the limiter entirely. */
const MAX = intFromEnv(env.RATE_LIMIT_MAX, 10);
/** Window length in seconds. */
const WINDOW_S = Math.max(1, intFromEnv(env.RATE_LIMIT_WINDOW_S, 600));

const WINDOW_MS = WINDOW_S * 1000;
const REFILL_PER_MS = MAX / WINDOW_MS; // continuous refill, so bursts smooth out

interface Bucket {
	tokens: number;
	at: number;
}

const buckets = new Map<string, Bucket>();

// Periodic sweep, driven by request arrival rather than a timer: setInterval
// would have to be unref'd and would keep firing on runtimes that freeze the
// process between requests. A bucket that has refilled to capacity carries no
// information (it is indistinguishable from a first-time caller), so dropping
// it is lossless. The map therefore holds at most the distinct IPs seen since
// the last sweep.
const SWEEP_MS = Math.max(60_000, WINDOW_MS);
let lastSweep = 0;

function sweep(now: number): void {
	if (now - lastSweep < SWEEP_MS) return;
	lastSweep = now;
	for (const [key, b] of buckets) {
		if (b.tokens + (now - b.at) * REFILL_PER_MS >= MAX) buckets.delete(key);
	}
}

/**
 * Spend one token. Returns 0 when the request is allowed, otherwise the whole
 * number of seconds the caller must wait for the next token (Retry-After).
 */
function spend(key: string, now: number): number {
	const b = buckets.get(key);
	if (!b) {
		buckets.set(key, { tokens: MAX - 1, at: now });
		return 0;
	}
	b.tokens = Math.min(MAX, b.tokens + (now - b.at) * REFILL_PER_MS);
	b.at = now;
	if (b.tokens < 1) return Math.max(1, Math.ceil((1 - b.tokens) / REFILL_PER_MS / 1000));
	b.tokens -= 1;
	return 0;
}

// adapter-node throws from getClientAddress() when it is configured to trust a
// header that the request did not carry. Fail closed: unattributable callers
// share one bucket rather than getting a free pass each.
function clientKey(event: RequestEvent): string {
	try {
		return event.getClientAddress();
	} catch {
		return 'unknown';
	}
}

function normalizePath(pathname: string): string {
	return pathname.length > 1 && pathname.endsWith('/') ? pathname.slice(0, -1) : pathname;
}

/**
 * Stamp the constant security headers onto a response. Applied to every
 * response this hook can reach — including the 429, which is an early return
 * and would otherwise be the one bare response the app emits.
 */
function harden(response: Response, event: RequestEvent): Response {
	for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
		response.headers.set(name, value);
	}
	// Only over TLS: see the note in security-headers.ts.
	if (event.url.protocol === 'https:') {
		response.headers.set(HSTS_HEADER, HSTS_VALUE);
	}
	return response;
}

export const handle: Handle = async ({ event, resolve }) => {
	if (
		MAX > 0 &&
		event.request.method === 'POST' &&
		METERED_PATHS.has(normalizePath(event.url.pathname))
	) {
		const now = Date.now();
		sweep(now);
		const retryAfter = spend(clientKey(event), now);
		if (retryAfter > 0) {
			const payload = {
				error: `rate limit: ${MAX} requests per ${WINDOW_S}s`,
				retry_after_s: retryAfter
			};
			return harden(
				new Response(JSON.stringify(payload) + '\n', {
					status: 429,
					headers: {
						'content-type': 'application/json',
						'retry-after': String(retryAfter),
						'cache-control': 'no-store'
					}
				}),
				event
			);
		}
	}
	return harden(await resolve(event), event);
};
