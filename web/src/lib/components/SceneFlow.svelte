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
	import { buildSceneView } from '$lib/render/sceneView';

	const nodeTypes = { entity: EntityNode };

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
			<Controls />
		</SvelteFlow>
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
	:global(.svelte-flow) {
		background: var(--bg-0);
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
</style>
