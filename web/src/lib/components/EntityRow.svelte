<script lang="ts">
	import {
		restingHint,
		colorSwatch,
		type EntityCardModel,
		type HasRef
	} from '$lib/render/sceneView';
	import { scene } from '$lib/scene.svelte';
	import { parseBbox, cropStyle } from '$lib/bbox';

	let { entity }: { entity: EntityCardModel } = $props();

	// One compact verification row per top-level entity. At rest it shows a crop
	// thumbnail + name + class + a single quality hint + part count. Click toggles
	// the in-place detail/edit drawer AND drives the shared selection so the
	// matching overlay box lights up with the same accent.

	let expanded = $state(false);

	let selected = $derived(scene.selectedNodeId === entity.id);
	let hovered = $derived(scene.hoveredNodeId === entity.id);

	// CROP THUMBNAIL: a CSS-sprite crop of the source image showing only this
	// entity's bbox sub-rect. Skipped when there's no preview or the box is the
	// full image (no localization to show).
	let bbox = $derived(parseBbox(entity.geometry.bbox));
	let showCrop = $derived(!!scene.imagePreview && !!bbox && !bbox.isFullImage);
	let cropCss = $derived(showCrop && bbox ? cropStyle(bbox, scene.imagePreview as string) : '');

	function itemCrop(h: HasRef): string {
		const b = parseBbox(h.geometry.bbox);
		if (!scene.imagePreview || !b || b.isFullImage) return '';
		return cropStyle(b, scene.imagePreview);
	}

	// Single quality hint for the resting row (colour-preferred), shared with the
	// Graph card via restingHint. A plain colour word also paints a swatch.
	let hint = $derived(restingHint(entity.qualities));
	let swatch = $derived(colorSwatch(hint));

	// Part count: every Has chip is a contained sub-entity (wears/holds/hasPart…).
	let partCount = $derived(entity.has.length);

	function name(): string {
		// Fall back to the semantic kind (e.g. "PhysicalObject"), never the raw
		// node id — an internal id has no place in the at-rest Glance view.
		return entity.klass ?? entity.kind;
	}

	// ROW HEADER: toggles the drawer and selects. mouseenter/leave sync the
	// cross-highlight with the overlay box.
	function toggle() {
		expanded = !expanded;
		// Selection follows the drawer: opening selects (lights its overlay box),
		// closing clears — so a second click also deselects, matching the toggle
		// semantics of the overlay box and the graph node.
		scene.setSelected(expanded ? entity.id : null);
	}
	function onEnter() {
		scene.setHovered(entity.id);
	}
	function onLeave() {
		scene.setHovered(null);
	}
	function focusPart(e: Event, partId: string) {
		e.stopPropagation();
		scene.setSelected(partId);
	}

	// INLINE EDIT — staged corrections accumulate in the scene store (flushed to
	// /api/correct on submit), mirroring the fields EntityCard edits: class,
	// per-dim qualities, a note, and a remove flag.
	let edit = $derived(scene.pendingEdits[entity.id]);
	let hasEdit = $derived(!!edit);

	// Stop inner controls from bubbling to the row toggle / select.
	function stop(e: Event) {
		e.stopPropagation();
	}
	function onKlassInput(e: Event) {
		scene.setEntityEdit(entity.id, { klass: (e.target as HTMLInputElement).value });
	}
	// Quality edits replace the FULL dim/value list so the correction payload
	// stays self-describing — start from the live qualities, layered with any
	// already-staged overrides, then patch the one dim the user touched.
	function currentQualityList(): { dim: string; value: string }[] {
		const staged = edit?.qualities;
		const base = staged ?? entity.qualities.map((q) => ({ dim: q.dim, value: q.value }));
		return base.map((q) => ({ dim: q.dim, value: q.value }));
	}
	function onQualityInput(dim: string, e: Event) {
		const value = (e.target as HTMLInputElement).value;
		const list = currentQualityList();
		const row = list.find((q) => q.dim === dim);
		if (row) row.value = value;
		else list.push({ dim, value });
		scene.setEntityEdit(entity.id, { qualities: list });
	}
	function onNoteInput(e: Event) {
		scene.setEntityEdit(entity.id, { note: (e.target as HTMLTextAreaElement).value });
	}
	function toggleRemove(e: Event) {
		e.stopPropagation();
		scene.setEntityEdit(entity.id, { remove: !edit?.remove });
	}
	function clearEdit(e: Event) {
		e.stopPropagation();
		scene.clearEntityEdit(entity.id);
	}
</script>

<div class="row" class:selected class:hovered class:edited={hasEdit} class:removing={edit?.remove}>
	<button
		type="button"
		class="row-head"
		aria-expanded={expanded}
		aria-pressed={selected}
		onclick={toggle}
		onmouseenter={onEnter}
		onmouseleave={onLeave}
	>
		{#if showCrop}
			<span class="crop" style={cropCss} aria-hidden="true"
			></span>
		{:else}
			<span class="crop crop-empty" aria-hidden="true">▣</span>
		{/if}

		<span class="name">{name()}</span>
		{#if entity.klass && entity.klass !== name()}
			<span class="klass font-mono">{entity.klass}</span>
		{/if}

		{#if hasEdit}<span class="edit-dot" title="staged correction" aria-label="edited"></span>{/if}

		<span class="row-meta">
			{#if hint}
				<span class="hint" title="{hint.dim}: {hint.value}">
					{#if swatch}<span class="swatch" style="background:{swatch}"></span>{/if}
					{hint.value}
				</span>
			{/if}
			{#if partCount}
				<span class="parts-count font-mono" title="{partCount} parts">{partCount}p</span>
			{/if}
		</span>

		<svg
			class="chevron"
			class:open={expanded}
			width="12"
			height="12"
			viewBox="0 0 12 12"
			aria-hidden="true"
		>
			<path
				d="M3 4.5L6 7.5L9 4.5"
				fill="none"
				stroke="currentColor"
				stroke-width="1.4"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
		</svg>
	</button>

	{#if expanded}
		<div class="detail">
			{#if entity.qualities.length}
				<ul class="qualities">
					{#each entity.qualities as q (q.dim)}
						<li>
							<span class="dim font-mono">{q.dim}</span>
							<span class="val">{q.value}</span>
						</li>
					{/each}
				</ul>
			{/if}

			{#if entity.has.length}
				<ul class="parts" aria-label="parts">
					{#each entity.has as h, i (h.label + h.to + i)}
						<li>
							<button
								type="button"
								class="part"
								title="{h.label} → {h.klass ?? '?'} @{h.to}"
								onclick={(e) => focusPart(e, h.to)}
							>
								{#if itemCrop(h)}
									<span class="part-crop" style={itemCrop(h)} aria-hidden="true"></span>
								{:else}
									<span class="part-crop part-crop-empty" aria-hidden="true">▣</span>
								{/if}
								<span class="part-label">{h.klass ?? h.to}</span>
								<span class="part-pred font-mono">{h.label}</span>
							</button>
						</li>
					{/each}
				</ul>
			{/if}

			<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
			<div class="editor" role="group" onclick={stop} onkeydown={stop}>
				<header class="editor-h">
					<span class="editor-title font-mono">edit</span>
					{#if hasEdit}
						<button type="button" class="editor-clear font-mono" onclick={clearEdit}>clear</button>
					{/if}
				</header>

				<label class="ed-row">
					<span class="ed-label font-mono">class</span>
					<input
						class="ed-input font-mono"
						type="text"
						value={edit?.klass ?? entity.klass ?? ''}
						placeholder="vso:class"
						oninput={onKlassInput}
					/>
				</label>

				{#if entity.qualities.length}
					<div class="ed-qualities">
						{#each entity.qualities as q (q.dim)}
							<label class="ed-row">
								<span class="ed-label font-mono">{q.dim}</span>
								<input
									class="ed-input"
									type="text"
									value={edit?.qualities?.find((e) => e.dim === q.dim)?.value ?? q.value}
									oninput={(e) => onQualityInput(q.dim, e)}
								/>
							</label>
						{/each}
					</div>
				{/if}

				<label class="ed-row ed-note-row">
					<span class="ed-label font-mono">note</span>
					<textarea
						class="ed-note"
						rows="2"
						placeholder="correction note for this entity"
						value={edit?.note ?? ''}
						oninput={onNoteInput}
					></textarea>
				</label>

				<button
					type="button"
					class="ed-remove"
					class:on={edit?.remove}
					aria-pressed={edit?.remove ?? false}
					onclick={toggleRemove}
				>
					{edit?.remove ? '✓ marked for removal' : 'remove this entity'}
				</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.row {
		list-style: none;
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		background: var(--bg-1);
		transition:
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
		min-width: 0;
	}
	/* Cross-highlight: subtle lift when the matching box/node is hovered. Stays
	   under .selected (selection wins). */
	.row.hovered:not(.selected) {
		border-color: var(--border-2);
	}
	.row.selected {
		border-color: var(--accent);
		background: var(--accent-bg);
	}
	.row.edited {
		border-color: var(--accent);
	}
	.row.removing {
		border-color: var(--danger);
	}

	.row-head {
		display: flex;
		align-items: center;
		gap: var(--s2);
		width: 100%;
		padding: var(--s2) var(--s3);
		background: transparent;
		border: 0;
		border-radius: var(--radius);
		color: var(--fg-0);
		font: inherit;
		text-align: left;
		cursor: pointer;
		min-width: 0;
	}
	.row-head:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.crop {
		width: 28px;
		height: 28px;
		flex-shrink: 0;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
	}
	.crop-empty {
		display: grid;
		place-items: center;
		background: var(--bg-2);
		color: var(--fg-4);
		font-size: 13px;
		line-height: 1;
	}

	.name {
		font-size: var(--text-base);
		color: var(--fg-0);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
	.klass {
		font-size: 9px;
		letter-spacing: 0.06em;
		color: var(--fg-4);
		flex-shrink: 0;
	}

	.edit-dot {
		width: 6px;
		height: 6px;
		flex-shrink: 0;
		border-radius: var(--radius-full);
		background: var(--accent);
	}

	.row-meta {
		display: flex;
		align-items: center;
		gap: var(--s2);
		margin-left: auto;
		flex-shrink: 0;
	}
	.hint {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		max-width: 110px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--text-xs);
		color: var(--fg-2);
	}
	.swatch {
		width: 11px;
		height: 11px;
		flex-shrink: 0;
		border-radius: var(--radius-full);
		border: 1px solid color-mix(in srgb, var(--fg-0) 22%, transparent);
	}
	.parts-count {
		font-size: 9px;
		color: var(--fg-4);
	}

	.chevron {
		flex-shrink: 0;
		color: var(--fg-4);
		transform: rotate(-90deg);
		transition: transform var(--duration-fast) var(--ease-out);
	}
	.chevron.open {
		transform: rotate(0deg);
	}

	/* DETAIL DRAWER — qualities, part chips, then the inline editor. Only present
	   while expanded. */
	.detail {
		display: flex;
		flex-direction: column;
		gap: var(--s3);
		padding: 0 var(--s3) var(--s3);
		border-top: 1px solid var(--border-1);
		margin-top: -1px;
		padding-top: var(--s3);
	}

	.qualities {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}
	.qualities li {
		display: grid;
		grid-template-columns: 88px 1fr;
		gap: var(--s2);
		font-size: var(--text-xs);
		align-items: baseline;
		min-width: 0;
	}
	.dim {
		color: var(--fg-4);
		font-size: 10px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.val {
		color: var(--fg-1);
		overflow-wrap: anywhere;
	}

	.parts {
		list-style: none;
		display: flex;
		flex-wrap: wrap;
		gap: var(--s2);
		min-width: 0;
	}
	.part {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 3px 7px 3px 4px;
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-full);
		color: var(--fg-1);
		font: inherit;
		cursor: pointer;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
		min-width: 0;
	}
	.part:hover {
		border-color: var(--border-2);
		background: var(--bg-1);
	}
	.part:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 1px;
	}
	.part-crop {
		width: 18px;
		height: 18px;
		flex-shrink: 0;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-full);
	}
	.part-crop-empty {
		display: grid;
		place-items: center;
		background: var(--bg-2);
		color: var(--fg-4);
		font-size: 10px;
		line-height: 1;
	}
	.part-label {
		font-size: var(--text-xs);
		color: var(--fg-0);
	}
	.part-pred {
		font-size: 8px;
		letter-spacing: 0.04em;
		color: var(--fg-4);
	}

	/* INLINE EDITOR — mirrors the EntityCard fields (class, per-dim qualities,
	   note, remove) writing through scene.setEntityEdit / clearEntityEdit. */
	.editor {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: var(--s2);
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
	}
	.editor-h {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.editor-title {
		font-size: 9px;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
	.editor-clear {
		background: transparent;
		border: 0;
		padding: 0;
		color: var(--fg-3);
		font-size: 9px;
		letter-spacing: 0.04em;
		cursor: pointer;
	}
	.editor-clear:hover {
		color: var(--fg-1);
	}
	.editor-clear:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 1px;
	}
	.ed-row {
		display: grid;
		grid-template-columns: 56px 1fr;
		align-items: center;
		gap: var(--s2);
		min-width: 0;
	}
	.ed-note-row {
		align-items: start;
	}
	.ed-label {
		font-size: 9px;
		color: var(--fg-4);
		letter-spacing: 0.04em;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.ed-input,
	.ed-note {
		width: 100%;
		min-width: 0;
		padding: 3px 6px;
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		color: var(--fg-0);
		font-family: inherit;
		font-size: var(--text-xs);
	}
	.ed-input:focus,
	.ed-note:focus {
		outline: none;
		border-color: var(--accent);
	}
	.ed-qualities {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.ed-note {
		resize: vertical;
		line-height: 1.4;
	}
	.ed-remove {
		align-self: flex-start;
		padding: 3px 8px;
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		color: var(--fg-3);
		font: inherit;
		font-size: var(--text-xs);
		cursor: pointer;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.ed-remove:hover {
		border-color: var(--danger);
		color: var(--danger);
	}
	.ed-remove.on {
		border-color: var(--danger);
		color: var(--danger);
	}
	.ed-remove:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 1px;
	}
</style>
