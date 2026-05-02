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
				body: JSON.stringify({ image_b64: b64, mime, source_uri: e.path })
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
	<div class="flex w-full max-w-[480px] flex-col gap-2">
		<span class="px-1 text-[11px] uppercase tracking-wider text-(--fg-4)">or try</span>
		<div class="grid grid-cols-6 gap-1.5">
			{#each entries as entry (entry.path)}
				<button
					type="button"
					class="group relative aspect-square overflow-hidden rounded border border-(--border-1) transition-colors hover:border-(--accent)"
					onclick={() => runDemo(entry)}
					disabled={loading !== null}
					aria-label={entry.label ?? entry.path}
					title={entry.label ?? entry.path}
				>
					<img
						src={entry.path}
						alt=""
						class="h-full w-full object-cover transition-opacity"
						class:opacity-40={loading === entry.path}
						loading="lazy"
					/>
					{#if loading === entry.path}
						<div
							class="absolute inset-0 flex items-center justify-center font-mono text-[10px] text-(--accent)"
						>
							•••
						</div>
					{/if}
				</button>
			{/each}
		</div>
	</div>
{/if}
