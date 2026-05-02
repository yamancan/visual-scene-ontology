<script lang="ts">
	import { onMount, onDestroy, untrack } from 'svelte';
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
		label: string;
		sub: string;
		w: number;
		h: number;
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
	let tick = $state(0);

	// Pan/zoom state.
	let zoom = $state(1);
	let panX = $state(0);
	let panY = $state(0);
	let panning = $state(false);
	let panStart = { x: 0, y: 0, panX: 0, panY: 0 };

	// Per-node drag state.
	let dragNode = $state<string | null>(null);
	let nodeDragOffset = { dx: 0, dy: 0 };

	// Track whether we've performed the auto-fit on the current scene.
	let didFit = false;

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
				return 'var(--node-annotation)';
			default:
				return 'var(--fg-3)';
		}
	};

	function shorten(s: string, max: number): string {
		return s.length <= max ? s : s.slice(0, max - 1) + '…';
	}

	// Each node renders as a card. Width depends on label length, capped.
	function makeNode(n: GraphNode): SimNode {
		const label = shorten(n.class ?? n.kind, 18);
		const sub = shorten(n.id, 16);
		const w = Math.max(110, Math.min(180, label.length * 7.4 + 24));
		const h = 38;
		return { ...n, label, sub, w, h };
	}

	function build(nodes: GraphNode[], edges: GraphEdge[]) {
		const W = dims.w || 1000;
		const H = dims.h || 600;
		// Seed positions on a ring around center so the center force has
		// nothing to do, and collision/charge forces can spread nodes
		// outward into a stable layout.
		const ringR = Math.min(W, H) * 0.32;
		const cx = W / 2;
		const cy = H / 2;
		simNodes = nodes.map((n, i) => {
			const sn = makeNode(n);
			const angle = (i / Math.max(1, nodes.length)) * Math.PI * 2;
			sn.x = cx + Math.cos(angle) * ringR;
			sn.y = cy + Math.sin(angle) * ringR;
			return sn;
		});
		simEdges = edges.map((e) => ({ source: e.from, target: e.to, label: e.label }));
		if (sim) sim.stop();
		sim = forceSimulation<SimNode, SimEdge>(simNodes)
			.force(
				'link',
				forceLink<SimNode, SimEdge>(simEdges)
					.id((d) => d.id)
					.distance(120)
					.strength(0.45)
			)
			.force('charge', forceManyBody<SimNode>().strength(-720))
			.force('center', forceCenter(cx, cy))
			.force('x', forceX<SimNode>(cx).strength(0.04))
			.force('y', forceY<SimNode>(cy).strength(0.05))
			.force(
				'collide',
				forceCollide<SimNode>().radius((d) => Math.max(d.w, d.h) / 2 + 14)
			)
			.alpha(1)
			.alphaDecay(0.024)
			.on('tick', () => {
				if (frame) cancelAnimationFrame(frame);
				frame = requestAnimationFrame(() => (tick += 1));
			})
			.on('end', () => {
				if (!didFit) {
					didFit = true;
					fitToView(60);
				}
			});
		didFit = false;
	}

	function fitToView(padding = 40) {
		if (simNodes.length === 0 || dims.w === 0 || dims.h === 0) return;
		let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
		for (const n of simNodes) {
			if (n.x === undefined || n.y === undefined) continue;
			minX = Math.min(minX, n.x - n.w / 2);
			minY = Math.min(minY, n.y - n.h / 2);
			maxX = Math.max(maxX, n.x + n.w / 2);
			maxY = Math.max(maxY, n.y + n.h / 2);
		}
		if (!isFinite(minX)) return;
		const contentW = maxX - minX + padding * 2;
		const contentH = maxY - minY + padding * 2;
		const scale = Math.min(dims.w / contentW, dims.h / contentH, 1.1);
		const cx = (minX + maxX) / 2;
		const cy = (minY + maxY) / 2;
		zoom = Math.max(0.4, scale);
		panX = dims.w / 2 - cx * zoom;
		panY = dims.h / 2 - cy * zoom;
	}

	$effect(() => {
		const env = scene.envelope;
		if (env?.graph && dims.w > 0) {
			untrack(() => build(env.graph!.nodes, env.graph!.edges));
		}
	});

	onMount(() => {
		if (!svgEl) return;
		const r0 = svgEl.getBoundingClientRect();
		if (r0.width > 0 && r0.height > 0) dims = { w: r0.width, h: r0.height };
		const ro = new ResizeObserver((entries) => {
			for (const e of entries) {
				const r = e.contentRect;
				if (r.width === 0 || r.height === 0) continue;
				const wasZero = dims.w === 0;
				dims = { w: r.width, h: r.height };
				// First dim-resolve: build now, no longer rely on the build effect
				// having dims at envelope-set time.
				if (wasZero && scene.envelope?.graph) {
					build(scene.envelope.graph.nodes, scene.envelope.graph.edges);
				} else if (sim) {
					sim.force('center', forceCenter(r.width / 2, r.height / 2));
					sim.alpha(0.3).restart();
				}
			}
		});
		ro.observe(svgEl);
		svgEl.addEventListener('wheel', onWheel, { passive: false });
		return () => {
			ro.disconnect();
			svgEl?.removeEventListener('wheel', onWheel);
		};
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

	let edgesForRender = $derived.by(() => {
		void tick;
		const sel = scene.selectedNodeId;
		const hov = hover;
		return simEdges.map((e) => {
			const a = nodeAt(e.source);
			const b = nodeAt(e.target);
			const ax = a?.x ?? 0;
			const ay = a?.y ?? 0;
			const bx = b?.x ?? 0;
			const by = b?.y ?? 0;
			const fromId = typeof e.source === 'string' ? e.source : e.source.id;
			const toId = typeof e.target === 'string' ? e.target : e.target.id;
			const touched = sel ? fromId === sel || toId === sel : false;
			const hovered = hov ? fromId === hov || toId === hov : false;
			// Cubic bezier control points biased horizontally for a clean
			// n8n-ish curve, with a slight vertical relaxation on near-vertical
			// edges so the spline doesn't snap to a straight line.
			const dx = bx - ax;
			const dy = by - ay;
			const horizK = 0.5;
			const c1x = ax + dx * horizK;
			const c1y = ay + dy * 0.1;
			const c2x = bx - dx * horizK;
			const c2y = by - dy * 0.1;
			const path = `M ${ax} ${ay} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${bx} ${by}`;
			return {
				path,
				ax,
				ay,
				bx,
				by,
				label: e.label,
				fromId,
				toId,
				touched,
				hovered,
				dim: sel !== null && !touched
			};
		});
	});

	// Wheel zoom around cursor.
	function onWheel(e: WheelEvent) {
		e.preventDefault();
		const rect = svgEl?.getBoundingClientRect();
		if (!rect) return;
		const cx = e.clientX - rect.left;
		const cy = e.clientY - rect.top;
		const factor = Math.exp(-e.deltaY * 0.0012);
		const next = Math.min(3, Math.max(0.25, zoom * factor));
		panX = cx - (cx - panX) * (next / zoom);
		panY = cy - (cy - panY) * (next / zoom);
		zoom = next;
	}

	function clientToWorld(clientX: number, clientY: number) {
		const rect = svgEl?.getBoundingClientRect();
		if (!rect) return { x: 0, y: 0 };
		const sx = clientX - rect.left;
		const sy = clientY - rect.top;
		return { x: (sx - panX) / zoom, y: (sy - panY) / zoom };
	}

	function onPointerDown(e: PointerEvent) {
		const t = e.target as Element;
		const nodeG = t.closest<SVGGElement>('g.node');
		if (nodeG) {
			const id = nodeG.dataset.id;
			if (id) {
				const n = simNodes.find((x) => x.id === id);
				if (n) {
					const w = clientToWorld(e.clientX, e.clientY);
					nodeDragOffset = { dx: w.x - (n.x ?? 0), dy: w.y - (n.y ?? 0) };
					n.fx = n.x ?? 0;
					n.fy = n.y ?? 0;
					dragNode = id;
					if (sim) sim.alphaTarget(0.25).restart();
					(e.currentTarget as Element).setPointerCapture(e.pointerId);
				}
			}
			return;
		}
		// Background → start panning.
		panning = true;
		panStart = { x: e.clientX, y: e.clientY, panX, panY };
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}

	function onPointerMove(e: PointerEvent) {
		if (dragNode) {
			const n = simNodes.find((x) => x.id === dragNode);
			if (!n) return;
			const w = clientToWorld(e.clientX, e.clientY);
			n.fx = w.x - nodeDragOffset.dx;
			n.fy = w.y - nodeDragOffset.dy;
			tick += 1;
			return;
		}
		if (panning) {
			panX = panStart.panX + (e.clientX - panStart.x);
			panY = panStart.panY + (e.clientY - panStart.y);
		}
	}

	function onPointerUp(e: PointerEvent) {
		if (dragNode) {
			const n = simNodes.find((x) => x.id === dragNode);
			if (n) {
				// Free the node so simulation can keep balancing things, but
				// hold position by zeroing velocity.
				n.fx = null;
				n.fy = null;
			}
			if (sim) sim.alphaTarget(0);
			dragNode = null;
		}
		panning = false;
		(e.currentTarget as Element).releasePointerCapture?.(e.pointerId);
	}

	function resetView() {
		didFit = false;
		fitToView(60);
		didFit = true;
	}
	function zoomBy(f: number) {
		const W = dims.w || 600;
		const H = dims.h || 400;
		const cx = W / 2;
		const cy = H / 2;
		const next = Math.min(3, Math.max(0.25, zoom * f));
		panX = cx - (cx - panX) * (next / zoom);
		panY = cy - (cy - panY) * (next / zoom);
		zoom = next;
	}

	const LEGEND: { label: string; color: string }[] = [
		{ label: 'Frame', color: 'var(--node-frame)' },
		{ label: 'Entity', color: 'var(--node-entity)' },
		{ label: 'Quality', color: 'var(--node-quality)' },
		{ label: 'Event', color: 'var(--node-perdurant)' },
		{ label: 'Spatial', color: 'var(--node-spatialfact)' },
		{ label: 'Annotation', color: 'var(--node-annotation)' }
	];
</script>

<div class="wrap">
	<svg
		bind:this={svgEl}
		class="canvas"
		role="img"
		aria-label="Scene graph"
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		onpointercancel={onPointerUp}
		class:panning
		class:dragging-node={dragNode !== null}
	>
		<defs>
			<pattern
				id="dotgrid"
				x={panX}
				y={panY}
				width={20 * zoom}
				height={20 * zoom}
				patternUnits="userSpaceOnUse"
			>
				<circle cx="1" cy="1" r="0.9" fill="var(--border-2)" opacity="0.5" />
			</pattern>
			<marker
				id="arrow"
				viewBox="0 0 10 10"
				refX="9"
				refY="5"
				markerWidth="6"
				markerHeight="6"
				orient="auto-start-reverse"
			>
				<path d="M0,0 L10,5 L0,10 z" fill="var(--border-2)" />
			</marker>
			<marker
				id="arrow-sel"
				viewBox="0 0 10 10"
				refX="9"
				refY="5"
				markerWidth="6"
				markerHeight="6"
				orient="auto-start-reverse"
			>
				<path d="M0,0 L10,5 L0,10 z" fill="var(--accent)" />
			</marker>
		</defs>

		<!-- Background grid that pans with the content -->
		<rect class="grid-bg" width="100%" height="100%" fill="url(#dotgrid)" />

		<g transform="translate({panX},{panY}) scale({zoom})">
			{#each edgesForRender as e (e.fromId + '|' + e.label + '|' + e.toId)}
				<path
					d={e.path}
					stroke={e.touched ? 'var(--accent)' : 'var(--border-2)'}
					stroke-width={(e.touched ? 1.5 : 1) / zoom}
					fill="none"
					marker-end={e.touched ? 'url(#arrow-sel)' : 'url(#arrow)'}
					opacity={e.dim ? 0.18 : e.touched || e.hovered ? 1 : 0.55}
				/>
				{#if e.touched || e.hovered}
					<text
						x={(e.ax + e.bx) / 2}
						y={(e.ay + e.by) / 2 - 4 / zoom}
						text-anchor="middle"
						font-family="var(--font-mono)"
						font-size={10 / zoom}
						fill="var(--fg-1)"
						style:user-select="none"
						pointer-events="none"
						class="edge-label"
					>
						{e.label}
					</text>
				{/if}
			{/each}

			{#each simNodes as n (n.id)}
				{@const isSelected = scene.selectedNodeId === n.id}
				{@const isHover = hover === n.id}
				{@const isNeighbor = scene.selectedNodeId !== null && neighbors.has(n.id)}
				{@const dim = scene.selectedNodeId !== null && !isNeighbor}
				{@const color = colorOf(n.kind)}
				<g
					class="node"
					data-id={n.id}
					transform="translate({n.x ?? 0},{n.y ?? 0})"
					role="button"
					tabindex="0"
					onclick={() => selectNode(n.id)}
					onkeydown={(e) => e.key === 'Enter' && selectNode(n.id)}
					onmouseenter={() => (hover = n.id)}
					onmouseleave={() => (hover = null)}
					opacity={dim ? 0.35 : 1}
					style:cursor={dragNode === n.id ? 'grabbing' : 'grab'}
				>
					<rect
						class="card-shadow"
						x={-n.w / 2 + 1}
						y={-n.h / 2 + 2}
						width={n.w}
						height={n.h}
						rx="7"
						fill="black"
						opacity="0.18"
					/>
					<rect
						class="card"
						x={-n.w / 2}
						y={-n.h / 2}
						width={n.w}
						height={n.h}
						rx="7"
						fill="var(--bg-1)"
						stroke={isSelected ? 'var(--accent)' : isHover ? color : 'var(--border-1)'}
						stroke-width={isSelected ? 1.6 : 1}
					/>
					<rect
						class="strip"
						x={-n.w / 2}
						y={-n.h / 2}
						width="3"
						height={n.h}
						rx="1.5"
						fill={color}
					/>
					<text
						x={-n.w / 2 + 12}
						y="-2"
						font-family="var(--font-body)"
						font-size="12"
						font-weight="500"
						fill={isSelected ? 'var(--accent)' : 'var(--fg-0)'}
						style:user-select="none"
						pointer-events="none"
					>
						{n.label}
					</text>
					<text
						x={-n.w / 2 + 12}
						y="11"
						font-family="var(--font-mono)"
						font-size="10"
						fill="var(--fg-4)"
						style:user-select="none"
						pointer-events="none"
					>
						{n.sub}
					</text>
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
			title="Zoom in (or scroll up)"
			aria-label="zoom in"
		>
			<svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
				<path d="M6 2 V10 M2 6 H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
			</svg>
		</button>
		<button
			type="button"
			onclick={() => zoomBy(0.8)}
			title="Zoom out (or scroll down)"
			aria-label="zoom out"
		>
			<svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
				<path d="M2 6 H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
			</svg>
		</button>
		<button type="button" onclick={resetView} title="Fit to content" aria-label="fit to content">
			<svg width="12" height="12" viewBox="0 0 14 14" aria-hidden="true">
				<path
					d="M2 5 V2 H5 M9 2 H12 V5 M12 9 V12 H9 M5 12 H2 V9"
					stroke="currentColor"
					stroke-width="1.4"
					fill="none"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
		</button>
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
		background: var(--bg-0);
	}
	.canvas {
		display: block;
		width: 100%;
		height: 100%;
		cursor: grab;
		touch-action: none;
		pointer-events: all;
	}
	.canvas.panning {
		cursor: grabbing;
	}
	.canvas.dragging-node {
		cursor: grabbing;
	}
	.grid-bg {
		pointer-events: none;
	}
	.legend {
		position: absolute;
		left: var(--s3);
		bottom: var(--s3);
		display: grid;
		grid-template-columns: repeat(2, auto);
		gap: 2px var(--s3);
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
		width: 24px;
		height: 24px;
		display: grid;
		place-items: center;
		background: transparent;
		border: 0;
		color: var(--fg-3);
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
		min-width: 38px;
		text-align: right;
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
	.node:focus-visible .card {
		stroke: var(--accent);
		stroke-width: 2;
	}
</style>
