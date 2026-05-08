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

	// Split into "basic" (01–11, v1.0 constructs) and "v1.1" (12–16, Persona +
	// reification + RDF-star). v1.1 set is more interesting for kapsam-conformance
	// demos so it stays expanded by default.
	let basic = $derived(entries.filter((e) => Number(e.stem.slice(0, 2)) <= 11));
	let advanced = $derived(entries.filter((e) => Number(e.stem.slice(0, 2)) >= 12));

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
			scene.setError(`gallery load failed · ${(err as Error).message}`);
		} finally {
			loading = null;
		}
	}
</script>

{#if entries.length > 0}
	<div class="gallery">
		<button
			class="gallery-toggle font-mono"
			onclick={() => (expanded = !expanded)}
			aria-expanded={expanded}
		>
			<span class="caret">{expanded ? '▾' : '▸'}</span>
			canonical fixtures · <span class="count">{entries.length}</span>
		</button>

		{#if expanded}
			<div class="gallery-body">
				<section class="group">
					<h4 class="group-h font-mono">v1.1 — persona, reification, rdf-star</h4>
					<ul class="grid">
						{#each advanced as e (e.stem)}
							<li>
								<button
									type="button"
									class="card"
									class:loading={loading === e.stem}
									onclick={() => loadFixture(e)}
									disabled={loading !== null}
									title={e.covers.join(' · ')}
								>
									<div class="card-h">
										<span class="stem font-mono">{e.stem}</span>
										<span class="counts font-mono">{e.nodes}n / {e.edges}e</span>
									</div>
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
				</section>

				<section class="group">
					<h4 class="group-h font-mono">v1.0 — core constructs</h4>
					<ul class="grid">
						{#each basic as e (e.stem)}
							<li>
								<button
									type="button"
									class="card"
									class:loading={loading === e.stem}
									onclick={() => loadFixture(e)}
									disabled={loading !== null}
									title={e.covers.join(' · ')}
								>
									<div class="card-h">
										<span class="stem font-mono">{e.stem}</span>
										<span class="counts font-mono">{e.nodes}n / {e.edges}e</span>
									</div>
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
				</section>
			</div>
		{/if}
	</div>
{/if}

<style>
	.gallery {
		width: 100%;
		max-width: 720px;
		display: flex;
		flex-direction: column;
		gap: var(--s3);
	}
	.gallery-toggle {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: var(--text-2xs);
		text-transform: uppercase;
		letter-spacing: 0.06em;
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
	.count {
		color: var(--accent);
	}
	.gallery-body {
		display: flex;
		flex-direction: column;
		gap: var(--s4);
	}
	.group {
		display: flex;
		flex-direction: column;
		gap: var(--s2);
	}
	.group-h {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
		margin: 0;
	}
	.grid {
		list-style: none;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
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
	.card-h {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		min-width: 0;
	}
	.stem {
		font-size: 10px;
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.counts {
		font-size: 9px;
		color: var(--fg-4);
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
		margin-top: 2px;
	}
	.cover-tag {
		font-size: 9px;
		padding: 1px 5px;
		background: var(--tag-bg);
		color: var(--fg-3);
		border-radius: var(--radius-sm);
	}
</style>
