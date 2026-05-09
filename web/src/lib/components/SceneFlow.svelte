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
	import { scene } from '$lib/scene.svelte';
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

	function getBbox(entityId: string): [number, number, number, number] | null {
		const src = scene.envelope?.graph?.nodes.find((n) => n.id === entityId);
		if (!src) return null;
		const raw = (src.properties?.bbox2d ?? src.bbox2d) as string | number | undefined;
		if (raw == null) return null;
		const parts = String(raw).split(',').map(Number);
		if (parts.length !== 4 || parts.some((p) => Number.isNaN(p))) return null;
		return parts as [number, number, number, number];
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
			const aFull = ba && ba[2] >= 0.95 && ba[3] >= 0.95;
			const bFull = bb && bb[2] >= 0.95 && bb[3] >= 0.95;
			if (aFull && !bFull) return 1;
			if (!aFull && bFull) return -1;
			if (!ba && !bb) return a.id.localeCompare(b.id);
			if (!ba) return 1;
			if (!bb) return -1;
			return ba[0] - bb[0];
		});

		nodes = sorted.map((e, i) => {
			const bb = getBbox(e.id);
			const isFull = bb && bb[2] >= 0.95 && bb[3] >= 0.95;
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
</script>

<div class="scene-flow">
	{#if isEmpty}
		<div class="empty font-mono">no entities</div>
	{:else}
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

		</SvelteFlow>

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
	{/if}
</div>

<style>
	.scene-flow {
		position: relative;
		height: 100%;
		min-height: 0;
		background: var(--bg-0);
	}
	.empty {
		display: grid;
		place-items: center;
		height: 100%;
		color: var(--fg-4);
		font-size: var(--text-2xs);
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
		font-family:
			ui-monospace,
			SFMono-Regular,
			Menlo,
			monospace;
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

	/* Floating frame-meta chip-rail anchored to the bottom of the flow
	 * canvas (not the parent SceneFrame body) so it never overlaps the
	 * FactsStrip pane that sits below the flow in ScenePanel. */
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
			0 4px 14px -8px rgba(0, 0, 0, 0.18);
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
