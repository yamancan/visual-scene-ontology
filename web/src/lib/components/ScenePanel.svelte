<script lang="ts">
	import GraphView from './GraphView.svelte';
	import TabsRail from './TabsRail.svelte';
	import SceneHeader from './SceneHeader.svelte';
	import ExportRow from './ExportRow.svelte';
	import { scene } from '$lib/scene.svelte';

	let railOpen = $state(true);
	let nodeCount = $derived(scene.envelope?.graph?.nodes.length ?? 0);
</script>

<div class="panel">
	<SceneHeader />

	<main class="body" class:rail-collapsed={!railOpen}>
		<section class="graph">
			<header class="bar">
				<span class="font-mono bar-label">graph</span>
				<span class="bar-meta font-mono">
					{nodeCount} nodes · drag to pan · scroll to zoom
				</span>
			</header>
			<div class="graph-host">
				<GraphView />
			</div>
		</section>

		<aside class="rail" aria-hidden={!railOpen}>
			<button
				type="button"
				class="rail-toggle"
				onclick={() => (railOpen = !railOpen)}
				aria-label={railOpen ? 'Hide right rail' : 'Show right rail'}
				aria-expanded={railOpen}
				title={railOpen ? 'Hide rail' : 'Show rail'}
			>
				<svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true">
					<path
						d={railOpen ? 'M3 2 L7 7 L3 12' : 'M7 2 L3 7 L7 12'}
						stroke="currentColor"
						stroke-width="1.5"
						fill="none"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
				</svg>
			</button>
			<div class="rail-inner">
				<TabsRail />
			</div>
		</aside>
	</main>

	<footer class="foot">
		<ExportRow />
	</footer>
</div>

<style>
	.panel {
		display: grid;
		grid-template-rows: auto 1fr auto;
		height: 100%;
		min-height: 0;
		background: var(--bg-0);
	}
	.body {
		display: grid;
		grid-template-columns: minmax(0, 1.4fr) minmax(360px, 0.9fr);
		min-height: 0;
		position: relative;
	}
	.body.rail-collapsed {
		grid-template-columns: minmax(0, 1fr) 0;
	}
	.graph {
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		border-right: 1px solid var(--border-1);
	}
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: var(--s2) var(--s3);
		border-bottom: 1px solid var(--border-1);
		flex-shrink: 0;
	}
	.bar-label {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
	.bar-meta {
		font-size: 10px;
		color: var(--fg-4);
	}
	.graph-host {
		flex: 1;
		min-height: 0;
		position: relative;
	}
	.rail {
		position: relative;
		min-height: 0;
		min-width: 0;
		overflow: visible;
		display: flex;
		flex-direction: column;
	}
	.rail-inner {
		flex: 1;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
		transition: opacity var(--duration-fast) var(--ease-out);
	}
	.body.rail-collapsed .rail-inner {
		opacity: 0;
		pointer-events: none;
	}
	.rail-toggle {
		position: absolute;
		top: 50%;
		left: -12px;
		transform: translateY(-50%);
		z-index: 5;
		width: 22px;
		height: 44px;
		display: grid;
		place-items: center;
		background: var(--bg-1);
		color: var(--fg-3);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.body.rail-collapsed .rail-toggle {
		left: auto;
		right: 8px;
	}
	.rail-toggle:hover {
		color: var(--accent);
		background: var(--bg-2);
	}
	.foot {
		border-top: 1px solid var(--border-1);
		background: var(--bg-1);
		flex-shrink: 0;
	}
	@media (max-width: 900px) {
		.body {
			grid-template-columns: 1fr;
			grid-template-rows: minmax(40vh, 1fr) minmax(30vh, 1fr);
		}
		.body.rail-collapsed {
			grid-template-columns: 1fr;
			grid-template-rows: 1fr 0;
		}
		.graph {
			border-right: 0;
			border-bottom: 1px solid var(--border-1);
		}
		.rail-toggle {
			top: -12px;
			left: 50%;
			transform: translateX(-50%) rotate(90deg);
		}
		.body.rail-collapsed .rail-toggle {
			top: auto;
			left: 50%;
			right: auto;
			bottom: 8px;
		}
	}
</style>
