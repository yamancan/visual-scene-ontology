<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import LayoutSwitcher from './LayoutSwitcher.svelte';

	let env = $derived(scene.envelope);
	let conforms = $derived(env?.conformance.conforms ?? null);
	let nodes = $derived(env?.graph?.nodes.length ?? 0);
	let edges = $derived(env?.graph?.edges.length ?? 0);
	let triples = $derived(env?.vson_t ? (env.vson_t.match(/\s\.\s*\n/g) || []).length : 0);
	let latency = $derived(env?.extraction?.latency_ms ?? 0);
	let retries = $derived(env?.extraction?.shacl_retries ?? 0);
	let model = $derived(env?.extraction?.model ?? scene.model);
	let prebuilt = $derived(model === 'fixture-bake');

	function shortModel(id: string): string {
		if (id === 'fixture-bake') return 'prebuilt';
		const i = id.indexOf('/');
		return i >= 0 ? id.slice(i + 1) : id;
	}
</script>

{#if env}
	<header class="hdr">
		<div class="hdr-left">
			{#if scene.imagePreview}
				<img src={scene.imagePreview} alt="source" class="thumb" />
			{:else}
				<div class="thumb thumb-empty"></div>
			{/if}
			<div class="meta">
				<div class="meta-row">
					<span
						class="conf-pill"
						class:pass={conforms === true}
						class:fail={conforms === false}
					>
						<span class="dot"></span>
						<span class="font-mono">{conforms ? 'CONFORMS' : 'VIOLATIONS'}</span>
					</span>
					<span class="scene-id font-mono" title="scene id">{env.scene_id}</span>
				</div>
				<div class="meta-row sub">
					<span class="font-mono" title={model}>{shortModel(model)}</span>
					{#if !prebuilt}
						<span class="sep">·</span>
						<span class="font-mono">{(latency / 1000).toFixed(2)}s</span>
					{/if}
					{#if retries > 0}
						<span class="sep">·</span>
						<span class="font-mono retry">{retries} repair{retries > 1 ? 's' : ''}</span>
					{/if}
				</div>
			</div>
		</div>

		<div class="hdr-right">
			<LayoutSwitcher />
			<dl class="stats">
				<div class="stat">
					<dt>nodes</dt>
					<dd class="num">{nodes}</dd>
				</div>
				<div class="stat">
					<dt>edges</dt>
					<dd class="num">{edges}</dd>
				</div>
				<div class="stat">
					<dt>triples</dt>
					<dd class="num">{triples}</dd>
				</div>
			</dl>
		</div>
	</header>
{/if}

<style>
	.hdr {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--s5);
		padding: var(--s3) var(--s5);
		background: var(--bg-1);
		border-bottom: 1px solid var(--border-1);
	}
	.hdr-left {
		display: flex;
		align-items: center;
		gap: var(--s4);
		min-width: 0;
	}
	.hdr-right {
		display: flex;
		align-items: center;
		gap: var(--s5);
		flex-shrink: 0;
	}
	.thumb {
		width: 56px;
		height: 56px;
		object-fit: cover;
		border-radius: var(--radius);
		border: 1px solid var(--border-1);
		background: var(--bg-2);
		flex-shrink: 0;
	}
	.thumb-empty {
		background: repeating-linear-gradient(
			45deg,
			var(--bg-2),
			var(--bg-2) 4px,
			var(--bg-1) 4px,
			var(--bg-1) 8px
		);
	}
	.meta {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}
	.meta-row {
		display: flex;
		align-items: center;
		gap: var(--s2);
		min-width: 0;
	}
	.meta-row.sub {
		font-size: var(--text-2xs);
		color: var(--fg-4);
	}
	.scene-id {
		font-size: var(--text-xs);
		color: var(--fg-3);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.sep {
		color: var(--border-2);
	}
	.retry {
		color: var(--warning, var(--accent));
	}
	.conf-pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 3px 8px 3px 7px;
		border-radius: var(--radius-full);
		font-size: var(--text-2xs);
		letter-spacing: 0.06em;
		border: 1px solid var(--border-1);
		background: var(--bg-2);
		color: var(--fg-3);
	}
	.conf-pill .dot {
		width: 6px;
		height: 6px;
		border-radius: 9999px;
		background: var(--fg-4);
	}
	.conf-pill.pass {
		color: var(--success);
		border-color: color-mix(in srgb, var(--success) 35%, var(--border-1));
		background: color-mix(in srgb, var(--success) 10%, var(--bg-2));
	}
	.conf-pill.pass .dot {
		background: var(--success);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 18%, transparent);
	}
	.conf-pill.fail {
		color: var(--danger);
		border-color: color-mix(in srgb, var(--danger) 35%, var(--border-1));
		background: color-mix(in srgb, var(--danger) 10%, var(--bg-2));
	}
	.conf-pill.fail .dot {
		background: var(--danger);
	}
	.stats {
		display: flex;
		align-items: stretch;
		gap: 0;
		margin: 0;
		flex-shrink: 0;
	}
	.stat {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
		padding: 0 var(--s4);
		border-left: 1px solid var(--border-1);
		min-width: 64px;
	}
	.stat:first-child {
		border-left: 0;
	}
	.stat dt {
		font-family: var(--font-mono);
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
	.stat dd {
		margin: 0;
		font-family: var(--font-mono);
		font-size: var(--text-lg);
		font-weight: 500;
		color: var(--fg-0);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}
	@media (max-width: 720px) {
		.scene-id {
			display: none;
		}
		.hdr-right {
			gap: var(--s3);
		}
		.stat {
			padding: 0 var(--s3);
			min-width: 48px;
		}
		.thumb {
			width: 44px;
			height: 44px;
		}
	}
</style>
