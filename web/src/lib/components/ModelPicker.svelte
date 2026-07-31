<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { scene } from '$lib/scene.svelte';

	interface PickerModel {
		id: string;
		name: string;
		provider: string;
		context_length: number;
		prompt_per_mtok: number;
		completion_per_mtok: number;
		supports_cache: boolean;
	}

	let open = $state(false);
	let query = $state('');
	let models = $state<PickerModel[]>([]);
	let loading = $state(true);
	// Distinct from "the catalog loaded and matched nothing": a dead or
	// unauthorised /api/models used to render as `no match`, which reads as
	// "your query is wrong" instead of "the list never arrived".
	let loadFailed = $state(false);
	let buttonEl: HTMLButtonElement | undefined = $state();
	let menuEl: HTMLDivElement | undefined = $state();
	let searchEl: HTMLInputElement | undefined = $state();
	let activeIdx = $state(0);

	// Per-instance id root so the option ids stay unique and stable across
	// re-renders (aria-activedescendant has to resolve to a real element).
	const uid = $props.id();
	const listId = `${uid}-list`;
	function optionId(modelId: string): string {
		return `${uid}-opt-${modelId.replace(/[^A-Za-z0-9_-]+/g, '-')}`;
	}

	onMount(async () => {
		try {
			const r = await fetch('/api/models');
			if (!r.ok) throw new Error(`models · ${r.status}`);
			models = (await r.json()) as PickerModel[];
		} catch {
			loadFailed = true;
		}
		loading = false;
	});

	let filtered = $derived.by(() => {
		const q = query.trim().toLowerCase();
		if (!q) return models;
		return models.filter(
			(m) =>
				m.id.toLowerCase().includes(q) ||
				m.name.toLowerCase().includes(q) ||
				m.provider.toLowerCase().includes(q)
		);
	});

	// Only the rendered slice is navigable — keyboard bounds and
	// aria-activedescendant have to agree with what is actually in the DOM.
	let visible = $derived(filtered.slice(0, 200));
	let activeId = $derived(visible[activeIdx] ? optionId(visible[activeIdx].id) : undefined);

	let current = $derived(models.find((m) => m.id === scene.model));

	function pick(m: PickerModel) {
		scene.setModel(m.id);
		open = false;
		query = '';
	}

	function onKey(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			open = false;
			e.preventDefault();
			return;
		}
		if (e.key === 'ArrowDown') {
			activeIdx = Math.min(activeIdx + 1, visible.length - 1);
			e.preventDefault();
		} else if (e.key === 'ArrowUp') {
			activeIdx = Math.max(activeIdx - 1, 0);
			e.preventDefault();
		} else if (e.key === 'Enter') {
			const m = visible[activeIdx];
			if (m) pick(m);
			e.preventDefault();
		}
	}

	function onDocClick(e: MouseEvent) {
		if (!open) return;
		const t = e.target as Node;
		if (menuEl?.contains(t) || buttonEl?.contains(t)) return;
		open = false;
	}

	$effect(() => {
		if (open) {
			activeIdx = Math.max(
				0,
				visible.findIndex((m) => m.id === scene.model)
			);
			tick().then(() => searchEl?.focus());
		}
	});

	function fmtCost(n: number): string {
		if (n === 0) return 'free';
		if (n < 1) return `$${n.toFixed(2)}`;
		return `$${n.toFixed(2)}`;
	}
	function shortId(id: string): string {
		const [, model] = id.split('/');
		return model ?? id;
	}
</script>

<svelte:window onkeydown={onKey} onclick={onDocClick} />

<div class="relative">
	<button
		bind:this={buttonEl}
		type="button"
		class="model-btn"
		onclick={(e) => {
			e.stopPropagation();
			open = !open;
		}}
		aria-haspopup="listbox"
		aria-expanded={open}
		title={scene.model}
	>
		<span class="model-dot" style:background={open ? 'var(--accent)' : 'var(--fg-4)'}></span>
		<span class="model-label">{current ? shortId(current.id) : shortId(scene.model)}</span>
		<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
			<path d="M2 4 L5 7 L8 4" stroke="currentColor" stroke-width="1.2" fill="none" />
		</svg>
	</button>

	{#if open}
		<div bind:this={menuEl} class="menu">
			<div class="search">
				<input
					bind:this={searchEl}
					type="text"
					placeholder="search models…"
					bind:value={query}
					oninput={() => (activeIdx = 0)}
					role="combobox"
					aria-controls={listId}
					aria-expanded="true"
					aria-autocomplete="list"
					aria-activedescendant={activeId}
					aria-label="Search models"
				/>
				<span class="hint font-mono">{filtered.length}</span>
			</div>
			<div class="list" id={listId} role="listbox" aria-label="Models">
				{#if loading}
					<div class="empty font-mono">loading…</div>
				{:else if loadFailed}
					<div class="empty font-mono">couldn't load models — using {shortId(scene.model)}</div>
				{:else if visible.length === 0}
					<div class="empty font-mono">no match</div>
				{:else}
					{#each visible as m, i (m.id)}
						<button
							type="button"
							class="row"
							class:active={i === activeIdx}
							class:current={m.id === scene.model}
							role="option"
							id={optionId(m.id)}
							aria-selected={m.id === scene.model}
							onclick={() => pick(m)}
							onmouseenter={() => (activeIdx = i)}
						>
							<div class="row-main">
								<span class="row-id font-mono">{m.id}</span>
								<span class="row-name">{m.name}</span>
							</div>
							<div class="row-meta font-mono">
								<span>{(m.context_length / 1000).toFixed(0)}k</span>
								<span class="sep">·</span>
								<span>{fmtCost(m.prompt_per_mtok)}/{fmtCost(m.completion_per_mtok)}</span>
								{#if m.supports_cache}
									<span class="sep">·</span>
									<span class="cache">cache</span>
								{/if}
							</div>
						</button>
					{/each}
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.model-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px;
		font-family: var(--font-mono);
		font-size: var(--text-2xs);
		color: var(--fg-3);
		background: transparent;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.model-btn:hover {
		color: var(--fg-1);
		border-color: var(--border-2);
		background: var(--bg-2);
	}
	.model-dot {
		width: 6px;
		height: 6px;
		border-radius: 9999px;
	}
	.model-label {
		max-width: 220px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.menu {
		position: absolute;
		top: calc(100% + 6px);
		right: 0;
		width: 460px;
		max-width: calc(100vw - 32px);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		box-shadow: var(--shadow-lg);
		z-index: 60;
		display: flex;
		flex-direction: column;
		max-height: 70vh;
		overflow: hidden;
	}
	.search {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		border-bottom: 1px solid var(--border-0);
	}
	.search input {
		flex: 1;
		background: transparent;
		border: 0;
		outline: 0;
		color: var(--fg-0);
		font-family: var(--font-body);
		font-size: var(--text-sm);
	}
	.search input::placeholder {
		color: var(--fg-4);
	}
	.search .hint {
		font-size: var(--text-2xs);
		color: var(--fg-4);
	}
	.list {
		overflow-y: auto;
		padding: 4px;
	}
	.empty {
		padding: 16px;
		text-align: center;
		font-size: var(--text-2xs);
		color: var(--fg-4);
	}
	.row {
		display: flex;
		flex-direction: column;
		align-items: stretch;
		gap: 2px;
		width: 100%;
		padding: 8px 10px;
		border: 0;
		border-radius: var(--radius-sm);
		background: transparent;
		text-align: left;
		cursor: pointer;
		transition: background var(--duration-fast) var(--ease-out);
	}
	.row:hover,
	.row.active {
		background: var(--bg-2);
	}
	.row.current {
		background: var(--accent-bg);
	}
	.row-main {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 12px;
		width: 100%;
	}
	.row-id {
		font-size: var(--text-xs);
		color: var(--fg-1);
	}
	.row.current .row-id {
		color: var(--accent);
	}
	.row-name {
		font-size: var(--text-2xs);
		color: var(--fg-4);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.row-meta {
		display: flex;
		gap: 6px;
		font-size: var(--text-2xs);
		color: var(--fg-4);
	}
	.row-meta .sep {
		color: var(--border-2);
	}
	.row-meta .cache {
		color: var(--success);
	}
</style>
