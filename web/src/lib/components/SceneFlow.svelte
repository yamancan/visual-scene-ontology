<script lang="ts">
	import {
		SvelteFlow,
		Background,
		Controls,
		type Node,
		type Edge,
		MarkerType
	} from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';

	import EntityNode from './EntityNode.svelte';
	import ImageOverlay from './ImageOverlay.svelte';
	import MaxButton from './MaxButton.svelte';
	import FitOnLayout from './FitOnLayout.svelte';
	import { scene } from '$lib/scene.svelte';
	import { layout } from '$lib/layout.svelte';
	import { parseBbox } from '$lib/bbox';
	import { buildSceneView, type FrameSlot } from '$lib/render/sceneView';

	const nodeTypes = { entity: EntityNode };

	const FRAME_LABEL: Record<FrameSlot['kind'], string> = {
		SceneContext: 'ctx',
		VisualStyle: 'style',
		CameraView: 'cam'
	};

	function shorten(v: string, n = 24): string {
		return v.length <= n ? v : v.slice(0, n - 1) + '…';
	}

	// Parsed bbox for an entity id, or null. Shared with the layout sort below;
	// parseBbox lives in $lib/bbox so the studio and canvas never disagree on
	// what "full image" means.
	function getBbox(entityId: string) {
		const src = scene.envelope?.graph?.nodes.find((n) => n.id === entityId);
		if (!src) return null;
		const raw = (src.properties?.bbox2d ?? src.bbox2d) as string | number | undefined;
		return parseBbox(raw);
	}

	let view = $derived.by(() => {
		const g = scene.envelope?.graph;
		return g ? buildSceneView(g) : null;
	});

	// Top-level entities: not contained inside another entity's Has chip-row.
	let topLevel = $derived.by(() => {
		if (!view) return [];
		const contained = new Set<string>();
		for (const e of view.entities) for (const h of e.has) contained.add(h.to);
		return view.entities.filter((e) => !contained.has(e.id));
	});

	const CARD_W = 260;
	const GAP_X = 32;
	const ROW_H = 280;

	let nodes = $state.raw<Node[]>([]);
	let edges = $state.raw<Edge[]>([]);

	$effect(() => {
		const tl = topLevel;
		if (!tl.length) {
			nodes = [];
			return;
		}

		// Sort by bbox left edge; bg-style entities (full-image bbox) sink last.
		const sorted = [...tl].sort((a, b) => {
			const ba = getBbox(a.id);
			const bb = getBbox(b.id);
			const aFull = ba?.isFullImage ?? false;
			const bFull = bb?.isFullImage ?? false;
			if (aFull && !bFull) return 1;
			if (!aFull && bFull) return -1;
			if (!ba && !bb) return a.id.localeCompare(b.id);
			if (!ba) return 1;
			if (!bb) return -1;
			return ba.x - bb.x;
		});

		nodes = sorted.map((e, i) => {
			const bb = getBbox(e.id);
			const isFull = bb?.isFullImage ?? false;
			return {
				id: e.id,
				type: 'entity',
				position: { x: i * (CARD_W + GAP_X), y: isFull ? ROW_H : 0 },
				data: { entity: e }
			};
		});
	});

	$effect(() => {
		if (!view) {
			edges = [];
			return;
		}
		const out: Edge[] = [];
		const AGENT_ROLES = new Set(['agent', 'holder', 'experiencer']);
		const PATIENT_ROLES = new Set([
			'patient',
			'theme',
			'stimulus',
			'recipient',
			'goal',
			'beneficiary'
		]);

		for (const a of view.actions) {
			const agent = a.roles.find((r) => AGENT_ROLES.has(r.role));
			const patient = a.roles.find((r) => PATIENT_ROLES.has(r.role));
			if (!agent || !patient) continue;
			out.push({
				id: a.id,
				source: agent.target,
				target: patient.target,
				label: a.lemma ?? a.kind.toLowerCase(),
				type: 'smoothstep',
				animated: a.kind === 'Process',
				markerEnd: { type: MarkerType.ArrowClosed },
				data: { kind: a.kind, actionId: a.id }
			});
		}
		edges = out;
	});

	let isEmpty = $derived(nodes.length === 0);

	let hasFrame = $derived((view?.frame.length ?? 0) > 0);
	let hasLayout = $derived(!!view?.composition && view.composition.qualities.length > 0);

	// How many top-level entities carry a parseable box — drives the band header
	// count and gates the whole image band.
	let boxCount = $derived(topLevel.reduce((n, e) => n + (getBbox(e.id) ? 1 : 0), 0));

	// Show the vertical split only when there's a preview AND at least one box to
	// overlay. Otherwise the canvas fills .scene-flow exactly as before.
	let hasImageBand = $derived(!!scene.imagePreview && boxCount > 0 && !isEmpty);

	// Image band/graph visibility now comes from the shared layout store instead of
	// a local toggle: the band body shows when image is visible (or maximized), the
	// band height tracks the preset's imagePct, and the band/graph hide entirely
	// when the opposite panel is maximized.
	let imageShown = $derived(layout.imageVisible || layout.isMax('image'));
	let bandGone = $derived(layout.isMax('graph'));
	// Only collapse the graph for an image-maximize when there's actually an image
	// band to fill the space. Without a band the maximize would hide BOTH panes
	// (band gated on hasImageBand, graph on graph-gone) leaving the stage blank —
	// so fall back to showing the graph.
	let graphGone = $derived(layout.isMax('image') && hasImageBand);
	let imageBasis = $derived(
		layout.isMax('image') ? '100%' : layout.imageVisible ? layout.imagePct + '%' : 'auto'
	);

	// A single value that changes whenever the graph container is shown/hidden or
	// resized — FitOnLayout re-fits the viewport on each change so nodes stay
	// centred after band toggles and maximize/restore cycles.
	let fitSignal = $derived(`${layout.maximized}|${imageBasis}|${bandGone}|${graphGone}`);
</script>

<div class="scene-flow" class:split={hasImageBand}>
	{#if isEmpty}
		<div class="empty font-mono">no entities</div>
	{:else}
		{#if hasImageBand && !bandGone}
			<div class="image-band" class:collapsed={!imageShown} style="--image-basis: {imageBasis}">
				<div class="band-bar">
					<span class="band-label font-mono">image</span>
					<span class="band-count font-mono">{boxCount} {boxCount === 1 ? 'box' : 'boxes'}</span>
					<button
						type="button"
						class="band-toggle"
						aria-label={layout.imageVisible ? 'collapse image band' : 'expand image band'}
						aria-expanded={layout.imageVisible}
						onclick={() => layout.togglePanel('image')}
					>
						<svg
							class="chevron"
							class:up={layout.imageVisible}
							width="12"
							height="12"
							viewBox="0 0 12 12"
							aria-hidden="true"
						>
							<path
								d="M3 4.5L6 7.5L9 4.5"
								fill="none"
								stroke="currentColor"
								stroke-width="1.4"
								stroke-linecap="round"
								stroke-linejoin="round"
							/>
						</svg>
					</button>
					<MaxButton panel="image" />
				</div>
				{#if imageShown}
					<div class="band-body">
						<ImageOverlay />
					</div>
				{/if}
			</div>
		{/if}

		<div class="graph" class:graph-gone={graphGone}>
			<SvelteFlow
				bind:nodes
				bind:edges
				{nodeTypes}
				fitView
				fitViewOptions={{ padding: 0.15 }}
				nodesConnectable={false}
				minZoom={0.3}
				maxZoom={2}
				proOptions={{ hideAttribution: true }}
			>
				<Background patternColor="var(--border-1)" gap={24} />
				<Controls position="top-left" showLock={false} />
				<FitOnLayout signal={fitSignal} options={{ padding: 0.15 }} />
			</SvelteFlow>

			<div class="graph-tools nodrag nopan">
				<MaxButton panel="graph" />
			</div>

			{#if view && (hasFrame || hasLayout)}
				<ul class="chip-rail" aria-label="frame metadata">
					{#each view.frame as slot (slot.id)}
						<li class="chip" data-kind={slot.kind}>
							<span class="chip-key font-mono">{FRAME_LABEL[slot.kind]}</span>
							{#each slot.properties as p (p.key)}
								<span class="chip-val font-mono" title="{p.key}: {p.value}">
									{shorten(String(p.value))}
								</span>
							{/each}
							{#if slot.properties.length === 0}
								<span class="chip-empty font-mono">—</span>
							{/if}
						</li>
					{/each}
					{#if hasLayout}
						<li class="chip comp-qualities">
							<span class="chip-key font-mono">layout</span>
							{#each view.composition!.qualities as q (q.dim)}
								<span class="chip-val font-mono" title="{q.dim}: {q.value}">
									{q.value}
								</span>
							{/each}
						</li>
					{/if}
				</ul>
			{/if}
		</div>
	{/if}
</div>

<style>
	.scene-flow {
		position: relative;
		height: 100%;
		min-height: 0;
		background: var(--bg-0);
	}
	/* When an image band is shown, the flow becomes a vertical stack: band on
	 * top, graph filling the rest. Without the band the single .graph child still
	 * fills 100% (position:absolute inset:0). */
	.scene-flow.split {
		display: flex;
		flex-direction: column;
	}
	.empty {
		display: grid;
		place-items: center;
		height: 100%;
		color: var(--fg-4);
		font-size: var(--text-2xs);
	}

	/* Collapsible image band — thin header bar + the overlay filling a share of the
	 * flow height while expanded. The basis comes from the layout store via the
	 * --image-basis var (preset imagePct, 100% when maximized, auto when collapsed).
	 * Collapsed: only the bar remains. */
	.image-band {
		display: flex;
		flex-direction: column;
		flex: 0 0 var(--image-basis, 42%);
		min-height: 120px;
		border-bottom: 1px solid var(--border-1);
		background: var(--bg-0);
		overflow: hidden;
	}
	.image-band.collapsed {
		flex: 0 0 auto;
		min-height: 0;
	}
	.band-bar {
		display: flex;
		align-items: center;
		gap: var(--s2);
		flex-shrink: 0;
		padding: 0 var(--s2);
		height: 28px;
		border-bottom: 1px solid var(--border-1);
		background: var(--bg-1);
	}
	.image-band.collapsed .band-bar {
		border-bottom: 0;
	}
	.band-label {
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-size: 9px;
		color: var(--fg-4);
	}
	.band-count {
		font-size: 9px;
		color: var(--fg-3);
	}
	.band-toggle {
		margin-left: auto;
		display: inline-grid;
		place-items: center;
		width: 20px;
		height: 20px;
		padding: 0;
		border: 0;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--fg-3);
		cursor: pointer;
		transition: color var(--duration-fast) var(--ease-out);
	}
	.band-toggle:hover {
		color: var(--fg-0);
		background: var(--bg-2);
	}
	.chevron {
		transform: rotate(180deg);
		transition: transform var(--duration-fast) var(--ease-out);
	}
	.chevron.up {
		transform: rotate(0deg);
	}
	.band-body {
		flex: 1;
		min-height: 0;
		position: relative;
	}

	/* Graph region: fills remaining space in the split, or the whole container
	 * (absolute inset) when there's no band. The chip-rail anchors to its bottom
	 * either way, so it always overlays the graph and never the image band. */
	.graph {
		position: relative;
		flex: 1;
		min-height: 0;
	}
	.scene-flow:not(.split) .graph {
		position: absolute;
		inset: 0;
	}
	/* Image maximized: the graph collapses out so the band fills the flow. */
	.graph.graph-gone {
		display: none;
	}
	/* Pinned tool cluster (graph maximize/restore) floating over the canvas,
	 * mirroring the top-left Controls but on the right. nodrag/nopan keeps clicks
	 * off the pane so the button never starts a canvas drag. */
	.graph-tools {
		position: absolute;
		top: var(--s2);
		right: var(--s2);
		z-index: 6;
		display: flex;
		align-items: center;
		gap: var(--s1);
		/* Backing surface so the maximize control stays legible over any node or
		 * canvas region beneath it, mirroring the bottom-left zoom Controls. */
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		padding: 2px;
	}
	/* xyflow ships hardcoded colors in its bundled CSS via --xy-* custom
	 * properties. Forward our theme tokens so the canvas + edge defaults
	 * track Kova theme switches instead of locking to the lib's white. */
	:global(.svelte-flow) {
		background: var(--bg-0);
		--xy-background-color: var(--bg-0);
		--xy-background-color-default: var(--bg-0);
		--xy-background-pattern-color: var(--border-1);
		--xy-background-pattern-color-default: var(--border-1);
		--xy-edge-stroke: var(--fg-3);
		--xy-edge-stroke-default: var(--fg-3);
		--xy-edge-stroke-selected: var(--accent);
		--xy-edge-stroke-selected-default: var(--accent);
		--xy-controls-button-background-color: var(--bg-1);
		--xy-controls-button-background-color-default: var(--bg-1);
		--xy-controls-button-background-color-hover: var(--bg-2);
		--xy-controls-button-background-color-hover-default: var(--bg-2);
		--xy-controls-button-color: var(--fg-2);
		--xy-controls-button-color-default: var(--fg-2);
		--xy-controls-button-color-hover: var(--fg-0);
		--xy-controls-button-color-hover-default: var(--fg-0);
		--xy-controls-button-border-color: var(--border-1);
		--xy-controls-button-border-color-default: var(--border-1);
	}
	:global(.svelte-flow__renderer),
	:global(.svelte-flow__pane),
	:global(.svelte-flow__viewport) {
		background: transparent;
	}
	:global(.svelte-flow__edge-path) {
		stroke: var(--fg-3);
		stroke-width: 1.5;
	}
	:global(.svelte-flow__edge.animated .svelte-flow__edge-path) {
		stroke: var(--accent);
	}
	:global(.svelte-flow__edge-text) {
		fill: var(--fg-1);
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 10px;
	}
	:global(.svelte-flow__edge-textbg) {
		fill: var(--bg-1);
	}
	:global(.svelte-flow__controls) {
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		box-shadow: none;
	}
	:global(.svelte-flow__controls button) {
		background: var(--bg-1);
		border-bottom: 1px solid var(--border-1);
		color: var(--fg-2);
	}
	:global(.svelte-flow__controls button:hover) {
		background: var(--bg-2);
		color: var(--fg-0);
	}
	:global(.svelte-flow__node.selected) {
		outline: none;
	}

	/* Floating frame-meta chip-rail anchored to the bottom of the graph region
	 * (not the parent SceneFrame body) so it never overlaps the FactsStrip pane
	 * that sits below the flow in ScenePanel, nor the image band above. */
	.chip-rail {
		position: absolute;
		left: var(--s3);
		right: var(--s3);
		bottom: var(--s3);
		display: flex;
		flex-wrap: wrap;
		gap: var(--s2);
		list-style: none;
		margin: 0;
		padding: var(--s2);
		background: color-mix(in srgb, var(--bg-1) 86%, transparent);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		box-shadow:
			0 1px 0 var(--border-1),
			0 4px 14px -8px color-mix(in srgb, var(--fg-0) 18%, transparent);
		z-index: 5;
		pointer-events: auto;
		max-width: calc(100% - 2 * var(--s3));
		overflow-x: auto;
		scrollbar-width: thin;
	}
	.chip {
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		padding: 2px 6px;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		background: var(--bg-0);
		font-size: 10px;
		white-space: nowrap;
	}
	.chip-key {
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-size: 9px;
	}
	.chip-val {
		color: var(--fg-1);
	}
	.chip-val + .chip-val::before {
		content: '·';
		color: var(--fg-4);
		margin-right: 4px;
	}
	.chip-empty {
		color: var(--fg-4);
	}
	.comp-qualities {
		border-style: dashed;
	}
	@media (max-width: 700px) {
		.chip-rail {
			left: var(--s2);
			right: var(--s2);
			bottom: var(--s2);
		}
	}
</style>
