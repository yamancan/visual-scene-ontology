<script lang="ts">
	import { scene } from '$lib/scene.svelte';

	let conforms = $derived(scene.envelope?.conformance.conforms ?? null);
	let triples = $derived(scene.envelope?.vson_t ? countTriples(scene.envelope.vson_t) : 0);
	let latency = $derived(scene.envelope?.extraction?.latency_ms ?? 0);

	function countTriples(turtle: string): number {
		// Each Turtle statement ends with " .". Conservative count.
		return (turtle.match(/\s\.\s*\n/g) || []).length;
	}
</script>

<header
	class="flex h-10 select-none items-center justify-between border-b border-(--border-1) bg-(--bg-0) px-4 text-(--fg-3)"
>
	<div class="flex items-center gap-4">
		<button
			class="text-(--fg-0) tracking-tight transition-colors hover:text-(--accent)"
			onclick={() => scene.reset()}
			aria-label="Reset"
		>
			vson
		</button>
		{#if scene.envelope}
			<span class="text-(--fg-4)">·</span>
			<span class="font-mono text-[12px] tabular text-(--fg-3)"
				>{scene.envelope.scene_id}</span
			>
		{/if}
	</div>

	<div class="flex items-center gap-4 text-[12px]">
		{#if scene.envelope}
			<span class="flex items-center gap-1.5 tabular text-(--fg-3)">
				<span
					class="dot"
					style:background={conforms ? 'var(--success)' : 'var(--danger)'}
				></span>
				{conforms ? 'conforms' : `${scene.envelope.conformance.violations?.length ?? 0} violations`}
			</span>
			<span class="text-(--fg-4)">·</span>
			<span class="font-mono tabular text-(--fg-3)"
				>{triples} <span class="text-(--fg-4)">triples</span></span
			>
			<span class="text-(--fg-4)">·</span>
			<span class="font-mono tabular text-(--fg-3)"
				>{(latency / 1000).toFixed(1)}<span class="text-(--fg-4)">s</span></span
			>
		{:else}
			<span class="text-[12px] text-(--fg-4)">drop image · graph out</span>
		{/if}
	</div>
</header>
