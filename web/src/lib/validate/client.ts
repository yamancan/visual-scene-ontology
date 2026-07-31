// Main-thread client for the Pyodide validation worker: a LAZY singleton
// with typed promise RPC. The core payload invariant of the static studio
// lives here — the worker (and its ~14MB cached runtime download) is not
// constructed until the first operation or an explicit warmup() prefetch, so
// the keyless demo/gallery path never pays a single Pyodide byte.
//
// Failure is designed, not inherited: a runtime that cannot boot (wasm
// compile refused, out of memory on a low-end device) resolves to a stable
// 'unavailable' status with CLI instructions instead of a spinner. Callers
// keep the extracted document — an operation that cannot run rejects with
// ValidationUnavailableError and destroys nothing.

import {
	toConformanceReport,
	type GateResult,
	type ValidateResult,
	type VsonOps
} from './pyodide-ops';
import type { WorkerPhase, WorkerRequest, WorkerResponse } from './vson.worker';

export { toConformanceReport };
export type { GateResult, ValidateResult, WorkerPhase };

export type UnavailableReason = 'wasm-compile-failed' | 'out-of-memory' | 'boot-failed';

export type ValidationStatus =
	/** Worker not spawned; nothing downloaded. The keyless resting state. */
	| { state: 'cold' }
	| { state: 'starting'; phase: WorkerPhase }
	| { state: 'ready' }
	| { state: 'unavailable'; reason: UnavailableReason; message: string };

/** Shown by the designed failure state; the document itself is preserved. */
export const VALIDATION_UNAVAILABLE_HELP =
	'Validation could not run on this device. Your extracted document is intact — ' +
	'copy it and verify locally with the CLI: `vson validate scene.ttl` ' +
	'(https://github.com/yamancan/visual-scene-ontology).';

export class ValidationUnavailableError extends Error {
	readonly reason: UnavailableReason;
	readonly help = VALIDATION_UNAVAILABLE_HELP;
	constructor(reason: UnavailableReason, message: string) {
		super(message);
		this.name = 'ValidationUnavailableError';
		this.reason = reason;
	}
}

function classify(message: string): UnavailableReason {
	const m = message.toLowerCase();
	if (m.includes('webassembly') || m.includes('wasm')) return 'wasm-compile-failed';
	if (m.includes('out of memory') || m.includes('oom') || m.includes('allocation'))
		return 'out-of-memory';
	return 'boot-failed';
}

interface Pending {
	resolve: (value: string | ValidateResult) => void;
	reject: (reason: Error) => void;
	onGate1?: (gate1: GateResult) => void;
}

/** Async mirror of the worker-side VsonOps surface. */
export type ValidationOps = {
	[K in keyof VsonOps]: (...args: Parameters<VsonOps[K]>) => Promise<ReturnType<VsonOps[K]>>;
};

export class ValidationClient implements ValidationOps {
	#worker: Worker | null = null;
	#pending = new Map<number, Pending>();
	#nextId = 1;
	#status: ValidationStatus = { state: 'cold' };
	#listeners = new Set<(status: ValidationStatus) => void>();

	/** Current lifecycle status (cold / starting+phase / ready / unavailable). */
	get status(): ValidationStatus {
		return this.#status;
	}

	/** Subscribe to status changes; returns an unsubscribe function. */
	subscribe(listener: (status: ValidationStatus) => void): () => void {
		this.#listeners.add(listener);
		listener(this.#status);
		return () => this.#listeners.delete(listener);
	}

	/**
	 * Boot the runtime without running an operation — call it while a model
	 * request is in flight so the 10-30s of chat latency absorbs the one-time
	 * download.
	 */
	async warmup(): Promise<void> {
		await this.#request('warmup', '');
	}

	p2t(vsonP: string): Promise<string> {
		return this.#request('p2t', vsonP) as Promise<string>;
	}

	x2t(vsonX: string): Promise<string> {
		return this.#request('x2t', vsonX) as Promise<string>;
	}

	/**
	 * Two-gate verdict. `onGate1` fires with the SHACL result (~0.2s) before
	 * the OWL 2 RL closure (~2.8s) finalizes conformance — the hook the
	 * progressive verdict UI hangs off.
	 */
	validate(turtle: string, onGate1?: (gate1: GateResult) => void): Promise<ValidateResult> {
		return this.#request('validate', turtle, onGate1) as Promise<ValidateResult>;
	}

	caption(turtle: string): Promise<string> {
		return this.#request('caption', turtle) as Promise<string>;
	}

	fol(turtle: string): Promise<string> {
		return this.#request('fol', turtle) as Promise<string>;
	}

	#setStatus(status: ValidationStatus): void {
		this.#status = status;
		for (const listener of this.#listeners) listener(status);
	}

	#ensureWorker(): Worker {
		if (!this.#worker) {
			this.#worker = new Worker(new URL('./vson.worker.ts', import.meta.url), {
				type: 'module'
			});
			this.#setStatus({ state: 'starting', phase: 'downloading' });
			this.#worker.addEventListener('message', (event: MessageEvent<WorkerResponse>) => {
				this.#onMessage(event.data);
			});
			this.#worker.addEventListener('error', (event) => {
				this.#fail(event.message || 'worker crashed');
			});
		}
		return this.#worker;
	}

	#onMessage(msg: WorkerResponse): void {
		switch (msg.type) {
			case 'progress':
				this.#setStatus(
					msg.phase === 'ready' ? { state: 'ready' } : { state: 'starting', phase: msg.phase }
				);
				return;
			case 'gate1':
				this.#pending.get(msg.id)?.onGate1?.(msg.gate1);
				return;
			case 'result': {
				const pending = this.#pending.get(msg.id);
				this.#pending.delete(msg.id);
				pending?.resolve(msg.result);
				return;
			}
			case 'error': {
				if (msg.fatal) {
					this.#fail(msg.message);
					return;
				}
				const pending = this.#pending.get(msg.id);
				this.#pending.delete(msg.id);
				pending?.reject(new Error(msg.message));
				return;
			}
		}
	}

	/** Runtime boot failed: settle into the designed unavailable state. */
	#fail(message: string): void {
		const reason = classify(message);
		this.#setStatus({ state: 'unavailable', reason, message });
		const error = new ValidationUnavailableError(reason, message);
		for (const pending of this.#pending.values()) pending.reject(error);
		this.#pending.clear();
		this.#worker?.terminate();
		this.#worker = null;
	}

	#request(
		op: WorkerRequest['op'],
		payload: string,
		onGate1?: (gate1: GateResult) => void
	): Promise<string | ValidateResult> {
		if (this.#status.state === 'unavailable') {
			const { reason, message } = this.#status;
			return Promise.reject(new ValidationUnavailableError(reason, message));
		}
		const worker = this.#ensureWorker();
		const id = this.#nextId++;
		return new Promise<string | ValidateResult>((resolve, reject) => {
			this.#pending.set(id, { resolve, reject, onGate1 });
			worker.postMessage({ id, op, payload } satisfies WorkerRequest);
		});
	}
}

let singleton: ValidationClient | null = null;

/**
 * The lazy singleton. Calling this constructs only the (tiny) client object;
 * the worker — and every Pyodide byte behind it — waits for the first
 * operation or warmup().
 */
export function validationClient(): ValidationClient {
	if (!singleton) singleton = new ValidationClient();
	return singleton;
}
