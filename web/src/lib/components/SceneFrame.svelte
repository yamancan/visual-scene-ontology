<script lang="ts">
	import type { Snippet } from 'svelte';
	import { scene } from '$lib/scene.svelte';
	import { buildSceneView } from '$lib/render/sceneView';

	let { children, meta }: { children: Snippet; meta?: string } = $props();

	let view = $derived.by(() => {
		const g = scene.envelope?.graph;
		return g ? buildSceneView(g) : null;
	});
</script>

<div class="scene-frame">
	{#if view}
		<header class="frame-header">
			<div class="lhs">
				<span class="scene-title">SCENE</span>
				{#if view.composition}
					<span class="comp-id font-mono">@{view.composition.id}</span>
				{/if}
			</div>
			{#if meta}
				<span class="frame-meta font-mono">{meta}</span>
			{/if}
		</header>
	{/if}

	<div class="frame-body">
		{@render children()}
	</div>
</div>

<style>
	.scene-frame {
		position: relative;
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		margin: var(--s3);
		background: var(--bg-0);
		border: 2px solid var(--border-2);
		border-radius: var(--radius);
		overflow: hidden;
		box-shadow: 0 1px 0 var(--border-1);
	}
	.frame-header {
		display: flex;
		align-items: center;
		gap: var(--s3);
		padding: var(--s2) var(--s3);
		border-bottom: 1px solid var(--border-2);
		background: var(--bg-1);
		flex-shrink: 0;
		min-width: 0;
	}
	.lhs {
		display: flex;
		align-items: baseline;
		gap: var(--s2);
		flex-shrink: 0;
	}
	.scene-title {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.12em;
		color: var(--fg-0);
		padding: 3px 8px;
		background: var(--accent-bg, var(--bg-2));
		color: var(--accent, var(--fg-0));
		border-radius: var(--radius-sm);
	}
	.comp-id {
		font-size: 11px;
		color: var(--fg-2);
	}
	.frame-meta {
		font-size: 10px;
		color: var(--fg-4);
		flex-shrink: 0;
		margin-left: auto;
	}
	.frame-body {
		flex: 1;
		min-height: 0;
		position: relative;
	}
	@media (max-width: 700px) {
		.frame-header {
			flex-wrap: wrap;
		}
	}
</style>
