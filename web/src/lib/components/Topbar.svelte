<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import ModelPicker from './ModelPicker.svelte';

	let conforms = $derived(scene.envelope?.conformance.conforms ?? null);
	let triples = $derived(scene.envelope?.vson_t ? countTriples(scene.envelope.vson_t) : 0);
	let latency = $derived(scene.envelope?.extraction?.latency_ms ?? 0);

	function countTriples(turtle: string): number {
		return (turtle.match(/\s\.\s*\n/g) || []).length;
	}
</script>

<header class="topbar">
	<div class="topbar-left">
		<button
			class="brand"
			onclick={() => scene.reset()}
			aria-label={scene.envelope ? 'Reset' : 'vson'}
		>
			<span class="brand-mark font-mono">v</span>
			<span class="brand-name">vson</span>
		</button>
		{#if scene.envelope}
			<span class="brand-meta font-mono">{scene.envelope.scene_id}</span>
		{/if}
	</div>

	<div class="topbar-right">
		{#if scene.envelope}
			<span class="stat" title={conforms ? 'SHACL: passes' : 'SHACL: violations present'}>
				<span class="dot" style:background={conforms ? 'var(--success)' : 'var(--danger)'}></span>
				<span class="font-mono">
					{conforms ? 'conforms' : `${scene.envelope.conformance.violations?.length ?? 0} violations`}
				</span>
			</span>
			<span class="sep">·</span>
			<span class="stat font-mono tabular">
				{triples}<span class="dim">&nbsp;triples</span>
			</span>
			<span class="sep">·</span>
			<span class="stat font-mono tabular">
				{(latency / 1000).toFixed(1)}<span class="dim">s</span>
			</span>
			<span class="sep">·</span>
		{/if}
		<ModelPicker />
		<a class="about-link font-mono" href="/about">about</a>
	</div>
</header>

<style>
	.topbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 48px;
		padding: 0 var(--s5);
		background: color-mix(in srgb, var(--bg-0) 88%, transparent);
		backdrop-filter: saturate(140%) blur(8px);
		-webkit-backdrop-filter: saturate(140%) blur(8px);
		border-bottom: 1px solid var(--border-0);
		user-select: none;
	}
	.topbar-left {
		display: flex;
		align-items: center;
		gap: var(--s3);
	}
	.topbar-right {
		display: flex;
		align-items: center;
		gap: var(--s3);
	}
	.brand {
		display: inline-flex;
		align-items: center;
		gap: var(--s2);
		background: transparent;
		border: 0;
		cursor: pointer;
		padding: 0;
	}
	.brand-mark {
		display: grid;
		place-items: center;
		width: 18px;
		height: 18px;
		border-radius: var(--radius-sm);
		background: var(--accent);
		color: var(--accent-fg);
		font-size: 11px;
		font-weight: 700;
	}
	.brand-name {
		font-size: var(--text-base);
		font-weight: 600;
		color: var(--fg-0);
		letter-spacing: -0.01em;
		transition: color var(--duration-fast) var(--ease-out);
	}
	.brand:hover .brand-name {
		color: var(--fg-1);
	}
	.brand-meta {
		padding-left: var(--s3);
		margin-left: var(--s1);
		border-left: 1px solid var(--border-1);
		font-size: var(--text-2xs);
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.stat {
		display: inline-flex;
		align-items: center;
		gap: var(--s2);
		font-size: var(--text-2xs);
		color: var(--fg-2);
	}
	.stat .dim {
		color: var(--fg-4);
	}
	.dot {
		display: inline-block;
		width: 6px;
		height: 6px;
		border-radius: 9999px;
	}
	.sep {
		color: var(--border-2);
		font-size: var(--text-2xs);
	}
	.about-link {
		font-size: var(--text-2xs);
		color: var(--fg-4);
		text-decoration: none;
		padding: 4px 6px;
		border-radius: var(--radius-sm);
		transition: color var(--duration-fast) var(--ease-out);
	}
	.about-link:hover {
		color: var(--fg-1);
	}
	@media (max-width: 640px) {
		.brand-meta {
			display: none;
		}
		.stat:nth-of-type(n + 2),
		.sep {
			display: none;
		}
	}
</style>
