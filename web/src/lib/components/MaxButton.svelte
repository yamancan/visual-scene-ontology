<script lang="ts">
	import { layout, type PanelId } from '$lib/layout.svelte';

	let { panel, size = 20 }: { panel: PanelId; size?: number } = $props();

	let max = $derived(layout.isMax(panel));

	function toggle(e: MouseEvent) {
		e.stopPropagation();
		e.preventDefault();
		layout.toggleMax(panel);
	}
</script>

<button
	type="button"
	class="max-btn nodrag nopan"
	class:active={max}
	style={'--max-size:' + size + 'px'}
	title={max ? 'Restore layout' : 'Maximize ' + panel}
	aria-label={max ? 'Restore layout' : 'Maximize ' + panel}
	aria-pressed={max}
	onclick={toggle}
>
	{#if max}
		<!-- corner COLLAPSE arrows (inward) -->
		<svg
			width="12"
			height="12"
			viewBox="0 0 12 12"
			fill="none"
			stroke="currentColor"
			stroke-width="1.4"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			<path d="M5 1.5V5H1.5" />
			<path d="M10.5 7H7V10.5" />
		</svg>
	{:else}
		<!-- corner EXPAND arrows (outward) -->
		<svg
			width="12"
			height="12"
			viewBox="0 0 12 12"
			fill="none"
			stroke="currentColor"
			stroke-width="1.4"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			<path d="M1.5 4.5V1.5H4.5" />
			<path d="M10.5 7.5V10.5H7.5" />
		</svg>
	{/if}
</button>

<style>
	.max-btn {
		display: inline-grid;
		place-items: center;
		width: var(--max-size, 20px);
		height: var(--max-size, 20px);
		padding: 0;
		border: 0;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--fg-3);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.max-btn:hover {
		color: var(--fg-0);
		background: var(--bg-2);
	}
	.max-btn.active {
		color: var(--accent);
	}
</style>
