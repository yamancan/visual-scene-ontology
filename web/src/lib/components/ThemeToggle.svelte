<script lang="ts">
	import { onMount } from 'svelte';

	type Mode = 'light' | 'dark';

	const THEME_FOR_MODE: Record<Mode, string> = {
		light: 'paper',
		dark: 'graphite'
	};

	let mode = $state<Mode>('dark');

	onMount(() => {
		const current = document.documentElement.getAttribute('data-mode');
		mode = current === 'light' ? 'light' : 'dark';
	});

	function apply(next: Mode) {
		const root = document.documentElement;
		root.setAttribute('data-mode', next);
		root.setAttribute('data-theme', THEME_FOR_MODE[next]);
		const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
		if (meta) meta.content = next === 'light' ? '#fbfaf7' : '#0d0d0d';
		try {
			localStorage.setItem('vson-mode', next);
		} catch {
			/* ignore */
		}
	}

	function toggle() {
		const next: Mode = mode === 'dark' ? 'light' : 'dark';
		mode = next;
		apply(next);
	}
</script>

<button
	type="button"
	class="theme-toggle"
	onclick={toggle}
	aria-label={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
	title={mode === 'dark' ? 'Light mode' : 'Dark mode'}
>
	{#if mode === 'dark'}
		<svg
			width="14"
			height="14"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			<circle cx="12" cy="12" r="4" />
			<path d="M12 2v2" />
			<path d="M12 20v2" />
			<path d="m4.93 4.93 1.41 1.41" />
			<path d="m17.66 17.66 1.41 1.41" />
			<path d="M2 12h2" />
			<path d="M20 12h2" />
			<path d="m6.34 17.66-1.41 1.41" />
			<path d="m19.07 4.93-1.41 1.41" />
		</svg>
	{:else}
		<svg
			width="14"
			height="14"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
		</svg>
	{/if}
</button>

<style>
	.theme-toggle {
		display: inline-grid;
		place-items: center;
		width: 28px;
		height: 28px;
		padding: 0;
		background: transparent;
		color: var(--fg-3);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-full);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out),
			border-color var(--duration-fast) var(--ease-out);
	}
	.theme-toggle:hover {
		color: var(--fg-0);
		background: var(--bg-2);
		border-color: var(--border-2);
	}
</style>
