<script lang="ts">
	import { scene, type RailTab } from '$lib/scene.svelte';
	import SourcePane from './SourcePane.svelte';
	import TurtlePane from './TurtlePane.svelte';
	import ConformancePane from './ConformancePane.svelte';
	import MaxButton from './MaxButton.svelte';

	// The source tab follows the envelope: if the user's sticky notation matches
	// what's in the envelope, label it that way; if not, label what we will
	// actually render (SourcePane falls back transparently). Avoids the dead-end
	// where the tab promises "vson-x" and the pane shows an empty state.
	let env = $derived(scene.envelope);
	let xPresent = $derived((env?.vson_x?.trim().length ?? 0) > 0);
	let pPresent = $derived((env?.vson_p?.trim().length ?? 0) > 0);
	let effectiveNotation = $derived<'p' | 'x'>(
		scene.notation === 'x'
			? xPresent
				? 'x'
				: pPresent
					? 'p'
					: 'x'
			: pPresent
				? 'p'
				: xPresent
					? 'x'
					: 'p'
	);

	let TABS = $derived<{ id: RailTab; label: string; sub: string }[]>([
		{
			id: 'source',
			label: effectiveNotation === 'x' ? 'vson-x' : 'penman',
			sub: effectiveNotation === 'x' ? 'compact' : 'vson-p'
		},
		{ id: 'turtle', label: 'turtle', sub: 'vson-t' },
		{ id: 'conformance', label: 'conformance', sub: 'shacl' }
	]);

	function pick(t: RailTab) {
		scene.setRailTab(t);
	}

	function onKey(e: KeyboardEvent, t: RailTab, i: number) {
		if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
			const dir = e.key === 'ArrowRight' ? 1 : -1;
			const next = TABS[(i + dir + TABS.length) % TABS.length];
			pick(next.id);
			e.preventDefault();
		} else if (e.key === 'Enter' || e.key === ' ') {
			pick(t);
			e.preventDefault();
		}
	}

	let conforms = $derived(scene.envelope?.conformance.conforms ?? null);
	let viol = $derived(scene.envelope?.conformance.violations?.length ?? 0);
</script>

<section class="rail">
	<div class="tabs" role="tablist" aria-label="result views">
		{#each TABS as t, i (t.id)}
			<button
				type="button"
				role="tab"
				aria-selected={scene.railTab === t.id}
				tabindex={scene.railTab === t.id ? 0 : -1}
				class="tab"
				class:active={scene.railTab === t.id}
				onclick={() => pick(t.id)}
				onkeydown={(e) => onKey(e, t.id, i)}
			>
				<span class="tab-label">{t.label}</span>
				<span class="tab-sub font-mono">{t.sub}</span>
				{#if t.id === 'conformance' && conforms === false}
					<span class="tab-badge font-mono" aria-label="{viol} violations">{viol}</span>
				{/if}
			</button>
		{/each}
		<div class="tabs-tools">
			<MaxButton panel="notation" />
		</div>
	</div>

	<div class="pane">
		{#if scene.railTab === 'source'}
			<SourcePane />
		{:else if scene.railTab === 'turtle'}
			<TurtlePane />
		{:else}
			<ConformancePane />
		{/if}
	</div>
</section>

<style>
	.rail {
		display: flex;
		flex-direction: column;
		height: 100%;
		background: var(--bg-1);
		min-width: 0;
	}
	.tabs {
		display: flex;
		align-items: center;
		gap: 0;
		padding: 0 var(--s2);
		border-bottom: 1px solid var(--border-1);
		flex-shrink: 0;
	}
	.tabs-tools {
		margin-left: auto;
		display: inline-flex;
		align-items: center;
	}
	.tab {
		position: relative;
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		padding: var(--s3) var(--s3) calc(var(--s3) - 1px);
		border: 0;
		background: transparent;
		color: var(--fg-4);
		font-size: var(--text-xs);
		letter-spacing: 0.02em;
		cursor: pointer;
		border-bottom: 1px solid transparent;
		margin-bottom: -1px;
		transition: color var(--duration-fast) var(--ease-out);
	}
	.tab:hover {
		color: var(--fg-2);
	}
	.tab.active {
		color: var(--fg-0);
		border-bottom-color: var(--accent);
	}
	.tab-sub {
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
	.tab.active .tab-sub {
		color: var(--accent);
	}
	.tab-badge {
		display: inline-grid;
		place-items: center;
		min-width: 16px;
		height: 16px;
		padding: 0 4px;
		font-size: 9px;
		color: var(--danger);
		background: color-mix(in srgb, var(--danger) 16%, transparent);
		border-radius: var(--radius-full);
	}
	.pane {
		flex: 1;
		overflow: hidden;
		min-height: 0;
	}
</style>
