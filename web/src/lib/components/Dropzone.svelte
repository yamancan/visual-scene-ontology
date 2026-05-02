<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { fileToBase64, formatBytes } from '$lib/utils';
	import type { VsonEnvelope } from '$lib/types';

	let dragOver = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();
	let dropError = $state<string | null>(null);

	const ACCEPT = ['image/jpeg', 'image/png'];

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
		scene.setError(null);
		scene.setStatus('uploading');
		const { b64, mime, preview } = await fileToBase64(file);
		scene.setImagePreview(preview);
		scene.setStatus('calling');
		try {
			const res = await fetch('/api/extract', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ image_b64: b64, mime, model: scene.model })
			});
			if (!res.ok) {
				const text = await res.text();
				scene.setError(`extract failed · ${res.status} · ${text.slice(0, 200)}`);
				return;
			}
			const env = (await res.json()) as VsonEnvelope;
			scene.setEnvelope(env);
			scene.setStatus('idle');
		} catch (e) {
			scene.setError(`network · ${(e as Error).message}`);
		}
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		const f = e.dataTransfer?.files?.[0];
		if (f) handleFile(f);
	}

	function onChange(e: Event) {
		const t = e.target as HTMLInputElement;
		const f = t.files?.[0];
		if (f) handleFile(f);
		t.value = '';
	}
</script>

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
		<svg width="28" height="28" viewBox="0 0 32 32" fill="none" class="zone-icon" aria-hidden="true">
			<rect
				x="6"
				y="8"
				width="20"
				height="16"
				rx="1.5"
				stroke="currentColor"
				stroke-width="1.2"
			/>
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
			<span class="zone-title">{dragOver ? 'release to extract' : 'drop image'}</span>
			<span class="zone-meta font-mono">jpeg or png · ≤5 MB</span>
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
</style>
