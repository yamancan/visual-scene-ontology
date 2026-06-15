<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { copyText, download } from '$lib/utils';

	let env = $derived(scene.envelope);
	let copied = $state<string | null>(null);
	let copiedPrompt = $state(false);

	// /api/skills response (subset). Fetched lazily once on first prompt-copy
	// click and cached for the lifetime of the page; the manifest is keyed by
	// stable skill id so subsequent clicks for either notation are zero-cost.
	let promptCache: Record<string, string> | null = null;

	type Fmt = 'vson' | 'ttl' | 'json' | 'cypher' | 'mermaid' | 'graphml' | 'dot' | 'caption' | 'fol';

	// `tooltip` carries the long-form label so the chip stays compact while
	// hover surfaces the canonical VSON-X / VSON-P / VSON-T family name.
	const FORMATS: { id: Fmt; label: string; ext: string; mime: string; tooltip: string }[] = [
		{ id: 'vson', label: 'penman', ext: 'vson', mime: 'text/plain', tooltip: 'VSON-P (Penman)' },
		{ id: 'ttl', label: 'turtle', ext: 'ttl', mime: 'text/turtle', tooltip: 'VSON-T (Turtle 1.2)' },
		{
			id: 'json',
			label: 'json',
			ext: 'json',
			mime: 'application/json',
			tooltip: 'VSON envelope (JSON)'
		},
		{
			id: 'caption',
			label: 'caption',
			ext: 'txt',
			mime: 'text/plain',
			tooltip: 'English caption (deterministic, image-gen friendly)'
		},
		{
			id: 'fol',
			label: 'fol',
			ext: 'fol',
			mime: 'text/plain',
			tooltip: 'First-order logic (Prolog-style facts)'
		},
		{
			id: 'cypher',
			label: 'cypher',
			ext: 'cypher',
			mime: 'text/x-cypher',
			tooltip: 'Cypher CREATE statements'
		},
		{
			id: 'mermaid',
			label: 'mermaid',
			ext: 'mmd',
			mime: 'text/x-mermaid',
			tooltip: 'Mermaid graph diagram'
		},
		{
			id: 'graphml',
			label: 'graphml',
			ext: 'graphml',
			mime: 'application/graphml+xml',
			tooltip: 'GraphML (yEd, Gephi)'
		},
		{ id: 'dot', label: 'dot', ext: 'gv', mime: 'text/vnd.graphviz', tooltip: 'Graphviz DOT' }
	];

	async function getContent(fmt: Fmt): Promise<string> {
		if (!env) return '';
		if (fmt === 'vson') return env.vson_p;
		if (fmt === 'ttl') return env.vson_t;
		if (fmt === 'json') return JSON.stringify(env, null, 2);
		if (fmt === 'caption' || fmt === 'fol') {
			const r = await fetch('/api/export', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ vson_p: env.vson_p, format: fmt })
			});
			return await r.text();
		}
		const r = await fetch('/api/export', {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify({ graph: env.graph, format: fmt })
		});
		return await r.text();
	}

	async function dl(fmt: Fmt, ext: string, mime: string) {
		if (!env) return;
		const content = await getContent(fmt);
		download(`${env.scene_id}.${ext}`, content, mime);
	}

	async function cp(fmt: Fmt) {
		const content = await getContent(fmt);
		const ok = await copyText(content);
		if (ok) {
			copied = fmt;
			setTimeout(() => (copied = null), 1100);
		}
	}

	async function cpPrompt() {
		if (!promptCache) {
			try {
				const r = await fetch('/api/skills');
				if (!r.ok) return;
				const skills = (await r.json()) as Array<{ id: string; body: string }>;
				promptCache = Object.fromEntries(skills.map((s) => [s.id, s.body]));
			} catch {
				return;
			}
		}
		const id = scene.notation === 'x' ? 'vson-x' : 'penman';
		const body = promptCache[id];
		if (!body) return;
		const ok = await copyText(body);
		if (ok) {
			copiedPrompt = true;
			setTimeout(() => (copiedPrompt = false), 1100);
		}
	}

	let promptLabel = $derived(
		scene.notation === 'x' ? 'VSON-X system prompt' : 'VSON-P system prompt'
	);
</script>

<div class="row">
	<span class="label font-mono">export</span>
	<div class="chips">
		{#each FORMATS as f (f.id)}
			<div class="chip" role="group">
				<button
					class="chip-main"
					onclick={() => dl(f.id, f.ext, f.mime)}
					title="{f.tooltip} · download .{f.ext}"
				>
					{f.label}
				</button>
				<button
					class="chip-icon"
					onclick={() => cp(f.id)}
					aria-label="Copy {f.label}"
					title="Copy {f.tooltip}"
				>
					{#if copied === f.id}
						<svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
							<path
								d="M2 6.5 L4.5 9 L10 3"
								stroke="var(--success)"
								stroke-width="1.6"
								fill="none"
								stroke-linecap="round"
								stroke-linejoin="round"
							/>
						</svg>
					{:else}
						<svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
							<rect x="3" y="3" width="6" height="7" rx="1" stroke="currentColor" fill="none" />
							<path d="M5 3 V1.5 H10 V8 H8.5" stroke="currentColor" fill="none" />
						</svg>
					{/if}
				</button>
			</div>
		{/each}
		<span class="divider" aria-hidden="true"></span>
		<div class="chip prompt-chip" role="group">
			<button
				class="chip-main"
				onclick={cpPrompt}
				title="Copy the system prompt that produces {scene.notation === 'x' ? 'VSON-X' : 'VSON-P'}"
				aria-label="Copy {promptLabel}"
			>
				{copiedPrompt ? 'copied' : 'system prompt'}
			</button>
		</div>
	</div>
</div>

<style>
	.row {
		display: flex;
		align-items: center;
		gap: var(--s3);
		padding: var(--s2) var(--s5);
		overflow-x: auto;
	}
	.label {
		font-size: var(--text-2xs);
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		flex-shrink: 0;
	}
	.chips {
		display: flex;
		gap: var(--s1);
		flex-wrap: wrap;
		align-items: center;
	}
	.divider {
		width: 1px;
		height: 16px;
		background: var(--border-1);
		margin: 0 4px;
		flex-shrink: 0;
	}
	.prompt-chip {
		border-color: color-mix(in srgb, var(--accent) 30%, var(--border-1));
		background: color-mix(in srgb, var(--accent) 6%, transparent);
	}
	.prompt-chip .chip-main {
		color: var(--accent);
	}
	.prompt-chip:hover {
		border-color: var(--accent);
	}
	.prompt-chip:hover .chip-main {
		background: color-mix(in srgb, var(--accent) 14%, transparent);
	}
	.chip {
		display: inline-flex;
		align-items: stretch;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		overflow: hidden;
		transition: border-color var(--duration-fast) var(--ease-out);
	}
	.chip:hover {
		border-color: var(--border-2);
	}
	.chip-main,
	.chip-icon {
		background: transparent;
		border: 0;
		padding: 4px 8px;
		font-family: var(--font-mono);
		font-size: var(--text-2xs);
		color: var(--fg-3);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.chip-main:hover {
		color: var(--accent);
		background: var(--accent-bg);
	}
	.chip-icon {
		padding: 4px 6px;
		border-left: 1px solid var(--border-1);
		display: grid;
		place-items: center;
		color: var(--fg-4);
	}
	.chip-icon:hover {
		color: var(--fg-1);
		background: var(--bg-2);
	}
</style>
