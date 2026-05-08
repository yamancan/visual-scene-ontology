<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { buildSceneView, type ActionFact } from '$lib/render/sceneView';
	import EntityCard from './EntityCard.svelte';

	const KIND_ICON: Record<ActionFact['kind'], string> = {
		Event: '⚡',
		Stative: '◐',
		Process: '◯'
	};

	let view = $derived.by(() => {
		const g = scene.envelope?.graph;
		return g ? buildSceneView(g) : null;
	});

	function selectNode(id: string) {
		scene.setSelected(scene.selectedNodeId === id ? null : id);
	}
</script>

<div class="scene-view">
	{#if !view}
		<div class="empty font-mono">no scene loaded</div>
	{:else}
		<section class="zone">
			<header class="zone-h">
				<span class="zone-lbl font-mono">cast</span>
				<span class="zone-meta font-mono">
					{view.entities.length}
					{view.entities.length === 1 ? 'entity' : 'entities'}
				</span>
			</header>
			{#if view.entities.length}
				<div class="cards">
					{#each view.entities as e (e.id)}
						<EntityCard
							entity={e}
							selected={scene.selectedNodeId === e.id}
							onselect={selectNode}
						/>
					{/each}
				</div>
			{:else}
				<div class="muted font-mono">no entities</div>
			{/if}
		</section>

		{#if view.actions.length}
			<section class="zone">
				<header class="zone-h">
					<span class="zone-lbl font-mono">actions</span>
					<span class="zone-meta font-mono">{view.actions.length}</span>
				</header>
				<ul class="rows actions">
					{#each view.actions as a (a.id)}
						<li class="row action" data-kind={a.kind}>
							<span class="kind-ico" aria-hidden="true">{KIND_ICON[a.kind]}</span>
							<span class="lemma font-mono">{a.lemma ?? a.id}</span>
							<span class="kind-tag font-mono">{a.kind.toLowerCase()}</span>
							<span class="row-id font-mono">@{a.id}</span>
							<ul class="role-list">
								{#each a.roles as r, i (r.role + r.target + i)}
									<li>
										<span class="role-k font-mono">{r.role}</span>
										<span class="role-v font-mono">@{r.target}</span>
									</li>
								{/each}
								{#if a.manner}
									<li>
										<span class="role-k font-mono">manner</span>
										<span class="role-v">{a.manner}</span>
									</li>
								{/if}
							</ul>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if view.spatial.length}
			<section class="zone">
				<header class="zone-h">
					<span class="zone-lbl font-mono">spatial</span>
					<span class="zone-meta font-mono">{view.spatial.length}</span>
				</header>
				<ul class="rows spatial">
					{#each view.spatial as s (s.id)}
						<li class="row spat">
							<span class="kind-ico spat-ico" aria-hidden="true">↗</span>
							<span class="ref font-mono">@{s.figure ?? '?'}</span>
							<span class="op font-mono">{s.directional ?? s.rcc ?? '·'}</span>
							<span class="ref font-mono">@{s.ground ?? '?'}</span>
							<span class="row-id font-mono">@{s.id}</span>
							<span class="meta font-mono">
								{#if s.rcc}<span class="m">rcc:{s.rcc}</span>{/if}
								{#if s.proximal}<span class="m">prox:{s.proximal}</span>{/if}
								{#if s.viewer}<span class="m">viewer:@{s.viewer}</span>{/if}
							</span>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if view.temporal.length}
			<section class="zone">
				<header class="zone-h">
					<span class="zone-lbl font-mono">temporal &amp; causal</span>
					<span class="zone-meta font-mono">{view.temporal.length}</span>
				</header>
				<ul class="rows temporal">
					{#each view.temporal as t, i (t.from + t.predicate + t.to + i)}
						<li class="row tcrow">
							<span class="ref font-mono">@{t.from}</span>
							<span class="pred font-mono">{t.predicate}</span>
							<span class="ref font-mono">@{t.to}</span>
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	{/if}
</div>

<style>
	.scene-view {
		height: 100%;
		overflow-y: auto;
		padding: var(--s3);
		display: flex;
		flex-direction: column;
		gap: var(--s4);
		background: var(--bg-0);
		min-width: 0;
	}
	.empty {
		display: grid;
		place-items: center;
		height: 100%;
		color: var(--fg-4);
		font-size: var(--text-2xs);
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
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: var(--s2);
	}
	.muted {
		color: var(--fg-4);
		font-size: 10px;
		padding: var(--s2);
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
	.action {
		border-left: 3px solid var(--node-perdurant);
	}
	.spat {
		border-left: 3px solid var(--node-spatialfact);
	}
	.tcrow {
		border-left: 3px dashed var(--fg-3);
	}
	.kind-ico {
		font-size: 12px;
		line-height: 1;
		color: var(--node-perdurant);
	}
	.spat-ico {
		color: var(--node-spatialfact);
	}
	.lemma {
		font-size: var(--text-sm);
		color: var(--fg-0);
	}
	.kind-tag {
		font-size: 9px;
		padding: 1px 5px;
		background: var(--tag-bg);
		color: var(--fg-4);
		border-radius: var(--radius-sm);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.row-id {
		font-size: 9px;
		color: var(--fg-4);
		margin-left: auto;
	}
	.role-list {
		list-style: none;
		display: flex;
		flex-wrap: wrap;
		gap: var(--s3);
		flex-basis: 100%;
		padding-top: var(--s1);
		margin-top: var(--s1);
		border-top: 1px dashed var(--border-1);
	}
	.role-list li {
		display: flex;
		align-items: baseline;
		gap: 4px;
		font-size: var(--text-xs);
	}
	.role-k {
		color: var(--fg-4);
		font-size: 10px;
	}
	.role-v {
		color: var(--fg-1);
	}
	.ref {
		color: var(--node-entity);
		font-size: var(--text-xs);
	}
	.op {
		color: var(--fg-1);
		font-size: var(--text-xs);
		padding: 0 4px;
	}
	.pred {
		color: var(--fg-1);
		font-size: var(--text-xs);
		padding: 0 var(--s2);
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
</style>
