<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { buildSceneView } from '$lib/render/sceneView';

	let view = $derived.by(() => {
		const g = scene.envelope?.graph;
		return g ? buildSceneView(g) : null;
	});

	let spatial = $derived(view?.spatial ?? []);
	let temporal = $derived(view?.temporal ?? []);

	// Allen interval predicates from VSV (spec §5.2). Anything else in the
	// temporal/causal zone is VSO-namespaced (causes, enables, prevents,
	// triggers).
	const ALLEN = new Set([
		'before',
		'after',
		'meets',
		'metBy',
		'overlaps',
		'overlappedBy',
		'starts',
		'startedBy',
		'during',
		'contains',
		'finishes',
		'finishedBy',
		'equals'
	]);

	function nsOfTemporal(p: string): string {
		return ALLEN.has(p) ? 'allen' : 'vso';
	}
</script>

{#if view && (spatial.length || temporal.length)}
	<div class="strip">
		{#if spatial.length}
			<section class="zone">
				<header class="zone-h">
					<span class="zone-lbl font-mono">spatial</span>
					<span class="zone-meta font-mono">{spatial.length}</span>
				</header>
				<ul class="rows">
					{#each spatial as s (s.id)}
						{@const needsViewer = !!s.directional && !s.viewer}
						<li class="row spat" class:warn={needsViewer}>
							<span class="ref font-mono">@{s.figure ?? '?'}</span>
							<span class="op font-mono">
								{#if s.directional}
									<span class="ns">vso:</span>{s.directional}
								{:else if s.rcc}
									<span class="ns">rcc:</span>{s.rcc}
								{:else}·{/if}
							</span>
							<span class="ref font-mono">@{s.ground ?? '?'}</span>
							<span class="row-id font-mono">@{s.id}</span>
							<span class="meta font-mono">
								{#if s.rcc && s.directional}<span class="m"><span class="ns">rcc:</span>{s.rcc}</span>{/if}
								{#if s.proximal}<span class="m"><span class="ns">vso:</span>{s.proximal}</span>{/if}
								{#if s.viewer}<span class="m">viewer:@{s.viewer}</span>{/if}
								{#if needsViewer}
									<span class="warn-chip" title="vss:DirectionalNeedsViewerShape — Talmy resolution requires a vso:viewer for any vso:directional fact">
										!viewer
									</span>
								{/if}
							</span>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if temporal.length}
			<section class="zone">
				<header class="zone-h">
					<span class="zone-lbl font-mono">temporal &amp; causal</span>
					<span class="zone-meta font-mono">{temporal.length}</span>
				</header>
				<ul class="rows">
					{#each temporal as t, i (t.from + t.predicate + t.to + i)}
						<li class="row tcrow">
							<span class="ref font-mono">@{t.from}</span>
							<span class="pred font-mono">
								<span class="ns">{nsOfTemporal(t.predicate)}:</span>{t.predicate}
							</span>
							<span class="ref font-mono">@{t.to}</span>
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	</div>
{/if}

<style>
	.strip {
		display: flex;
		flex-direction: column;
		gap: var(--s3);
		padding: var(--s3);
		background: var(--bg-0);
		overflow-y: auto;
		min-width: 0;
		min-height: 0;
		height: 100%;
	}
	.zone {
		display: flex;
		flex-direction: column;
		gap: var(--s2);
		min-width: 0;
	}
	.zone-h {
		display: flex;
		align-items: baseline;
		gap: var(--s2);
		padding-bottom: var(--s1);
		border-bottom: 1px solid var(--border-1);
	}
	.zone-lbl {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-3);
	}
	.zone-meta {
		font-size: 10px;
		color: var(--fg-4);
	}
	.rows {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: var(--s2);
	}
	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--s2);
		padding: var(--s2) var(--s3);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		min-width: 0;
	}
	.spat {
		border-left: 3px solid var(--node-spatialfact);
	}
	.tcrow {
		border-left: 3px dashed var(--fg-3);
	}
	.row-id {
		font-size: 9px;
		color: var(--fg-4);
		margin-left: auto;
	}
	.ref {
		color: var(--node-entity);
		font-size: var(--text-xs);
	}
	.op,
	.pred {
		color: var(--fg-1);
		font-size: var(--text-xs);
		padding: 0 4px;
	}
	.meta {
		display: flex;
		gap: var(--s2);
		font-size: 10px;
		color: var(--fg-4);
		margin-left: auto;
	}
	.m::before {
		content: '·';
		margin-right: 4px;
		color: var(--fg-4);
	}
	.m:first-child::before {
		display: none;
	}
	.ns {
		color: var(--fg-4);
		font-size: 9px;
		margin-right: 1px;
	}
	.warn {
		border-left-color: var(--danger, #c0392b);
		background: color-mix(in srgb, var(--danger, #c0392b) 6%, var(--bg-1));
	}
	.warn-chip {
		font-size: 9px;
		padding: 1px 5px;
		background: var(--danger, #c0392b);
		color: white;
		border-radius: var(--radius-sm);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.warn-chip::before {
		content: none !important;
	}
</style>
