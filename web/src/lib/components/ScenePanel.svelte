<script lang="ts">
	import SceneFlow from './SceneFlow.svelte';
	import FactsStrip from './FactsStrip.svelte';
	import SceneFrame from './SceneFrame.svelte';
	import TabsRail from './TabsRail.svelte';
	import SceneHeader from './SceneHeader.svelte';
	import ExportRow from './ExportRow.svelte';
	import CorrectionBar from './CorrectionBar.svelte';
	import MaxButton from './MaxButton.svelte';
	import { scene } from '$lib/scene.svelte';
	import { layout } from '$lib/layout.svelte';

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

	// A scene with no spatial facts has nothing to show in the FactsStrip, so the
	// pane only appears when both the layout says so AND there are facts to render.
	let factsShown = $derived(spatialCount > 0 && layout.factsVisible);
	let splitRows = $derived(
		layout.isMax('facts')
			? '0 auto minmax(0,1fr)'
			: factsShown
				? 'minmax(0,1.6fr) auto minmax(0,0.6fr)'
				: 'minmax(0,1fr) auto 0'
	);

	// Escape releases a maximized pane — matches the universal "Esc leaves
	// fullscreen" convention so a maximized panel never traps the user. We bow
	// out when a field is focused so we never steal Escape from the model
	// picker's search or a correction note (those dismiss themselves first).
	function onWindowKey(e: KeyboardEvent) {
		if (e.key !== 'Escape' || !layout.anyMax) return;
		const el = document.activeElement as HTMLElement | null;
		const tag = el?.tagName;
		if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el?.isContentEditable) return;
		layout.clearMax();
	}
</script>

<svelte:window onkeydown={onWindowKey} />

<div class="panel">
	<SceneHeader />

	<main class="body" style={'--body-cols:' + layout.bodyCols}>
		{#if layout.stageVisible}
			<section class="stage">
				<SceneFrame {meta}>
					<div class="split" style={'--split-rows:' + splitRows}>
						<div class="flow-pane">
							<SceneFlow />
						</div>
						{#if spatialCount > 0}
							<div class="divider" role="separator" aria-orientation="horizontal">
								<button
									type="button"
									class="facts-toggle"
									onclick={() => layout.togglePanel('facts')}
									aria-label={layout.factsVisible ? 'Collapse facts' : 'Expand facts'}
									aria-expanded={layout.factsVisible}
								>
									<span class="font-mono">facts · {spatialCount} spatial</span>
									<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
										<path
											d={layout.factsVisible ? 'M2 6 L5 3 L8 6' : 'M2 4 L5 7 L8 4'}
											stroke="currentColor"
											stroke-width="1.4"
											fill="none"
											stroke-linecap="round"
											stroke-linejoin="round"
										/>
									</svg>
								</button>
								<MaxButton panel="facts" />
							</div>
							{#if factsShown || layout.isMax('facts')}
								<div class="facts-pane">
									<FactsStrip />
								</div>
							{/if}
						{/if}
					</div>
				</SceneFrame>
				<CorrectionBar />
			</section>
		{/if}

		<aside
			class="rail"
			class:collapsed={!layout.railVisible}
			class:rail-gone={layout.anyMax && !layout.isMax('notation')}
		>
			<button
				type="button"
				class="rail-toggle"
				onclick={() => layout.togglePanel('rail')}
				aria-label={layout.railVisible ? 'Hide right rail' : 'Show right rail'}
				aria-expanded={layout.railVisible}
				title={layout.railVisible ? 'Hide rail' : 'Show rail'}
			>
				<svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true">
					<path
						d={layout.railVisible ? 'M3 2 L7 7 L3 12' : 'M7 2 L3 7 L7 12'}
						stroke="currentColor"
						stroke-width="1.5"
						fill="none"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
				</svg>
			</button>
			<!-- aria-hidden lives on the inner content only, never the <aside>, so the
			     still-focusable rail-toggle stays in the a11y tree and a keyboard/AT
			     user can always re-expand a collapsed rail. -->
			<div class="rail-inner" aria-hidden={!layout.railVisible}>
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
		grid-template-columns: var(--body-cols);
		min-height: 0;
		position: relative;
	}
	.stage {
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		position: relative;
		border-right: 1px solid var(--border-1);
	}
	.split {
		display: grid;
		grid-template-rows: var(--split-rows);
		height: 100%;
		min-height: 0;
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
	/* A non-notation panel is maximized: bodyCols is '1fr' (stage only), so the
	   rail has no column to occupy — drop it entirely rather than overflow. */
	.rail.rail-gone {
		display: none;
	}
	/* Normal collapsed case (rail hidden via override, not maximized): bodyCols is
	   a single '1fr' track, so the still-rendered rail flows into an implicit
	   track. Pin it to 0 width so that track is deterministically empty — matching
	   the old explicit `minmax(0,1fr) 0` — instead of relying on min-content
	   heuristics. The rail-toggle is position:absolute so it stays reachable. */
	.rail.collapsed:not(.rail-gone) {
		width: 0;
		overflow: visible;
	}
	.rail-inner {
		flex: 1;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
		transition: opacity var(--duration-fast) var(--ease-out);
	}
	.rail.collapsed .rail-inner {
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
	.rail.collapsed .rail-toggle {
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
		/* On mobile the body stacks vertically; these literal grids override the
		   --body-cols / --split-rows vars set inline above. Two rows is the default
		   (stage on top, rail below). */
		.body {
			grid-template-columns: 1fr;
			grid-template-rows: minmax(40vh, 1fr) minmax(30vh, 1fr);
		}
		/* Stage absent (notation maximized): the body has only the rail child, so
		   collapse to a single row track — otherwise the second 30vh track is dead
		   space below the rail. */
		.body:not(:has(.stage)) {
			grid-template-rows: 1fr;
		}
		.body:has(.rail.collapsed) {
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
		.rail.collapsed .rail-toggle {
			top: auto;
			left: 50%;
			right: auto;
			bottom: 8px;
		}
	}
</style>
