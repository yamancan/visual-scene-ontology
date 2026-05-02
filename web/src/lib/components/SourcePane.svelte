<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { copyText } from '$lib/utils';

	let copied = $state(false);
	let lines = $derived((scene.envelope?.vson_p ?? '').split('\n'));

	async function doCopy() {
		const ok = await copyText(scene.envelope?.vson_p ?? '');
		if (ok) {
			copied = true;
			setTimeout(() => (copied = false), 1200);
		}
	}

	// Single-pass tokenizer. Each match emits an HTML segment in order; the
	// gaps between matches are HTML-escaped and emitted verbatim. Avoids the
	// regex-stacking bug where a later .replace() matched substrings inside
	// an earlier .replace()'s injected <span> tags.
	const TOKEN_RE = new RegExp(
		[
			'(#[^\\n]*)', // 1: comment
			'("(?:[^"\\\\]|\\\\.)*")', // 2: string
			'(:[A-Za-z_][\\w-]*)', // 3: role
			'(\\/\\s+)([A-Z][\\w-]*)' // 4+5: "/ Concept"
		].join('|'),
		'g'
	);

	function escapeHtml(s: string): string {
		return s
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;');
	}

	function highlight(line: string): string {
		let out = '';
		let last = 0;
		for (const m of line.matchAll(TOKEN_RE)) {
			const idx = m.index ?? 0;
			if (idx > last) out += escapeHtml(line.slice(last, idx));
			if (m[1]) out += `<span class="src-cm">${escapeHtml(m[1])}</span>`;
			else if (m[2]) out += `<span class="src-st">${escapeHtml(m[2])}</span>`;
			else if (m[3]) out += `<span class="src-rl">${escapeHtml(m[3])}</span>`;
			else if (m[4] && m[5])
				out += `${escapeHtml(m[4])}<span class="src-cn">${escapeHtml(m[5])}</span>`;
			last = idx + m[0].length;
		}
		if (last < line.length) out += escapeHtml(line.slice(last));
		return out;
	}
</script>

<section class="flex h-full flex-col bg-(--bg-1)">
	<header class="flex h-7 items-center justify-between border-b border-(--border-1) px-3">
		<span class="font-mono text-[10px] uppercase tracking-wider text-(--fg-4)">vson-p</span>
		<button
			class="font-mono text-[10px] uppercase tracking-wider text-(--fg-4) transition-colors hover:text-(--accent)"
			onclick={doCopy}
		>
			{copied ? 'copied' : 'copy'}
		</button>
	</header>

	<div class="flex-1 overflow-auto">
		<pre class="font-mono text-[12px] leading-[1.55]">{#each lines as line, i (i)}<div
					class="flex items-start"
					><span
						class="select-none px-3 text-right text-(--fg-4) tabular"
						style:min-width="3rem">{i + 1}</span
					><code class="whitespace-pre pr-4">{@html highlight(line) || ' '}</code></div
				>{/each}</pre>
	</div>
</section>

<style>
	:global(.src-rl) {
		color: var(--node-quality);
	}
	:global(.src-cn) {
		color: var(--accent);
	}
	:global(.src-st) {
		color: var(--fg-3);
	}
	:global(.src-cm) {
		color: var(--fg-4);
		font-style: italic;
	}
</style>
