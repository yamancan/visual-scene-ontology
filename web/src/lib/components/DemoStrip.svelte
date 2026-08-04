<script lang="ts">
	import { onMount } from 'svelte';
	import { scene } from '$lib/scene.svelte';
	import type { VsonEnvelope } from '$lib/types';

	interface DemoEntry {
		path: string;
		label?: string;
		mime?: 'image/jpeg' | 'image/png';
		envelope_path?: string;
		credit?: string;
		license?: string;
		source_url?: string;
	}

	let entries = $state<DemoEntry[]>([]);
	let loading = $state<string | null>(null);

	// The demo photographs are third-party work and this page serves the pixels,
	// so the people who took them are named on the page that shows them — one
	// muted line, not a modal. Full provenance (licence URL, the Lorem Picsum
	// re-serve the bytes came through, and the sha256 of those bytes) lives in
	// /demos/CREDITS.md and the repository's NOTICE; this is the pointer to it.
	const credited = $derived(entries.filter((e) => e.credit && e.source_url));
	const licenses = $derived([...new Set(credited.map((e) => e.license).filter(Boolean))]);
	// Built as strings rather than as markup: the separators are the only thing
	// between two links, and markup whitespace around a Svelte block is not
	// something the formatter is obliged to preserve — an expression is.
	const licenceSuffix = $derived(licenses.length > 0 ? ` · ${licenses.join(' · ')}` : '');
	const joiner = (i: number, n: number) => (i < n - 2 ? ', ' : i === n - 2 ? ' and ' : '');

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

	async function imageDataUrl(path: string, mimeHint?: string): Promise<string> {
		const img = await fetch(path);
		if (!img.ok) throw new Error(`fetch ${path} → ${img.status}`);
		const blob = await img.blob();
		const mime = mimeHint ?? blob.type ?? 'image/jpeg';
		const buf = await blob.arrayBuffer();
		let bin = '';
		const u8 = new Uint8Array(buf);
		for (let i = 0; i < u8.length; i++) bin += String.fromCharCode(u8[i]);
		return `data:${mime};base64,${btoa(bin)}`;
	}

	async function runDemo(e: DemoEntry) {
		// Baked envelopes are the ONLY demo path: every manifest entry carries
		// one, and the corpus is genuine LLM provenance that is never
		// regenerated. An entry without envelope_path is a maintainer error —
		// skip it loudly rather than spend anyone's OpenRouter key on a demo
		// click.
		if (!e.envelope_path) {
			console.error(`demo entry has no envelope_path — skipping: ${e.path}`);
			return;
		}
		loading = e.path;
		scene.setError(null);
		try {
			// Fetch the baked envelope (~8 KB) and render without an LLM call.
			// Costs nothing, works without an API key.
			const [previewUrl, envRes] = await Promise.all([
				imageDataUrl(e.path, e.mime),
				fetch(e.envelope_path)
			]);
			if (!envRes.ok) {
				throw new Error(`cached envelope missing · ${envRes.status}`);
			}
			scene.setImagePreview(previewUrl);
			scene.setEnvelope((await envRes.json()) as VsonEnvelope);
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
					title={[
						entry.label ?? entry.path,
						entry.envelope_path ? 'prebuilt' : null,
						entry.credit ? `photo: ${entry.credit}` : null
					]
						.filter(Boolean)
						.join(' · ')}
				>
					<img src={entry.path} alt="" loading="lazy" />
					{#if loading === entry.path}
						<div class="thumb-overlay font-mono">•••</div>
					{/if}
				</button>
			{/each}
		</div>
		{#if credited.length > 0}
			<p class="demos-credit">
				photos by {#each credited as entry, i (entry.path)}<a href={entry.source_url} rel="external"
						>{entry.credit}</a
					>{joiner(i, credited.length)}{/each}{licenceSuffix}
			</p>
		{/if}
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
	.demos-credit {
		margin: 0;
		text-align: center;
		text-wrap: balance;
		font-size: var(--text-2xs);
		line-height: 1.5;
		color: var(--fg-4);
	}
	.demos-credit a {
		color: inherit;
		text-decoration: none;
		border-bottom: 1px solid var(--border-1);
	}
	.demos-credit a:hover {
		color: var(--fg-2);
		border-bottom-color: currentColor;
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
