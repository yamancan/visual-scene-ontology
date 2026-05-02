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
			dropError = `unsupported format · ${file.type || 'unknown'} · use jpeg or png`;
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
				body: JSON.stringify({ image_b64: b64, mime })
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

<div class="flex w-full max-w-[480px] flex-col items-stretch gap-3">
	<button
		type="button"
		onclick={() => inputEl?.click()}
		ondragover={(e) => {
			e.preventDefault();
			dragOver = true;
		}}
		ondragleave={() => (dragOver = false)}
		ondrop={onDrop}
		class="group flex h-[280px] w-full flex-col items-center justify-center gap-3 rounded-md border border-dashed transition-all duration-200"
		class:border-color-border={!dragOver}
		class:border-color-accent={dragOver}
		style:border-color={dragOver ? 'var(--accent)' : 'var(--border-1)'}
		style:background={dragOver ? 'var(--accent-bg)' : 'var(--bg-1)'}
	>
		<svg
			width="32"
			height="32"
			viewBox="0 0 32 32"
			fill="none"
			class="transition-colors"
			style:color={dragOver ? 'var(--accent)' : 'var(--fg-4)'}
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
		<div class="flex flex-col items-center gap-1">
			<span class="text-(--fg-0) text-[15px] tracking-tight">
				{dragOver ? 'release to extract' : 'drop an image'}
			</span>
			<span class="text-[12px] text-(--fg-4)">jpeg or png · up to 5 MB</span>
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
		<p
			class="font-mono px-1 text-[12px]"
			style:color="var(--danger)"
			role="alert"
		>
			{dropError}
		</p>
	{/if}
</div>
