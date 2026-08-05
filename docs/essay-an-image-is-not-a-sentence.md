<!--
The canonical long form of this argument, and the only one. The studio's about
page (web/src/routes/about/+page.svelte) carries two sections distilled from it —
"Where the ideas come from" and "What a verdict refuses to say" — which make no
claim this file does not. Change this file first; the two sections follow it.
-->

# An image is not a sentence

A vision-language model, shown a photograph, returns a paragraph. It may be entirely right. What it
cannot be is *rejected*: there is no schema it violates, no gate it fails, no exit code it produces.
You cannot diff two of them or fail a build on one. A description nothing can refuse is not a
measurement — it is an opinion wearing the grammar of a fact.

This notation starts from the other end: **a claim you cannot reject is not a claim.**

## What a claim about a picture is

"A queen stands behind a knight, holding a sceptre." Four people can deny four different things.
That there is a queen at all (an entity). That she is a queen and not a woman in costume (a
quality). That she is behind him, and from whose vantage (a relation). That she is holding anything
(an event with roles). The sentence fuses all four into one string, where no denial can find its
part.

So the unit is not the sentence but the assertion someone could deny, and each gets a node:
[five node kinds](./vson.md#31-the-five-node-kinds) — Frame, Entity, Quality, Perdurant,
SpatialFact — under one [reification rule](./vson.md#34-reification--the-universal-pattern): *if you
might want to negate it, refer to it, or attach a probability, make it a node, not an edge.* A node
can be pointed at; a clause cannot.

What that buys is the exit code. [`bad_no_viewer.vson`](../tests/fixtures/bad_no_viewer.vson) says
one thing is left of another and never says left from where; `vson validate` exits 1, naming the
shape that refused it: [`vss:DirectionalNeedsViewerShape`](../shapes/vson-shapes.ttl).

## What is inherited

Almost none of this thinking is this project's.
[Appendix E](./vson.md#appendix-e--related-work-and-bibliography) states, per source, what was taken
and what was left.

**Talmy (2000)** is why a spatial relation has two slots that cannot be swapped: one names the
located thing (`vso:figure`), the other the thing it is located against (`vso:ground`), and an
unordered pair would lose the distinction.

**Levinson (2003)** is why a directional fact must name a viewer. Three frames of reference are
available — intrinsic, relative, absolute — and "left of" is a different claim in each. VSON commits
to the relative frame and makes the anchor a structural obligation: clause
[C5](./vson.md#33-viewer-anchoring-directional-facts), the shape above, the rejected document.

The credit must be stated plainly; this project's README once did not. **Reifying a spatial
relation with required, asymmetric figure and ground slots is standardized practice.** ISO
24617-7:2020 requires a link structure to carry a relation type and two named arguments — `@figure`
and `@ground` in its revised movement link, established from the open-access revision paper, not the
paywalled standard ([Appendix E.7](./vson.md#appendix-e--related-work-and-bibliography)).
SemEval-2012's spatial-role-labeling task ran the same asymmetry as *trajector* and *landmark*. What
is added is one thing wide: those schemes instruct an annotator; this one rejects a document. C5 is
not a stronger claim about space; it is the same claim with an exit code attached.

**RCC-8** (Randell, Cui & Cohn 1992) and **Allen** (1983) arrive as closed calculi, and this notation
takes their names, not their inference: no composition table ships, so given NTPP(a,b) and NTPP(b,c),
nothing here follows about a and c.

**DOLCE** (Masolo et al. 2003) supplies the spine: the endurant/perdurant cut, a thing wholly present
at a moment against one that unfolds through it. Inspired, not aligned — no DOLCE IRI imported, no
axiom asserted, no reasoner required.

**AMR** (Banarescu et al. 2013) is proof that a graph can be an authoring format, not only a storage
one: people hand-annotate corpora in its Penman surface, which
[VSON-P](./vson.md#42-vson-p-penman-authoring-human) borrows.

## What a green check establishes, and refuses to

[§2.1](./vson.md#21-what-conformance-establishes) is the section this project would keep if it had to
delete every other. Conformance is three properties decided by three mechanisms — the parser
(syntax), SHACL over the shapes (structure), an OWL 2 RL closure (self-consistency) — and a pass
establishes only what its mechanism examined.

None of the three reads pixels. The specification's own example: a document asserting a red cube left
of a blue sphere, describing a photograph that contains neither, parses, satisfies every shape, and
has a clash-free closure — fully conformant, entirely false.

Geometry narrows that by one step. A bounding box is *extensive* — the region sits inside its box —
and *monotone* — if one region is inside another, so are their boxes. A relation between regions
therefore entails something about the boxes, and boxes that falsify the entailment refute the
relation. The converse never holds: a cat on a mat stands in `rcc:EC`, regions touching, interiors
disjoint, while their rectangles overlap with area. A box can say *no*; it can never say *yes*.
Measured: of the ten `vso:rcc` facts the baked studio envelopes state over two rectangles, a
check demanding the rectangles' own relation match would reject six; the refutation rule rejects
one ([§5.13.2](./vson.md#5132-the-engine-a-bounding-box-refutes-it-does-not-confirm)) — a
self-contradiction in real model output that every conformance gate passes. The cat itself ships:
the demo strip's `cat.json` asserts `rcc:EC` for a cat on a rug whose rectangles overlap — the
example above, in frozen extractor output.

Agreement is not correctness. The same throne-room scene — hand-authored once, rendered from the
gallery once — scores F1 0.767 under `vson diff`; both are conformant, both ship, neither is wrong
([§5.15.5](./vson.md#5155-what-a-score-establishes)). Two runs that agree have agreed, and that is
all.

Which leaves the absent property. **Groundedness — that each assertion corresponds to what the image
depicts — does not exist here, and the specification says so itself.** It would need ground truth
this repository lacks: a fixed image set, human annotation, a protocol, an agreement figure.

## Why the vocabulary is closed

`vso:directional` admits six values, `vso:proximal` five
([§5.12](./vson.md#512-reserved--closed-enumerations-full-list)). A producer may not invent a
seventh.

That reads as a limitation and is the commitment everything rests on: a vocabulary that accepts
a fresh word for every scene can never say no, and a notation that can never say no is prose with
extra punctuation. [`bad_orphan_term.ttl`](../tests/fixtures/bad_orphan_term.ttl) mints
`vso:Ambience`, a perfectly reasonable dimension for a picture. Every shape passes it and the closure
is clean; the [C2 gate](./vson.md#2-conformance) rejects it anyway, because
[`ontology/vso.ttl`](../ontology/vso.ttl) never declared the term.

The bill is coarseness, itemized rather than hidden: GUM-Space and FrameNet are the finer analyses
that six directional values and a VerbNet-style role set give up, because a model cannot reliably
assign them from a still image
([Appendix E.4, E.7](./vson.md#appendix-e--related-work-and-bibliography)).

## The refusal is the engineering

One disposition, repeated: **the notation refuses to say more than it knows.** It will not
call a conformant document accurate, read a bounding box as a confirmation, treat two agreeing runs
as two correct ones, or accept a category it never declared. None of those refusals is a promise in a
document. Each is a gate with an exit code and a fixture that proves the gate is reached — the
difference between having a philosophy about a notation and having a notation.

— [Yaman Can](https://github.com/yamancan), 2026
