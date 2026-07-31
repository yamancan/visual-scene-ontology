<script lang="ts">
	import { scene, isMeaningfulEdit } from '$lib/scene.svelte';
	import { correctScene, type CorrectRequest } from '$lib/extract/orchestrator';
	import { OpenRouterError } from '$lib/openrouter/client';
	import type { VsonEnvelope } from '$lib/types';
	import type { Notation } from '$lib/scene.svelte';

	// The staged-corrections tray. Shown over the bottom of the scene editor
	// whenever the user has queued at least one fix (entity edit or scene note)
	// or while a correction round-trip is in flight / errored. Flushes the
	// accumulated edits through the client correction orchestrator as a
	// targeted correction (not a re-extraction) and swaps in the returned
	// envelope.

	let visible = $derived(scene.pendingCount > 0 || scene.correctionStatus !== 'idle');
	let correcting = $derived(scene.correctionStatus === 'correcting');
	let pendingCount = $derived(scene.pendingCount);

	// Mirror SourcePane / contract: prefer the notation form that actually
	// carries a body, honoring the sticky preference when it has content.
	function pickSource(env: VsonEnvelope): { notation: Notation; source: string } | null {
		const pBody = (env.vson_p?.trim().length ?? 0) > 0;
		const xBody = (env.vson_x?.trim().length ?? 0) > 0;
		if (scene.notation === 'x' && xBody) return { notation: 'x', source: env.vson_x! };
		if (pBody) return { notation: 'p', source: env.vson_p };
		if (xBody) return { notation: 'x', source: env.vson_x! };
		return null;
	}

	// Only forward an inline image when the preview is a real jpeg/png data URL.
	// Gallery scenes (or other sources) lack one — the orchestrator treats the
	// image as optional, so we simply omit it.
	const DATA_URL_RE = /^data:(image\/(?:jpeg|png));base64,(.+)$/;

	// Same taxonomy as the dropzone (401 key / 402 credits / 429 provider limit
	// / network); the ValidationUnavailableError match is by name so the worker
	// chunk stays out of the page bundle.
	function correctFailure(e: unknown): string {
		if (e instanceof OpenRouterError) return e.message;
		const err = e as Error & { help?: string };
		if (err?.name === 'ValidationUnavailableError') return err.help ?? err.message;
		return `correct failed · ${err?.message ?? String(e)}`;
	}

	async function send() {
		const env = scene.envelope;
		if (!env || correcting || pendingCount === 0) return;

		const picked = pickSource(env);
		if (!picked) {
			scene.setCorrectionStatus('error', 'no source notation to correct');
			return;
		}

		// Drop no-op edits (opened-then-cleared) so we never burn an LLM
		// round-trip applying nothing. Matches the pendingCount badge.
		const corrections = Object.entries(scene.pendingEdits)
			.filter(([, e]) => isMeaningfulEdit(e))
			.map(([id, e]) => ({ id, ...e }));

		const req: CorrectRequest = {
			notation: picked.notation,
			source: picked.source,
			corrections,
			sceneNote: scene.sceneNote,
			model: scene.model,
			// Progressive verdict: SHACL result ~0.2s into each round, ahead of
			// the OWL RL gate — rendered as the quiet line under the actions.
			onGate1: (gate1) => scene.setGate1(gate1)
		};

		const m = scene.imagePreview?.match(DATA_URL_RE);
		if (m) {
			req.mime = m[1] as 'image/jpeg' | 'image/png';
			req.image_b64 = m[2];
		}

		scene.setCorrectionStatus('correcting');
		scene.setGate1(null);
		try {
			const corrected = await correctScene(req);
			// setEnvelope clears the staged corrections + selection (and the
			// interim gate line) for us.
			scene.setEnvelope(corrected);
			scene.setCorrectionStatus('idle');
		} catch (e) {
			scene.setGate1(null);
			scene.setCorrectionStatus('error', correctFailure(e));
		}
	}
</script>

{#if visible}
	<div class="bar" role="region" aria-label="Pending corrections">
		<div class="row">
			<span class="count font-mono">
				{pendingCount} pending fix{pendingCount === 1 ? '' : 'es'}
			</span>
			<div class="actions">
				<button
					type="button"
					class="clear"
					onclick={() => scene.clearCorrections()}
					disabled={correcting}
				>
					clear
				</button>
				<button
					type="button"
					class="send"
					onclick={send}
					disabled={correcting || pendingCount === 0}
				>
					{#if correcting}
						<span class="spinner" aria-hidden="true"></span>
						correcting…
					{:else}
						Send to AI →
					{/if}
				</button>
			</div>
		</div>

		<textarea
			class="note font-mono"
			placeholder="scene-level note — describe anything the per-entity fixes miss"
			value={scene.sceneNote}
			oninput={(e) => scene.setSceneNote((e.currentTarget as HTMLTextAreaElement).value)}
			disabled={correcting}
			rows="2"
		></textarea>

		{#if correcting && scene.gate1}
			<p class="gate font-mono">
				{scene.gate1.conforms
					? 'shacl passed · consistency check running…'
					: 'shacl violations · repair round in flight…'}
			</p>
		{/if}

		{#if scene.correctionError}
			<p class="err font-mono" role="alert">{scene.correctionError}</p>
		{/if}
	</div>
{/if}

<style>
	/* Floating tray anchored to the bottom of the scene stage — same blur /
	 * token treatment as SceneFlow's frame-meta chip-rail so it reads as part
	 * of the canvas chrome, not the rail. */
	.bar {
		position: absolute;
		left: var(--s3);
		right: var(--s3);
		bottom: var(--s3);
		z-index: 6;
		display: flex;
		flex-direction: column;
		gap: var(--s2);
		padding: var(--s2) var(--s3);
		background: color-mix(in srgb, var(--bg-1) 88%, transparent);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		box-shadow:
			0 1px 0 var(--border-1),
			0 4px 14px -8px rgba(0, 0, 0, 0.18);
		pointer-events: auto;
		max-width: calc(100% - 2 * var(--s3));
	}
	.row {
		display: flex;
		align-items: center;
		gap: var(--s3);
	}
	.count {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--fg-4);
	}
	.actions {
		display: flex;
		align-items: center;
		gap: var(--s2);
		margin-left: auto;
	}
	.clear,
	.send {
		font-family: var(--font-mono);
		font-size: var(--text-2xs);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		cursor: pointer;
		border-radius: var(--radius-sm);
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out),
			border-color var(--duration-fast) var(--ease-out);
	}
	.clear {
		padding: 4px 8px;
		background: transparent;
		border: 1px solid var(--border-1);
		color: var(--fg-4);
	}
	.clear:not(:disabled):hover {
		color: var(--fg-1);
		background: var(--bg-2);
		border-color: var(--border-2);
	}
	.send {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 12px;
		background: var(--accent);
		border: 1px solid var(--accent);
		color: var(--accent-fg, var(--bg-0));
	}
	.send:not(:disabled):hover {
		background: color-mix(in srgb, var(--accent) 88%, #000);
	}
	.clear:disabled,
	.send:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.note {
		width: 100%;
		resize: vertical;
		min-height: 2.4em;
		padding: var(--s2);
		font-size: var(--text-xs);
		line-height: 1.5;
		color: var(--fg-1);
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		outline: none;
		transition: border-color var(--duration-fast) var(--ease-out);
	}
	.note::placeholder {
		color: var(--fg-4);
	}
	.note:focus {
		border-color: var(--accent);
	}
	.note:disabled {
		opacity: 0.6;
	}
	.err {
		margin: 0;
		font-size: var(--text-2xs);
		color: var(--danger);
		word-break: break-word;
	}
	/* Progressive-verdict whisper; gone the moment the envelope lands. */
	.gate {
		margin: 0;
		font-size: var(--text-2xs);
		color: var(--fg-4);
	}
	.spinner {
		width: 10px;
		height: 10px;
		border: 1.5px solid color-mix(in srgb, var(--accent-fg, var(--bg-0)) 40%, transparent);
		border-top-color: var(--accent-fg, var(--bg-0));
		border-radius: var(--radius-full);
		animation: spin 0.6s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	@media (max-width: 700px) {
		.bar {
			left: var(--s2);
			right: var(--s2);
			bottom: var(--s2);
		}
	}
</style>
