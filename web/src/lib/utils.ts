export function fileToBase64(file: File): Promise<{ b64: string; mime: string; preview: string }> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onerror = () => reject(reader.error ?? new Error('FileReader failed'));
		reader.onload = () => {
			const dataUrl = reader.result as string;
			const m = /^data:([^;]+);base64,(.+)$/.exec(dataUrl);
			if (!m) return reject(new Error('Unexpected dataURL shape'));
			resolve({ mime: m[1], b64: m[2], preview: dataUrl });
		};
		reader.readAsDataURL(file);
	});
}

// Uploads at or under this size go to the API byte-for-byte, so the server's
// sha256 → baked-envelope cache still matches the bundled demo images if a user
// drags one in from disk (the largest is ~176 KB). Larger files are re-encoded.
export const DOWNSCALE_ABOVE_BYTES = 1024 * 1024;
// Longest edge the vision models actually consume; pixels beyond this are paid
// for in tokens and thrown away upstream.
export const MAX_UPLOAD_EDGE_PX = 1568;
const DOWNSCALE_JPEG_QUALITY = 0.85;

/** Box-fit `w`×`h` so the longest edge is at most `maxEdge`. Never upscales. */
export function fitWithin(w: number, h: number, maxEdge: number): { w: number; h: number } {
	const longest = Math.max(w, h);
	if (longest <= 0 || longest <= maxEdge) return { w, h };
	const scale = maxEdge / longest;
	return { w: Math.max(1, Math.round(w * scale)), h: Math.max(1, Math.round(h * scale)) };
}

function loadImage(src: string): Promise<HTMLImageElement> {
	return new Promise((resolve, reject) => {
		const img = new Image();
		img.onload = () => resolve(img);
		img.onerror = () => reject(new Error('image decode failed'));
		img.src = src;
	});
}

/**
 * Decode a data URL to a canvas, resize it so the longest edge is at most
 * `maxEdge`, and re-encode as JPEG. Returns null when the browser refuses a 2D
 * context or hands back an unexpected data URL shape.
 */
export async function downscaleDataUrl(
	dataUrl: string,
	maxEdge = MAX_UPLOAD_EDGE_PX,
	quality = DOWNSCALE_JPEG_QUALITY
): Promise<{ b64: string; mime: string } | null> {
	const img = await loadImage(dataUrl);
	const w = img.naturalWidth || img.width;
	const h = img.naturalHeight || img.height;
	if (!w || !h) return null;
	const fit = fitWithin(w, h, maxEdge);
	const canvas = document.createElement('canvas');
	canvas.width = fit.w;
	canvas.height = fit.h;
	const ctx = canvas.getContext('2d');
	if (!ctx) return null;
	// JPEG carries no alpha: paint an opaque backdrop first so a transparent
	// PNG re-encodes to white rather than black.
	ctx.fillStyle = '#ffffff';
	ctx.fillRect(0, 0, fit.w, fit.h);
	ctx.drawImage(img, 0, 0, fit.w, fit.h);
	const out = canvas.toDataURL('image/jpeg', quality);
	const m = /^data:([^;]+);base64,(.+)$/.exec(out);
	if (!m) return null;
	return { mime: m[1], b64: m[2] };
}

export interface PreparedUpload {
	/** Base64 payload for /api/extract — re-encoded when the file was oversized. */
	b64: string;
	/** Mime that matches `b64` (image/jpeg after a downscale). */
	mime: string;
	/** Full-resolution data URL, kept for the local preview and bbox crops. */
	preview: string;
	downscaled: boolean;
}

/**
 * Read a picked file for upload. Small files keep their exact bytes; anything
 * over `thresholdBytes` is downscaled and re-encoded so a 4 MB phone photo
 * doesn't spend its size on tokens (or trip a proxy body limit). The preview
 * stays full-resolution either way. A downscale that fails or grows the payload
 * falls back to the original bytes rather than to an error.
 */
export async function prepareImageUpload(
	file: File,
	thresholdBytes = DOWNSCALE_ABOVE_BYTES
): Promise<PreparedUpload> {
	const { b64, mime, preview } = await fileToBase64(file);
	if (file.size <= thresholdBytes) return { b64, mime, preview, downscaled: false };
	try {
		const small = await downscaleDataUrl(preview);
		if (!small || small.b64.length >= b64.length) {
			return { b64, mime, preview, downscaled: false };
		}
		return { b64: small.b64, mime: small.mime, preview, downscaled: true };
	} catch {
		return { b64, mime, preview, downscaled: false };
	}
}

export function download(filename: string, content: string, mime = 'text/plain') {
	const blob = new Blob([content], { type: mime });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}

export async function copyText(text: string): Promise<boolean> {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch {
		return false;
	}
}

export function formatBytes(n: number): string {
	if (n < 1024) return `${n} B`;
	if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
	return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export function formatMs(n: number): string {
	if (n < 1000) return `${n} ms`;
	return `${(n / 1000).toFixed(1)} s`;
}

export function shortId(): string {
	const alpha = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
	let s = '';
	for (let i = 0; i < 12; i++) s += alpha[Math.floor(Math.random() * alpha.length)];
	return s;
}
