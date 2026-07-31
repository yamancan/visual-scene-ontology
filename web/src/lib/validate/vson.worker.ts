// Dedicated module worker hosting the Pyodide verification stack. Thin by
// design: all real logic lives in pyodide-ops.ts (shared with the offline
// Node parity test); this file only speaks the postMessage protocol.
//
// Everything it loads is same-origin: the vendored runtime under /pyodide/,
// the committed wheels under /pyodide/wheels/, and the repo sources inlined
// into its own bundle — zero third-party origins, zero index lookups.

import {
	initVsonOps,
	wheelUrls,
	type GateResult,
	type ValidateResult,
	type VsonOps
} from './pyodide-ops';

const PYODIDE_BASE = '/pyodide';

// ── protocol (client.ts type-imports these; erased at runtime) ─────────────

export type WorkerPhase = 'downloading' | 'booting' | 'installing' | 'ready';

export type WorkerOp = 'p2t' | 'x2t' | 'validate' | 'caption' | 'fol';

export interface WorkerRequest {
	id: number;
	/** 'warmup' boots the runtime without running an operation (prefetch). */
	op: WorkerOp | 'warmup';
	payload: string;
}

export type WorkerResponse =
	| { type: 'progress'; phase: WorkerPhase }
	| { type: 'gate1'; id: number; gate1: GateResult }
	| { type: 'result'; id: number; result: string | ValidateResult }
	/** fatal: the runtime itself failed to boot — the worker is unusable. */
	| { type: 'error'; id: number; message: string; fatal: boolean };

// ── worker body ────────────────────────────────────────────────────────────

const ctx = self as unknown as Worker;

function post(msg: WorkerResponse): void {
	ctx.postMessage(msg);
}

function messageOf(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}

let opsPromise: Promise<VsonOps> | null = null;

async function boot(): Promise<VsonOps> {
	post({ type: 'progress', phase: 'downloading' });
	// Dynamic import of the VENDORED loader — never the npm package, which is
	// a devDependency for types and the Node test only. @vite-ignore: this is
	// a runtime URL on our own origin, not a module for the bundler.
	const { loadPyodide } = (await import(/* @vite-ignore */ `${PYODIDE_BASE}/pyodide.mjs`)) as {
		loadPyodide: typeof import('pyodide').loadPyodide;
	};
	post({ type: 'progress', phase: 'booting' });
	const pyodide = await loadPyodide({ indexURL: `${PYODIDE_BASE}/` });
	post({ type: 'progress', phase: 'installing' });
	const ops = await initVsonOps(pyodide, { wheelUrls: wheelUrls() });
	post({ type: 'progress', phase: 'ready' });
	return ops;
}

function ensureOps(): Promise<VsonOps> {
	if (!opsPromise) opsPromise = boot();
	return opsPromise;
}

ctx.addEventListener('message', (event: MessageEvent<WorkerRequest>) => {
	void (async () => {
		const { id, op, payload } = event.data;

		let ops: VsonOps;
		try {
			ops = await ensureOps();
		} catch (e) {
			// Boot is retryable on a later request; the client decides whether
			// this device gets a retry or the designed unavailable state.
			opsPromise = null;
			post({ type: 'error', id, message: messageOf(e), fatal: true });
			return;
		}

		if (op === 'warmup') {
			post({ type: 'result', id, result: '' });
			return;
		}

		try {
			if (op === 'validate') {
				const result = ops.validate(payload, (gate1) => post({ type: 'gate1', id, gate1 }));
				post({ type: 'result', id, result });
			} else {
				post({ type: 'result', id, result: ops[op](payload) });
			}
		} catch (e) {
			post({ type: 'error', id, message: messageOf(e), fatal: false });
		}
	})();
});
