// Geometry util for vso:bbox2d normalized 0–1 image coordinates.
//
// A bbox is the four-tuple "x,y,w,h" the extractor emits per entity. Parsing +
// the "full image" heuristic mirror EntityCard.parseBbox exactly so the studio
// and the graph canvas agree on what counts as a meaningful localization vs. a
// background/scene-coverage signal. cropStyle turns a bbox into a CSS-sprite
// crop of the source image (a data: URL) for sub-rect previews.

export interface BBox {
	x: number;
	y: number;
	w: number;
	h: number;
	isFullImage: boolean;
}

/**
 * Parse a normalized bbox tuple "x,y,w,h" (each 0–1). Tolerates a bare number
 * or null/undefined input (the graph stores bbox2d as either a string or a
 * number depending on the notation round-trip). Returns null unless the input
 * resolves to exactly four finite numbers.
 *
 * isFullImage matches the existing EntityCard heuristic (spec §14: bbox is
 * opaque, so this is a local convention): an entity filling ≥95% of both
 * dimensions is signaling scene-coverage intent, not a meaningful box.
 */
export function parseBbox(s?: string | number | null): BBox | null {
	if (s == null) return null;
	const parts = String(s)
		.split(',')
		.map((v) => Number(v.trim()));
	if (parts.length !== 4 || parts.some((p) => !Number.isFinite(p))) return null;
	const [x, y, w, h] = parts;
	const isFullImage = w >= 0.95 && h >= 0.95 && x <= 0.05 && y <= 0.05;
	return { x, y, w, h, isFullImage };
}

/**
 * Inline CSS style string that makes a fixed-size element show ONLY the bbox
 * sub-rect of imageSrc via a CSS-sprite crop. For a full-image bbox we fall
 * back to a centered cover. imageSrc is expected to be a data: URL (no quotes
 * inside the base64 payload) so wrapping it in double-quotes is safe.
 */
export function cropStyle(bbox: BBox, imageSrc: string): string {
	const base = `background-image:url("${imageSrc}"); background-repeat:no-repeat; background-color:var(--bg-2);`;
	if (bbox.isFullImage) {
		return `${base} background-size:cover; background-position:center;`;
	}
	const w = Math.max(bbox.w, 0.0001);
	const h = Math.max(bbox.h, 0.0001);
	const bgSizeX = (1 / w) * 100;
	const bgSizeY = (1 / h) * 100;
	const posX = w >= 1 ? 0 : (bbox.x / (1 - w)) * 100;
	const posY = h >= 1 ? 0 : (bbox.y / (1 - h)) * 100;
	// Trim floating-point dust (e.g. 50.000000000000014 → 50) while preserving
	// genuine fractional percentages like 33.3333.
	const pct = (n: number) => `${parseFloat(n.toFixed(4))}`;
	return `${base} background-size:${pct(bgSizeX)}% ${pct(bgSizeY)}%; background-position:${pct(posX)}% ${pct(posY)}%;`;
}

/** Compact human-readable bbox label, e.g. "x=0.30 y=0.10 w=0.40 h=0.80". */
export function fmtBbox(b: BBox): string {
	return `x=${b.x.toFixed(2)} y=${b.y.toFixed(2)} w=${b.w.toFixed(2)} h=${b.h.toFixed(2)}`;
}
