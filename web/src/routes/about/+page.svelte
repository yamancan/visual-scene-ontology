<script lang="ts">
	import Topbar from '$lib/components/Topbar.svelte';
	import { VSON_VERSION } from '$lib';
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
				<strong>If you clicked a demo or a spec example</strong>, no model ran and no key was spent.
				The studio fetched a committed file: for a demo, the envelope one real extraction produced,
				kept with its provenance; for a spec example, a hand-authored document. What you are looking
				at is that file, rendered. The verdict beside it is the one recorded when the file was made
				— which is why the conformance panel offers to re-run the two browser gates over the
				document on screen, live, so you can watch them agree rather than take the stored answer on
				trust.
			</p>
			<p>
				<strong>If you uploaded an image</strong>, your browser sent it straight to a
				vision-language model through OpenRouter, on your own key — the request never touches the
				studio host — with a <a href="/prompts" rel="self">5 KB system prompt</a> that lists the
				closed vocabulary, the five hard rules, and a worked example. The model emitted a Penman
				tree — text that looks like nested S-expressions. A Pyodide worker, also in your browser,
				rewrote that tree into Turtle 1.2 with the reference emitter CI byte-compares against the
				<code>vson</code> CLI, then checked it with two of the three gates the CLI runs. If it conformed,
				you saw the graph. If it didn't, the studio fed the violations back to the model and asked for
				a fix, up to twice.
			</p>
			<p class="aside">
				The image goes from your browser to OpenRouter and nowhere else. There is no studio backend
				to store, log, or cache it. Only the resulting envelope (≤8 KB of text) is small enough to
				keep around.
			</p>
		</section>

		<section>
			<h2>Why a graph?</h2>
			<p>
				A caption is fine for a search index. It is wrong for everything else. <em
					>"A queen with a crown stands behind a knight"</em
				> hides the spatial relation, fuses two entities into one phrase, and offers no way to say what
				the knight is holding. Try to query it. Try to merge it with another caption of the same scene.
				It melts.
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
					The world from a viewer's chair: <code>SceneContext</code> (where),
					<code>VisualStyle</code>
					(how rendered), <code>CameraView</code> (from where). Every directional spatial fact must name
					a viewer; perspective is not optional.
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
				The full vocabulary lives in <a
					href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/vson.md"
					rel="external">docs/vson.md</a
				>. It is closed: out-of-vocabulary tokens fail SHACL by design.
			</p>
		</section>

		<section>
			<h2>Where the ideas come from</h2>
			<p>
				Almost none of this thinking is ours;
				<a
					href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/vson.md#appendix-e--related-work-and-bibliography"
					rel="external">Appendix E</a
				> states, per source, what was taken and what was left.
			</p>
			<p>
				Talmy (2000) is why a spatial relation has two slots that cannot be swapped: one names the
				located thing, the other what it is located against. Levinson (2003) is why a directional
				fact must name a viewer — three frames of reference exist and
				<em>left of</em> is a different claim in each, so VSON fixes the relative frame and makes
				the anchor a structural obligation (<a
					href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/vson.md#33-viewer-anchoring-directional-facts"
					rel="external">C5</a
				>). That obligation is not new: ISO 24617-7:2020 requires a spatial link to carry a relation
				type and two arguments — <code>@figure</code> and <code>@ground</code> in its movement link
				— the asymmetry SemEval-2012 evaluated as <em>trajector</em> and <em>landmark</em>. What
				VSON adds is one thing wide: those schemes instruct an annotator, this one rejects a
				document.
			</p>
			<p>
				DOLCE (Masolo et al. 2003) supplies the endurant/perdurant spine — inspired, not aligned: no
				IRI imported, no axiom asserted. AMR (Banarescu et al. 2013) proves a graph can be written
				by hand;
				<a
					href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/vson.md#42-vson-p-penman-authoring-human"
					rel="external">VSON-P</a
				> borrows its Penman surface. RCC-8 and Allen arrive as closed calculi; this notation takes their
				names, not their inference: no composition table ships.
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
				All of it runs in your browser: a Pyodide worker executes pyshacl over the shapes (Gate 1),
				then an owlrl OWL 2 RL consistency check (Gate 2) — the same two gates, in the same order
				and from the same source files, as <code>vson validate</code>. The CLI has a third gate the
				browser does not: a vocabulary-closure check that rejects VSON terms the ontology never
				declared. So a document that passes here passes the CLI's first two gates too, and may still
				fail its third. The first live validation downloads ~16 MB of runtime (less over the wire
				with compression); after that it is cached.
			</p>
			<p>
				If the model emits a non-conformant document, the studio feeds the SHACL report back to the
				model and asks it to repair. Up to two repair rounds, then it ships whatever it has with the
				violations attached so you can see what failed. No silent corrections.
			</p>
		</section>

		<section>
			<h2>What a verdict refuses to say</h2>
			<p>
				Conformance is three properties, decided by the parser, SHACL over the shapes and an OWL 2
				RL closure; a pass establishes only what its mechanism examined (<a
					href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/vson.md#21-what-conformance-establishes"
					rel="external">§2.1</a
				>). None of them reads pixels: a document asserting a red cube left of a blue sphere,
				describing a photograph containing neither, is fully conformant and entirely false.
			</p>
			<p>
				Geometry narrows that by one step. A box bounds the region it is asserted of, so boxes that
				cannot support a relation refute it; boxes that agree confirm nothing — a cat on a mat
				touches its mat while their rectangles overlap with area (<a
					href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/vson.md#5132-the-engine-a-bounding-box-refutes-it-does-not-confirm"
					rel="external">§5.13.2</a
				>). A box can say no; it can never say yes.
			</p>
			<p>
				Agreement is not correctness: two conformant documents <code>vson diff</code>
				scores have agreed, and that is all (<a
					href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/vson.md#5155-what-a-score-establishes"
					rel="external">§5.15.5</a
				>). Groundedness — that each assertion matches what the image depicts — does not exist here,
				and the specification says so itself.
			</p>
			<p>
				The argument at length, with the clause or fixture behind each refusal, is the essay these
				two sections distill:
				<a
					href="https://github.com/yamancan/visual-scene-ontology/blob/main/docs/essay-an-image-is-not-a-sentence.md"
					rel="external">An image is not a sentence</a
				>.
			</p>
		</section>

		<section>
			<h2>Why it's free</h2>
			<p>
				The four demo images were extracted once, for real, and their envelopes are committed to the
				repo with the model's genuine provenance. Clicking a thumbnail fetches the baked envelope —
				no model call, no API key, no spend. The sixteen gallery scenes are hand-authored conformant
				fixtures served the same way. That is the keyless $0 path. A new upload is different: it
				goes from your browser straight to OpenRouter on your own key — your spend — and never
				routes through the studio host. Image bytes are never persisted, in either path.
			</p>
			<p class="aside">
				The four photographs are not ours. They are Unsplash photographs, credited under the demo
				strip and in full — photographer, licence, source and file hash — in
				<a href="/demos/CREDITS.md" rel="external">CREDITS.md</a>. The licence is the Unsplash
				License, which covers the photograph and not the people in it; that is why there are four
				and not five.
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
				<a
					href="https://github.com/yamancan/visual-scene-ontology/tree/main/skills/vson-extractor"
					rel="external">vson-extractor skill</a
				>
				is one such producer.
			</p>
			<p class="aside">
				Built by <a href="https://github.com/yamancan" rel="external">Yaman Can</a> — BSc
				Philosophy, Boğaziçi University. The notation is that philosophy put through a build
				gate.
			</p>
		</section>

		<section>
			<h2>What's next</h2>
			<p>
				An IndexedDB envelope cache so re-uploading the same image is free for you too, and
				streaming responses. The ontology itself is published at
				<a href="https://vson.pages.dev/v1/ontology.ttl" rel="external">vson.pages.dev</a>
				under the <code>w3id.org/vson</code> names. Status, in honest terms, is on
				<a href="https://github.com/yamancan/visual-scene-ontology" rel="external">GitHub</a>.
			</p>
		</section>

		<footer class="foot font-mono">
			<a href="/" rel="self">← back to the studio</a>
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
	strong {
		color: var(--fg-1);
		font-weight: 500;
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
