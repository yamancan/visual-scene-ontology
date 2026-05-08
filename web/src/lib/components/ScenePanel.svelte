<script lang="ts">
	import SceneFlow from './SceneFlow.svelte';
	import FactsStrip from './FactsStrip.svelte';
	import SceneFrame from './SceneFrame.svelte';
	import TabsRail from './TabsRail.svelte';
	import SceneHeader from './SceneHeader.svelte';
	import ExportRow from './ExportRow.svelte';
	import { scene } from '$lib/scene.svelte';

	let railOpen = $state(true);
	let factsOpen = $state(true);
	let nodeCount = $derived(scene.envelope?.graph?.nodes.length ?? 0);
	let edgeCount = $derived(scene.envelope?.graph?.edges.length ?? 0);
	let entityCount = $derived(
		scene.envelope?.graph?.nodes.filter((n) =>
			['PhysicalObject', 'Aggregate', 'Substance'].includes(n.kind)
		).length ?? 0
	);
	let spatialCount = $derived(
		scene.envelope?.graph?.nodes.filter((n) => n.kind === 'SpatialFact').length ?? 0
	);
	let meta = $derived(`${entityCount} entities · ${nodeCount} nodes · ${edgeCount} edges`);
</script>

<div class="panel">
	<SceneHeader />

	<main class="body" class:rail-collapsed={!railOpen}>
		<section class="stage">
			<SceneFrame {meta}>
				<div class="split" class:facts-collapsed={!factsOpen}>
					<div class="flow-pane">
						<SceneFlow />
					</div>
					{#if spatialCount > 0}
						<div class="divider" role="separator" aria-orientation="horizontal">
							<button
								type="button"
								class="facts-toggle"
								onclick={() => (factsOpen = !factsOpen)}
								aria-label={factsOpen ? 'Collapse facts' : 'Expand facts'}
								aria-expanded={factsOpen}
							>
								<span class="font-mono">facts · {spatialCount} spatial</span>
								<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
									<path
										d={factsOpen ? 'M2 6 L5 3 L8 6' : 'M2 4 L5 7 L8 4'}
										stroke="currentColor"
										stroke-width="1.4"
										fill="none"
										stroke-linecap="round"
										stroke-linejoin="round"
									/>
								</svg>
							</button>
						</div>
						{#if factsOpen}
							<div class="facts-pane">
								<FactsStrip />
							</div>
						{/if}
					{/if}
				</div>
			</SceneFrame>
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
	.stage {
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		border-right: 1px solid var(--border-1);
	}
	.split {
		display: grid;
		grid-template-rows: minmax(0, 1.6fr) auto minmax(0, 0.6fr);
		height: 100%;
		min-height: 0;
	}
	.split.facts-collapsed {
		grid-template-rows: minmax(0, 1fr) auto 0;
	}
	.flow-pane {
		min-height: 0;
		position: relative;
		overflow: hidden;
	}
	.facts-pane {
		min-height: 0;
		overflow: hidden;
	}
	.divider {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0 var(--s3);
		border-top: 1px solid var(--border-1);
		border-bottom: 1px solid var(--border-1);
		background: var(--bg-1);
		flex-shrink: 0;
	}
	.facts-toggle {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 10px;
		border: 0;
		background: transparent;
		color: var(--fg-3);
		cursor: pointer;
		font-family: inherit;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		transition: color var(--duration-fast) var(--ease-out);
	}
	.facts-toggle:hover {
		color: var(--fg-0);
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
		.stage {
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
