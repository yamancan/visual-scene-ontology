<script lang="ts">
	import Topbar from '$lib/components/Topbar.svelte';
	import { copyText, formatBytes } from '$lib/utils';
	import type { PageData } from './$types';

	const { data }: { data: PageData } = $props();

	let openId = $state<string | null>(null);
	let copiedId = $state<string | null>(null);

	function toggle(id: string) {
		openId = openId === id ? null : id;
	}

	async function doCopy(id: string, body: string) {
		const ok = await copyText(body);
		if (ok) {
			copiedId = id;
			setTimeout(() => {
				if (copiedId === id) copiedId = null;
			}, 1200);
		}
	}
</script>

<svelte:head>
	<title>system prompts · vson</title>
	<meta
		name="description"
		content="Copy-paste system prompts that teach a vision-LLM to emit SHACL-conformant VSON scene graphs. VSON-P (Penman) and VSON-X (compact) notations."
	/>
</svelte:head>

<div class="page">
	<Topbar />

	<main class="prose">
		<header class="hero">
			<span class="eyebrow font-mono">system prompts</span>
			<h1>Notations, distilled.</h1>
			<p class="lede">
				Three system prompts that teach any vision-capable LLM to emit a SHACL-conformant scene
				graph. Pick a notation, copy the prompt, paste it as the system message — same closed
				vocabulary, different surface syntax.
			</p>
		</header>

		<section class="primer">
			<h2>The three notations</h2>
			<dl class="grid">
				<dt>VSON-P</dt>
				<dd>
					<strong>Penman.</strong> Nested S-expressions, AMR-like. Familiar to parsers, easy to
					machine-edit, ~30-40% larger than VSON-X for dense scenes. The default for the studio
					and the safest choice if you don't know which to pick.
				</dd>

				<dt>VSON-X</dt>
				<dd>
					<strong>Compact, sigil-based.</strong> Eight prefix sigils (<code>~ / @ * &gt; &gt;&gt; ! &amp; ^</code>),
					line-significant, no brackets. Lower token count, friendlier to vision-LLM emission patterns.
					Same RDF graph as VSON-P; round-trips losslessly via Turtle (modulo one documented edge collapse).
				</dd>

				<dt>Orchestrator</dt>
				<dd>
					<strong>Full pipeline.</strong> The 18 KB original — strongest first-try conformance,
					includes the closed vocabulary, the five hard rules, and worked examples for each
					primitive kind. Use when you need maximum conformance and don't mind the prompt size.
				</dd>
			</dl>
		</section>

		<section>
			<h2>Skills</h2>
			<p>
				Each card below is one system prompt. Open it to inspect, then copy the body and paste it
				as the <code>system</code> message in your model call. Feed an image with a one-line user
				message (<em>"Emit the document."</em>); the model returns a single document — no prose, no
				fences.
			</p>

			<div class="cards">
				{#each data.skills as skill (skill.id)}
					{@const open = openId === skill.id}
					<article class="card" class:disabled={!skill.available}>
						<header class="card-head">
							<div class="card-title">
								<span class="badge font-mono">{skill.notation}</span>
								<span class="version font-mono">{skill.version}</span>
							</div>
							<div class="card-meta font-mono">
								<span>{formatBytes(skill.size_bytes)}</span>
								<span class="sep">·</span>
								<span>→ {skill.output}</span>
								{#if !skill.available}
									<span class="sep">·</span>
									<span class="warn">not shipped</span>
								{/if}
							</div>
						</header>

						<div class="card-actions">
							<button
								type="button"
								class="ghost"
								disabled={!skill.available}
								onclick={() => toggle(skill.id)}
							>
								{open ? 'hide' : 'show'} prompt
							</button>
							<button
								type="button"
								class="primary"
								disabled={!skill.available}
								onclick={() => doCopy(skill.id, skill.body)}
							>
								{copiedId === skill.id ? 'copied' : 'copy prompt'}
							</button>
						</div>

						{#if open && skill.available}
							<pre class="body"><code>{skill.body}</code></pre>
						{/if}
					</article>
				{/each}
			</div>
		</section>

		<section>
			<h2>How to use</h2>
			<p>
				The skill body is plain Markdown. With Anthropic Claude, set
				<code>cache_control: ephemeral</code> on the system block so the prompt is cached across a
				5-minute window — subsequent calls in the same conversation pay ~10% of the input-token
				cost on the cached prefix. With OpenAI / OpenRouter, paste it as <code>system</code> and
				attach the image as a user content part.
			</p>
			<p>
				The <a href="https://github.com/yamancan/visual-scene-ontology/tree/main/skills" rel="external">skills/ directory on GitHub</a>
				ships each prompt alongside a <code>conformance.json</code> acceptance fixture and per-platform
				code snippets. To validate output locally:
				<code>vson convert p2t scene.vson | vson validate</code> for VSON-P, or
				<code>vson convert x2t scene.x.vson | vson validate</code> for VSON-X.
			</p>
		</section>

		<footer class="foot font-mono">
			<a href="/" rel="self">← back to the studio</a>
			<span class="sep">·</span>
			<a href="/about">about</a>
			<span class="sep">·</span>
			<span>vson · v1.1</span>
		</footer>
	</main>
</div>

<style>
	.page {
		display: flex;
		flex-direction: column;
		min-height: 100svh;
	}
	.prose {
		max-width: 72ch;
		width: 100%;
		margin: 0 auto;
		padding: var(--s10) var(--s6) var(--s14);
		color: var(--fg-2);
		font-size: var(--text-base);
		line-height: var(--leading-relaxed);
	}
	.hero {
		display: flex;
		flex-direction: column;
		gap: var(--s4);
		margin-bottom: var(--s10);
	}
	.eyebrow {
		font-size: var(--text-2xs);
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	h1 {
		font-family: var(--font-display);
		font-weight: 500;
		font-size: var(--text-4xl, 2.5rem);
		line-height: 1.05;
		letter-spacing: -0.015em;
		color: var(--fg-0);
	}
	.lede {
		font-size: var(--text-lg, 1.125rem);
		color: var(--fg-1);
		max-width: 60ch;
	}
	section {
		display: flex;
		flex-direction: column;
		gap: var(--s3);
		margin-top: var(--s10);
	}
	h2 {
		font-family: var(--font-display);
		font-weight: 500;
		font-size: var(--text-2xl, 1.5rem);
		letter-spacing: -0.01em;
		color: var(--fg-0);
		margin-bottom: var(--s1);
	}
	p {
		margin: 0;
	}
	em {
		color: var(--fg-1);
		font-style: italic;
	}
	code {
		font-family: var(--font-mono);
		font-size: 0.92em;
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 10%, transparent);
		padding: 1px 5px;
		border-radius: var(--radius-sm);
	}
	.grid {
		display: grid;
		grid-template-columns: 8rem 1fr;
		column-gap: var(--s5);
		row-gap: var(--s4);
		margin: var(--s2) 0 var(--s3);
	}
	.grid dt {
		font-family: var(--font-mono);
		font-size: var(--text-xs);
		color: var(--fg-1);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding-top: 4px;
	}
	.grid dd {
		margin: 0;
	}
	a {
		color: var(--fg-1);
		text-decoration: underline;
		text-decoration-color: var(--border-2);
		text-underline-offset: 3px;
	}
	a:hover {
		color: var(--accent);
		text-decoration-color: var(--accent);
	}
	.cards {
		display: flex;
		flex-direction: column;
		gap: var(--s4);
		margin-top: var(--s2);
	}
	.card {
		display: flex;
		flex-direction: column;
		gap: var(--s3);
		padding: var(--s4);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-md);
	}
	.card.disabled {
		opacity: 0.55;
	}
	.card-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--s3);
		flex-wrap: wrap;
	}
	.card-title {
		display: flex;
		align-items: baseline;
		gap: var(--s3);
	}
	.badge {
		display: inline-flex;
		align-items: center;
		padding: 2px 8px;
		font-size: var(--text-xs);
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border-1));
		border-radius: var(--radius-full);
	}
	.version {
		font-size: 10px;
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.card-meta {
		display: flex;
		gap: 6px;
		font-size: 10px;
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.card-meta .sep {
		color: var(--border-2);
	}
	.card-meta .warn {
		color: var(--danger);
	}
	.card-actions {
		display: flex;
		gap: var(--s2);
	}
	.card-actions button {
		font-family: var(--font-mono);
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding: 6px 10px;
		border-radius: var(--radius-sm);
		cursor: pointer;
		transition:
			color var(--duration-fast) var(--ease-out),
			background var(--duration-fast) var(--ease-out);
	}
	.card-actions button:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}
	.ghost {
		color: var(--fg-3);
		background: transparent;
		border: 1px solid var(--border-1);
	}
	.ghost:not(:disabled):hover {
		color: var(--fg-1);
		border-color: var(--border-2);
	}
	.primary {
		color: var(--accent-fg);
		background: var(--accent);
		border: 1px solid var(--accent);
	}
	.primary:not(:disabled):hover {
		background: color-mix(in srgb, var(--accent) 88%, white);
	}
	.body {
		max-height: 28rem;
		overflow: auto;
		margin: 0;
		padding: var(--s3);
		background: var(--bg-0);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		font-family: var(--font-mono);
		font-size: 11.5px;
		line-height: 1.55;
		color: var(--fg-1);
		white-space: pre;
	}
	.foot {
		margin-top: var(--s14);
		padding-top: var(--s5);
		border-top: 1px solid var(--border-1);
		display: flex;
		gap: var(--s3);
		font-size: var(--text-2xs);
		color: var(--fg-4);
	}
	.foot .sep {
		color: var(--border-2);
	}
	@media (max-width: 540px) {
		h1 {
			font-size: var(--text-3xl, 2rem);
		}
		.grid {
			grid-template-columns: 1fr;
			row-gap: var(--s2);
		}
		.grid dt {
			padding-top: 0;
		}
	}
</style>
