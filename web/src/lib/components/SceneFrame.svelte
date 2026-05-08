<script lang="ts">
	import type { Snippet } from 'svelte';
	import { scene } from '$lib/scene.svelte';
	import { buildSceneView, type FrameSlot } from '$lib/render/sceneView';

	let { children, meta }: { children: Snippet; meta?: string } = $props();

	let view = $derived.by(() => {
		const g = scene.envelope?.graph;
		return g ? buildSceneView(g) : null;
	});

	const FRAME_LABEL: Record<FrameSlot['kind'], string> = {
		SceneContext: 'ctx',
		VisualStyle: 'style',
		CameraView: 'cam'
	};

	function shorten(v: string, n = 24): string {
		return v.length <= n ? v : v.slice(0, n - 1) + '…';
	}
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

		{#if view}
			{@const hasFrame = view.frame.length > 0}
			{@const hasLayout = !!view.composition && view.composition.qualities.length > 0}
			{#if hasFrame || hasLayout}
				<ul class="chip-rail floating" aria-label="frame metadata">
					{#each view.frame as slot (slot.id)}
						<li class="chip" data-kind={slot.kind}>
							<span class="chip-key font-mono">{FRAME_LABEL[slot.kind]}</span>
							{#each slot.properties as p (p.key)}
								<span class="chip-val font-mono" title="{p.key}: {p.value}">
									{shorten(String(p.value))}
								</span>
							{/each}
							{#if slot.properties.length === 0}
								<span class="chip-empty font-mono">—</span>
							{/if}
						</li>
					{/each}
					{#if hasLayout}
						<li class="chip comp-qualities">
							<span class="chip-key font-mono">layout</span>
							{#each view.composition!.qualities as q (q.dim)}
								<span class="chip-val font-mono" title="{q.dim}: {q.value}">
									{q.value}
								</span>
							{/each}
						</li>
					{/if}
				</ul>
			{/if}
		{/if}
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
		font-family:
			ui-monospace,
			SFMono-Regular,
			Menlo,
			monospace;
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
	.chip-rail {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s3);
		list-style: none;
		flex: 1;
		min-width: 0;
		overflow-x: auto;
		scrollbar-width: thin;
	}
	.chip-rail.floating {
		position: absolute;
		left: var(--s3);
		right: var(--s3);
		bottom: var(--s3);
		flex: 0 0 auto;
		padding: var(--s2);
		background: color-mix(in srgb, var(--bg-1) 86%, transparent);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		box-shadow:
			0 1px 0 var(--border-1),
			0 4px 14px -8px rgba(0, 0, 0, 0.18);
		z-index: 5;
		pointer-events: auto;
	}
	.chip {
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		padding: 2px 6px;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		background: var(--bg-0);
		font-size: 10px;
		white-space: nowrap;
	}
	.chip-key {
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-size: 9px;
	}
	.chip-val {
		color: var(--fg-1);
	}
	.chip-val + .chip-val::before {
		content: '·';
		color: var(--fg-4);
		margin: 0 4px 0 0;
	}
	.chip-empty {
		color: var(--fg-4);
	}
	.comp-qualities {
		border-style: dashed;
	}
	.frame-meta {
		font-size: 10px;
		color: var(--fg-4);
		flex-shrink: 0;
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
		.chip-rail.floating {
			left: var(--s2);
			right: var(--s2);
			bottom: var(--s2);
		}
	}
</style>
