<script lang="ts">
	import { onMount } from 'svelte';
	import { scene } from '$lib/scene.svelte';
	import type { VsonEnvelope } from '$lib/types';

	interface DemoEntry {
		path: string;
		label?: string;
		mime?: 'image/jpeg' | 'image/png';
	}

	let entries = $state<DemoEntry[]>([]);
	let loading = $state<string | null>(null);

	onMount(async () => {
		try {
			const r = await fetch('/demos/manifest.json');
			if (!r.ok) return;
			const m = (await r.json()) as { entries?: DemoEntry[] };
			entries = m.entries ?? [];
		} catch {
			/* no demos */
		}
	});

	async function runDemo(e: DemoEntry) {
		loading = e.path;
		scene.setError(null);
		try {
			const img = await fetch(e.path);
			if (!img.ok) throw new Error(`fetch ${e.path} → ${img.status}`);
			const blob = await img.blob();
			const mime = (e.mime ?? blob.type ?? 'image/jpeg') as 'image/jpeg' | 'image/png';
			const buf = await blob.arrayBuffer();
			let bin = '';
			const u8 = new Uint8Array(buf);
			for (let i = 0; i < u8.length; i++) bin += String.fromCharCode(u8[i]);
			const b64 = btoa(bin);
			scene.setImagePreview(`data:${mime};base64,${b64}`);
			scene.setStatus('calling');
			const res = await fetch('/api/extract', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ image_b64: b64, mime, source_uri: e.path, model: scene.model })
			});
			if (!res.ok) {
				scene.setError(`extract failed · ${res.status}`);
				return;
			}
			scene.setEnvelope((await res.json()) as VsonEnvelope);
			scene.setStatus('idle');
		} catch (err) {
			scene.setError(`demo failed · ${(err as Error).message}`);
		} finally {
			loading = null;
		}
	}
</script>

{#if entries.length > 0}
	<div class="demos">
		<span class="demos-label font-mono">or try one</span>
		<div class="demos-grid" style:grid-template-columns="repeat({entries.length}, 1fr)">
			{#each entries as entry (entry.path)}
				<button
					type="button"
					class="thumb"
					class:loading={loading === entry.path}
					onclick={() => runDemo(entry)}
					disabled={loading !== null}
					aria-label={entry.label ?? entry.path}
					title={entry.label ?? entry.path}
				>
					<img src={entry.path} alt="" loading="lazy" />
					{#if loading === entry.path}
						<div class="thumb-overlay font-mono">•••</div>
					{/if}
				</button>
			{/each}
		</div>
	</div>
{/if}

<style>
	.demos {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--s3);
		width: 100%;
		max-width: 480px;
	}
	.demos-label {
		font-size: var(--text-2xs);
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.demos-grid {
		display: grid;
		gap: var(--s2);
		width: 100%;
	}
	.thumb {
		position: relative;
		aspect-ratio: 1;
		overflow: hidden;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		background: var(--bg-1);
		cursor: pointer;
		padding: 0;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			transform var(--duration-fast) var(--ease-out);
	}
	.thumb:hover:not([disabled]) {
		border-color: var(--accent);
		transform: translateY(-1px);
	}
	.thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		transition: opacity var(--duration-fast) var(--ease-out);
	}
	.thumb.loading img {
		opacity: 0.35;
	}
	.thumb-overlay {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		font-size: var(--text-xs);
		color: var(--accent);
		letter-spacing: 0.2em;
	}
</style>
