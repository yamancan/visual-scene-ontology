<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { copyText } from '$lib/utils';

	let copied = $state(false);
	let lines = $derived((scene.envelope?.vson_t ?? '').split('\n'));

	async function doCopy() {
		const ok = await copyText(scene.envelope?.vson_t ?? '');
		if (ok) {
			copied = true;
			setTimeout(() => (copied = false), 1200);
		}
	}

	const TOKEN_RE = new RegExp(
		[
			'(#[^\\n]*)', // comment
			'("(?:[^"\\\\]|\\\\.)*")', // string
			'(@(?:prefix|base)\\b)', // directive
			'([a-zA-Z][\\w-]*:[A-Za-z_][\\w-]*)', // qname
			'(\\b(?:a)\\b)', // RDF "a"
			'(<<|>>)', // RDF-star markers
			'(<[^>\\s]*>)' // IRI
		].join('|'),
		'g'
	);

	function escapeHtml(s: string): string {
		return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
	}

	function highlight(line: string): string {
		let out = '';
		let last = 0;
		for (const m of line.matchAll(TOKEN_RE)) {
			const idx = m.index ?? 0;
			if (idx > last) out += escapeHtml(line.slice(last, idx));
			if (m[1]) out += `<span class="t-cm">${escapeHtml(m[1])}</span>`;
			else if (m[2]) out += `<span class="t-st">${escapeHtml(m[2])}</span>`;
			else if (m[3]) out += `<span class="t-dr">${escapeHtml(m[3])}</span>`;
			else if (m[4]) out += `<span class="t-qn">${escapeHtml(m[4])}</span>`;
			else if (m[5]) out += `<span class="t-kw">${escapeHtml(m[5])}</span>`;
			else if (m[6]) out += `<span class="t-rs">${escapeHtml(m[6])}</span>`;
			else if (m[7]) out += `<span class="t-ir">${escapeHtml(m[7])}</span>`;
			last = idx + m[0].length;
		}
		if (last < line.length) out += escapeHtml(line.slice(last));
		return out;
	}
</script>

<section class="wrap">
	<header class="head">
		<span class="head-label font-mono">{lines.length} lines</span>
		<button class="copy" onclick={doCopy}>
			{copied ? 'copied' : 'copy turtle'}
		</button>
	</header>
	<div class="body">
		<pre class="code">{#each lines as line, i (i)}<div class="ln"><span class="lno">{i + 1}</span
					><code class="ltxt">{@html highlight(line) || ' '}</code></div>{/each}</pre>
	</div>
</section>

<style>
	.wrap {
		display: flex;
		flex-direction: column;
		height: 100%;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: var(--s2) var(--s3);
		border-bottom: 1px solid var(--border-1);
		flex-shrink: 0;
	}
	.head-label {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
	.copy {
		font-family: var(--font-mono);
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--fg-4);
		background: transparent;
		border: 0;
		cursor: pointer;
		padding: 2px 6px;
		border-radius: var(--radius-sm);
		transition: color var(--duration-fast) var(--ease-out);
	}
	.copy:hover {
		color: var(--accent);
	}
	.body {
		flex: 1;
		overflow: auto;
		min-height: 0;
	}
	.code {
		margin: 0;
		padding: var(--s2) 0;
		font-family: var(--font-mono);
		font-size: 11.5px;
		line-height: 1.55;
	}
	.ln {
		display: flex;
		align-items: flex-start;
	}
	.lno {
		flex-shrink: 0;
		min-width: 2.6rem;
		padding: 0 var(--s3);
		text-align: right;
		color: var(--fg-4);
		user-select: none;
		font-variant-numeric: tabular-nums;
	}
	.ltxt {
		white-space: pre;
		padding-right: var(--s4);
		color: var(--fg-1);
	}
	:global(.t-cm) {
		color: var(--fg-4);
		font-style: italic;
	}
	:global(.t-st) {
		color: var(--fg-3);
	}
	:global(.t-dr) {
		color: var(--node-quality);
		font-weight: 600;
	}
	:global(.t-qn) {
		color: var(--accent);
	}
	:global(.t-kw) {
		color: var(--node-perdurant);
	}
	:global(.t-rs) {
		color: var(--node-spatialfact);
	}
	:global(.t-ir) {
		color: var(--node-frame);
	}
</style>
