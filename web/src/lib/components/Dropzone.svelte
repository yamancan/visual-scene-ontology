<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { byok } from '$lib/byok.svelte';
	import { formatBytes, prepareImageUpload } from '$lib/utils';
	import { extractScene } from '$lib/extract/orchestrator';
	import { OpenRouterError } from '$lib/openrouter/client';

	let dragOver = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();
	let dropError = $state<string | null>(null);
	// The keyless-drop hint: ONE quiet line under the drop surface, shown only
	// after a non-demo drop with no key stored. Not an error — nothing failed;
	// live extraction simply runs on the visitor's own OpenRouter key.
	let needKey = $state(false);

	const ACCEPT = ['image/jpeg', 'image/png'];

	// Failure lines in OpenRouter's own taxonomy — key not accepted (401), out
	// of credits (402), provider rate limit (429), network — plus the designed
	// validation-unavailable state. The old 413/429 map described a body-size
	// proxy and a rate limiter that no longer sit in front of this app.
	function extractFailure(e: unknown): string {
		if (e instanceof OpenRouterError) return e.message;
		const err = e as Error & { help?: string };
		// Matched by name: importing the class from $lib/validate/client would
		// pull the worker chunk (and its inlined Python/ontology sources) into
		// the page bundle the keyless path pays for.
		if (err?.name === 'ValidationUnavailableError') return err.help ?? err.message;
		return `extract failed · ${err?.message ?? String(e)}`;
	}

	// Once a key exists the hint has done its job.
	$effect(() => {
		if (byok.active) needKey = false;
	});

	async function handleFile(file: File) {
		if (!ACCEPT.includes(file.type)) {
			dropError = `unsupported · ${file.type || 'unknown'} · use jpeg or png`;
			return;
		}
		if (file.size > 5 * 1024 * 1024) {
			dropError = `too large · ${formatBytes(file.size)} · 5 MB cap`;
			return;
		}
		dropError = null;
		needKey = false;
		scene.setError(null);
		scene.setGate1(null);
		scene.setStatus('uploading');
		try {
			// Decode (and, above 1 MB, downscale) inside the try: a FileReader or
			// canvas failure has to land in the same error path as a dead network
			// instead of escaping as an unhandled rejection with the UI stuck on
			// "uploading". The preview stays full-resolution; only the uploaded
			// bytes shrink.
			const { b64, mime, preview } = await prepareImageUpload(file);
			scene.setImagePreview(preview);
			scene.setStatus('calling');
			// Entirely in the browser: sha256 demo short-circuit (keyless, $0),
			// else chat → worker transpile → two-gate validate → repair loop.
			const env = await extractScene({
				image_b64: b64,
				mime: mime as 'image/jpeg' | 'image/png',
				model: scene.model,
				variant: scene.notation === 'x' ? 'skill-x' : 'skill',
				onGate1: (gate1) => {
					// Progressive verdict: the SHACL result lands ~0.2s into each
					// validation round, well before the OWL RL gate finalizes.
					scene.setGate1(gate1);
					scene.setStatus('validating');
				}
			});
			scene.setEnvelope(env);
			scene.setStatus('idle');
		} catch (e) {
			if (e instanceof OpenRouterError && e.kind === 'no-key') {
				// Keyless non-demo drop: one quiet line + focus the existing key
				// field in the model picker. No modal, no banner, no toast.
				needKey = true;
				scene.setGate1(null);
				scene.setStatus('idle');
				byok.requestKeyFocus();
				return;
			}
			scene.setError(extractFailure(e));
		}
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		const f = e.dataTransfer?.files?.[0];
		if (f) {
			handleFile(f);
			return;
		}
		// A drag from another tab or app carries a URL, not the image bytes —
		// dataTransfer.files is empty and silently doing nothing reads as a
		// broken dropzone. The bytes can't be fetched either: connect-src is
		// 'self' + openrouter.ai only. Say so, and point at the paths that work.
		const types = e.dataTransfer?.types ?? [];
		if (types.length > 0) {
			dropError =
				'that drag carried a link, not the image · copy the image and paste it here, or drop a saved file';
		}
	}

	// Paste-to-extract: browsers put real image bytes on the clipboard for
	// "copy image" and screenshots, so paste works even where cross-tab drag
	// cannot. Only acts when an image file is present; other pastes are not
	// this component's business.
	function onPaste(e: ClipboardEvent) {
		const items = e.clipboardData?.items ?? [];
		for (const item of items) {
			if (item.kind === 'file' && item.type.startsWith('image/')) {
				const f = item.getAsFile();
				if (f) {
					e.preventDefault();
					handleFile(f);
				}
				return;
			}
		}
	}

	function onChange(e: Event) {
		const t = e.target as HTMLInputElement;
		const f = t.files?.[0];
		if (f) handleFile(f);
		t.value = '';
	}
</script>

<svelte:window onpaste={onPaste} />

<div class="zone-wrap">
	<button
		type="button"
		onclick={() => inputEl?.click()}
		ondragover={(e) => {
			e.preventDefault();
			dragOver = true;
		}}
		ondragleave={() => (dragOver = false)}
		ondrop={onDrop}
		class="zone"
		class:active={dragOver}
		aria-label="Upload image"
	>
		<svg
			width="28"
			height="28"
			viewBox="0 0 32 32"
			fill="none"
			class="zone-icon"
			aria-hidden="true"
		>
			<rect x="6" y="8" width="20" height="16" rx="1.5" stroke="currentColor" stroke-width="1.2" />
			<circle cx="12" cy="14" r="1.6" fill="currentColor" />
			<path
				d="M9 22 L14 16 L19 21 L23 17 L26 20"
				stroke="currentColor"
				stroke-width="1.2"
				fill="none"
				stroke-linejoin="round"
			/>
		</svg>
		<div class="zone-copy">
			<span class="zone-title">{dragOver ? 'release to extract' : 'drop image here'}</span>
			<span class="zone-meta font-mono">jpeg or png · ≤5 MB · browse, drop, or paste</span>
		</div>
	</button>
	<input
		bind:this={inputEl}
		type="file"
		accept="image/jpeg,image/png"
		class="sr-only"
		onchange={onChange}
	/>
	{#if dropError}
		<p class="zone-err font-mono" role="alert">{dropError}</p>
	{:else if needKey}
		<button type="button" class="zone-hint font-mono" onclick={() => byok.requestKeyFocus()}>
			Live extraction runs with your OpenRouter key — add it in the model picker
		</button>
	{/if}
</div>

<style>
	.zone-wrap {
		display: flex;
		flex-direction: column;
		gap: var(--s3);
		width: 100%;
		max-width: 480px;
	}
	.zone {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--s4);
		height: 240px;
		padding: var(--s6);
		background: var(--bg-1);
		border: 1px dashed var(--border-1);
		border-radius: var(--radius);
		cursor: pointer;
		transition:
			background var(--duration-normal) var(--ease-out),
			border-color var(--duration-normal) var(--ease-out),
			transform var(--duration-normal) var(--ease-out);
	}
	.zone:hover {
		border-color: var(--border-2);
		background: var(--bg-2);
	}
	.zone.active {
		background: var(--accent-bg);
		border-color: var(--accent);
		transform: scale(1.005);
	}
	.zone-icon {
		color: var(--fg-4);
		transition: color var(--duration-normal) var(--ease-out);
	}
	.zone:hover .zone-icon,
	.zone.active .zone-icon {
		color: var(--accent);
	}
	.zone-copy {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
	}
	.zone-title {
		font-size: var(--text-base);
		color: var(--fg-0);
		letter-spacing: -0.005em;
	}
	.zone-meta {
		font-size: var(--text-2xs);
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.zone-err {
		padding: 0 var(--s2);
		font-size: var(--text-2xs);
		color: var(--danger);
	}
	/* Quiet by design: plain text at rest, only the pointer gives it away. */
	.zone-hint {
		padding: 0 var(--s2);
		font-size: var(--text-2xs);
		color: var(--fg-3);
		background: transparent;
		border: 0;
		text-align: left;
		cursor: pointer;
		transition: color var(--duration-fast) var(--ease-out);
	}
	.zone-hint:hover {
		color: var(--fg-1);
	}
</style>
