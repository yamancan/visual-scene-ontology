<script lang="ts">
	import { useSvelteFlow, useNodesInitialized } from '@xyflow/svelte';

	// Re-fits the xyflow viewport whenever the graph container is shown or resized.
	// xyflow only auto-fits on initial node mount, NOT on container resize, so after
	// the image band toggles or the graph is display:none'd and restored (maximize
	// cycles) the saved transform was computed for a stale size and nodes can sit
	// off-centre/clipped. This helper MUST render inside <SvelteFlow> so the
	// useSvelteFlow context resolves.
	//
	// `signal` is any value the parent flips on a relevant layout change (e.g. a
	// string of maximized + imageBasis + bandGone + graphGone). We read it inside
	// the effect so the effect re-runs on every change.
	let {
		signal,
		options = { padding: 0.15 }
	}: { signal: unknown; options?: Record<string, unknown> } = $props();

	const { fitView } = useSvelteFlow();
	const initialized = useNodesInitialized();

	$effect(() => {
		// Track both the layout signal and node initialization.
		void signal;
		if (!initialized.current) return;
		// Defer one frame so the container has measured its new size before we fit;
		// fitView against a not-yet-resized box would compute the wrong transform.
		const id = requestAnimationFrame(() => {
			void fitView(options);
		});
		return () => cancelAnimationFrame(id);
	});
</script>
