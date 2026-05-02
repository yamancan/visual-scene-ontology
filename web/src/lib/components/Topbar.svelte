<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import ModelPicker from './ModelPicker.svelte';
</script>

<header class="topbar">
	<div class="topbar-left">
		<button
			class="brand"
			onclick={() => scene.reset()}
			aria-label={scene.envelope ? 'Reset' : 'vson'}
			title={scene.envelope ? 'Start over' : 'vson'}
		>
			<span class="brand-mark font-mono">v</span>
			<span class="brand-name">vson</span>
		</button>
	</div>

	<div class="topbar-right">
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
	.topbar-left,
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
</style>
