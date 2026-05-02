<script lang="ts">
	import Topbar from '$lib/components/Topbar.svelte';
</script>

<svelte:head>
	<title>about · vson</title>
	<meta
		name="description"
		content="VSON turns an image into a SHACL-conformant scene graph. Why a graph, why these primitives, how it stays correct, why it's free."
	/>
</svelte:head>

<div class="page">
	<Topbar />

	<main class="prose">
		<header class="hero">
			<span class="eyebrow font-mono">about</span>
			<h1>An image is not a sentence.</h1>
			<p class="lede">
				A caption flattens a scene into a string. A scene graph keeps the structure: who is where,
				holding what, doing what to whom, in what kind of place. VSON is one notation for that
				graph, designed so any vision-capable model can produce it and any database can read it.
			</p>
		</header>

		<section>
			<h2>What you just saw</h2>
			<p>
				You uploaded an image. The studio sent it to a vision-language model with a 4 KB system
				prompt that lists the closed vocabulary, the five hard rules, and a worked example. The
				model emitted a Penman tree — text that looks like nested S-expressions. A small Rust
				binary (<code>vson</code>) rewrote that tree into Turtle 1.2, then a SHACL validator checked
				it against the published shape graph. If it conformed, you saw the graph. If it didn't, the
				server fed the violations back to the model and asked for a fix, up to twice.
			</p>
			<p class="aside">
				The image bytes never leave the request body. They are not stored, not logged, not cached.
				Only the resulting envelope (≤8 KB of text) is small enough to keep around.
			</p>
		</section>

		<section>
			<h2>Why a graph?</h2>
			<p>
				A caption is fine for a search index. It is wrong for everything else. <em>"A queen with a
				crown stands behind a knight"</em> hides the spatial relation, fuses two entities into one
				phrase, and offers no way to say what the knight is holding. Try to query it. Try to merge
				it with another caption of the same scene. It melts.
			</p>
			<p>
				A graph is the format the rest of the stack already wants. Knowledge graphs, retrieval, 3D
				reconstruction, scene-aware tools, simulators, evaluation harnesses — they all consume
				edges, not strings. VSON is what the model emits when you ask for the same data the
				downstream code is going to need anyway.
			</p>
		</section>

		<section>
			<h2>Why these primitives?</h2>
			<dl class="grid">
				<dt>Frame</dt>
				<dd>
					The world from a viewer's chair: <code>SceneContext</code> (where), <code>VisualStyle</code>
					(how rendered), <code>CameraView</code> (from where). Every directional spatial fact must
					name a viewer; perspective is not optional.
				</dd>

				<dt>Entity</dt>
				<dd>
					What the scene contains: <code>PhysicalObject</code>, <code>Aggregate</code>,
					<code>Substance</code>. Carries traits — animacy, countability, individuation — derived
					from the class, not re-inferred per call.
				</dd>

				<dt>Quality</dt>
				<dd>
					Properties that vary independently of identity: color, material, affect, action-state.
					Reified as their own nodes so they can be annotated, cited, or revised without rewriting
					the entity.
				</dd>

				<dt>Event</dt>
				<dd>
					A predication with thematic roles: <code>:agent</code>, <code>:patient</code>,
					<code>:instrument</code>. Actions are nodes, not edges, so a third party can attach
					confidence, time, or counter-claims to them.
				</dd>

				<dt>SpatialFact</dt>
				<dd>
					RCC-8 topology + Talmy-style direction + proximity, all reified as a single node so a
					viewer can be attached. <em>"left of"</em> is meaningless without saying left of whom.
				</dd>
			</dl>
			<p>
				The full vocabulary lives in <a href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/vson.md" rel="external">docs/vson.md</a>.
				It is closed: out-of-vocabulary tokens fail SHACL by design.
			</p>
		</section>

		<section>
			<h2>How it stays correct</h2>
			<p>
				Every document is checked against a published SHACL shape graph before it is returned. The
				shapes encode the constraints that matter most:
			</p>
			<ul>
				<li>Every directional <code>SpatialFact</code> must carry a viewer.</li>
				<li>Every <code>Event</code> must carry a lemma.</li>
				<li>Every <code>Quality</code> must carry both a dimension and a value.</li>
				<li>Bounding boxes are normalized to <code>[0,1]</code>.</li>
				<li>Trait values come from a closed enumeration.</li>
			</ul>
			<p>
				If the model emits a non-conformant document, the server replies with the SHACL report and
				asks the model to repair. Two retries, then it ships whatever it has with the violations
				attached so the caller can see what failed. No silent corrections.
			</p>
		</section>

		<section>
			<h2>Why it's free</h2>
			<p>
				The five demo images are pre-extracted at build time, the envelopes are committed to the
				repo, and clicking a thumbnail reads from disk — no model call, no API key, no spend. New
				uploads route to OpenRouter against either our key (rate-limited free tier) or your own key
				(unlimited, your spend). Image bytes are never persisted, in either path.
			</p>
			<p class="aside">
				The studio is stateless. Refresh the page and the scene is gone. There is no account, no
				database, no session. The only durable artifact of a run is the envelope you choose to
				download.
			</p>
		</section>

		<section>
			<h2>Why it's open</h2>
			<p>
				The ontology, the shapes, the CLI, and the studio are all Apache-2.0. The vocabulary maps
				directly to AMR (for actions), Cypher (for property graphs), and Visual Genome (for
				image-graph corpora). Anyone can extend the vocabulary, ship a model that emits VSON, or
				build a consumer that reads it. The
				<a href="/" rel="self">studio</a> is one such consumer; the
				<a href="https://github.com/yamancan/visual-scene-ontology/tree/main/skills/vson-extractor" rel="external">vson-extractor skill</a>
				is one such producer.
			</p>
		</section>

		<section>
			<h2>What's next</h2>
			<p>
				A bring-your-own-key flow, an IndexedDB envelope cache so re-uploading the same image is
				free for you too, streaming responses, and a public IRI host at <code>vson.dev/v1/…</code>
				so the ontology is dereferenceable. Status, in honest terms, is on
				<a href="https://github.com/yamancan/visual-scene-ontology" rel="external">GitHub</a>.
			</p>
		</section>

		<footer class="foot font-mono">
			<a href="/" rel="self">← back to the studio</a>
			<span class="sep">·</span>
			<span>vson · v1.0</span>
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
		max-width: 64ch;
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
		display: inline-flex;
		align-items: center;
		gap: var(--s2);
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
		line-height: var(--leading-relaxed);
		max-width: 56ch;
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
		background: var(--accent-bg, color-mix(in srgb, var(--accent) 10%, transparent));
		padding: 1px 5px;
		border-radius: var(--radius-sm);
	}
	.aside {
		padding: var(--s3) var(--s4);
		border-left: 2px solid var(--border-2);
		color: var(--fg-3);
		background: var(--bg-1);
		border-radius: var(--radius-sm);
		font-size: var(--text-sm);
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
	ul {
		display: flex;
		flex-direction: column;
		gap: var(--s2);
		padding-left: var(--s4);
	}
	li {
		list-style: disc;
	}
	a {
		color: var(--fg-1);
		text-decoration: underline;
		text-decoration-color: var(--border-2);
		text-underline-offset: 3px;
		transition: color var(--duration-fast) var(--ease-out);
	}
	a:hover {
		color: var(--accent);
		text-decoration-color: var(--accent);
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
