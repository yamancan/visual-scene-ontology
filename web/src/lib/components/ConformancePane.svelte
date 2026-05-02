<script lang="ts">
	import { scene } from '$lib/scene.svelte';

	let env = $derived(scene.envelope);
	let conforms = $derived(env?.conformance.conforms ?? false);
	let violations = $derived(env?.conformance.violations ?? []);
	let extraction = $derived(env?.extraction);
</script>

<section class="flex h-full flex-col bg-(--bg-1)">
	<header
		class="flex h-7 items-center justify-between border-b border-(--border-1) px-3 text-(--fg-4)"
	>
		<span class="font-mono text-[10px] uppercase tracking-wider">conformance</span>
		<span class="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider">
			<span
				class="dot"
				style:background={conforms ? 'var(--success)' : 'var(--danger)'}
			></span>
			{conforms ? 'pass' : 'fail'}
		</span>
	</header>

	<div class="flex-1 overflow-auto">
		{#if env}
			<div class="flex flex-col gap-3 p-3">
				{#if conforms}
					<div class="flex flex-col gap-1.5 text-[12px] text-(--fg-3)">
						<span class="text-(--fg-0)">{env.graph?.nodes.length ?? 0} nodes</span>
						<span>{env.graph?.edges.length ?? 0} edges</span>
					</div>
				{:else}
					<div class="flex flex-col gap-2">
						{#each violations as v, i (i)}
							<div
								class="flex flex-col gap-1 border-l-2 px-3 py-1.5"
								style:border-color="var(--danger)"
							>
								<div class="font-mono text-[10px] uppercase tracking-wider text-(--fg-4)">
									{v.shape}
								</div>
								<div class="text-[12px] text-(--fg-0)">{v.message}</div>
								{#if v.focus_node}
									<div class="font-mono text-[10px] text-(--fg-4)">{v.focus_node}</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}

				{#if extraction}
					<dl class="meta">
						<dt>model</dt>
						<dd title={extraction.model}>{extraction.model}</dd>
						<dt>latency</dt>
						<dd>{((extraction.latency_ms ?? 0) / 1000).toFixed(2)}s</dd>
						<dt>retries</dt>
						<dd>{extraction.shacl_retries ?? 0}</dd>
						<dt>tokens</dt>
						<dd>{extraction.input_tokens ?? 0} <span class="sep">/</span> {extraction.output_tokens ?? 0}</dd>
					</dl>
				{/if}
			</div>
		{/if}
	</div>
</section>

<style>
	.meta {
		display: grid;
		grid-template-columns: 4.5rem 1fr;
		column-gap: var(--s3);
		row-gap: 4px;
		margin-top: var(--s2);
		padding-top: var(--s3);
		border-top: 1px solid var(--border-1);
		font-family: var(--font-mono);
		font-size: var(--text-2xs);
		font-variant-numeric: tabular-nums;
	}
	.meta dt {
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.meta dd {
		color: var(--fg-2);
		margin: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
	.meta dd .sep {
		color: var(--fg-4);
	}
</style>
