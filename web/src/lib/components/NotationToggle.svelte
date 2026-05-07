<script lang="ts">
	import { onMount } from 'svelte';
	import { scene, type Notation } from '$lib/scene.svelte';

	interface SkillManifestEntry {
		id: 'penman' | 'vson-x' | 'orchestrator';
		available: boolean;
	}

	// Default to true; flips to false only if /api/skills explicitly says X is
	// not shipped. This avoids disabling the toggle when the manifest endpoint
	// is slow or temporarily unreachable.
	let xAvailable = $state(true);

	onMount(async () => {
		try {
			const res = await fetch('/api/skills');
			if (!res.ok) return;
			const skills = (await res.json()) as SkillManifestEntry[];
			const x = skills.find((s) => s.id === 'vson-x');
			if (x && !x.available) xAvailable = false;
		} catch {
			/* keep default */
		}
	});

	function pick(n: Notation) {
		if (n === 'x' && !xAvailable) return;
		scene.setNotation(n);
	}
</script>

<fieldset class="toggle" aria-label="extraction notation">
	<legend class="font-mono">notation</legend>
	<label class:active={scene.notation === 'p'}>
		<input
			type="radio"
			name="notation"
			value="p"
			checked={scene.notation === 'p'}
			onchange={() => pick('p')}
		/>
		<span class="font-mono">penman</span>
		<span class="sub font-mono">vson-p</span>
	</label>
	<label class:active={scene.notation === 'x'} class:disabled={!xAvailable}>
		<input
			type="radio"
			name="notation"
			value="x"
			disabled={!xAvailable}
			checked={scene.notation === 'x'}
			onchange={() => pick('x')}
		/>
		<span class="font-mono">vson-x</span>
		<span class="sub font-mono">{xAvailable ? 'compact' : 'unavailable'}</span>
	</label>
</fieldset>

<style>
	.toggle {
		display: inline-flex;
		align-items: center;
		gap: var(--s2);
		padding: 4px 6px;
		border: 1px solid var(--border-1);
		border-radius: var(--radius-full);
		background: var(--bg-1);
	}
	legend {
		float: left;
		padding: 0 var(--s2) 0 var(--s1);
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
	label {
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		padding: 4px 10px;
		border-radius: var(--radius-full);
		cursor: pointer;
		color: var(--fg-3);
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	label:hover {
		color: var(--fg-1);
	}
	label.active {
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 12%, transparent);
	}
	label.disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	label.disabled:hover {
		color: var(--fg-3);
	}
	input[type='radio'] {
		position: absolute;
		opacity: 0;
		width: 0;
		height: 0;
	}
	span:first-of-type {
		font-size: var(--text-xs);
	}
	.sub {
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--fg-4);
	}
</style>
