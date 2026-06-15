<script lang="ts">
	import { tick } from 'svelte';
	import { scene } from '$lib/scene.svelte';
	import { copyText, download } from '$lib/utils';

	let env = $derived(scene.envelope);
	let copied = $state<string | null>(null);
	let copiedPrompt = $state(false);

	let open = $state(false);
	let buttonEl: HTMLButtonElement | undefined = $state();
	let menuEl: HTMLDivElement | undefined = $state();

	// /api/skills response (subset). Fetched lazily once on first prompt-copy
	// click and cached for the lifetime of the page; the manifest is keyed by
	// stable skill id so subsequent clicks for either notation are zero-cost.
	let promptCache: Record<string, string> | null = null;

	type Fmt = 'vson' | 'ttl' | 'json' | 'cypher' | 'mermaid' | 'graphml' | 'dot' | 'caption' | 'fol';

	// `tooltip` carries the long-form label so each menu row stays compact while
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

	function onKey(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			open = false;
			e.preventDefault();
			buttonEl?.focus();
		}
	}

	function onDocClick(e: MouseEvent) {
		if (!open) return;
		const t = e.target as Node;
		if (menuEl?.contains(t) || buttonEl?.contains(t)) return;
		open = false;
	}

	function toggle(e: MouseEvent) {
		e.stopPropagation();
		open = !open;
	}

	$effect(() => {
		if (open) {
			tick().then(() => menuEl?.querySelector<HTMLElement>('button')?.focus());
		}
	});
</script>

<svelte:window onkeydown={onKey} onclick={onDocClick} />

<div class="row">
	<div class="relative">
		<button
			bind:this={buttonEl}
			type="button"
			class="export-btn"
			onclick={toggle}
			disabled={!env}
			aria-haspopup="menu"
			aria-expanded={open}
			title="Export this scene graph"
		>
			<span class="dot" style:background={open ? 'var(--accent)' : 'var(--fg-4)'}></span>
			<span class="export-label">Export</span>
			<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
				<path d="M2 4 L5 7 L8 4" stroke="currentColor" stroke-width="1.2" fill="none" />
			</svg>
		</button>

		{#if open}
			<div bind:this={menuEl} class="menu" role="menu" aria-label="Export formats">
				{#each FORMATS as f (f.id)}
					<div class="item" role="none">
						<button
							type="button"
							role="menuitem"
							class="item-main"
							onclick={() => dl(f.id, f.ext, f.mime)}
							title="{f.tooltip} · download .{f.ext}"
						>
							<span class="item-label font-mono">{f.label}</span>
							<span class="item-hint">{f.tooltip}</span>
						</button>
						<button
							type="button"
							role="menuitem"
							class="item-icon"
							onclick={() => cp(f.id)}
							aria-label="Copy {f.label}"
							title="Copy {f.tooltip}"
						>
							{#if copied === f.id}
								<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
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
								<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
									<rect x="3" y="3" width="6" height="7" rx="1" stroke="currentColor" fill="none" />
									<path d="M5 3 V1.5 H10 V8 H8.5" stroke="currentColor" fill="none" />
								</svg>
							{/if}
						</button>
					</div>
				{/each}

				<div class="menu-divider" role="separator"></div>

				<button
					type="button"
					role="menuitem"
					class="item-main prompt-item"
					onclick={cpPrompt}
					title="Copy the system prompt that produces {scene.notation === 'x' ? 'VSON-X' : 'VSON-P'}"
					aria-label="Copy {promptLabel}"
				>
					<span class="item-label font-mono">{copiedPrompt ? 'copied' : 'system prompt'}</span>
					<span class="item-hint">{promptLabel}</span>
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	.row {
		display: flex;
		align-items: center;
		padding: var(--s2) var(--s5);
	}
	.relative {
		position: relative;
	}

	.export-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 10px;
		font-family: var(--font-mono);
		font-size: var(--text-2xs);
		color: var(--fg-3);
		background: transparent;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			border-color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.export-btn:hover:not(:disabled) {
		color: var(--fg-1);
		border-color: var(--border-2);
		background: var(--bg-2);
	}
	.export-btn:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.dot {
		width: 6px;
		height: 6px;
		border-radius: var(--radius-full);
	}
	.export-label {
		letter-spacing: 0.02em;
	}

	.menu {
		position: absolute;
		bottom: calc(100% + 6px);
		left: 0;
		width: 280px;
		max-width: calc(100vw - 32px);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
		box-shadow: var(--shadow-lg);
		z-index: 60;
		padding: 4px;
		display: flex;
		flex-direction: column;
		max-height: 70vh;
		overflow-y: auto;
	}

	.item {
		display: flex;
		align-items: stretch;
		border-radius: var(--radius-sm);
		overflow: hidden;
	}
	.item:hover {
		background: var(--bg-2);
	}

	.item-main {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
		align-items: flex-start;
		padding: 7px 10px;
		border: 0;
		background: transparent;
		text-align: left;
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.item-main:hover {
		background: var(--accent-bg);
	}
	.item-label {
		font-size: var(--text-xs);
		color: var(--fg-1);
	}
	.item-main:hover .item-label {
		color: var(--accent);
	}
	.item-hint {
		font-size: var(--text-2xs);
		color: var(--fg-4);
	}

	.item-icon {
		flex-shrink: 0;
		display: grid;
		place-items: center;
		width: 32px;
		border: 0;
		border-left: 1px solid var(--border-1);
		background: transparent;
		color: var(--fg-4);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.item-icon:hover {
		color: var(--fg-1);
		background: var(--bg-2);
	}

	.menu-divider {
		height: 1px;
		background: var(--border-1);
		margin: 4px 0;
	}

	.prompt-item {
		border-radius: var(--radius-sm);
	}
	.prompt-item .item-label {
		color: var(--accent);
	}
	.prompt-item:hover {
		background: color-mix(in srgb, var(--accent) 10%, transparent);
	}
</style>
