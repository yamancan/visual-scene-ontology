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

	// Minimal token highlight: roles, concepts, strings, comments.
	function highlight(line: string): string {
		return line
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/(#[^\n]*)/g, '<span class="src-cm">$1</span>')
			.replace(/(:[A-Za-z_][\w-]*)/g, '<span class="src-rl">$1</span>')
			.replace(/(\/\s+)([A-Z][\w-]*)/g, '$1<span class="src-cn">$2</span>')
			.replace(/("(?:[^"\\]|\\.)*")/g, '<span class="src-st">$1</span>');
	}
</script>

<section class="flex h-full flex-col bg-(--bg-1)">
	<header class="flex h-7 items-center justify-between border-b border-(--border-1) px-3">
		<span class="font-mono text-[10px] uppercase tracking-wider text-(--fg-4)"
			>vson-p</span
		>
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
