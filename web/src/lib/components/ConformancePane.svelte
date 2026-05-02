<script lang="ts">
	import { scene } from '$lib/scene.svelte';

	let env = $derived(scene.envelope);
	let conforms = $derived(env?.conformance.conforms ?? false);
	let violations = $derived(env?.conformance.violations ?? []);
	let extraction = $derived(env?.extraction);

	function shortShape(s: string): string {
		const i = s.indexOf(':');
		return i >= 0 ? s.slice(i + 1) : s;
	}

	function jumpToNode(id: string | undefined) {
		if (!id) return;
		scene.setSelected(id);
		scene.setRailTab('penman');
	}
</script>

<section class="wrap">
	{#if env}
		<div class="hero" class:pass={conforms} class:fail={!conforms}>
			<div class="hero-stat">
				<span class="hero-num font-mono">{env.graph?.nodes.length ?? 0}</span>
				<span class="hero-label font-mono">nodes</span>
			</div>
			<div class="hero-divider"></div>
			<div class="hero-stat">
				<span class="hero-num font-mono">{env.graph?.edges.length ?? 0}</span>
				<span class="hero-label font-mono">edges</span>
			</div>
			<div class="hero-divider"></div>
			<div class="hero-stat conf">
				<span class="hero-num font-mono">{conforms ? 'PASS' : violations.length}</span>
				<span class="hero-label font-mono">{conforms ? 'shacl' : 'violations'}</span>
			</div>
		</div>

		{#if !conforms && violations.length > 0}
			<div class="viol-list">
				<div class="section-label font-mono">violations</div>
				{#each violations as v, i (i)}
					<div class="viol">
						<div class="viol-head">
							<span class="viol-shape font-mono">{shortShape(v.shape)}</span>
							{#if v.focus_node}
								<button
									class="viol-focus font-mono"
									onclick={() => jumpToNode(v.focus_node)}
									title="Jump to this node in the graph + Penman"
								>
									{v.focus_node}
								</button>
							{/if}
						</div>
						<div class="viol-msg">{v.message}</div>
					</div>
				{/each}
			</div>
		{:else if conforms}
			<div class="pass-msg">
				<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
					<path
						d="M3 8.5 L7 12 L13 4"
						stroke="var(--success)"
						stroke-width="2"
						fill="none"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
				</svg>
				<span>Document satisfies every published SHACL shape.</span>
			</div>
		{/if}

		{#if extraction}
			<dl class="meta">
				<div class="meta-row">
					<dt>model</dt>
					<dd title={extraction.model}>{extraction.model}</dd>
				</div>
				<div class="meta-row">
					<dt>prompt</dt>
					<dd>{extraction.prompt_version ?? '—'}</dd>
				</div>
				<div class="meta-row">
					<dt>latency</dt>
					<dd>{((extraction.latency_ms ?? 0) / 1000).toFixed(2)}s</dd>
				</div>
				<div class="meta-row">
					<dt>repairs</dt>
					<dd>
						{extraction.shacl_retries ?? 0}
						{#if (extraction.shacl_retries ?? 0) > 0}<span class="warn"> · used</span>{:else}<span class="ok"> · clean</span>{/if}
					</dd>
				</div>
				<div class="meta-row">
					<dt>tokens in</dt>
					<dd>{(extraction.input_tokens ?? 0).toLocaleString()}</dd>
				</div>
				<div class="meta-row">
					<dt>tokens out</dt>
					<dd>{(extraction.output_tokens ?? 0).toLocaleString()}</dd>
				</div>
			</dl>
		{/if}

		{#if env.source?.sha256}
			<div class="src-line font-mono" title={env.source.sha256}>
				<span class="src-key">sha256</span>
				<span class="src-val">{env.source.sha256.slice(0, 12)}…{env.source.sha256.slice(-6)}</span>
			</div>
		{/if}
	{/if}
</section>

<style>
	.wrap {
		display: flex;
		flex-direction: column;
		gap: var(--s4);
		height: 100%;
		padding: var(--s3);
		overflow-y: auto;
	}
	.hero {
		display: flex;
		align-items: stretch;
		justify-content: space-around;
		padding: var(--s3) var(--s2);
		border-radius: var(--radius);
		border: 1px solid var(--border-1);
		background: var(--bg-2);
		flex-shrink: 0;
	}
	.hero.pass {
		border-color: color-mix(in srgb, var(--success) 30%, var(--border-1));
		background: color-mix(in srgb, var(--success) 6%, var(--bg-2));
	}
	.hero.fail {
		border-color: color-mix(in srgb, var(--danger) 30%, var(--border-1));
		background: color-mix(in srgb, var(--danger) 6%, var(--bg-2));
	}
	.hero-stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		flex: 1;
	}
	.hero-num {
		font-size: var(--text-xl);
		font-weight: 500;
		line-height: 1;
		color: var(--fg-0);
		font-variant-numeric: tabular-nums;
	}
	.hero.pass .hero-stat.conf .hero-num {
		color: var(--success);
		font-size: var(--text-base);
	}
	.hero.fail .hero-stat.conf .hero-num {
		color: var(--danger);
	}
	.hero-label {
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
	.hero-divider {
		width: 1px;
		background: var(--border-1);
		margin: 4px 0;
	}
	.section-label {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
		margin-bottom: var(--s2);
	}
	.viol-list {
		display: flex;
		flex-direction: column;
		gap: var(--s2);
	}
	.viol {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: var(--s2) var(--s3);
		border-left: 2px solid var(--danger);
		background: color-mix(in srgb, var(--danger) 5%, var(--bg-2));
		border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
	}
	.viol-head {
		display: flex;
		align-items: center;
		gap: var(--s2);
		justify-content: space-between;
	}
	.viol-shape {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--danger);
	}
	.viol-focus {
		font-size: 10px;
		color: var(--accent);
		background: var(--accent-bg, color-mix(in srgb, var(--accent) 12%, transparent));
		border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border-1));
		border-radius: var(--radius-sm);
		padding: 1px 6px;
		cursor: pointer;
	}
	.viol-focus:hover {
		background: color-mix(in srgb, var(--accent) 22%, transparent);
	}
	.viol-msg {
		font-size: var(--text-xs);
		color: var(--fg-1);
		line-height: 1.5;
	}
	.pass-msg {
		display: flex;
		align-items: center;
		gap: var(--s2);
		padding: var(--s2) var(--s3);
		font-size: var(--text-xs);
		color: var(--fg-2);
		background: color-mix(in srgb, var(--success) 8%, var(--bg-2));
		border: 1px solid color-mix(in srgb, var(--success) 22%, var(--border-1));
		border-radius: var(--radius-sm);
	}
	.meta {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: var(--s2) var(--s3);
		border-radius: var(--radius);
		background: var(--bg-2);
		border: 1px solid var(--border-1);
		font-family: var(--font-mono);
		font-size: 10.5px;
		font-variant-numeric: tabular-nums;
	}
	.meta-row {
		display: grid;
		grid-template-columns: 5rem 1fr;
		column-gap: var(--s3);
		padding: 3px 0;
	}
	.meta-row + .meta-row {
		border-top: 1px dashed color-mix(in srgb, var(--border-1) 60%, transparent);
	}
	.meta dt {
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.meta dd {
		color: var(--fg-1);
		margin: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.meta dd .ok {
		color: var(--success);
	}
	.meta dd .warn {
		color: var(--warning, var(--accent));
	}
	.src-line {
		display: flex;
		align-items: center;
		gap: var(--s2);
		font-size: 10px;
		color: var(--fg-4);
	}
	.src-key {
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.src-val {
		color: var(--fg-3);
	}
</style>
