<script lang="ts">
	import type { EntityCardModel, HasRef } from '$lib/render/sceneView';
	import { scene } from '$lib/scene.svelte';
	import { parseBbox, cropStyle, fmtBbox } from '$lib/bbox';

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

	function fmt(n: number): string {
		return n.toFixed(2);
	}

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
				title={cardBbox ? fmtBbox(cardBbox) : ''}
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

	{#if entity.traits.individuation || entity.traits.animacy || entity.traits.countability || entity.traits.affordance.length}
		<div class="traits font-mono">
			{#if entity.traits.individuation}
				<span class="trait" title="vso:individuation">
					<span class="trait-axis">indiv</span>{entity.traits.individuation}
				</span>
			{/if}
			{#if entity.traits.animacy}
				<span class="trait" title="vso:animacy">
					<span class="trait-axis">anim</span>{entity.traits.animacy}
				</span>
			{/if}
			{#if entity.traits.countability}
				<span class="trait" title="vso:countability">
					<span class="trait-axis">count</span>{entity.traits.countability}
				</span>
			{/if}
			{#if entity.traits.affordance.length}
				<span class="trait" title="vso:affordance">
					<span class="trait-axis">aff</span>{entity.traits.affordance.join(',')}
				</span>
			{/if}
		</div>
	{/if}

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

	{#if entity.geometry.bbox || entity.geometry.position3d || entity.geometry.scale3d || entity.geometry.rotation || entity.geometry.visibleFraction || entity.geometry.occludes.length}
		<div class="geometry">
			{#if entity.geometry.bbox}
				{@const b = parseBbox(entity.geometry.bbox)}
				<div
					class="entity-bbox"
					title={b
						? `vso:bbox2d normalized 0–1 image coords · x=${fmt(b.x)} y=${fmt(b.y)} w=${fmt(b.w)} h=${fmt(b.h)}`
						: 'vso:bbox2d (unparseable)'}
				>
					<span class="g-key font-mono">bbox</span>
					{#if b && b.isFullImage}
						<span class="bbox-full font-mono">full</span>
					{:else if b}
						<svg class="bbox-mini" viewBox="0 0 24 24" aria-hidden="true">
							<rect
								x="0.5"
								y="0.5"
								width="23"
								height="23"
								fill="none"
								stroke="currentColor"
								stroke-opacity="0.18"
								stroke-width="1"
							/>
							<rect
								x={(b.x * 23 + 0.5).toFixed(2)}
								y={(b.y * 23 + 0.5).toFixed(2)}
								width={(b.w * 23).toFixed(2)}
								height={(b.h * 23).toFixed(2)}
								fill="currentColor"
								fill-opacity="0.18"
								stroke="currentColor"
								stroke-width="1.2"
							/>
						</svg>
						<span class="bbox-coord"><span class="bc-k">x</span>{fmt(b.x)}</span>
						<span class="bbox-coord"><span class="bc-k">y</span>{fmt(b.y)}</span>
						<span class="bbox-coord"><span class="bc-k">w</span>{fmt(b.w)}</span>
						<span class="bbox-coord"><span class="bc-k">h</span>{fmt(b.h)}</span>
					{:else}
						<span class="g-val font-mono">{entity.geometry.bbox}</span>
					{/if}
				</div>
			{/if}
			{#if entity.geometry.position3d}
				<div class="g-row" title="vso:position3d (x,y,z world coords)">
					<span class="g-key font-mono">pos3d</span>
					<span class="g-val font-mono">{entity.geometry.position3d}</span>
				</div>
			{/if}
			{#if entity.geometry.scale3d}
				<div class="g-row" title="vso:scale3d">
					<span class="g-key font-mono">scale3d</span>
					<span class="g-val font-mono">{entity.geometry.scale3d}</span>
				</div>
			{/if}
			{#if entity.geometry.rotation}
				<div class="g-row" title="vso:rotation (quaternion or Euler)">
					<span class="g-key font-mono">rot</span>
					<span class="g-val font-mono">{entity.geometry.rotation}</span>
				</div>
			{/if}
			{#if entity.geometry.visibleFraction}
				<div class="g-row" title="vso:visibleFraction (0–1)">
					<span class="g-key font-mono">visible</span>
					<span class="g-val font-mono">{entity.geometry.visibleFraction}</span>
				</div>
			{/if}
			{#if entity.geometry.occludes.length}
				<div class="g-row" title="vso:occludes — entities this one hides from the camera">
					<span class="g-key font-mono">occludes</span>
					<span class="g-val font-mono">
						{#each entity.geometry.occludes as o, i (o + i)}<button
								type="button"
								class="occludes-ref"
								onclick={(ev) =>
									focusItem(ev, {
										label: 'occludes',
										to: o,
										traits: { affordance: [] },
										qualities: [],
										geometry: { occludes: [] }
									})}>@{o}</button
							>{i < entity.geometry.occludes.length - 1 ? ', ' : ''}{/each}
					</span>
				</div>
			{/if}
		</div>
	{/if}

	{#if hasGroups.length}
		<div class="has-block">
			{#each hasGroups as g (g.label)}
				<div class="has-group">
					<header class="has-group-h">
						<span class="has-pred font-mono">{g.label}</span>
						<span class="has-count font-mono">{g.items.length}</span>
					</header>
					<ul class="has-items">
						{#each g.items as h, i (h.label + h.to + i)}
							<li>
								<button
									type="button"
									class="has-item"
									onclick={(e) => focusItem(e, h)}
									onkeydown={(e) => focusItem(e, h)}
									title="{h.label} → {h.klass ?? '?'} @{h.to}"
								>
									<div class="item-head">
										{#if itemCrop(h)}
											<span class="item-crop" style={itemCrop(h)} aria-hidden="true"></span>
										{:else}
											<span class="item-ico" aria-hidden="true">{iconFor(h.klass)}</span>
										{/if}
										<span class="item-klass">{h.klass ?? '?'}</span>
										<span class="item-id font-mono">@{h.to}</span>
									</div>
									{#if h.traits.individuation || h.traits.animacy || h.traits.countability || h.traits.affordance.length}
										<div class="item-traits font-mono">
											{#if h.traits.individuation}
												<span class="item-trait" title="vso:individuation">
													<span class="trait-axis">indiv</span>{h.traits.individuation}
												</span>
											{/if}
											{#if h.traits.animacy}
												<span class="item-trait" title="vso:animacy">
													<span class="trait-axis">anim</span>{h.traits.animacy}
												</span>
											{/if}
											{#if h.traits.countability}
												<span class="item-trait" title="vso:countability">
													<span class="trait-axis">count</span>{h.traits.countability}
												</span>
											{/if}
											{#if h.traits.affordance.length}
												<span class="item-trait" title="vso:affordance">
													<span class="trait-axis">aff</span>{h.traits.affordance.join(',')}
												</span>
											{/if}
										</div>
									{/if}
									{#if h.qualities.length}
										<div class="item-meta">
											{#each h.qualities as q (q.dim)}
												<span class="item-q">
													<span class="q-dim font-mono">{q.dim}</span>
													<span class="q-val">{q.value}</span>
												</span>
											{/each}
										</div>
									{/if}
									{#if h.geometry.bbox}
										{@const b = parseBbox(h.geometry.bbox)}
										<div
											class="item-bbox"
											title={b
												? `vso:bbox2d normalized 0–1 image coords · x=${fmt(b.x)} y=${fmt(b.y)} w=${fmt(b.w)} h=${fmt(b.h)}`
												: 'vso:bbox2d (unparseable)'}
										>
											<span class="q-dim font-mono">bbox</span>
											{#if b && b.isFullImage}
												<span class="bbox-full font-mono">full</span>
											{:else if b}
												<svg class="bbox-mini" viewBox="0 0 24 24" aria-hidden="true">
													<rect
														x="0.5"
														y="0.5"
														width="23"
														height="23"
														fill="none"
														stroke="currentColor"
														stroke-opacity="0.18"
														stroke-width="1"
													/>
													<rect
														x={(b.x * 23 + 0.5).toFixed(2)}
														y={(b.y * 23 + 0.5).toFixed(2)}
														width={(b.w * 23).toFixed(2)}
														height={(b.h * 23).toFixed(2)}
														fill="currentColor"
														fill-opacity="0.18"
														stroke="currentColor"
														stroke-width="1.2"
													/>
												</svg>
												<span class="bbox-coord"><span class="bc-k">x</span>{fmt(b.x)}</span>
												<span class="bbox-coord"><span class="bc-k">y</span>{fmt(b.y)}</span>
												<span class="bbox-coord"><span class="bc-k">w</span>{fmt(b.w)}</span>
												<span class="bbox-coord"><span class="bc-k">h</span>{fmt(b.h)}</span>
											{:else}
												<span class="q-val font-mono">{h.geometry.bbox}</span>
											{/if}
										</div>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
				</div>
			{/each}
		</div>
	{/if}

	{#if entity.outgoing.length}
		<ul class="outgoing">
			{#each entity.outgoing as e, i (e.label + e.to + i)}
				<li>
					<span class="rel font-mono">{e.label}</span>
					<span class="arrow" aria-hidden="true">→</span>
					<span class="ref font-mono">@{e.to}</span>
				</li>
			{/each}
		</ul>
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
		text-transform: uppercase;
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
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--fg-4);
		margin-left: auto;
	}
	.traits {
		display: flex;
		flex-wrap: wrap;
		gap: 3px;
	}
	.trait {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
		font-size: 9px;
		padding: 1px 5px;
		background: var(--tag-bg);
		color: var(--fg-2);
		border-radius: var(--radius-sm);
	}
	.trait-axis {
		font-size: 8px;
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.qualities,
	.outgoing {
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
	.has-block {
		display: flex;
		flex-direction: column;
		gap: var(--s2);
		padding-top: var(--s2);
		border-top: 1px dashed var(--border-1);
		margin-top: 2px;
	}
	.has-group {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}
	.has-group-h {
		display: flex;
		align-items: baseline;
		gap: 6px;
	}
	.has-pred {
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-3);
	}
	.has-count {
		font-size: 9px;
		color: var(--fg-4);
	}
	.has-items {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 3px;
		min-width: 0;
	}
	.has-item {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding: 5px 7px;
		width: 100%;
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		color: var(--fg-1);
		font-family: inherit;
		text-align: left;
		cursor: pointer;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
		min-width: 0;
	}
	.has-item:hover {
		border-color: var(--border-2);
		background: var(--bg-1);
	}
	.has-item:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 1px;
	}
	.item-head {
		display: flex;
		align-items: baseline;
		gap: 5px;
		min-width: 0;
	}
	.item-ico {
		font-size: 12px;
		line-height: 1;
		flex-shrink: 0;
	}
	.item-crop {
		width: 18px;
		height: 18px;
		flex-shrink: 0;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
	}
	.item-klass {
		font-size: 11px;
		color: var(--fg-0);
		font-weight: 500;
	}
	.item-id {
		font-size: 9px;
		color: var(--fg-4);
		margin-left: auto;
	}
	.item-traits {
		display: flex;
		flex-wrap: wrap;
		gap: 3px;
	}
	.item-trait {
		display: inline-flex;
		align-items: baseline;
		gap: 3px;
		font-size: 9px;
		padding: 0 4px;
		background: var(--tag-bg);
		color: var(--fg-2);
		border-radius: var(--radius-sm);
	}
	.item-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		font-size: 10px;
		min-width: 0;
	}
	.item-q {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
		min-width: 0;
	}
	.q-dim {
		font-size: 9px;
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.q-val {
		color: var(--fg-2);
	}
	.item-bbox {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		font-size: 10px;
	}
	.bbox-mini {
		width: 18px;
		height: 18px;
		flex-shrink: 0;
		color: var(--accent);
	}
	.bbox-full {
		font-size: 9px;
		padding: 1px 5px;
		background: var(--tag-bg);
		color: var(--fg-3);
		border-radius: var(--radius-sm);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.geometry {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding-top: var(--s2);
		border-top: 1px dashed var(--border-1);
		margin-top: 2px;
	}
	.entity-bbox {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		font-size: 10px;
	}
	.g-row {
		display: flex;
		align-items: baseline;
		gap: 6px;
		font-size: 10px;
		min-width: 0;
	}
	.g-key {
		font-size: 9px;
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		flex-shrink: 0;
	}
	.g-val {
		color: var(--fg-2);
		overflow-wrap: anywhere;
	}
	.occludes-ref {
		background: transparent;
		border: 0;
		padding: 0;
		color: var(--accent);
		font: inherit;
		cursor: pointer;
		text-decoration: underline dotted;
		text-underline-offset: 2px;
	}
	.occludes-ref:hover {
		text-decoration-style: solid;
	}
	.bbox-coord {
		display: inline-flex;
		align-items: baseline;
		gap: 2px;
		font-family: var(--font-mono);
		color: var(--fg-2);
		font-size: 10px;
	}
	.bc-k {
		font-size: 9px;
		color: var(--fg-4);
		text-transform: uppercase;
	}
	.outgoing {
		padding-top: var(--s2);
		border-top: 1px dashed var(--border-1);
		margin-top: 2px;
	}
	.outgoing li {
		display: flex;
		align-items: baseline;
		gap: 6px;
		font-size: var(--text-xs);
		min-width: 0;
	}
	.rel {
		color: var(--node-perdurant);
		font-size: 10px;
	}
	.arrow {
		color: var(--fg-4);
		font-size: 10px;
	}
	.ref {
		color: var(--fg-1);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
