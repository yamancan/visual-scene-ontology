export function fileToBase64(
	file: File
): Promise<{ b64: string; mime: string; preview: string }> {
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
