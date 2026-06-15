<script lang="ts">
	import { layout, PRESET_ORDER, PRESET_META, type LayoutPreset } from '$lib/layout.svelte';

	// A preset is "active" only when it's selected AND no panel is maximized —
	// a maximized panel is a transient state that overrides the chosen shape.
	function isActive(p: LayoutPreset) {
		return layout.preset === p && !layout.anyMax;
	}
</script>

<div class="switcher" role="group" aria-label="layout preset">
	<div class="segs">
		{#each PRESET_ORDER as p (p)}
			<button
				type="button"
				class="seg"
				class:active={isActive(p)}
				aria-pressed={isActive(p)}
				title={PRESET_META[p].hint}
				aria-label={PRESET_META[p].label}
				onclick={() => layout.setPreset(p)}
			>
				<svg width="18" height="14" viewBox="0 0 18 14" aria-hidden="true">
					{#if p === 'image'}
						<!-- Inspect: big image over a list of rows -->
						<rect class="g-fill" x="1" y="1" width="16" height="7.5" rx="1" />
						<rect class="g-line" x="1" y="10" width="11" height="1.6" rx="0.8" />
						<rect class="g-line" x="1" y="12.4" width="8" height="1.6" rx="0.8" />
					{:else if p === 'graph'}
						<!-- Graph: scatter of connected nodes -->
						<line class="g-stroke" x1="4" y1="4" x2="9" y2="10" />
						<line class="g-stroke" x1="14" y1="3.5" x2="9" y2="10" />
						<circle class="g-fill" cx="4" cy="4" r="1.9" />
						<circle class="g-fill" cx="14" cy="3.5" r="1.9" />
						<circle class="g-fill" cx="9" cy="10" r="1.9" />
					{:else}
						<!-- Source (notation): lines of text -->
						<rect class="g-line" x="1" y="2" width="16" height="1.6" rx="0.8" />
						<rect class="g-fill" x="1" y="5.5" width="11" height="1.6" rx="0.8" />
						<rect class="g-line" x="1" y="9" width="14" height="1.6" rx="0.8" />
						<rect class="g-line" x="1" y="12.5" width="9" height="1.6" rx="0.8" />
					{/if}
				</svg>
				<span class="seg-label font-mono">{PRESET_META[p].label}</span>
			</button>
		{/each}
	</div>

	{#if layout.anyMax}
		<button
			type="button"
			class="exit font-mono"
			title="Exit fullscreen — back to layout"
			aria-label="Exit fullscreen"
			onclick={() => layout.clearMax()}
		>
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
			<span>exit</span>
		</button>
	{/if}

	<button
		type="button"
		class="reset"
		title="Reset layout"
		aria-label="Reset layout"
		onclick={() => layout.resetLayout()}
	>
		<svg
			width="13"
			height="13"
			viewBox="0 0 13 13"
			fill="none"
			stroke="currentColor"
			stroke-width="1.4"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			<path d="M10.5 3.5A4.5 4.5 0 1 0 11 7" />
			<path d="M10.8 1.2V3.7H8.3" />
		</svg>
	</button>
</div>

<style>
	.switcher {
		display: inline-flex;
		align-items: center;
		gap: var(--s2);
	}
	.segs {
		display: inline-flex;
		align-items: stretch;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		background: var(--bg-1);
		overflow: hidden;
	}
	.seg {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 4px var(--s2);
		border: 0;
		border-right: 1px solid var(--border-1);
		background: transparent;
		color: var(--fg-4);
		cursor: pointer;
		transition: color var(--duration-fast) var(--ease-out);
	}
	.seg:last-child {
		border-right: 0;
	}
	.seg:hover {
		color: var(--fg-2);
	}
	.seg.active {
		color: var(--fg-0);
	}
	.seg.active::after {
		content: '';
		position: absolute;
		left: var(--s2);
		right: var(--s2);
		bottom: 0;
		height: 2px;
		background: var(--accent);
		border-radius: var(--radius-full);
	}
	.seg-label {
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.07em;
	}
	/* Glyph parts inherit the button's currentColor for hover/active states.
	 * g-fill = the "focused" pane (accent on active), g-line = secondary panes. */
	.g-line {
		fill: none;
		stroke: currentColor;
		stroke-width: 1.2;
		opacity: 0.55;
	}
	.g-fill {
		fill: currentColor;
		opacity: 0.32;
	}
	.g-stroke {
		stroke: currentColor;
		stroke-width: 1.1;
		opacity: 0.5;
	}
	.seg.active .g-fill {
		fill: var(--accent);
		opacity: 0.9;
	}
	.seg.active .g-line {
		stroke: var(--accent);
		opacity: 0.7;
	}
	.seg.active .g-stroke {
		stroke: var(--accent);
		opacity: 0.7;
	}
	.exit {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 3px var(--s2);
		border: 1px solid var(--accent);
		border-radius: var(--radius-sm);
		background: var(--accent-bg);
		color: var(--accent);
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		cursor: pointer;
		transition: background var(--duration-fast) var(--ease-out);
	}
	.exit:hover {
		background: color-mix(in srgb, var(--accent) 22%, transparent);
	}
	.reset {
		display: inline-grid;
		place-items: center;
		width: 22px;
		height: 22px;
		padding: 0;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		background: var(--bg-1);
		color: var(--fg-4);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.reset:hover {
		color: var(--fg-0);
		background: var(--bg-2);
	}
</style>
