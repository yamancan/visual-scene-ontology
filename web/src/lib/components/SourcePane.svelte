<script lang="ts">
	import { tick } from 'svelte';
	import { scene } from '$lib/scene.svelte';
	import { copyText } from '$lib/utils';

	let copied = $state(false);
	let containerEl: HTMLDivElement | undefined = $state();

	let body = $derived(
		scene.notation === 'x'
			? (scene.envelope?.vson_x ?? '')
			: (scene.envelope?.vson_p ?? '')
	);
	let lines = $derived(body.split('\n'));
	let label = $derived(scene.notation === 'x' ? 'vson-x' : 'penman');
	let copyLabel = $derived(scene.notation === 'x' ? 'copy vson-x' : 'copy penman');

	async function doCopy() {
		const ok = await copyText(body);
		if (ok) {
			copied = true;
			setTimeout(() => (copied = false), 1200);
		}
	}

	// VSON-P tokenizer (legacy). Captures groups: comment, string, role,
	// "/ Concept", and a bare lowercase id (for var declarations + reentrancy).
	const TOKEN_RE_P = new RegExp(
		[
			'(#[^\\n]*)', // 1: comment
			'("(?:[^"\\\\]|\\\\.)*")', // 2: string
			'(:[A-Za-z_][\\w-]*)', // 3: role
			'(\\/\\s+)([A-Z][\\w-]*)', // 4+5: / Concept
			'\\b([a-z][\\w-]*)\\b' // 6: var / bareword
		].join('|'),
		'g'
	);

	// VSON-X tokenizer. Longest-first sigil match (>> before >). Line-anchored
	// lead sigils detect indent + sigil at column 0; the inline structural
	// sigils (>>, >, !, &) are captured separately so we can color them.
	// Concept = PascalCase after `/`; handle = `@id` or bareword id.
	const TOKEN_RE_X = new RegExp(
		[
			'(#[^\\n]*)', // 1: comment
			'("(?:[^"\\\\]|\\\\.)*")', // 2: string
			'(\\*)([a-zA-Z_][\\w-]*)', // 3+4: *key
			'(>>|>|!|&|~|\\^|\\/|@)', // 5: sigil
			'\\b([A-Z][\\w-]*)\\b', // 6: Concept (PascalCase)
			'\\b([a-z_][\\w-]*)\\b' // 7: bareword/var
		].join('|'),
		'g'
	);

	function escapeHtml(s: string): string {
		return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
	}

	function highlightP(line: string, sel: string | null): string {
		let out = '';
		let last = 0;
		for (const m of line.matchAll(TOKEN_RE_P)) {
			const idx = m.index ?? 0;
			if (idx > last) out += escapeHtml(line.slice(last, idx));
			if (m[1]) out += `<span class="src-cm">${escapeHtml(m[1])}</span>`;
			else if (m[2]) out += `<span class="src-st">${escapeHtml(m[2])}</span>`;
			else if (m[3]) out += `<span class="src-rl">${escapeHtml(m[3])}</span>`;
			else if (m[4] && m[5])
				out += `${escapeHtml(m[4])}<span class="src-cn">${escapeHtml(m[5])}</span>`;
			else if (m[6]) {
				const v = m[6];
				const cls = sel && v === sel ? 'src-vr src-vr-sel' : 'src-vr';
				out += `<span class="${cls}">${escapeHtml(v)}</span>`;
			}
			last = idx + m[0].length;
		}
		if (last < line.length) out += escapeHtml(line.slice(last));
		return out;
	}

	function highlightX(line: string, sel: string | null): string {
		let out = '';
		let last = 0;
		for (const m of line.matchAll(TOKEN_RE_X)) {
			const idx = m.index ?? 0;
			if (idx > last) out += escapeHtml(line.slice(last, idx));
			if (m[1]) out += `<span class="src-cm">${escapeHtml(m[1])}</span>`;
			else if (m[2]) out += `<span class="src-st">${escapeHtml(m[2])}</span>`;
			else if (m[3] && m[4]) {
				out += `<span class="src-x-key">${escapeHtml(m[3])}</span>`;
				out += `<span class="src-x-key-name">${escapeHtml(m[4])}</span>`;
			} else if (m[5]) out += `<span class="src-x-sigil">${escapeHtml(m[5])}</span>`;
			else if (m[6]) out += `<span class="src-cn">${escapeHtml(m[6])}</span>`;
			else if (m[7]) {
				const v = m[7];
				const cls = sel && v === sel ? 'src-vr src-vr-sel' : 'src-vr';
				out += `<span class="${cls}">${escapeHtml(v)}</span>`;
			}
			last = idx + m[0].length;
		}
		if (last < line.length) out += escapeHtml(line.slice(last));
		return out;
	}

	function highlight(line: string, sel: string | null): string {
		return scene.notation === 'x' ? highlightX(line, sel) : highlightP(line, sel);
	}

	// Highlight whole line if it declares the selected var.
	// Penman: `(<sel> /` anywhere on the line.
	// VSON-X: `@<sel> /Concept` or bare `<sel> /Concept` at item lead.
	function declaresSelected(line: string, sel: string | null): boolean {
		if (!sel) return false;
		const escaped = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
		if (scene.notation === 'x') {
			return new RegExp(`(?:^|\\s)@?${escaped}\\s+\\/`).test(line);
		}
		return new RegExp(`\\(\\s*${escaped}\\s*\\/`).test(line);
	}

	// On selection change, scroll the declaring line into view.
	$effect(() => {
		const sel = scene.selectedNodeId;
		if (!sel || !containerEl) return;
		tick().then(() => {
			const target = containerEl?.querySelector<HTMLElement>('.ln.declares');
			if (target) target.scrollIntoView({ block: 'center', behavior: 'smooth' });
		});
	});
</script>

<section class="wrap">
	<header class="head">
		<span class="head-label font-mono">{label} · {lines.length} lines</span>
		{#if scene.selectedNodeId}
			<button
				class="clear-sel"
				onclick={() => scene.setSelected(null)}
				title="Clear selection"
			>
				<span class="font-mono">{scene.selectedNodeId}</span>
				<svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true">
					<path d="M2 2 L8 8 M8 2 L2 8" stroke="currentColor" stroke-width="1.4" />
				</svg>
			</button>
		{/if}
		<button class="copy" onclick={doCopy}>
			{copied ? 'copied' : copyLabel}
		</button>
	</header>
	<div bind:this={containerEl} class="body">
		<pre class="code">{#each lines as line, i (i)}{@const decl = declaresSelected(line, scene.selectedNodeId)}<div
					class="ln"
					class:declares={decl}
					><span class="lno">{i + 1}</span><code class="ltxt"
						>{@html highlight(line, scene.selectedNodeId) || ' '}</code
					></div
				>{/each}</pre>
	</div>
</section>

<style>
	.wrap {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}
	.head {
		display: flex;
		align-items: center;
		gap: var(--s2);
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
	.clear-sel {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		margin-left: auto;
		padding: 2px 6px;
		font-size: 10px;
		color: var(--accent);
		background: var(--accent-bg, color-mix(in srgb, var(--accent) 12%, transparent));
		border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border-1));
		border-radius: var(--radius-full);
		cursor: pointer;
	}
	.clear-sel:hover {
		background: color-mix(in srgb, var(--accent) 22%, transparent);
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
	.copy:not(:disabled):hover {
		color: var(--accent);
	}
	.head .copy {
		margin-left: auto;
	}
	.head:has(.clear-sel) .copy {
		margin-left: 0;
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
		font-size: 12px;
		line-height: 1.6;
	}
	.ln {
		display: flex;
		align-items: flex-start;
		padding: 0 0;
		transition: background var(--duration-fast) var(--ease-out);
	}
	.ln.declares {
		background: color-mix(in srgb, var(--accent) 10%, transparent);
		box-shadow: inset 2px 0 0 var(--accent);
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
	:global(.src-rl) {
		color: var(--node-quality);
	}
	:global(.src-cn) {
		color: var(--accent);
		font-weight: 500;
	}
	:global(.src-st) {
		color: var(--fg-3);
	}
	:global(.src-cm) {
		color: var(--fg-4);
		font-style: italic;
	}
	:global(.src-vr) {
		color: var(--fg-2);
	}
	:global(.src-vr-sel) {
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 18%, transparent);
		border-radius: 2px;
		padding: 0 2px;
	}
	:global(.src-x-sigil) {
		color: var(--node-quality);
		font-weight: 600;
	}
	:global(.src-x-key) {
		color: var(--node-quality);
	}
	:global(.src-x-key-name) {
		color: var(--fg-2);
	}
</style>
