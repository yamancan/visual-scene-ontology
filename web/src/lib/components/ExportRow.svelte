<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { copyText, download } from '$lib/utils';

	let env = $derived(scene.envelope);
	let copied = $state<string | null>(null);

	type Fmt = 'vson' | 'ttl' | 'json' | 'cypher' | 'mermaid' | 'graphml' | 'dot';

	const FORMATS: { id: Fmt; label: string; ext: string; mime: string }[] = [
		{ id: 'vson', label: 'penman', ext: 'vson', mime: 'text/plain' },
		{ id: 'ttl', label: 'turtle', ext: 'ttl', mime: 'text/turtle' },
		{ id: 'json', label: 'json', ext: 'json', mime: 'application/json' },
		{ id: 'cypher', label: 'cypher', ext: 'cypher', mime: 'text/x-cypher' },
		{ id: 'mermaid', label: 'mermaid', ext: 'mmd', mime: 'text/x-mermaid' },
		{ id: 'graphml', label: 'graphml', ext: 'graphml', mime: 'application/graphml+xml' },
		{ id: 'dot', label: 'dot', ext: 'gv', mime: 'text/vnd.graphviz' }
	];

	async function getContent(fmt: Fmt): Promise<string> {
		if (!env) return '';
		if (fmt === 'vson') return env.vson_p;
		if (fmt === 'ttl') return env.vson_t;
		if (fmt === 'json') return JSON.stringify(env, null, 2);
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
</script>

<div class="row">
	<span class="label font-mono">export</span>
	<div class="chips">
		{#each FORMATS as f (f.id)}
			<div class="chip" role="group">
				<button class="chip-main" onclick={() => dl(f.id, f.ext, f.mime)} title="Download .{f.ext}">
					{f.label}
				</button>
				<button
					class="chip-icon"
					onclick={() => cp(f.id)}
					aria-label="Copy {f.label}"
					title="Copy"
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
	</div>
</div>

<style>
	.row {
		display: flex;
		align-items: center;
		gap: var(--s3);
		padding: var(--s2) var(--s3);
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
