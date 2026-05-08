<script lang="ts">
	import type { EntityCardModel, HasRef } from '$lib/render/sceneView';

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

	interface BBox {
		x: number;
		y: number;
		w: number;
		h: number;
		isFullImage: boolean;
	}
	function parseBbox(s?: string): BBox | null {
		if (!s) return null;
		const parts = s.split(',').map((v) => Number(v.trim()));
		if (parts.length !== 4 || parts.some((p) => Number.isNaN(p))) return null;
		const [x, y, w, h] = parts;
		// "Full image" heuristic (spec §14: bbox is opaque so this is local
		// convention): an entity that fills ≥95% of both dimensions is signaling
		// background/scene-coverage intent, not a meaningful localization. Show
		// a badge instead of four 0/1 numbers.
		const isFullImage = w >= 0.95 && h >= 0.95 && x <= 0.05 && y <= 0.05;
		return { x, y, w, h, isFullImage };
	}
	function fmt(n: number): string {
		return n.toFixed(2);
	}
</script>

<div
	class="card"
	class:selected
	role="button"
	tabindex="0"
	aria-pressed={selected}
	onclick={activate}
	onkeydown={onCardKey}
>
	<header class="head">
		<span class="ico" aria-hidden="true">{icon}</span>
		<span class="id font-mono">@{entity.id}</span>
		{#if entity.klass}<span class="klass">{entity.klass}</span>{/if}
	</header>

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
							<rect x="0.5" y="0.5" width="23" height="23" fill="none" stroke="currentColor" stroke-opacity="0.18" stroke-width="1" />
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
							onclick={(ev) => focusItem(ev, { label: 'occludes', to: o, traits: { affordance: [] }, qualities: [], geometry: { occludes: [] } })}
						>@{o}</button>{i < entity.geometry.occludes.length - 1 ? ', ' : ''}{/each}
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
										<span class="item-ico" aria-hidden="true">{iconFor(h.klass)}</span>
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
													<rect x="0.5" y="0.5" width="23" height="23" fill="none" stroke="currentColor" stroke-opacity="0.18" stroke-width="1" />
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
	.head {
		display: flex;
		align-items: baseline;
		gap: var(--s2);
		min-width: 0;
	}
	.ico {
		font-size: 14px;
		line-height: 1;
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
