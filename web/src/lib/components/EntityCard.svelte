<script lang="ts">
	import {
		restingHint,
		colorSwatch,
		type EntityCardModel,
		type HasRef
	} from '$lib/render/sceneView';
	import { scene } from '$lib/scene.svelte';
	import { parseBbox, cropStyle } from '$lib/bbox';

	let {
		entity,
		selected = false,
		onselect
	}: {
		entity: EntityCardModel;
		selected?: boolean;
		onselect?: (id: string) => void;
	} = $props();

	// Tiny curated registry — the open `vso:class` vocabulary means we cannot
	// pre-icon every class. Falls back to the generic glyph.
	const CLASS_ICON: Record<string, string> = {
		Human: '👤',
		Person: '👤',
		Woman: '👤',
		Man: '👤',
		Boar: '🐗',
		Dog: '🐕',
		Cat: '🐈',
		Horse: '🐎',
		Bird: '🐦',
		Sword: '⚔',
		Shield: '🛡',
		Crown: '👑',
		Lamp: '💡',
		Lampshade: '💡',
		Bed: '🛏',
		Door: '🚪',
		Table: '🪑',
		Chair: '🪑',
		Tree: '🌳',
		Book: '📖',
		Window: '🪟',
		Headwear: '🧢',
		Hat: '🎩',
		Top: '👕',
		Shirt: '👕',
		Jacket: '🧥',
		Coat: '🧥',
		Jeans: '👖',
		Pants: '👖',
		Skirt: '👗',
		Dress: '👗',
		Shoes: '👟',
		Boots: '👢',
		Sunglasses: '🕶',
		Glasses: '👓',
		Bag: '👜',
		Handbag: '👜',
		Backpack: '🎒',
		Watch: '⌚',
		Ring: '💍',
		Necklace: '📿',
		Wall: '🧱'
	};
	const FALLBACK = '▣';
	function iconFor(klass?: string): string {
		return klass ? (CLASS_ICON[klass] ?? FALLBACK) : FALLBACK;
	}
	let icon = $derived(iconFor(entity.klass));

	function activate() {
		onselect?.(entity.id);
	}
	function onCardKey(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			activate();
		}
	}
	function focusItem(e: MouseEvent | KeyboardEvent, ref: HasRef) {
		e.stopPropagation();
		if (e instanceof KeyboardEvent && e.key !== 'Enter' && e.key !== ' ') return;
		if (e instanceof KeyboardEvent) e.preventDefault();
		onselect?.(ref.to);
	}

	let hasGroups = $derived.by(() => {
		const m = new Map<string, HasRef[]>();
		for (const h of entity.has) {
			const arr = m.get(h.label) ?? [];
			arr.push(h);
			m.set(h.label, arr);
		}
		return Array.from(m.entries()).map(([label, items]) => ({ label, items }));
	});

	// ONE quality hint at rest (colour-preferred), shared with the Inspect row via
	// restingHint so both surfaces agree. A plain colour word also paints a
	// swatch. The full per-dim list lives in the inline editor.
	let hint = $derived(restingHint(entity.qualities));
	let swatch = $derived(colorSwatch(hint));

	// CROP THUMBNAIL: a CSS-sprite crop of the source image showing only this
	// entity's bbox sub-rect. Shown in the header in place of the emoji icon, but
	// ONLY when we have a preview image AND a localized (non-full-image) box.
	let cardBbox = $derived(parseBbox(entity.geometry.bbox));
	let showCrop = $derived(!!scene.imagePreview && !!cardBbox && !cardBbox.isFullImage);
	let cropCss = $derived(
		showCrop && cardBbox ? cropStyle(cardBbox, scene.imagePreview as string) : ''
	);

	function itemCrop(h: HasRef): string {
		const b = parseBbox(h.geometry.bbox);
		if (!scene.imagePreview || !b || b.isFullImage) return '';
		return cropStyle(b, scene.imagePreview);
	}

	// INLINE EDIT: staged corrections accumulate in the scene store (flushed to
	// /api/correct on submit). All edit-mode controls carry nodrag/nopan/nowheel
	// and stop event propagation so xyflow never drags the node and the card's
	// select-onclick never fires while the user is typing.
	let editing = $state(false);
	let edit = $derived(scene.pendingEdits[entity.id]);
	let hasEdit = $derived(!!edit);

	// Stop pointerdown/keydown/click from bubbling to the draggable node or the
	// card's activate() handler.
	function stop(e: Event) {
		e.stopPropagation();
	}
	function toggleEdit(e: Event) {
		e.stopPropagation();
		editing = !editing;
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

	// CROSS-HIGHLIGHT: light hover sync with the rest of the studio.
	function onEnter() {
		scene.setHovered(entity.id);
	}
	function onLeave() {
		scene.setHovered(null);
	}
</script>

<div
	class="card"
	class:selected
	class:hovered={scene.hoveredNodeId === entity.id}
	class:edited={hasEdit}
	class:removing={edit?.remove}
	role="button"
	tabindex="0"
	aria-pressed={selected}
	onclick={activate}
	onkeydown={onCardKey}
	onmouseenter={onEnter}
	onmouseleave={onLeave}
>
	<header class="head">
		{#if showCrop}
			<span
				class="crop"
				style={cropCss}
				aria-hidden="true"
			></span>
		{:else}
			<span class="ico" aria-hidden="true">{icon}</span>
		{/if}
		<span class="id font-mono">@{entity.id}</span>
		{#if entity.klass}<span class="klass">{entity.klass}</span>{/if}
		{#if hasEdit}<span class="edit-dot" title="staged correction" aria-label="edited"></span>{/if}
		<button
			type="button"
			class="edit-toggle nodrag nopan nowheel"
			class:active={editing}
			aria-pressed={editing}
			title={editing ? 'Close editor' : 'Edit entity'}
			onclick={toggleEdit}
			onpointerdown={stop}
			onkeydown={stop}>✎</button
		>
	</header>

	{#if editing}
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<div
			class="editor nodrag nopan nowheel"
			role="group"
			onclick={stop}
			onpointerdown={stop}
			onkeydown={stop}
		>
			<label class="ed-row">
				<span class="ed-label font-mono">class</span>
				<input
					class="ed-input nodrag nopan nowheel font-mono"
					type="text"
					value={edit?.klass ?? entity.klass ?? ''}
					placeholder="vso:class"
					oninput={onKlassInput}
					onpointerdown={stop}
					onkeydown={stop}
				/>
			</label>

			{#if entity.qualities.length}
				<div class="ed-qualities">
					{#each entity.qualities as q (q.dim)}
						<label class="ed-row">
							<span class="ed-label font-mono">{q.dim}</span>
							<input
								class="ed-input nodrag nopan nowheel"
								type="text"
								value={edit?.qualities?.find((e) => e.dim === q.dim)?.value ?? q.value}
								oninput={(e) => onQualityInput(q.dim, e)}
								onpointerdown={stop}
								onkeydown={stop}
							/>
						</label>
					{/each}
				</div>
			{/if}

			<label class="ed-row ed-note-row">
				<span class="ed-label font-mono">note</span>
				<textarea
					class="ed-note nodrag nopan nowheel"
					rows="2"
					placeholder="correction note for this entity"
					value={edit?.note ?? ''}
					oninput={onNoteInput}
					onpointerdown={stop}
					onkeydown={stop}
				></textarea>
			</label>

			<button
				type="button"
				class="ed-remove nodrag nopan nowheel"
				class:on={edit?.remove}
				aria-pressed={edit?.remove ?? false}
				onclick={toggleRemove}
				onpointerdown={stop}
				onkeydown={stop}
			>
				{edit?.remove ? '✓ marked for removal' : 'remove this entity'}
			</button>
		</div>
	{/if}

	{#if !editing && hint}
		<p class="hint">
			{#if swatch}<span class="swatch" style="background:{swatch}"></span>{/if}
			{hint.value}
		</p>
	{/if}

	{#if !editing && hasGroups.length}
		<div class="parts">
			{#each hasGroups as g (g.label)}
				<div class="part-group">
					<span class="part-pred font-mono">{g.label}</span>
					{#each g.items as h, i (h.label + h.to + i)}
						<button
							type="button"
							class="part-chip"
							onclick={(e) => focusItem(e, h)}
							onkeydown={(e) => focusItem(e, h)}
							title="{g.label} → {h.klass ?? '?'} @{h.to}"
						>
							{#if itemCrop(h)}
								<span class="chip-crop" style={itemCrop(h)} aria-hidden="true"></span>
							{:else}
								<span class="chip-ico" aria-hidden="true">{iconFor(h.klass)}</span>
							{/if}
							<span class="chip-label">{h.klass ?? `@${h.to}`}</span>
						</button>
					{/each}
				</div>
			{/each}
		</div>
	{/if}

	{#if !editing && entity.outgoing.length}
		<div class="parts">
			<div class="part-group">
				<span class="part-pred font-mono">links</span>
				{#each entity.outgoing as e, i (e.label + e.to + i)}
					<button
						type="button"
						class="part-chip"
						onclick={(ev) =>
							focusItem(ev, {
								label: e.label,
								to: e.to,
								traits: { affordance: [] },
								qualities: [],
								geometry: { occludes: [] }
							})}
						onkeydown={(ev) =>
							focusItem(ev, {
								label: e.label,
								to: e.to,
								traits: { affordance: [] },
								qualities: [],
								geometry: { occludes: [] }
							})}
						title="{e.label} → @{e.to}"
					>
						<span class="chip-label font-mono">{e.label} @{e.to}</span>
					</button>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: var(--s2);
		padding: var(--s3);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		text-align: left;
		font-family: inherit;
		cursor: pointer;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
		min-width: 0;
	}
	.card:hover {
		border-color: var(--border-2);
	}
	.card:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.card.selected {
		border-color: var(--accent);
		background: var(--accent-bg);
	}
	/* Cross-highlight: subtle border lift when the matching node is hovered
	   anywhere in the studio. Stays under .selected (selection wins). */
	.card.hovered:not(.selected) {
		border-color: var(--border-2);
	}
	.card.edited {
		border-color: var(--accent);
	}
	.card.removing {
		border-color: var(--danger);
	}
	.head {
		display: flex;
		align-items: center;
		gap: var(--s2);
		min-width: 0;
	}
	.ico {
		font-size: 14px;
		line-height: 1;
	}
	.crop {
		width: 30px;
		height: 30px;
		flex-shrink: 0;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
	}
	.edit-dot {
		width: 6px;
		height: 6px;
		flex-shrink: 0;
		border-radius: var(--radius-full);
		background: var(--accent);
	}
	.edit-toggle {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		padding: 0;
		margin-left: var(--s2);
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		color: var(--fg-3);
		font: inherit;
		font-size: var(--text-xs);
		line-height: 1;
		cursor: pointer;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.edit-toggle:hover {
		border-color: var(--border-2);
		color: var(--fg-1);
	}
	.edit-toggle.active {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-bg);
	}
	.edit-toggle:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 1px;
	}
	.editor {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: var(--s2);
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
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
	.id {
		font-size: var(--text-xs);
		color: var(--fg-1);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.klass {
		font-size: 9px;
		letter-spacing: 0.06em;
		color: var(--fg-4);
		margin-left: auto;
	}
	/* ONE quality hint — a calm single line, sentence-case, no axis labels. */
	.hint {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		margin: 0;
		font-size: var(--text-xs);
		color: var(--fg-2);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.swatch {
		width: 11px;
		height: 11px;
		flex-shrink: 0;
		border-radius: var(--radius-full);
		border: 1px solid color-mix(in srgb, var(--fg-0) 22%, transparent);
	}
	/* PART SUMMARY — compact chips, one row per predicate. Each chip jumps to
	   the referenced entity. Full per-part detail lives in the inline editor. */
	.parts {
		display: flex;
		flex-direction: column;
		gap: var(--s2);
		padding-top: var(--s2);
		border-top: 1px dashed var(--border-1);
		margin-top: 2px;
	}
	.part-group {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px;
		min-width: 0;
	}
	.part-pred {
		font-size: 9px;
		color: var(--fg-4);
		flex-shrink: 0;
	}
	.part-chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		max-width: 100%;
		padding: 2px 6px 2px 3px;
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-full);
		color: var(--fg-1);
		font-family: inherit;
		font-size: var(--text-xs);
		cursor: pointer;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
		min-width: 0;
	}
	.part-chip:hover {
		border-color: var(--border-2);
		background: var(--bg-1);
	}
	.part-chip:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 1px;
	}
	.chip-ico {
		font-size: 11px;
		line-height: 1;
		flex-shrink: 0;
	}
	.chip-crop {
		width: 16px;
		height: 16px;
		flex-shrink: 0;
		border-radius: var(--radius-full);
	}
	.chip-label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
</style>
