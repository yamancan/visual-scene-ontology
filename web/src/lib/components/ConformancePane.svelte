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
					<div
						class="mt-2 flex flex-col gap-1 border-t border-(--border-1) pt-3 font-mono text-[10px] tabular text-(--fg-4)"
					>
						<div class="flex justify-between">
							<span>model</span><span class="text-(--fg-3)">{extraction.model}</span>
						</div>
						<div class="flex justify-between">
							<span>latency</span><span class="text-(--fg-3)"
								>{((extraction.latency_ms ?? 0) / 1000).toFixed(2)}s</span
							>
						</div>
						<div class="flex justify-between">
							<span>retries</span><span class="text-(--fg-3)"
								>{extraction.shacl_retries ?? 0}</span
							>
						</div>
						<div class="flex justify-between">
							<span>tokens in/out</span><span class="text-(--fg-3)"
								>{extraction.input_tokens ?? 0} / {extraction.output_tokens ?? 0}</span
							>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</section>
