<script lang="ts">
	import { scene } from '$lib/scene.svelte';
	import { download } from '$lib/utils';

	let env = $derived(scene.envelope);

	function dlPenman() {
		if (!env) return;
		download(`${env.scene_id}.vson`, env.vson_p, 'text/plain');
	}
	function dlTurtle() {
		if (!env) return;
		download(`${env.scene_id}.ttl`, env.vson_t, 'text/turtle');
	}
	function dlEnvelope() {
		if (!env) return;
		download(`${env.scene_id}.json`, JSON.stringify(env, null, 2), 'application/json');
	}
</script>

<div class="flex items-center gap-1 px-2 py-1.5">
	<button class="exp" onclick={dlPenman}>.vson</button>
	<span class="sep">·</span>
	<button class="exp" onclick={dlTurtle}>.ttl</button>
	<span class="sep">·</span>
	<button class="exp" onclick={dlEnvelope}>.json</button>
</div>

<style>
	.exp {
		font-family: var(--font-mono);
		font-size: 11px;
		text-transform: lowercase;
		letter-spacing: 0.02em;
		padding: 2px 6px;
		color: var(--fg-3);
		transition: color 100ms var(--ease-out);
	}
	.exp:hover {
		color: var(--accent);
	}
	.sep {
		color: var(--fg-4);
		font-size: 10px;
		user-select: none;
	}
</style>
