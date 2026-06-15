<script lang="ts">
	let { label }: { label: string } = $props();
</script>

<div class="flex items-center gap-3 font-mono text-[12px] text-(--fg-3)">
	<span class="relative flex h-2 w-12 overflow-hidden rounded-full bg-(--bg-2)">
		<span
			class="animate-pulse-slide absolute inset-y-0 w-3 rounded-full"
			style:background="var(--accent)"
		></span>
	</span>
	<span class="tabular">{label}</span>
</div>

<style>
	@keyframes slide {
		0% {
			transform: translateX(-100%);
		}
		100% {
			transform: translateX(400%);
		}
	}
	:global(.animate-pulse-slide) {
		animation: slide 1.4s cubic-bezier(0.45, 0, 0.55, 1) infinite;
	}
</style>
