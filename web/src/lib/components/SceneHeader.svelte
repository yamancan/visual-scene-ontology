<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { isPrebuilt } from '$lib/utils';
	import { buildSceneView } from '$lib/render/sceneView';
	import LayoutSwitcher from './LayoutSwitcher.svelte';

	let env = $derived(scene.envelope);
	let conforms = $derived(env?.conformance.conforms ?? null);
	let violations = $derived(env?.conformance?.violations?.length ?? 0);
	let nodes = $derived(env?.graph?.nodes.length ?? 0);
	let edges = $derived(env?.graph?.edges.length ?? 0);
	let triples = $derived(env?.vson_t ? (env.vson_t.match(/\s\.\s*\n/g) || []).length : 0);
	let latency = $derived(env?.extraction?.latency_ms ?? 0);
	let retries = $derived(env?.extraction?.shacl_retries ?? 0);
	let model = $derived(env?.extraction?.model ?? scene.model);
	let prebuilt = $derived(isPrebuilt(model));

	// The resting "N entities" count mirrors the canvas: top-level entities only,
	// i.e. those not nested inside another entity's Has chip-row. This is the one
	// human-readable count the header keeps; the raw graph stats move behind "i".
	let entityCount = $derived.by(() => {
		const g = env?.graph;
		if (!g) return 0;
		const view = buildSceneView(g);
		const contained = new Set<string>();
		for (const e of view.entities) for (const h of e.has) contained.add(h.to);
		return view.entities.filter((e) => !contained.has(e.id)).length;
	});

	function shortModel(id: string): string {
		if (isPrebuilt(id)) return 'prebuilt';
		const i = id.indexOf('/');
		return i >= 0 ? id.slice(i + 1) : id;
	}

	// Details popover (ModelPicker pattern: outside-click + Escape close).
	let infoOpen = $state(false);
	let infoBtnEl: HTMLButtonElement | undefined = $state();
	let infoMenuEl: HTMLDivElement | undefined = $state();

	function onKey(e: KeyboardEvent) {
		if (infoOpen && e.key === 'Escape') {
			infoOpen = false;
			e.preventDefault();
		}
	}
	function onDocClick(e: MouseEvent) {
		if (!infoOpen) return;
		const t = e.target as Node;
		if (infoMenuEl?.contains(t) || infoBtnEl?.contains(t)) return;
		infoOpen = false;
	}
</script>

<svelte:window onkeydown={onKey} onclick={onDocClick} />

{#if env}
	<header class="hdr">
		<div class="hdr-left">
			{#if scene.imagePreview}
				<img src={scene.imagePreview} alt="source" class="thumb" />
			{:else}
				<div class="thumb thumb-empty"></div>
			{/if}
			<span class="conf-pill" class:pass={conforms === true} class:fail={conforms === false}>
				<span class="dot"></span>
				<span class="font-mono">{conforms ? 'Conforms' : 'Violations'}</span>
				{#if conforms === false && violations > 0}
					<span class="conf-count font-mono">{violations}</span>
				{/if}
			</span>
			<span class="count">
				<span class="count-num font-mono">{entityCount}</span>
				<span class="count-label">{entityCount === 1 ? 'entity' : 'entities'}</span>
			</span>
		</div>

		<div class="hdr-right">
			<LayoutSwitcher />

			<div class="info-wrap">
				<button
					bind:this={infoBtnEl}
					type="button"
					class="info-btn"
					class:open={infoOpen}
					onclick={(e) => {
						e.stopPropagation();
						infoOpen = !infoOpen;
					}}
					aria-haspopup="dialog"
					aria-expanded={infoOpen}
					title="Scene details"
					aria-label="Scene details"
				>
					<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
						<circle cx="7" cy="7" r="6" fill="none" stroke="currentColor" stroke-width="1.2" />
						<circle cx="7" cy="4.1" r="0.85" fill="currentColor" />
						<path d="M7 6.4V10.2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
					</svg>
				</button>

				{#if infoOpen}
					<div bind:this={infoMenuEl} class="info-menu" role="dialog" aria-label="Scene details">
						<dl class="details">
							<div class="d-row">
								<dt>scene</dt>
								<dd class="d-id font-mono" title={env.scene_id}>{env.scene_id}</dd>
							</div>
							<div class="d-row">
								<dt>model</dt>
								<dd class="font-mono" title={model}>{shortModel(model)}</dd>
							</div>
							{#if !prebuilt}
								<div class="d-row">
									<dt>latency</dt>
									<dd class="font-mono">{(latency / 1000).toFixed(2)}s</dd>
								</div>
							{/if}
							{#if retries > 0}
								<div class="d-row">
									<dt>repairs</dt>
									<dd class="retry font-mono">{retries}</dd>
								</div>
							{/if}
							<div class="d-sep"></div>
							<div class="d-row">
								<dt>nodes</dt>
								<dd class="font-mono">{nodes}</dd>
							</div>
							<div class="d-row">
								<dt>edges</dt>
								<dd class="font-mono">{edges}</dd>
							</div>
							<div class="d-row">
								<dt>triples</dt>
								<dd class="font-mono">{triples}</dd>
							</div>
						</dl>
					</div>
				{/if}
			</div>
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
		gap: var(--s3);
		flex-shrink: 0;
	}
	.thumb {
		width: 40px;
		height: 40px;
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
	.count {
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		color: var(--fg-3);
		min-width: 0;
	}
	.count-num {
		font-size: var(--text-lg);
		font-weight: 500;
		color: var(--fg-0);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}
	.count-label {
		font-size: var(--text-xs);
		color: var(--fg-4);
	}
	.retry {
		color: var(--warning, var(--accent));
	}
	.conf-pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 3px 9px 3px 8px;
		border-radius: var(--radius-full);
		font-size: var(--text-2xs);
		letter-spacing: 0.02em;
		border: 1px solid var(--border-1);
		background: var(--bg-2);
		color: var(--fg-3);
		flex-shrink: 0;
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
	.conf-count {
		padding: 0 5px;
		border-radius: var(--radius-full);
		background: color-mix(in srgb, var(--danger) 18%, transparent);
		color: var(--danger);
		font-variant-numeric: tabular-nums;
	}

	.info-wrap {
		position: relative;
	}
	.info-btn {
		display: inline-grid;
		place-items: center;
		width: 26px;
		height: 26px;
		padding: 0;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		background: var(--bg-1);
		color: var(--fg-4);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.info-btn:hover {
		color: var(--fg-1);
		border-color: var(--border-2);
		background: var(--bg-2);
	}
	.info-btn.open {
		color: var(--accent);
		border-color: color-mix(in srgb, var(--accent) 45%, var(--border-1));
		background: var(--accent-bg);
	}

	.info-menu {
		position: absolute;
		top: calc(100% + 6px);
		right: 0;
		width: 240px;
		max-width: calc(100vw - 32px);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		box-shadow: var(--shadow-lg);
		z-index: 60;
		padding: var(--s3);
	}
	.details {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin: 0;
	}
	.d-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--s4);
		padding: 3px 0;
	}
	.d-row dt {
		font-size: var(--text-2xs);
		color: var(--fg-4);
		letter-spacing: 0.02em;
	}
	.d-row dd {
		margin: 0;
		font-size: var(--text-xs);
		color: var(--fg-1);
		font-variant-numeric: tabular-nums;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.d-id {
		max-width: 150px;
	}
	.d-sep {
		height: 1px;
		background: var(--border-1);
		margin: var(--s2) 0;
	}

	@media (max-width: 720px) {
		.hdr-right {
			gap: var(--s2);
		}
		.thumb {
			width: 36px;
			height: 36px;
		}
	}
</style>
