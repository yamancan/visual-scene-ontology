<script lang="ts">
	import Topbar from '$lib/components/Topbar.svelte';
	import Dropzone from '$lib/components/Dropzone.svelte';
	import DemoStrip from '$lib/components/DemoStrip.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import ScenePanel from '$lib/components/ScenePanel.svelte';
	import { scene } from '$lib/scene.svelte';

	const STATUS_LABEL: Record<string, string> = {
		uploading: 'reading image',
		calling: 'calling vision model',
		validating: 'validating',
		rendering: 'rendering'
	};

	let busy = $derived(['uploading', 'calling', 'validating', 'rendering'].includes(scene.status));
</script>

<div class="flex h-svh flex-col">
	<Topbar />
	<main class="relative flex-1 overflow-hidden">
		{#if scene.envelope}
			<ScenePanel />
		{:else}
			<div class="flex h-full w-full flex-col items-center justify-center px-6 py-10">
				<div class="flex flex-col items-center gap-8">
					<div class="flex flex-col items-center gap-2 text-center">
						<h1 class="text-(--fg-0) text-[28px] font-medium tracking-tight">
							drop image · graph out
						</h1>
						<p class="max-w-[420px] text-[13px] text-(--fg-3)">
							upload an image, get a SHACL-conformant scene graph in
							<span class="tabular text-(--fg-0)">~10s</span>. penman, turtle, json. no
							account.
						</p>
					</div>

					{#if busy}
						<div
							class="flex h-[280px] w-full max-w-[480px] flex-col items-center justify-center gap-4 rounded-md border border-(--border-1) bg-(--bg-1)"
						>
							{#if scene.imagePreview}
								<img
									src={scene.imagePreview}
									alt="source"
									class="h-[160px] w-auto rounded object-cover ring-1 ring-(--border-1)"
								/>
							{/if}
							<Spinner label={STATUS_LABEL[scene.status] ?? scene.status} />
						</div>
					{:else}
						<Dropzone />
					{/if}

					{#if scene.errorMsg}
						<p
							class="max-w-[480px] text-center font-mono text-[12px]"
							style:color="var(--danger)"
							role="alert"
						>
							{scene.errorMsg}
						</p>
					{/if}

					<DemoStrip />
				</div>
			</div>
		{/if}
	</main>
</div>
