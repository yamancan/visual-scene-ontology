<script lang="ts">
	import Topbar from '$lib/components/Topbar.svelte';
	import { copyText, formatBytes } from '$lib/utils';
	import { VSON_VERSION } from '$lib';
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

	const PENMAN_EXAMPLE = `(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :framing close_up)
   :depicts (apple / PhysicalObject :class Apple
               :hasQuality (q / Quality :dimension Color :value red)))`;

	const VSON_X_EXAMPLE = `~scene
  /CameraView @cam *angle eye_level *framing close_up
  ^cam
  apple /PhysicalObject *class Apple *color red`;

	const FOL_EXAMPLE = `Composition(scene). PhysicalObject(apple). Quality(q).
class(apple, Apple). hasQuality(apple, q).
dimension(q, Color). value(q, red).`;

	const ANTHROPIC_SNIPPET = `client.messages.create(
    model="claude-sonnet-4-6",
    system=[{"type": "text", "text": SKILL,
             "cache_control": {"type": "ephemeral"}}],
    messages=[{"role": "user", "content": [
        {"type": "image", "source": {...}},
        {"type": "text", "text": "Emit the document."},
    ]}],
)`;
</script>

<svelte:head>
	<title>system prompts · vson</title>
	<meta
		name="description"
		content="Three system prompts that teach a vision-LLM to emit a SHACL-conformant scene graph. Same closed vocabulary, three surface notations."
	/>
</svelte:head>

<div class="page">
	<Topbar />

	<main class="prose">
		<header class="hero">
			<span class="eyebrow font-mono">system prompts</span>
			<h1>Vision-LLMs invent scenes. SHACL doesn't lie.</h1>
			<p class="lede">
				The trick is sticking a closed vocabulary between them — small enough to fit in a system
				prompt, expressive enough to encode a picture, strict enough that violations point
				somewhere. One RDF graph underneath, three surface notations on top. Same predicate logic
				either way:
				<code>contains(scene, p) ∧ class(p, Person)</code> doesn't change because you wrote it with sigils
				instead of parens.
			</p>
		</header>

		<section>
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

						<p class="card-pitch">
							{#if skill.id === 'penman'}
								Penman. Nested S-expressions, AMR-style. Verbose but easy to read; paren count
								diagnoses most failures. The studio default.
							{:else if skill.id === 'vson-x'}
								Eight prefix sigils, line-significant, no brackets. Cheaper in tokens.
								Graph-equivalent to Penman across the gallery; one documented collapse on symmetric
								spatial facts.
							{:else}
								The eighteen-kilobyte original. Closed vocabulary inline, hard rules, a worked
								example per primitive kind. Heaviest, and the size earns its keep when conformance
								matters more than tokens.
							{/if}
						</p>

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
			<h2>One graph, three spellings</h2>
			<p>
				Same scene — a red apple, eye-level close-up — written three ways. The notations are the
				surface; the graph is the commitment.
			</p>

			<div class="example-grid">
				<div class="example">
					<span class="example-label font-mono">penman</span>
					<pre><code>{PENMAN_EXAMPLE}</code></pre>
				</div>
				<div class="example">
					<span class="example-label font-mono">vson-x</span>
					<pre><code>{VSON_X_EXAMPLE}</code></pre>
				</div>
			</div>

			<p>Render the RDF as English:</p>
			<blockquote>
				<em>"Eye level close up, 50mm lens. A red apple."</em>
			</blockquote>

			<p>Or as predicate logic:</p>
			<pre class="fol"><code>{FOL_EXAMPLE}</code></pre>

			<p class="muted">
				Two surface notations, one English caption, one logical form — all from one graph. The
				studio's <code>caption</code> and <code>fol</code> exporters are deterministic functions of the
				RDF, not separate prompts.
			</p>
		</section>

		<section>
			<h2>Wire it in</h2>
			<p>
				Paste the prompt body as the <code>system</code> message. Cache it on the system block so follow-up
				calls in the same conversation pay around 10% of the input-token cost on the cached prefix.
			</p>

			<pre class="snippet"><code>{ANTHROPIC_SNIPPET}</code></pre>

			<p>Validate locally:</p>
			<pre class="snippet"><code>vson convert p2t scene.vson | vson validate</code></pre>

			<p class="muted">
				<a href="https://github.com/yamancan/visual-scene-ontology/tree/main/skills" rel="external"
					>/skills/&lt;name&gt;/</a
				>
				on GitHub ships each prompt with a <code>conformance.json</code> acceptance fixture and per-platform
				code snippets.
			</p>
		</section>

		<footer class="foot font-mono">
			<a href="/" rel="self">← studio</a>
			<span class="sep">·</span>
			<a href="/about">about</a>
			<span class="sep">·</span>
			<span>vson · {VSON_VERSION}</span>
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
		max-width: 64ch;
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
	.muted {
		color: var(--fg-3);
		font-size: var(--text-sm);
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
	.card-pitch {
		font-size: var(--text-sm);
		color: var(--fg-2);
		line-height: var(--leading-relaxed);
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
	.example-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--s3);
		margin: var(--s2) 0;
	}
	.example {
		display: flex;
		flex-direction: column;
		gap: var(--s1);
		min-width: 0;
	}
	.example-label {
		font-size: 10px;
		color: var(--fg-4);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.example pre {
		margin: 0;
		padding: var(--s3);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		font-family: var(--font-mono);
		font-size: 11px;
		line-height: 1.55;
		color: var(--fg-1);
		white-space: pre;
		overflow-x: auto;
	}
	blockquote {
		margin: 0;
		padding: var(--s3) var(--s4);
		border-left: 2px solid var(--accent);
		background: color-mix(in srgb, var(--accent) 6%, var(--bg-1));
		color: var(--fg-1);
		border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
	}
	.fol,
	.snippet {
		margin: 0;
		padding: var(--s3);
		background: var(--bg-1);
		border: 1px solid var(--border-1);
		border-radius: var(--radius-sm);
		font-family: var(--font-mono);
		font-size: 11.5px;
		line-height: 1.6;
		color: var(--fg-1);
		white-space: pre;
		overflow-x: auto;
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
		.example-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
