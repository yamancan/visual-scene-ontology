<script lang="ts">
	import { onMount } from 'svelte';
	import { scene } from '$lib/scene.svelte';
	import type { VsonEnvelope } from '$lib/types';

	interface GalleryEntry {
		stem: string;
		label: string;
		envelope_path: string;
		conforms: boolean;
		nodes: number;
		edges: number;
		covers: string[];
	}

	let entries = $state<GalleryEntry[]>([]);
	let loading = $state<string | null>(null);
	let expanded = $state(false);

	onMount(async () => {
		try {
			const r = await fetch('/demos/manifest-gallery.json');
			if (!r.ok) return;
			const m = (await r.json()) as { entries?: GalleryEntry[] };
			entries = m.entries ?? [];
		} catch {
			/* gallery not baked yet */
		}
	});

	// Stems 12+ exercise v1.1 constructs (Persona, reification, RDF-star).
	// Surface those first since they answer "can I see this construct in
	// the studio?" — the basic v1.0 ones (01-11) are still listed but
	// after the headline set. Parse defensively: a stem that doesn't start
	// with a number falls into `basic` rather than being silently dropped.
	const stemNum = (stem: string) => parseInt(stem, 10);
	let advanced = $derived(entries.filter((e) => stemNum(e.stem) >= 12));
	let basic = $derived(entries.filter((e) => !(stemNum(e.stem) >= 12)));

	async function loadFixture(e: GalleryEntry) {
		loading = e.stem;
		scene.setError(null);
		scene.setImagePreview(null);
		try {
			const res = await fetch(e.envelope_path);
			if (!res.ok) throw new Error(`fetch ${e.envelope_path} → ${res.status}`);
			scene.setEnvelope((await res.json()) as VsonEnvelope);
			scene.setStatus('idle');
		} catch (err) {
			scene.setError(`example load failed · ${(err as Error).message}`);
		} finally {
			loading = null;
		}
	}
</script>

{#if entries.length > 0}
	<div class="gallery">
		<button
			type="button"
			class="gallery-toggle"
			onclick={() => (expanded = !expanded)}
			aria-expanded={expanded}
		>
			<span class="caret" aria-hidden="true">{expanded ? '▾' : '▸'}</span>
			<span class="toggle-label">spec examples</span>
			<span class="count">{entries.length}</span>
		</button>

		{#if expanded}
			<p class="gallery-help">
				Inspect a conformant scene — no model involved. Hand-authored VSON documents that pass
				strict SHACL, one per construct: load any and read the graph, the source and the verdict.
			</p>

			<ul class="grid">
				{#each [...advanced, ...basic] as e (e.stem)}
					<li>
						<button
							type="button"
							class="card"
							class:loading={loading === e.stem}
							onclick={() => loadFixture(e)}
							disabled={loading !== null}
							title="{e.covers.join(' · ')} · {e.nodes} nodes, {e.edges} edges"
						>
							<div class="card-label">{e.label}</div>
							{#if e.covers.length}
								<div class="covers">
									{#each e.covers as c (c)}<span class="cover-tag font-mono">{c}</span>{/each}
								</div>
							{/if}
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
{/if}

<style>
	.gallery {
		width: 100%;
		max-width: 960px;
		margin-top: var(--s6);
		display: flex;
		flex-direction: column;
		gap: var(--s3);
	}
	.gallery-toggle {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: var(--text-2xs);
		color: var(--fg-3);
		background: transparent;
		border: 0;
		padding: 4px 0;
		cursor: pointer;
		align-self: center;
	}
	.gallery-toggle:hover {
		color: var(--fg-1);
	}
	.caret {
		font-size: 10px;
		color: var(--fg-4);
	}
	.toggle-label {
		font-family: var(--font-mono);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.count {
		font-family: var(--font-mono);
		color: var(--accent);
	}
	.gallery-help {
		margin: 0;
		font-size: var(--text-2xs);
		color: var(--fg-4);
		text-align: center;
		line-height: 1.5;
		max-width: 520px;
		align-self: center;
	}
	.grid {
		list-style: none;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
		gap: var(--s2);
		padding: 0;
		margin: 0;
	}
	.card {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: var(--s2) var(--s3);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		cursor: pointer;
		text-align: left;
		font: inherit;
		color: inherit;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out),
			transform var(--duration-fast) var(--ease-out);
		min-width: 0;
	}
	.card:hover:not([disabled]) {
		border-color: var(--accent);
		transform: translateY(-1px);
	}
	.card.loading {
		opacity: 0.6;
	}
	.card-label {
		font-size: var(--text-xs);
		color: var(--fg-1);
		font-weight: 500;
	}
	.covers {
		display: flex;
		flex-wrap: wrap;
		gap: 3px;
	}
	.cover-tag {
		font-size: 9px;
		padding: 1px 5px;
		background: var(--tag-bg);
		color: var(--fg-3);
		border-radius: var(--radius-sm);
	}
</style>
