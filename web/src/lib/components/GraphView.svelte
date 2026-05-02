<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		forceCenter,
		forceCollide,
		forceLink,
		forceManyBody,
		forceSimulation,
		type Simulation
	} from 'd3-force';
	import { scene } from '$lib/scene.svelte';
	import type { GraphEdge, GraphNode, NodeKind } from '$lib/types';

	interface SimNode extends GraphNode {
		x?: number;
		y?: number;
		fx?: number | null;
		fy?: number | null;
		vx?: number;
		vy?: number;
	}
	interface SimEdge {
		source: string | SimNode;
		target: string | SimNode;
		label: string;
	}

	let simNodes = $state<SimNode[]>([]);
	let simEdges = $state<SimEdge[]>([]);
	let hover = $state<string | null>(null);
	let dims = $state({ w: 0, h: 0 });
	let svgEl: SVGSVGElement | undefined = $state();
	let sim: Simulation<SimNode, SimEdge> | null = null;
	let frame = 0;
	let tick = $state(0); // bumped each render to force reactivity

	const colorOf = (k: NodeKind | undefined): string => {
		switch (k) {
			case 'Composition':
			case 'SceneContext':
			case 'VisualStyle':
			case 'CameraView':
				return 'var(--node-frame)';
			case 'PhysicalObject':
			case 'Aggregate':
			case 'Substance':
				return 'var(--node-entity)';
			case 'Quality':
				return 'var(--node-quality)';
			case 'Event':
			case 'Process':
			case 'Stative':
				return 'var(--node-perdurant)';
			case 'SpatialFact':
				return 'var(--node-spatialfact)';
			default:
				return 'var(--fg-3)';
		}
	};

	const radiusOf = (k: NodeKind | undefined): number => {
		switch (k) {
			case 'Composition':
				return 9;
			case 'PhysicalObject':
			case 'Aggregate':
			case 'Substance':
				return 7;
			case 'Event':
			case 'Process':
			case 'Stative':
				return 6;
			case 'Quality':
				return 4;
			case 'SpatialFact':
				return 6;
			default:
				return 5;
		}
	};

	function build(nodes: GraphNode[], edges: GraphEdge[]) {
		simNodes = nodes.map((n) => ({ ...n }));
		simEdges = edges.map((e) => ({ source: e.from, target: e.to, label: e.label }));
		if (sim) sim.stop();
		const w = dims.w || 600;
		const h = dims.h || 400;
		sim = forceSimulation<SimNode, SimEdge>(simNodes)
			.force(
				'link',
				forceLink<SimNode, SimEdge>(simEdges)
					.id((d) => d.id)
					.distance(70)
					.strength(0.6)
			)
			.force('charge', forceManyBody().strength(-220))
			.force('center', forceCenter(w / 2, h / 2))
			.force(
				'collide',
				forceCollide<SimNode>().radius((d) => radiusOf(d.kind) + 4)
			)
			.alphaDecay(0.04)
			.on('tick', () => {
				if (frame) cancelAnimationFrame(frame);
				frame = requestAnimationFrame(() => (tick += 1));
			});
	}

	$effect(() => {
		const env = scene.envelope;
		if (env?.graph && dims.w > 0) build(env.graph.nodes, env.graph.edges);
	});

	onMount(() => {
		if (!svgEl) return;
		const ro = new ResizeObserver((entries) => {
			for (const e of entries) {
				const r = e.contentRect;
				dims = { w: r.width, h: r.height };
				if (sim) {
					sim.force('center', forceCenter(r.width / 2, r.height / 2));
					sim.alpha(0.3).restart();
				}
			}
		});
		ro.observe(svgEl);
		return () => ro.disconnect();
	});

	onDestroy(() => {
		if (sim) sim.stop();
		if (frame) cancelAnimationFrame(frame);
	});

	function nodeAt(id: string | SimNode): SimNode | undefined {
		if (typeof id === 'string') return simNodes.find((n) => n.id === id);
		return id;
	}

	function selectNode(id: string) {
		scene.setSelected(scene.selectedNodeId === id ? null : id);
	}

	let edgesForRender = $derived.by(() => {
		// Reactive on tick so coords flush.
		void tick;
		return simEdges.map((e) => {
			const a = nodeAt(e.source);
			const b = nodeAt(e.target);
			return {
				x1: a?.x ?? 0,
				y1: a?.y ?? 0,
				x2: b?.x ?? 0,
				y2: b?.y ?? 0,
				label: e.label,
				fromId: typeof e.source === 'string' ? e.source : e.source.id,
				toId: typeof e.target === 'string' ? e.target : e.target.id,
				selected: hover !== null && (hover === (typeof e.source === 'string' ? e.source : e.source.id) || hover === (typeof e.target === 'string' ? e.target : e.target.id))
			};
		});
	});
</script>

<svg
	bind:this={svgEl}
	class="h-full w-full"
	role="img"
	aria-label="Scene graph"
	style:background="transparent"
>
	<defs>
		<marker
			id="arrow"
			viewBox="0 0 8 8"
			refX="7.5"
			refY="4"
			markerWidth="8"
			markerHeight="8"
			orient="auto-start-reverse"
		>
			<path d="M0,0 L8,4 L0,8 z" fill="var(--border-1)" />
		</marker>
		<marker
			id="arrow-sel"
			viewBox="0 0 8 8"
			refX="7.5"
			refY="4"
			markerWidth="8"
			markerHeight="8"
			orient="auto-start-reverse"
		>
			<path d="M0,0 L8,4 L0,8 z" fill="var(--accent)" />
		</marker>
	</defs>

	{#each edgesForRender as e (e.fromId + '|' + e.label + '|' + e.toId)}
		<line
			x1={e.x1}
			y1={e.y1}
			x2={e.x2}
			y2={e.y2}
			stroke={e.selected ? 'var(--accent)' : 'var(--border-1)'}
			stroke-width={e.selected ? 1.2 : 0.8}
			marker-end={e.selected ? 'url(#arrow-sel)' : 'url(#arrow)'}
			opacity={e.selected ? 1 : 0.7}
		/>
		{#if e.selected || hover === e.fromId || hover === e.toId}
			<text
				x={(e.x1 + e.x2) / 2}
				y={(e.y1 + e.y2) / 2 - 4}
				text-anchor="middle"
				font-family="var(--font-mono)"
				font-size="10"
				fill="var(--fg-3)"
				style:user-select="none"
				pointer-events="none">{e.label}</text
			>
		{/if}
	{/each}

	{#each simNodes as n (n.id)}
		{@const r = radiusOf(n.kind)}
		{@const isSelected = scene.selectedNodeId === n.id}
		{@const isHover = hover === n.id}
		<g
			transform="translate({n.x ?? 0},{n.y ?? 0})"
			role="button"
			tabindex="0"
			onclick={() => selectNode(n.id)}
			onkeydown={(e) => e.key === 'Enter' && selectNode(n.id)}
			onmouseenter={() => (hover = n.id)}
			onmouseleave={() => (hover = null)}
			style:cursor="pointer"
		>
			<circle
				r={r + 4}
				fill="transparent"
				stroke={isSelected ? 'var(--accent)' : 'transparent'}
				stroke-width="1"
			/>
			<circle
				r={r}
				fill={colorOf(n.kind)}
				opacity={n.kind === 'SpatialFact' ? 0 : 1}
				stroke={n.kind === 'SpatialFact' ? colorOf(n.kind) : 'transparent'}
				stroke-width={n.kind === 'SpatialFact' ? 1.5 : 0}
			/>
			{#if isHover || isSelected}
				<text
					x={r + 6}
					y={3}
					font-family="var(--font-mono)"
					font-size="11"
					fill="var(--fg-0)"
					style:user-select="none"
					pointer-events="none">{n.id}</text
				>
			{/if}
		</g>
	{/each}
</svg>
