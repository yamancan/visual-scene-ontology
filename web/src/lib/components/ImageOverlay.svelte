<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { buildSceneView } from '$lib/render/sceneView';
	import { parseBbox, type BBox } from '$lib/bbox';

	// Curated class→glyph registry, mirrored from EntityCard so the overlay
	// label chip matches the card list. Open `vso:class` vocabulary means we
	// can't pre-icon everything — fall back to the generic glyph.
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

	let view = $derived.by(() => {
		const g = scene.envelope?.graph;
		return g ? buildSceneView(g) : null;
	});

	interface OverlayBox {
		id: string;
		klass?: string;
		bbox: BBox;
	}

	// Every entity (PhysicalObject/Aggregate/Substance — buildSceneView already
	// filters to those) that carries a parseable bbox. buildSceneView surfaces
	// the geometry block per card; the same string parses through bbox.parseBbox
	// so the overlay agrees with the canvas + EntityCard on coords and the
	// full-image heuristic.
	let boxes = $derived.by<OverlayBox[]>(() => {
		if (!view) return [];
		const out: OverlayBox[] = [];
		for (const e of view.entities) {
			const bbox = parseBbox(e.geometry.bbox);
			if (!bbox) continue;
			out.push({ id: e.id, klass: e.klass, bbox });
		}
		return out;
	});

	// Draw full-image boxes first (back) so the meaningful localized boxes sit
	// on top and stay clickable.
	let fullBoxes = $derived(boxes.filter((b) => b.bbox.isFullImage));
	let localBoxes = $derived(boxes.filter((b) => !b.bbox.isFullImage));

	let hasBoxes = $derived(boxes.length > 0);

	function labelFor(b: OverlayBox): string {
		return b.klass ?? `@${b.id}`;
	}

	function onClick(id: string) {
		// Toggle: clicking the already-selected box clears the selection.
		scene.setSelected(scene.selectedNodeId === id ? null : id);
	}
</script>

<div class="overlay-root">
	{#if !scene.imagePreview}
		<p class="placeholder font-mono">no image</p>
	{:else if !hasBoxes}
		<div class="frame">
			<img class="img" src={scene.imagePreview} alt="source scene" />
		</div>
		<p class="placeholder placeholder-over font-mono">no boxes</p>
	{:else}
		<div class="frame">
			<img class="img" src={scene.imagePreview} alt="source scene" />
			<div class="box-layer">
				{#each fullBoxes as b (b.id)}
					{@const sel = scene.selectedNodeId === b.id}
					{@const hov = scene.hoveredNodeId === b.id}
					<button
						type="button"
						class="box box-full"
						class:selected={sel}
						class:hovered={hov}
						style="left:{b.bbox.x * 100}%; top:{b.bbox.y * 100}%; width:{b.bbox.w * 100}%; height:{b
							.bbox.h * 100}%;"
						aria-label="{labelFor(b)} (full frame)"
						aria-pressed={sel}
						onclick={() => onClick(b.id)}
						onmouseenter={() => scene.setHovered(b.id)}
						onmouseleave={() => scene.setHovered(null)}
					>
						<span class="chip font-mono">
							<span class="chip-ico" aria-hidden="true">{iconFor(b.klass)}</span>
							{labelFor(b)}
						</span>
					</button>
				{/each}
				{#each localBoxes as b (b.id)}
					{@const sel = scene.selectedNodeId === b.id}
					{@const hov = scene.hoveredNodeId === b.id}
					<button
						type="button"
						class="box"
						class:selected={sel}
						class:hovered={hov}
						style="left:{b.bbox.x * 100}%; top:{b.bbox.y * 100}%; width:{b.bbox.w * 100}%; height:{b
							.bbox.h * 100}%;"
						aria-label="{labelFor(b)}"
						aria-pressed={sel}
						onclick={() => onClick(b.id)}
						onmouseenter={() => scene.setHovered(b.id)}
						onmouseleave={() => scene.setHovered(null)}
					>
						<span class="chip font-mono">
							<span class="chip-ico" aria-hidden="true">{iconFor(b.klass)}</span>
							{labelFor(b)}
						</span>
					</button>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.overlay-root {
		display: grid;
		place-items: center;
		height: 100%;
		overflow: hidden;
		padding: var(--s2);
		background: var(--bg-0);
	}
	.placeholder {
		color: var(--fg-4);
		font-size: var(--text-2xs);
		letter-spacing: 0.06em;
	}
	/* "no boxes" sits over the rendered image instead of replacing it. */
	.placeholder-over {
		position: absolute;
		bottom: var(--s3);
		left: 50%;
		transform: translateX(-50%);
		padding: 2px 8px;
		background: color-mix(in srgb, var(--bg-1) 86%, transparent);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-full);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
	}
	/* Wrapper hugs the rendered image so the box layer's % maps to pixels. */
	.frame {
		position: relative;
		line-height: 0;
		max-width: 100%;
		max-height: 100%;
	}
	.img {
		max-width: 100%;
		max-height: 100%;
		width: auto;
		height: auto;
		display: block;
		border-radius: var(--radius-sm);
	}
	.box-layer {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}
	.box {
		position: absolute;
		margin: 0;
		padding: 0;
		background: transparent;
		border: 1.5px solid color-mix(in srgb, var(--accent) 45%, transparent);
		border-radius: var(--radius-sm);
		cursor: pointer;
		pointer-events: auto;
		font-family: inherit;
		transition:
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out),
			box-shadow var(--duration-fast) var(--ease-out);
	}
	.box:hover {
		border-color: var(--accent);
	}
	.box:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.box.selected,
	.box.hovered {
		border-color: var(--accent);
		background: var(--accent-bg);
		box-shadow: 0 0 0 1px var(--accent);
	}
	/* Full-image entities: a faint dashed frame at the back. Keep it
	 * clickable but visually recessive so it never competes with localized
	 * boxes drawn on top. */
	.box-full {
		border-style: dashed;
		border-color: color-mix(in srgb, var(--accent) 22%, transparent);
	}
	.box-full.selected,
	.box-full.hovered {
		border-style: solid;
		background: color-mix(in srgb, var(--accent-bg) 60%, transparent);
	}
	/* Label chip pinned to the box top — hidden until hover/selection so a
	 * dense scene isn't a wall of text. */
	.chip {
		position: absolute;
		bottom: 100%;
		left: -1.5px;
		margin-bottom: 2px;
		display: inline-flex;
		align-items: center;
		gap: 4px;
		max-width: 220px;
		padding: 1px 6px;
		background: var(--accent);
		color: var(--bg-0);
		font-size: 10px;
		line-height: 1.4;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		border-radius: var(--radius-sm);
		opacity: 0;
		transform: translateY(2px);
		transition:
			opacity var(--duration-fast) var(--ease-out),
			transform var(--duration-fast) var(--ease-out);
		pointer-events: none;
	}
	.box:hover .chip,
	.box.selected .chip,
	.box.hovered .chip {
		opacity: 1;
		transform: translateY(0);
	}
	.chip-ico {
		font-size: 11px;
		line-height: 1;
	}
</style>
