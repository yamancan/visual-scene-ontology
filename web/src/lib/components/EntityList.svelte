<script lang="ts">
	import EntityRow from './EntityRow.svelte';
	import { scene } from '$lib/scene.svelte';
	import { buildSceneView, topLevelEntities } from '$lib/render/sceneView';

	// The scannable VERIFICATION checklist for the right sidebar (Inspect mode).
	// Reads scene.envelope via buildSceneView — the same projection SceneFlow
	// uses — and lists the top-level entities (those not contained as another
	// entity's part) as compact, expandable rows.

	let view = $derived.by(() => {
		const g = scene.envelope?.graph;
		return g ? buildSceneView(g) : null;
	});

	// Top-level entities (not contained as another entity's part). Shared with
	// SceneFlow via topLevelEntities so the list and the canvas always agree.
	let topLevel = $derived.by(() => (view ? topLevelEntities(view) : []));

	// Thin, cheap scene-context line: a couple of composition/camera cues so the
	// checklist has a frame of reference without pulling in the full notation.
	let contextBits = $derived.by(() => {
		if (!view) return [] as string[];
		const bits: string[] = [];
		for (const q of view.composition?.qualities ?? []) bits.push(q.value);
		const cam = view.frame.find((f) => f.kind === 'CameraView');
		for (const p of cam?.properties ?? []) bits.push(String(p.value));
		return bits.slice(0, 4);
	});

	// Selected row scrolls into view so a click in the overlay keeps its checklist
	// counterpart visible.
	let listEl = $state<HTMLUListElement | null>(null);
	$effect(() => {
		const id = scene.selectedNodeId;
		if (!id || !listEl) return;
		const el = listEl.querySelector<HTMLElement>(`[data-entity="${CSS.escape(id)}"]`);
		el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
	});
</script>

<section class="entity-list" aria-label="entities">
	<header class="head">
		<span class="title font-mono">Entities</span>
	</header>

	{#if contextBits.length}
		<p class="context" title="scene context">
			{#each contextBits as bit, i (bit + i)}
				<span class="ctx-bit">{bit}</span>
			{/each}
		</p>
	{/if}

	{#if topLevel.length}
		<ul class="rows" bind:this={listEl}>
			{#each topLevel as entity (entity.id)}
				<li data-entity={entity.id} class="row-anchor">
					<EntityRow {entity} />
				</li>
			{/each}
		</ul>
	{:else}
		<p class="empty font-mono">no entities</p>
	{/if}
</section>

<style>
	.entity-list {
		display: flex;
		flex-direction: column;
		gap: var(--s3);
		height: 100%;
		min-height: 0;
		padding: var(--s3);
		overflow-y: auto;
		background: var(--bg-0);
	}

	.head {
		display: flex;
		align-items: baseline;
		gap: var(--s1);
		flex-shrink: 0;
	}
	.title {
		font-size: var(--text-2xs);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-3);
	}

	.context {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin: 0;
		flex-shrink: 0;
	}
	.ctx-bit {
		font-size: var(--text-xs);
		color: var(--fg-3);
	}
	.ctx-bit + .ctx-bit::before {
		content: '·';
		color: var(--fg-4);
		margin-right: 6px;
	}

	.rows {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: var(--s2);
		margin: 0;
		min-width: 0;
	}
	/* Scroll anchor wrapper so the $effect can target a stable element per id
	   without reaching into the EntityRow internals. */
	.row-anchor {
		min-width: 0;
	}

	.empty {
		margin: 0;
		color: var(--fg-4);
		font-size: var(--text-2xs);
	}
</style>
