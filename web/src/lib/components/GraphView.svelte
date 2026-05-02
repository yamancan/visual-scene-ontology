<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		forceCenter,
		forceCollide,
		forceLink,
		forceManyBody,
		forceSimulation,
		forceX,
		forceY,
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

	// Pan/zoom state — applied as a single transform on a <g>.
	let zoom = $state(1);
	let panX = $state(0);
	let panY = $state(0);
	let dragging = $state(false);
	let dragStart = { x: 0, y: 0, panX: 0, panY: 0 };

	const KIND_GROUPS: Record<string, NodeKind[]> = {
		Frame: ['Composition', 'SceneContext', 'VisualStyle', 'CameraView'],
		Entity: ['PhysicalObject', 'Aggregate', 'Substance'],
		Quality: ['Quality'],
		Perdurant: ['Event', 'Process', 'Stative'],
		Spatial: ['SpatialFact'],
		Annotation: ['Annotation']
	};

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
			case 'Annotation':
				return 'var(--node-annotation, var(--fg-3))';
			default:
				return 'var(--fg-3)';
		}
	};

	const radiusOf = (k: NodeKind | undefined): number => {
		switch (k) {
			case 'Composition':
				return 10;
			case 'PhysicalObject':
			case 'Aggregate':
			case 'Substance':
				return 7.5;
			case 'Event':
			case 'Process':
			case 'Stative':
				return 6.5;
			case 'Quality':
				return 4;
			case 'SpatialFact':
				return 6;
			case 'Annotation':
				return 4;
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
					.distance(72)
					.strength(0.55)
			)
			.force('charge', forceManyBody().strength(-260))
			.force('center', forceCenter(w / 2, h / 2))
			.force('x', forceX(w / 2).strength(0.04))
			.force('y', forceY(h / 2).strength(0.04))
			.force(
				'collide',
				forceCollide<SimNode>().radius((d) => radiusOf(d.kind) + 5)
			)
			.alpha(0.9)
			.alphaDecay(0.035)
			.on('tick', () => {
				if (frame) cancelAnimationFrame(frame);
				frame = requestAnimationFrame(() => (tick += 1));
			});
	}

	$effect(() => {
		const env = scene.envelope;
		// reset transform on new scene
		zoom = 1;
		panX = 0;
		panY = 0;
		if (env?.graph) build(env.graph.nodes, env.graph.edges);
	});

	onMount(() => {
		if (!svgEl) return;
		const r0 = svgEl.getBoundingClientRect();
		if (r0.width > 0 && r0.height > 0) dims = { w: r0.width, h: r0.height };
		const ro = new ResizeObserver((entries) => {
			for (const e of entries) {
				const r = e.contentRect;
				if (r.width === 0 || r.height === 0) continue;
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
		void tick;
		const sel = scene.selectedNodeId;
		const hov = hover;
		return simEdges.map((e) => {
			const a = nodeAt(e.source);
			const b = nodeAt(e.target);
			const fromId = typeof e.source === 'string' ? e.source : e.source.id;
			const toId = typeof e.target === 'string' ? e.target : e.target.id;
			const touched = sel ? fromId === sel || toId === sel : false;
			const hovered = hov ? fromId === hov || toId === hov : false;
			return {
				x1: a?.x ?? 0,
				y1: a?.y ?? 0,
				x2: b?.x ?? 0,
				y2: b?.y ?? 0,
				label: e.label,
				fromId,
				toId,
				touched,
				hovered,
				dim: sel !== null && !touched
			};
		});
	});

	let neighbors = $derived.by(() => {
		const sel = scene.selectedNodeId;
		if (!sel) return new Set<string>();
		const set = new Set<string>([sel]);
		for (const e of simEdges) {
			const f = typeof e.source === 'string' ? e.source : e.source.id;
			const t = typeof e.target === 'string' ? e.target : e.target.id;
			if (f === sel) set.add(t);
			else if (t === sel) set.add(f);
		}
		return set;
	});

	// Pan + zoom handlers.
	function onWheel(e: WheelEvent) {
		e.preventDefault();
		const rect = svgEl?.getBoundingClientRect();
		if (!rect) return;
		const cx = e.clientX - rect.left;
		const cy = e.clientY - rect.top;
		const factor = Math.exp(-e.deltaY * 0.001);
		const next = Math.min(4, Math.max(0.4, zoom * factor));
		// Keep cursor anchor stable: zoom around cursor.
		panX = cx - (cx - panX) * (next / zoom);
		panY = cy - (cy - panY) * (next / zoom);
		zoom = next;
	}

	function onPointerDown(e: PointerEvent) {
		// Only start drag on background, not on a node group
		const t = e.target as Element;
		if (t.closest('g.node')) return;
		dragging = true;
		dragStart = { x: e.clientX, y: e.clientY, panX, panY };
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}
	function onPointerMove(e: PointerEvent) {
		if (!dragging) return;
		panX = dragStart.panX + (e.clientX - dragStart.x);
		panY = dragStart.panY + (e.clientY - dragStart.y);
	}
	function onPointerUp(e: PointerEvent) {
		dragging = false;
		(e.currentTarget as Element).releasePointerCapture?.(e.pointerId);
	}

	function resetView() {
		zoom = 1;
		panX = 0;
		panY = 0;
	}
	function zoomBy(f: number) {
		const w = dims.w || 600;
		const h = dims.h || 400;
		const cx = w / 2;
		const cy = h / 2;
		const next = Math.min(4, Math.max(0.4, zoom * f));
		panX = cx - (cx - panX) * (next / zoom);
		panY = cy - (cy - panY) * (next / zoom);
		zoom = next;
	}

	const LEGEND: { label: string; color: string }[] = [
		{ label: 'Frame', color: 'var(--node-frame)' },
		{ label: 'Entity', color: 'var(--node-entity)' },
		{ label: 'Quality', color: 'var(--node-quality)' },
		{ label: 'Event', color: 'var(--node-perdurant)' },
		{ label: 'Spatial', color: 'var(--node-spatialfact)' }
	];
	void KIND_GROUPS;
</script>

<div class="wrap">
	<svg
		bind:this={svgEl}
		class="canvas"
		role="img"
		aria-label="Scene graph"
		onwheel={onWheel}
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		onpointercancel={onPointerUp}
		class:dragging
	>
		<defs>
			<marker
				id="arrow"
				viewBox="0 0 8 8"
				refX="7.5"
				refY="4"
				markerWidth="7"
				markerHeight="7"
				orient="auto-start-reverse"
			>
				<path d="M0,0 L8,4 L0,8 z" fill="var(--border-2)" />
			</marker>
			<marker
				id="arrow-sel"
				viewBox="0 0 8 8"
				refX="7.5"
				refY="4"
				markerWidth="7"
				markerHeight="7"
				orient="auto-start-reverse"
			>
				<path d="M0,0 L8,4 L0,8 z" fill="var(--accent)" />
			</marker>
		</defs>

		<g transform="translate({panX},{panY}) scale({zoom})">
			{#each edgesForRender as e (e.fromId + '|' + e.label + '|' + e.toId)}
				<line
					x1={e.x1}
					y1={e.y1}
					x2={e.x2}
					y2={e.y2}
					stroke={e.touched ? 'var(--accent)' : 'var(--border-2)'}
					stroke-width={e.touched ? 1.4 : 0.8}
					marker-end={e.touched ? 'url(#arrow-sel)' : 'url(#arrow)'}
					opacity={e.dim ? 0.18 : e.touched || e.hovered ? 1 : 0.55}
				/>
				{#if e.touched || e.hovered}
					<text
						x={(e.x1 + e.x2) / 2}
						y={(e.y1 + e.y2) / 2 - 4}
						text-anchor="middle"
						font-family="var(--font-mono)"
						font-size={10 / zoom}
						fill="var(--fg-2)"
						style:user-select="none"
						pointer-events="none">{e.label}</text
					>
				{/if}
			{/each}

			{#each simNodes as n (n.id)}
				{@const r = radiusOf(n.kind)}
				{@const isSelected = scene.selectedNodeId === n.id}
				{@const isHover = hover === n.id}
				{@const isNeighbor = scene.selectedNodeId !== null && neighbors.has(n.id)}
				{@const dim = scene.selectedNodeId !== null && !isNeighbor}
				<g
					class="node"
					transform="translate({n.x ?? 0},{n.y ?? 0})"
					role="button"
					tabindex="0"
					onclick={() => selectNode(n.id)}
					onkeydown={(e) => e.key === 'Enter' && selectNode(n.id)}
					onmouseenter={() => (hover = n.id)}
					onmouseleave={() => (hover = null)}
					opacity={dim ? 0.35 : 1}
					style:cursor="pointer"
				>
					<circle
						r={r + 4}
						fill="transparent"
						stroke={isSelected ? 'var(--accent)' : 'transparent'}
						stroke-width={1.5 / zoom}
					/>
					<circle
						r={r}
						fill={n.kind === 'SpatialFact' ? 'var(--bg-0)' : colorOf(n.kind)}
						stroke={n.kind === 'SpatialFact' ? colorOf(n.kind) : 'transparent'}
						stroke-width={n.kind === 'SpatialFact' ? 1.5 : 0}
					/>
					{#if isHover || isSelected || (scene.selectedNodeId && isNeighbor)}
						<text
							x={r + 6}
							y={3.5}
							font-family="var(--font-mono)"
							font-size={11 / zoom}
							fill={isSelected ? 'var(--accent)' : 'var(--fg-1)'}
							style:user-select="none"
							pointer-events="none">{n.id}</text
						>
					{/if}
				</g>
			{/each}
		</g>
	</svg>

	<aside class="legend" aria-label="node kinds">
		{#each LEGEND as l (l.label)}
			<div class="legend-item">
				<span class="legend-dot" style:background={l.color}></span>
				<span>{l.label}</span>
			</div>
		{/each}
	</aside>

	<div class="zoom-ctl" aria-label="zoom controls">
		<button
			type="button"
			onclick={() => zoomBy(1.25)}
			title="Zoom in (or scroll up)">+</button
		>
		<button
			type="button"
			onclick={() => zoomBy(0.8)}
			title="Zoom out (or scroll down)">−</button
		>
		<button
			type="button"
			onclick={resetView}
			title="Reset view">⌖</button
		>
		<span class="zoom-readout font-mono">{Math.round(zoom * 100)}%</span>
	</div>

	{#if simNodes.length === 0}
		<div class="empty font-mono">no nodes</div>
	{/if}
</div>

<style>
	.wrap {
		position: relative;
		width: 100%;
		height: 100%;
		overflow: hidden;
		background:
			radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--fg-4) 22%, transparent) 1px, transparent 1px),
			var(--bg-0);
		background-size: 18px 18px;
	}
	.canvas {
		display: block;
		width: 100%;
		height: 100%;
		cursor: grab;
		touch-action: none;
	}
	.canvas.dragging {
		cursor: grabbing;
	}
	.legend {
		position: absolute;
		left: var(--s3);
		bottom: var(--s3);
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: var(--s2) var(--s3);
		background: color-mix(in srgb, var(--bg-1) 88%, transparent);
		backdrop-filter: blur(6px);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--fg-3);
		pointer-events: none;
	}
	.legend-item {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.legend-dot {
		width: 8px;
		height: 8px;
		border-radius: 9999px;
		flex-shrink: 0;
	}
	.zoom-ctl {
		position: absolute;
		right: var(--s3);
		bottom: var(--s3);
		display: flex;
		align-items: center;
		gap: 0;
		padding: 2px;
		background: color-mix(in srgb, var(--bg-1) 88%, transparent);
		backdrop-filter: blur(6px);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
	}
	.zoom-ctl button {
		width: 22px;
		height: 22px;
		display: grid;
		place-items: center;
		background: transparent;
		border: 0;
		color: var(--fg-3);
		font-family: var(--font-mono);
		font-size: 13px;
		line-height: 1;
		cursor: pointer;
		border-radius: var(--radius-sm);
		transition: background var(--duration-fast) var(--ease-out);
	}
	.zoom-ctl button:hover {
		background: var(--bg-2);
		color: var(--fg-0);
	}
	.zoom-readout {
		padding: 0 6px;
		font-size: 10px;
		color: var(--fg-4);
		font-variant-numeric: tabular-nums;
	}
	.empty {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		font-size: var(--text-2xs);
		color: var(--fg-4);
		pointer-events: none;
	}
</style>
