<script lang="ts">
	import GraphView from './GraphView.svelte';
	import SourcePane from './SourcePane.svelte';
	import ConformancePane from './ConformancePane.svelte';
	import ExportRow from './ExportRow.svelte';
	import { scene } from '$lib/scene.svelte';
</script>

<div class="grid h-full grid-cols-3 gap-px bg-(--border-1)">
	<div class="relative flex flex-col bg-(--bg-0)">
		<header class="flex h-7 items-center justify-between border-b border-(--border-1) px-3">
			<span class="font-mono text-[10px] uppercase tracking-wider text-(--fg-4)"
				>graph</span
			>
			{#if scene.imagePreview}
				<img
					src={scene.imagePreview}
					alt="source"
					class="h-5 w-5 rounded object-cover ring-1 ring-(--border-1)"
				/>
			{/if}
		</header>
		<div class="flex-1 overflow-hidden">
			<GraphView />
		</div>
		<footer class="border-t border-(--border-1)">
			<ExportRow />
		</footer>
	</div>

	<SourcePane />
	<ConformancePane />
</div>
