<script lang="ts">
	import Topbar from '$lib/components/Topbar.svelte';
	import Dropzone from '$lib/components/Dropzone.svelte';
	import DemoStrip from '$lib/components/DemoStrip.svelte';
	import GalleryStrip from '$lib/components/GalleryStrip.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import ScenePanel from '$lib/components/ScenePanel.svelte';
	import NotationToggle from '$lib/components/NotationToggle.svelte';
	import { scene } from '$lib/scene.svelte';
	import { VSON_VERSION } from '$lib';

	const STATUS_LABEL: Record<string, string> = {
		uploading: 'reading image',
		calling: 'calling vision model'
	};

	let busy = $derived(['uploading', 'calling'].includes(scene.status));
</script>

<div class="flex h-svh flex-col">
	<Topbar />
	<main class="relative flex-1 overflow-hidden">
		{#if scene.envelope}
			<div class="scene-enter h-full">
				<ScenePanel />
			</div>
		{:else}
			<div class="hero">
				<div class="hero-stack">
					<span class="eyebrow">
						<span class="eyebrow-dot"></span>
						<span class="font-mono">vson · {VSON_VERSION}</span>
					</span>

					<div class="hero-copy">
						<h1>Drop image, get scene graph.</h1>
						<p>
							Upload an image. <span class="num">~10s</span> later you'll have a SHACL-conformant scene
							graph — entities, qualities, events, spatial facts. No account. Tweak what you want.
						</p>
					</div>

					{#if busy}
						<div class="busy-card">
							{#if scene.imagePreview}
								<img src={scene.imagePreview} alt="" class="busy-img" />
							{/if}
							<Spinner label={STATUS_LABEL[scene.status] ?? scene.status} />
						</div>
					{:else}
						<NotationToggle />
						<Dropzone />
					{/if}

					{#if scene.errorMsg}
						<p class="err font-mono" role="alert">{scene.errorMsg}</p>
					{/if}

					<DemoStrip />
				</div>

				<GalleryStrip />
			</div>
		{/if}
	</main>
</div>

<style>
	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 100%;
		padding: var(--s10) var(--s6) var(--s14);
	}
	.hero-stack {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--s8);
		width: 100%;
		max-width: 520px;
	}
	.eyebrow {
		display: inline-flex;
		align-items: center;
		gap: var(--s2);
		padding: 4px 10px;
		font-size: var(--text-2xs);
		color: var(--fg-3);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-full);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.eyebrow-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--accent);
	}
	.hero-copy {
		display: flex;
		flex-direction: column;
		gap: var(--s3);
		text-align: center;
	}
	.hero-copy h1 {
		font-family: var(--font-display);
		font-weight: 500;
		font-size: var(--text-3xl);
		line-height: 1.05;
		letter-spacing: -0.01em;
		color: var(--fg-0);
	}
	.hero-copy p {
		font-size: var(--text-base);
		color: var(--fg-3);
		line-height: var(--leading-relaxed);
		max-width: 440px;
	}
	.hero-copy .num {
		color: var(--fg-1);
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
	.busy-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--s5);
		width: 100%;
		max-width: 480px;
		min-height: 280px;
		padding: var(--s6);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius);
	}
	.busy-img {
		max-height: 160px;
		border-radius: var(--radius-sm);
		box-shadow: var(--shadow-sm);
		object-fit: contain;
	}
	.err {
		max-width: 480px;
		text-align: center;
		font-size: var(--text-2xs);
		color: var(--danger);
	}
	@media (max-width: 540px) {
		.hero-copy h1 {
			font-size: var(--text-2xl);
		}
	}

	.scene-enter {
		animation: scene-in var(--duration-enter) var(--ease-out);
	}
	@keyframes scene-in {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
