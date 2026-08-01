# VSON v1.2 — Visual Scene Ontology Notation

**Specification, Quick Start, Reference, JSON Schema, and Example Gallery — single document, RFC-style.**

| Field | Value |
|---|---|
| Status | v1.2 stable |
| Date | 2026-07-31 |
| Editors | Yamancan (github.com/yamancan) |
| Source repo | this repository (root: `visual-scene-ontology/`) |
| Normative source | this document; `docs/vson-x-semantics.md`; `shapes/vson-shapes.ttl`; `ontology/*.ttl`; `tools/schema/*.json` — ranked in §2 |
| Companion artifacts | `cli/` (Rust binary), `tools/penman/` (Python reference), `examples/gallery/` (16 scenes) |

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** are interpreted per RFC 2119 as updated by RFC 8174 — that is, only when they appear in all capitals.

**Layer names.** `VSO` is the OWL ontology (`ontology/*.ttl`). `VSV` is the closed value vocabularies VSO declares: RCC-8 relations, Allen relations, the directional and proximal values, and the thematic roles — §5.12 lists the enumerations that are closed to producer invention. `VSON-S` is the SHACL shapes layer (`shapes/vson-shapes.ttl`). `VSON-T`, `VSON-P`, and `VSON-X` are the three concrete syntaxes of §4.

---

## Table of contents

1. [Quick Start (image → graph in 60 seconds)](#1-quick-start)
2. [Conformance](#2-conformance)
3. [Concepts](#3-concepts)
4. [Concrete syntaxes](#4-concrete-syntaxes)
5. [Spec reference (per-field)](#5-spec-reference)
6. [JSON Schema and validation rules](#6-json-schema-and-validation-rules)
7. [Exporters](#7-exporters)
8. [Versioning and extension](#8-versioning-and-extension)
9. [Examples gallery (16 scenes)](#9-examples-gallery)
10. [Reference implementations](#10-reference-implementations)
11. [Migration from v0.1](#11-migration-from-v01)
12. [Changelog](#12-changelog)
13. [Teaching an AI image generator](#13-teaching-an-ai-image-generator)
14. [Appendix A — Consolidated JSON Schemas](#appendix-a)
15. [Appendix B — Penman EBNF](#appendix-b)
16. [Appendix C — Class registry](#appendix-c)
17. [Appendix D — VSON-X grammar (normative)](#appendix-d)
18. [Appendix E — Related work and bibliography](#appendix-e)

---

## 1. Quick Start

### 1.1 What you upload, what you get back

```
┌────────────┐    image bytes      ┌────────────────┐   JSON envelope     ┌──────────────────┐
│   client   │ ──────────────────▶ │   extractor    │ ──────────────────▶ │     consumer     │
│ (UI / API) │                     │ (web studio /  │                     │ (graph view,     │
│            │                     │  OpenRouter)   │                     │ Cypher, caption) │
└────────────┘                     └────────────────┘                     └──────────────────┘
```

The envelope is a single JSON document conforming to [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json). It carries:

- `vson_p` — Penman authoring text (the canonical authoring artifact; **MAY** be the empty string in a v1.1 envelope whose surface was VSON-X — see §6.1);
- `vson_x` (optional, v1.1+) — the compact sigil form, populated when VSON-X was the authoring surface;
- `vson_t` — Turtle 1.2 / Turtle-star (machine canonical, derivable from whichever authoring surface is populated);
- `graph` (optional) — `{nodes, edges}` projection for UI clients;
- `conformance.conforms` — SHACL pass/fail, always read together with `conformance.profile` (§6.1).

### 1.2 Install

```bash
git clone https://github.com/yamancan/visual-scene-ontology.git && cd visual-scene-ontology
pip install pyshacl rdflib                       # SHACL validator
cd cli && cargo build --release && cd ..         # Rust CLI (~30s cold)
```

### 1.3 First valid output in under 60 seconds

```bash
cli/target/release/vson validate examples/gallery/01_minimal.vson
# Validation Report
# Conforms: True
# OK  examples/gallery/01_minimal.vson

cli/target/release/vson convert p2t examples/gallery/01_minimal.vson
# @prefix vso:   <https://w3id.org/vson/v1/ontology#> .
# @prefix :      <https://example.org/scenes/anonymous#> .
# :scene a vso:Composition .
# :cam a vso:CameraView .
# :cam vso:angle "eye_level" .
# ...

cli/target/release/vson export cypher examples/gallery/01_minimal.vson
# CREATE (scene:Composition {id: 'scene'});
# CREATE (cam:CameraView {id: 'cam'});
# SET cam.angle = 'eye_level';
# ...
```

If the `Conforms: True` line printed, the document is a valid VSON v1.2 scene. **You are done with Quick Start.** The rest of this document is reference material.

### 1.4 First image → graph (preview)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python tools/extractor/baseline/extract.py --live --images path/to/image.jpg
# emits results.csv with one row per image:
#   image, shacl_first_try, shacl_after_retries, retries, latency_ms, ...
```

The studio at [`web/`](../web/) is a static site with no backend: extraction goes from the visitor's browser straight to OpenRouter on the visitor's own key, and validation runs in the browser too — a Pyodide worker executes the same two gates as `vson validate` (pyshacl SHACL, then owlrl OWL 2 RL), byte-pinned to the CLI in CI. This baseline eval runner calls the Anthropic API directly.

The runner returns a SHACL-conformant `vson_p` string per image. To produce the full envelope from §1.1, wrap that string with the metadata fields described in §6. A reference wrapper (`vson generate <image>`) is planned for a future CLI release; the `cli/` crate versions independently of this spec.

---

## 2. Conformance

A document is a **conformant VSON v1.2 document** iff all of the following hold:

| # | Requirement |
|---|---|
| C1 | It is a syntactically valid VSON-T (Turtle 1.2 / Turtle-star) **or** VSON-P (Penman) document per §4. |
| C2 | All IRIs it asserts under the VSO namespace resolve to a class or property declared in [`ontology/vso.ttl`](../ontology/vso.ttl), [`ontology/rcc8.ttl`](../ontology/rcc8.ttl), or [`ontology/allen.ttl`](../ontology/allen.ttl) — no orphan VSO terms. |
| C3 | Its triple set passes SHACL validation against [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) with `inference="rdfs"` and no violations. |
| C4 | Every `vso:Composition` declared in the document carries at least one `vso:depicts` edge. |
| C5 | Every `vso:SpatialFact` carrying a `vso:directional` predicate **MUST** also carry exactly one `vso:viewer` referencing a `vso:CameraView` (viewer anchoring — see §3.3). |
| C6 | Every `vso:Event`, `vso:Process`, and `vso:Stative` carries exactly one `vso:lemma` literal. |
| C7 | Every `vso:Quality` carries exactly one `vso:dimension` and one `vso:value`. |
| C8 | If `vso:rcc` appears, its value **MUST** be one of `rcc:DC`, `rcc:EC`, `rcc:PO`, `rcc:EQ`, `rcc:TPP`, `rcc:NTPP`, `rcc:TPPi`, `rcc:NTPPi`. |
| C9 | `vso:depicts` **MUST NOT** target a `vso:Frame`; frames attach via `vso:framedBy`. |

**Producer conformance.** A producer (extractor, generator, CLI) is conformant iff every document it emits satisfies C1–C9, validated by SHACL before emission.

**Consumer conformance.** A consumer is conformant iff it accepts every document satisfying C1–C9 without modification, and rejects (or flags) documents that do not.

**Verification.** The reference verifier is `cli/target/release/vson validate <file>`. Exit code 0 establishes C1 and C3–C9 — it parses the document and runs SHACL. Exit code 1 means at least one of those failed. **It does not establish C2**: no tool inspects a document for orphan VSO terms at validate time. C2 is covered instead by the C2 coverage test in `tests/`, which `make check` runs against the ontology.

**Normative precedence.** VSON's normative content is spread across five artifacts. When two of them disagree, the higher entry wins:

1. **this document** (`docs/vson.md`) — the contract;
2. [`docs/vson-x-semantics.md`](./vson-x-semantics.md) — for VSON-X surface semantics only (bearer dispatch, sigil routing, lemma aspect routing);
3. [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) — the SHACL shapes (VSON-S);
4. [`ontology/vso.ttl`](../ontology/vso.ttl), [`ontology/rcc8.ttl`](../ontology/rcc8.ttl), [`ontology/allen.ttl`](../ontology/allen.ttl) — the ontology (VSO/VSV);
5. [`tools/schema/*.json`](../tools/schema/) — the JSON Schemas for the wire envelope and the JSON-LD form.

Any conflict between two entries in this list is a bug. Resolve it by changing the lower-ranked artifact, or — if the lower-ranked artifact is right and this document is wrong — by fixing this document. Do not route around the disagreement.

### 2.1 What conformance establishes

Conformance is not one property. C1–C9 name three separable ones, checked by three different mechanisms, and a passing result establishes only what the mechanism that produced it examined.

| Construct | Mechanism | Clauses |
|---|---|---|
| **Syntactic well-formedness** | the parser for the surface the document is written in — VSON-T (§4.1), VSON-P (§4.2, Appendix B), VSON-X (§4.3, Appendix D) | C1 |
| **Structural well-formedness** | SHACL over [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) at `inference="rdfs"` | C3–C9 |
| **Internal consistency** | the OWL 2 RL closure of the document plus the TBox, checked for disjointness clashes ([`tools/owlrl_check.py`](../tools/owlrl_check.py)) | none — see below |

**Syntactic well-formedness.** The bytes parse into one RDF graph under the surface the document declares. A conformant document **MUST** parse (C1). Parsing establishes nothing about what the resulting graph says: a document asserting `vso:rcc "banana"` is syntactically well-formed, and so is one that describes the same object twice under two names.

**Structural well-formedness.** The parsed graph satisfies the shapes — the required edges are present, the cardinalities hold, the closed vocabularies of §5.12 are respected, and a directional fact carries its viewer (§3.3). A conformant document **MUST** satisfy C3–C9 with no violation. This is a statement about graph shape and nothing else: every value a shape does not constrain — a bounding box, a confidence, a lemma, a `vso:value` literal — is unexamined, and a structurally well-formed document **MAY** carry any of them. Where a clause is stated more tightly than the shape that enforces it, the clause is the requirement and the shape is incomplete; two such gaps are open — C5's *exactly one* `vso:viewer` and C6's *exactly one* `vso:lemma` on `vso:Process` and `vso:Stative` are enforced as *at least one*, so a document carrying two of either violates the clause and passes SHACL.

**Internal consistency.** The OWL 2 RL closure of the document together with the ontology contains no individual inferred into two classes VSO declares disjoint. This is the document's agreement with itself and with the TBox, and it is the one construct **no numbered clause requires**: C1–C9 do not mention it, while `vson validate` runs it as its second gate — the SHACL gate runs at `inference="rdfs"`, which does not process `owl:disjointWith` and therefore cannot see those clashes. A document **MAY** satisfy C1–C9 and still be OWL 2 RL inconsistent. A verifier **SHOULD** run both gates, and a consumer **MUST NOT** read "conformant" as meaning the closure was computed.

C2 belongs to none of the three. It is a vocabulary-closure property — no orphan VSO terms — and, as stated above, no tool checks it at validate time.

**None of the three establishes correspondence to the image.** Nothing in this specification reads pixels. A document asserting a red cube left of a blue sphere, describing a photograph that contains neither, parses, satisfies every shape, and has a clash-free closure: fully conformant, entirely false. Producers, consumers, exporters, and user interfaces **MUST NOT** describe a conformant document as accurate, correct, faithful, or verified against the image, and **MUST NOT** present a passing result as evidence that a claim about the depicted scene is true. A tool reporting one pass/fail verdict **SHOULD** name the constructs it checked.

**The absent construct is groundedness** — the property that each assertion in a document corresponds to what the image depicts. VSON v1.x defines no groundedness check, ships no groundedness evidence, and makes no groundedness claim. Establishing it would take at least two things this repository does not have:

1. **A geometry consistency decision.** Where a document already carries the geometry of §5.10, agreement between that geometry and the relations asserted over it is decidable *inside the document*: two `vso:bbox2d` rectangles determine which RCC-8 relation of C8 holds between them, and their positions under the viewer's `vso:CameraView` determine the directional values §3.3 anchors. A document whose `vso:rcc` contradicts its own boxes is ungrounded in a way that needs no image to detect — and nothing in v1.x detects it. This one is checkable and unchecked.
2. **Ground truth for what geometry cannot decide.** Class, dimension values, lemmas, thematic roles, and frame attributions do not follow from boxes. Evidence for those means comparison against human annotation over a fixed image set, with a published protocol and a reported inter-annotator agreement figure. No such corpus, protocol, or figure exists in this repository.

Until both exist, **verified** in VSON means *verified against the schema*. Any stronger reading is unsupported by anything this project ships.

---

## 3. Concepts

### 3.1 The five node kinds

| Kind | Examples | Purpose |
|---|---|---|
| **Frame** | `Composition`, `SceneContext`, `CameraView`, `VisualStyle` | Perspectival, authorial, or stylistic context. Scopes other content. |
| **Entity** | `PhysicalObject`, `Aggregate`, `Substance` | What the scene is "about" — depicted things. |
| **Quality** | dimension/value pair | Reified property (`color=red`, `affect=joyful`, `material=gold`). |
| **Perdurant** | `Event`, `Process`, `Stative` | Reified action/state. Carries thematic roles. |
| **SpatialFact** | viewer + figure + ground + RCC + directional | Reified spatial relation; directional facts require a viewer. |

Underneath those five kinds, [`ontology/vso.ttl`](../ontology/vso.ttl) declares a **DOLCE-inspired top-level taxonomy** — `vso:Endurant` / `vso:Perdurant` / `vso:Quality` / `vso:Region`, declared pairwise disjoint — after Masolo et al. 2003 ([Appendix E](#appendix-e)). *Inspired*, not aligned: VSON reuses the four category names and the endurant/perdurant cut, but hangs all four under `vso:Entity` (DOLCE puts regions under `Abstract`), imports no DOLCE IRI, and asserts no DOLCE axiom. Nothing in this document depends on a DOLCE reasoner.

### 3.2 Trait-bundle entity model

A v0.1 "Object" / "Item" / "Unique Object" / "Attribute" sigil mess is replaced by four orthogonal trait axes attached to every Entity:

```
individuation × animacy × countability × affordance
```

Translate:

| v0.1 idea | v1.0 trait bundle |
|---|---|
| "Generic object" | `individuation=Generic, animacy=Inert, countability=Count` |
| "Named character (Alice)" | `individuation=Named, animacy=Agentive, countability=Count` |
| "A handful of grain" | `individuation=Generic, countability=Mass` (Substance) |
| "A holdable item" | any class with `affordance ⊇ {Holdable}` |

### 3.3 Viewer anchoring (directional facts)

"The lamp is to the left of the chair." Left from whose vantage? Without a viewer, the assertion is ambiguous. **VSON enforces an explicit viewer at the schema level**: any `vso:SpatialFact` carrying a `vso:directional` value **MUST** also carry exactly one `vso:viewer` pointing at a `vso:CameraView`. Symmetric/topological facts (`rcc:EC`, `rcc:DC`) do not need a viewer.

Directional facts are viewer-anchored by schema — VSON commits to the relative frame of reference (Levinson 2003) and makes the anchor explicit and machine-checkable; intrinsic and absolute frames are out of scope for v1.x. Figure/ground asymmetry follows Talmy 2000: `vso:figure` is the located thing, `vso:ground` the reference thing, and the two slots are not interchangeable. Both citations are in [Appendix E](#appendix-e). (Shapes, tests, and tooling comments in this repository call the constraint "Talmy resolution" for historical reasons; the mechanism is the one described here.)

### 3.4 Reification — the universal pattern

If you might want to negate it, modify it, quantify it, refer to it, or attach a probability — make it a node, not an edge. Six places where v1.0 reifies what v0.1 left as edges or attributes:

- Action → `Event` / `Process` / `Stative` node + thematic roles;
- Property → `Quality` node + dimension/value;
- Spatial relation → `SpatialFact` node + figure/ground/rcc/directional/viewer;
- Negation → `Negation` node;
- Belief / propositional attitude → `BeliefState` node;
- Annotation (probability, source, confidence) → `Annotation` node (RDF 1.1-portable) **or** an RDF-star quoted-triple `<<s p o>> :prob "0.9"^^xsd:decimal` (canonical when a Turtle-star parser is available).

---

## 4. Concrete syntaxes

VSON has three surface syntaxes that share one abstract graph: VSON-T (canonical, machine), VSON-P (Penman, human authoring), and VSON-X (compact sigil-based, LLM-optimized — added in v1.1). VSON-T and VSON-P are graph-equivalent across all 16 gallery scenes. VSON-X counterparts exist for scenes 01–11 plus `12_persona` (12 files), and the tested round-trip covers 01–11 — see §4.3 and §9.17. Scenes 13–16 are Penman/Turtle only.

### 4.1 VSON-T (Turtle-star canonical, machine)

VSON-T is **W3C Turtle 1.2 with RDF-star quoted triples**, no syntactic deviation. Producers MUST be valid Turtle 1.2; consumers SHOULD use a standard Turtle parser (rdflib, Apache Jena, oxigraph). Canonical media type: `text/turtle`.

### 4.2 VSON-P (Penman authoring, human)

VSON-P is a Penman-style nested syntax (the same family used by AMR), tuned to the VSV vocabulary. Form:

```ebnf
document   = node ;
node       = "(" var [ "/" Concept ] role* ")" ;
role       = ":" name term ;
term       = node | var | literal ;
literal    = quoted-string | number | unit | bareword ;
var        = ID ;
Concept    = ID ;
name       = ID ;
ID         = /[A-Za-z_][\w-]*/ ;
```

Reentrancy: a `term` that is a bare `var` (no `/`) refers to a previously-declared node. Forward references are allowed; the transpiler does a pre-pass to register all declared variables before emission.

The reference transpiler is [`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py); the Rust port is [`cli/src/penman/`](../cli/src/penman/). Both consume [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json) as their single source of truth, so they cannot drift.

### 4.3 VSON-X (compact sigil-based, LLM-optimized) — v1.1

VSON-X is a bracket-free sigil syntax targeting LLM emission and human authoring. Nine sigils, bearer-class dispatch, newlines insignificant. Canonical media type: `text/vson-x` (proposed). File extension: `.x.vson` (the `.vson` suffix is preserved so the file still reads as a VSON document; the `vson` CLI selects the surface form by subcommand — `convert x2t` — not by sniffing the extension).

This section is the overview. The **normative grammar** — lexical productions, syntactic productions, the closed token vocabularies, and the complete parse-time error set — is [Appendix D](#appendix-d), reconciled line by line against the reference parser [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py). The per-key routing rationale is [`docs/vson-x-semantics.md`](./vson-x-semantics.md).

**Sigil set (closed):**

| Sigil | Kind | Example |
|---|---|---|
| `~` | Composition root | `~scene` |
| `/` | Concept marker | `/PhysicalObject`, `/CameraView` |
| `@` | Named/Skolem handle | `@alice`, `@cam` |
| `*` | Quality kv / direct property / role arg | `*color red` |
| `>` | Stative role-edge | `@bob > hold sword` |
| `>>` | Event/Process role-edge | `@bob >> strike boar *instrument sword` |
| `!` | Asymmetric SpatialFact | `crown ! EC @alice ^cam *dir above` |
| `&` | Symmetric SpatialFact (emits 2 nodes, figure/ground swapped) | `a & near & b` |
| `^` | Viewer anchor | `^cam` |

**Item boundaries.** Newlines are insignificant — no syntactic production has a NEWLINE terminal (the only line break the lexer notices is the one that ends a `#` comment). A new item begins when the parser sees a lead token at top level (`~`, `/Concept`, `^`, or a handle followed by `/`, `>`, `>>`, `!`, or `&`), so a single declaration may span several lines with arbitrary indentation, and a whole scene may equally be written on one line. Full rule and lookahead budget: [Appendix D](#appendix-d) §D.4; rationale in [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §3.7.

**Bearer-class dispatch for `*K V`** (the central rule):

| Bearer (LHS) | `*K V` is interpreted as |
|---|---|
| Composition (`~scene`) | Quality node (`vso:hasQuality`), with one exception: `*rendersAs` is a direct property |
| Frame (`/CameraView`, `/VisualStyle`, `/SceneContext`) | Direct property on the Frame |
| `/Persona` Frame | `vso:hasInvariant`-attached Quality node |
| Entity (`/PhysicalObject`, `/Aggregate`, `/Substance`) | Quality node (`vso:hasQuality`), with seven exceptions: `*class`, `*bbox2d`, `*position3d`, `*scale3d`, `*rotation`, `*visibleFraction`, `*embodies` are direct properties |
| Perdurant arglist (after `>` / `>>`) | Thematic role; the value is either a ref (entity) or a literal (e.g. `*manner swift`) |
| SpatialFact arglist (after `!`) | Direct property on the SpatialFact (`*dir above`, `*viewer @cam`) |

**Symmetric-by-construction.** The `&` form `a & near & b` MUST emit two SpatialFact nodes with figure/ground swapped (one with `figure=a, ground=b` and one with `figure=b, ground=a`), each with `vso:proximal=near`. This closes v0.1's asymmetry-by-fiat bug at the syntax level. The ontology's `vso:proximal` enum is the five-value closed list of §5.12; VSON-X's `&` form admits the three symmetric members of it (`near`, `far`, `adjacent`) — `next_to` and `facing` are proximal values but are not `&` lemmas in v1.1. Symmetric lemma with `!` (asymmetric form) is a parse error.

**Viewer anchoring.** `! ... *dir X` without a `^viewer` anchor is a parse error (matches the SHACL `vss:DirectionalNeedsViewerShape` constraint at the syntax layer).

**Lemma → kind table** (as shipped in [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py); see [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §5 for the rationale):

- Stative: `hold`, `wear`, `carry`, `own`, `sit`, `stand`, `lie`, `lean`, `look_at`, `gaze_at`, `see`, `hear`, `know`, `believe`, `intend` (signature: holder/experiencer + theme/stimulus).
- Event: `strike`, `throw`, `fall`, `give`, `send`, `arrive`, `depart`, `break`, `catch`, `drop`, `charge` (signatures: agent + theme/patient + recipient/etc.).
- Process: `run`, `walk`, `swim`, `fly`, `dance`, `burn`, `bleed`, `flow`, `pour` (signatures: agent/patient + theme).
- Symmetric proximal: `near`, `far`, `adjacent` (used only in `&` form). This list **is** closed — an unlisted `&` lemma is a parse error.

The three perdurant lists are routing tables, not a closed vocabulary: a lemma absent from all three is accepted and routed to a default signature (`>` → Stative with holder + theme; `>>` → Event with agent + patient). `>` with an Event/Process lemma OR `>>` with a Stative lemma is a parse error.

**Reference implementation:** [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py). Native Rust parser planned for v1.2; until then `vson convert x2t` shells out to Python.

**Round-trip parity.** Gallery scenes 01–11 (plus a `12_persona` X file) have an [`examples/gallery-x/N.x.vson`](../examples/gallery-x/) form (12 files); the test suite asserts each tested pair is graph-equivalent (modulo blank-node identity for auto-anonymous reified nodes; see [`tools/vson_x/equiv.py`](../tools/vson_x/equiv.py)) via `make x-check`. Round-trip coverage currently runs over scenes 01–11; `12_persona` is pending, and scenes 13–16 are Penman/Turtle only.

### 4.4 JSON-LD form

A VSON document MAY be exchanged as JSON-LD bound to context `https://w3id.org/vson/v1/context.jsonld`. Structural skeleton in [`tools/schema/vson-jsonld.schema.json`](../tools/schema/vson-jsonld.schema.json). Well-formedness is enforced by SHACL on the materialized graph, not by JSON Schema alone.

### 4.5 Image-extractor envelope (the Quick Start payload)

The wire format between an image-to-VSON extractor and its consumer is the JSON envelope in [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json). See §6.1 for the per-field reference. Every field is also annotated with its JSON Schema fragment in §6.

---

## 5. Spec reference

Per-field template:

> **`field_name`** *(type, required?)*
> — short description.
> **JSON Schema fragment.**
> **Validation rule.** SHACL shape or other constraint.
> *Example.*

### 5.1 Namespaces

| Prefix | IRI | Purpose |
|---|---|---|
| `vso:`   | `https://w3id.org/vson/v1/ontology#` | Core ontology and vocabulary |
| `vss:`   | `https://w3id.org/vson/v1/shapes#`   | SHACL shape names |
| `rcc:`   | `https://w3id.org/vson/v1/rcc8#`     | RCC-8 base relations |
| `allen:` | `https://w3id.org/vson/v1/allen#`   | Allen interval relations |
| `xsd:`   | `http://www.w3.org/2001/XMLSchema#` | Datatypes |
| `rdf:`   | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` | RDF |
| `rdfs:`  | `http://www.w3.org/2000/01/rdf-schema#` | RDFS |
| `sh:`    | `http://www.w3.org/ns/shacl#`   | SHACL |
| `:`      | `https://example.org/scenes/anonymous#` (default; consumers MAY override) | Document-local |

**Namespace host — resolved in v1.2.** Through v1.1 every canonical IRI above was minted under `https://vson.dev/`, a hostname this project never registered: squattable by anyone, permanently non-dereferenceable, and dependent on one maintainer paying one registrar forever. v1.2 remints all five namespaces under `https://w3id.org/vson/` — the W3C Permanent Identifier Community Group's redirect service, which is free, community-maintained, and designed to keep resolving after any single maintainer stops paying attention. That permanence is the property a namespace host has to have and a private domain cannot promise.

The old names are **withdrawn, not aliased.** There is no `owl:sameAs` bridge, no redirect, and no shape that targets them: a document minted under `https://vson.dev/` selects zero focus nodes against the v1.2 shapes and does not validate. Withdrawal is the honest option here precisely because the legacy names had **zero external consumers** — they never dereferenced, no third party could have resolved or cached them, and every producer and consumer of them lives in this repository. Aliasing would have preserved a name that was never real.

These IRIs are stable names, and they dereference. The documents behind them — three ontologies, both shape profiles, the JSON-LD context, and both JSON Schemas — are served at `https://vson.pages.dev/v1/`, a static site assembled from this repository by [`scripts/build_site.py`](../scripts/build_site.py); and since 2026-07-31, when the [w3id redirect](https://github.com/perma-id/w3id.org/pull/6471) merged, each canonical name resolves to its document. `https://w3id.org/vson/v1/ontology` answers `303 See Other` to `https://vson.pages.dev/v1/ontology.ttl`, as do the other four namespace documents; the context IRI and both schema `$id`s answer `302 Found` to theirs. Cite the `w3id.org` names, not the Pages paths: the names are the identifiers, the host is only where the bytes currently sit. [`scripts/check_live_claims.py`](../scripts/check_live_claims.py) (`make live-check`) re-checks all eight of those redirects against the live services and fails when a response contradicts this paragraph — deliberately outside `make check`, which stays answerable from the checkout alone. See §8 for the immutability rule and its one historical exception.

### 5.2 `vso:Composition`

The mereological root of a scene. Every conformant document **MUST** declare at least one Composition.

**Required edges**

#### `vso:depicts` *(IRI ref → Entity, required, 1..n)*
Lists the entities the composition depicts. **MUST NOT** target a `vso:Frame`.
```json
{ "type": "array", "minItems": 1, "items": { "type": "string" } }
```
**SHACL.** `vss:CompositionShape` requires `sh:minCount 1` on `vso:depicts`. `vss:FrameNotDepictedShape` forbids Frame targets.
*Example.* `:scene vso:depicts :alice .`

#### `vso:viewedBy` *(IRI ref → CameraView, exactly 1 when present)*
The composition's primary viewer. It **SHOULD** always be present, and it **MUST** be present whenever the document asserts any directional `SpatialFact` — that case is what C5 enforces, via `vss:DirectionalNeedsViewerShape` on the fact itself.

No shape constrains `vso:viewedBy` on a `vso:Composition` directly: a composition with zero directional facts and no `vso:viewedBy` passes SHACL today. The reference VSON-X parser does not close that gap either — it rejects `! ... *dir X` with no `^viewer` anchor, but accepts a composition with no top-level `^` anchor. `docs/vson-x-semantics.md` §4.10.1 specifies a stricter parser rule that is **not yet implemented**.
```json
{ "type": "string" }
```
*Example.* `:scene vso:viewedBy :cam .`

**Optional edges**

#### `vso:framedBy` *(IRI ref → Frame, optional, 0..n)*
Attaches scene-context, style, and additional camera frames.
*Example.* `:scene vso:framedBy :ctx, :style, :cam .`

#### `vso:rendersAs` *(IRI ref → VisualStyle, optional, 0..1)*
Designates which framedBy VisualStyle is the dominant aesthetic.

#### `vso:hasQuality` *(IRI ref → Quality, optional, 0..n)*
Composition-level qualities (e.g. `Layout=triangular`, `Focal=center`).

#### `vso:hasFact` *(IRI ref → SpatialFact, optional, 0..n)*
Spatial facts that hold within this composition.

#### `vso:occurs` *(IRI ref → Perdurant, optional, 0..n)*
Events / Processes / Statives observed within this composition. Producers MAY also use `vso:depicts` for perdurants; both are conformant.

### 5.3 Frame subtypes

#### 5.3.1 `vso:SceneContext`

| Field | Type | Required | Description | Validation |
|---|---|---|---|---|
| `vso:venue` | `xsd:string` (snake_case noun) | no | `throne_room`, `marketplace`, `forest_path`, `Unknown` | none |
| `vso:atmosphere` | `xsd:string` enum | no | `tense, calm, joyful, somber, mysterious, festive, ominous, neutral, romantic, energetic, Unknown` | enum check |
| `vso:timeOfDay` | `xsd:string` enum | no | `dawn, morning, noon, afternoon, dusk, night, Unknown` | enum check |
| `vso:weather` | `xsd:string` enum | no | `clear, cloudy, overcast, rain, snow, fog, storm, indoor, Unknown` | enum check |

```json
{
  "type": "object",
  "properties": {
    "@type":      { "const": "SceneContext" },
    "venue":      { "type": "string" },
    "atmosphere": { "enum": ["tense","calm","joyful","somber","mysterious","festive","ominous","neutral","romantic","energetic","Unknown"] },
    "timeOfDay":  { "enum": ["dawn","morning","noon","afternoon","dusk","night","Unknown"] },
    "weather":    { "enum": ["clear","cloudy","overcast","rain","snow","fog","storm","indoor","Unknown"] }
  }
}
```

#### 5.3.2 `vso:VisualStyle`

| Field | Type | Required | Description |
|---|---|---|---|
| `vso:aesthetic` | `xsd:string` | no | `photographic, oil_painting, watercolor, pencil_sketch, ink_drawing, 3d_render, pixel_art, vector_illustration, anime, comic_book, concept_art, studio_ghibli, disney_classic, cyberpunk, steampunk, noir, vaporwave, ai_diffusion, ai_realistic, ai_anime, Unknown` |
| `vso:palette` | `xsd:string` | no | `warm, cool, neutral, monochrome, high_contrast, pastel, muted, saturated, earth_tones, neon, Unknown` |
| `vso:medium` | `xsd:string` | no | `photograph, canvas, paper, digital, screen, fresco, mural, screenshot, scan, Unknown` |

#### 5.3.3 `vso:CameraView`

| Field | Type | Required | Description |
|---|---|---|---|
| `vso:angle` | `xsd:string` | no | `eye_level, low, high, dutch, top_down, worms_eye` |
| `vso:focalLength` | `xsd:string` | no | `"24mm"`, `"35mm"`, `"50mm"`, `"85mm"` (lensequivalent), or numeric mm |
| `vso:framing` | `xsd:string` | no | `extreme_close_up, close_up, medium_shot, wide_shot, extreme_wide_shot` |
| `vso:cameraPosition` | `xsd:string` | no | Free-form positional cue (`"front_left_dolly"`, `"overhead"`). |

#### 5.3.4 `vso:Persona` (v1.1)

A Persona is a Frame that carries the cross-document invariants of a recurring character (an actor, a fictional protagonist, a brand mascot). It is **disjoint from `Entity`** — a Persona is never depicted directly; instead, an Entity in a scene declares `vso:embodies` pointing at a Persona, and that Entity inherits the Persona's invariants for cross-scene consistency checks.

| Field | Type | Required | Description |
|---|---|---|---|
| `vso:hasInvariant` | `vso:Quality` | yes (≥1) | Each Persona MUST carry at least one Quality (e.g. `Hair=auburn`). |

```turtle
:alice_id a vso:Persona ;
  vso:hasInvariant [ a vso:Quality ; vso:dimension vso:Hair ; vso:value "auburn" ] ,
                   [ a vso:Quality ; vso:dimension vso:Eye  ; vso:value "green"  ] .

:alice a vso:PhysicalObject ;
  vso:individuation vso:Named ; vso:animacy vso:Agentive ;
  vso:class :Knight ;
  vso:embodies :alice_id .
```

`vss:EmbodimentConsistencyShape` (Warning severity) flags scenes where an Entity's Quality contradicts its Persona's invariant for the same dimension. SHACL violation here is a *suggestion*, not a hard failure — scene-level Quality always wins (a character can be wounded, costumed, transformed); the shape exists to catch authoring mistakes, not to enforce immutability.

### 5.4 `vso:PhysicalObject` (and `vso:Aggregate`, `vso:Substance`)

Concrete entities in the scene. Subtypes share trait axes; differ only in countability defaults and inferred class.

**Required traits (every Entity)**

**Enforcement.** These four are required by this specification, but the shapes constrain them only *where the property appears*: `vss:IndividuationShape`, `vss:AnimacyShape`, and `vss:CountabilityShape` each use `sh:targetSubjectsOf` on their own property, and nothing constrains `vso:class` at all. No shape and no clause in §2 requires an Entity to carry any of them, so an Entity that omits all four still passes SHACL. Completeness here is a producer obligation.

#### `vso:individuation` *(IRI, required, exactly 1)*
One of `vso:Generic`, `vso:Named`, `vso:Kind`, `vso:Skolem`.
```json
{ "enum": ["Generic", "Named", "Kind", "Skolem"] }
```
**SHACL.** `vss:IndividuationShape` pins `sh:in (vso:Generic vso:Named vso:Kind vso:Skolem)` with `sh:maxCount 1`. (`vss:AnimacyShape` and `vss:CountabilityShape` do the same for their axes.)

#### `vso:animacy` *(IRI, required, exactly 1)*
One of `vso:Agentive`, `vso:Inert`. Agents — humans, animals, animated mechanisms — get `Agentive`. Inanimate matter — furniture, vegetation, weapons-at-rest — gets `Inert`.

#### `vso:countability` *(IRI, required, exactly 1)*
One of `vso:Count`, `vso:Mass`, `vso:Collective`. Substances are Mass; Aggregates are Collective; otherwise Count.

#### `vso:class` *(string bareword or IRI, required, exactly 1)*
Domain class — see Appendix C registry. Use `Unknown` rather than guessing.

**Optional traits/edges**

#### `vso:affordance` *(IRI, optional, 0..n)*
Subset of `{Holdable, Wearable, Mountable, Container, Edible}` — a closed list (§5.12): `vss:AffordanceShape` rejects any other value, and unlike its three sibling axes it carries no `sh:maxCount`, so an Entity MAY offer several. Reasoner-friendly; consumers MAY use it to filter.

#### `vso:hasQuality` *(IRI ref → Quality, 0..n)*
Per-entity qualities.

#### `vso:bbox2d` *(string, optional, 0..1)*
Normalized 2D bounding box in `"x,y,w,h"` form, all components in `[0, 1]`.
```json
{ "type": "string", "pattern": "^(0|0\\.\\d+|1|1\\.0+),(0|0\\.\\d+|1|1\\.0+),(0|0\\.\\d+|1|1\\.0+),(0|0\\.\\d+|1|1\\.0+)$" }
```

### 5.5 `vso:Quality`

Reified property. Always a node, never an inline literal on the bearer.

| Field | Type | Required | Description | Validation |
|---|---|---|---|---|
| `vso:dimension` | IRI | yes (1) | A registered VSO dimension (table below), or an IRI in the document's own namespace | `vss:QualityShape` requires exactly 1 |
| `vso:value` | bareword/string/integer | yes (1) | Per dimension's enum or free-form | exactly 1 |

```json
{
  "type": "object",
  "required": ["@type", "dimension", "value"],
  "properties": {
    "@type":     { "const": "Quality" },
    "dimension": { "type": "string" },
    "value":     { "type": ["string", "number"] }
  }
}
```

**SHACL.** `vss:QualityShape` enforces `sh:property [ sh:path vso:dimension; sh:minCount 1; sh:maxCount 1 ]` and the same for `vso:value`.

#### 5.5.1 Dimension registry (closed under the VSO namespace)

**The registry is closed.** The VSO namespace carries exactly the twenty-one dimensions below — no others. A `vso:dimension` whose value is any other IRI under `https://w3id.org/vson/v1/ontology#` is an orphan VSO term and the document is **non-conformant** by clause C2 (§2). Producers **MUST NOT** mint new `vso:` dimensions.

**Extension stays open.** A dimension the registry does not carry is minted under the producer's *own* namespace, never under `vso:` — `[ a vso:Quality ; vso:dimension :Reflectance ; vso:value "matte" ]` with `:` bound to the document namespace is conformant, and is profile-specific rather than portable (§8). This is the only sanctioned way to extend the axis set inside v1.x.

| Dimension | Bearer | Reading |
|---|---|---|
| `vso:Color` | Entity | Perceived colour |
| `vso:Weight` | Entity | Heaviness as read off the scene, not measured |
| `vso:Material` | Entity | What it is made of (stone, silk, iron) |
| `vso:Affect` | Entity | Mood or emotional state |
| `vso:Age` | Entity | Years, or an age band |
| `vso:Role` | Entity | Social or narrative role (queen, knight) |
| `vso:Size` | Entity | Relative size |
| `vso:Enchantment` | Entity | Magical or supernatural property |
| `vso:ActionState` | Entity | Transient action phase (drawn, raised, running) |
| `vso:Layout` | Composition | How the scene is arranged |
| `vso:Focal` | Composition | What the scene draws attention to |
| `vso:Amount` | Entity | Quantity, for Substances and Aggregates read by amount not count |
| `vso:Hair` | Entity / Persona | Hair colour or length (auburn, black_short) |
| `vso:Hairstyle` | Entity / Persona | Cut or styling (bob, braided, ponytail) |
| `vso:Skin` | Entity / Persona | Skin tone or complexion |
| `vso:Eye` | Entity / Persona | Eye colour |
| `vso:Eyewear` | Entity | Eyewear worn (sunglasses, round_frames) |
| `vso:Headwear` | Entity | Headwear worn (beanie, wide_brim_hat) |
| `vso:Outfit` | Entity | Garment or ensemble read as a whole |
| `vso:Fit` | Entity | How a garment sits (oversized, tailored, cropped) |
| `vso:Pose` | Entity / Persona | Bodily posture |

The **Bearer** column is guidance for producers, not a constraint: no shape ties a dimension to a bearer class, so `vso:Layout` on an Entity parses and validates. The compositional pair (`Layout`, `Focal`) attaches to the `vso:Composition` root; the rest attach to an Entity, and the appearance axes double as `vso:Persona` invariants (§5.3.4).

**Reaching them from the other syntaxes.** VSON-P names the dimension directly (`:dimension Layout`). VSON-X derives it from the `*key` by PascalCasing (`*action_state` → `ActionState`), and that derivation is mechanical — a key outside this table produces a `vso:` IRI outside the registry, which is the C2 failure above, not a warning. [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §3.2.1 lists the twenty keys the extractor skill is tuned to emit; that list is a subset of this table (it omits `Eye`), not a second registry.

**Where this list is enforced.** `ontology/vso.ttl` declares all twenty-one as `vso:Dimension` individuals and names all twenty-one in one `owl:AllDifferent` — necessary because `vso:dimension` is an `owl:FunctionalProperty`, so a Quality asserting two dimensions collapses them to `owl:sameAs` under `prp-fp`, and only pairwise distinctness turns that collapse into a reported clash (§5.9). A member missing from the `owl:AllDifferent` list is a member that can silently collapse. Membership itself is checked by the C2 coverage test in `tests/`, not by SHACL: `vss:QualityShape` deliberately carries no `sh:in` on `vso:dimension`, because such an enum would reject the document-namespace dimensions that §8 keeps conformant. `shapes/vson-shapes.ttl` records that reasoning beside the shape.

### 5.6 `vso:Event` / `vso:Process` / `vso:Stative`

Reified perdurants. Differ in aspectual character:

| Class | Aspect | Examples |
|---|---|---|
| `vso:Event` | punctual / completable | `strike, throw, fall, give, arrive` |
| `vso:Process` | durative, atelic | `run, dance, burn, bleed, pour` |
| `vso:Stative` | continuous state | `hold, wear, look_at, sit, believe` |

#### `vso:lemma` *(xsd:string, required, exactly 1)*
Snake_case verb naming the perdurant.
```json
{ "type": "string", "pattern": "^[a-z][a-z0-9_]*$" }
```
**SHACL.** `vss:EventShape` requires `sh:datatype xsd:string; sh:minCount 1; sh:maxCount 1` on `vso:lemma`. `vss:ProcessShape` and `vss:StativeShape` require `sh:datatype xsd:string; sh:minCount 1` but set no cap, so C6's "exactly one" is fully shape-enforced only for `vso:Event`; on Process and Stative a second lemma is a spec violation that `vson validate` does not report.

**Thematic roles (zero or more, depending on class)**

The role inventory below is closed and deliberately coarse — VerbNet-style thematic roles (Kipper Schuler 2005) rather than predicate-specific argument slots. PropBank (Palmer, Gildea & Kingsbury 2005) numbers arguments per verb sense (`ARG0` of *give* is not `ARG0` of *melt*), and FrameNet (Baker, Fillmore & Lowe 1998) names them per semantic frame (`Donor`, `Recipient`, `Theme`); both give a finer analysis than a vision-language model can reliably produce from a still image, and both require a per-predicate lexicon that VSON does not ship. VSON therefore takes the third option: one small, frame-independent role set a producer can memorize. It is closed by C2 (§2) — an invented `vso:` role is an orphan VSO term — and not by any SHACL shape, so `vson validate` will not flag it; Appendix D §D.8 note 6 records the same gap in the VSON-X parser. Citations in [Appendix E](#appendix-e); the AMR exporter mapping in §7 is where PropBank's per-sense numbering resurfaces.

| Predicate | Used on | Description |
|---|---|---|
| `vso:agent` | Event, Process | Volitional doer |
| `vso:patient` | Event | Affected entity |
| `vso:theme` | Event, Process, Stative | Entity in a relation/state |
| `vso:instrument` | Event | Means / tool |
| `vso:recipient` | Event | Goal-receiver in transfers |
| `vso:source` | Event | Origin in transfers |
| `vso:goal` | Event, Process | Target / destination |
| `vso:beneficiary` | Event | For-whose-benefit |
| `vso:experiencer` | Stative | Sentient in cognitive/perceptual state |
| `vso:stimulus` | Stative | What the experiencer is oriented toward |
| `vso:holder` | Stative | Possessor in `hold/wear/own` |
| `vso:manner` | any | Bareword adverbial (`swift, careful, forceful`) |
| `vso:cause` / `vso:result` | Event | Causal / resultative linkage |
| `vso:location` / `vso:time` | any | Spatial / temporal grounding |

```json
{
  "type": "object",
  "required": ["@type", "lemma"],
  "properties": {
    "@type":      { "enum": ["Event", "Process", "Stative"] },
    "lemma":      { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" },
    "agent":      { "type": "string" },
    "patient":    { "type": "string" },
    "theme":      { "type": "string" },
    "instrument": { "type": "string" },
    "recipient":  { "type": "string" },
    "experiencer":{ "type": "string" },
    "stimulus":   { "type": "string" },
    "holder":     { "type": "string" },
    "manner":     { "type": "string" }
  }
}
```

### 5.7 `vso:SpatialFact`

Reified spatial relation. Carries figure, ground, optional viewer, and one or more of `rcc/directional/proximal`.

`vso:rcc` takes the eight RCC-8 base relation names of Randell, Cui & Cohn 1992 ([Appendix E](#appendix-e)). VSON ships them as a **closed value vocabulary, not as the calculus**: [`ontology/rcc8.ttl`](../ontology/rcc8.ttl) declares the eight as individuals of `rcc:Relation` and asserts only that they denote distinct values. Jointly-exhaustive-pairwise-disjoint holds in the intended interpretation, not as an axiom, and no composition table ships — given `NTPP(a,b)` and `NTPP(b,c)`, VSON derives nothing about `a` and `c`. Each of the eight carries a `skos:closeMatch` to its OGC GeoSPARQL counterpart (`geo:rcc8dc` …); see the design note in §5.9 for why the GeoSPARQL IRIs are not used directly.

| Field | Type | Required | Description | Validation |
|---|---|---|---|---|
| `vso:figure` | IRI ref → Entity | yes (1) | The thing being located | `vss:SpatialFactShape` |
| `vso:ground` | IRI ref → Entity | yes (1) | The reference frame | `vss:SpatialFactShape` |
| `vso:rcc` | IRI in `rcc:` | no (0..1) | One of `DC, EC, PO, EQ, TPP, NTPP, TPPi, NTPPi` | `vss:RccValueShape` |
| `vso:directional` | IRI in VSO | no (0..1) | `above, below, left_of, right_of, in_front_of, behind` | requires viewer |
| `vso:proximal` | IRI in VSO | no (0..1) | `near, far, adjacent, next_to, facing` | `vss:ProximalValueShape` |
| `vso:viewer` | IRI ref → CameraView | conditional | **MUST** be present when `vso:directional` is present (C5) | `vss:DirectionalNeedsViewerShape` |

```json
{
  "type": "object",
  "required": ["@type", "figure", "ground"],
  "properties": {
    "@type":       { "const": "SpatialFact" },
    "figure":      { "type": "string" },
    "ground":      { "type": "string" },
    "rcc":         { "enum": ["DC","EC","PO","EQ","TPP","NTPP","TPPi","NTPPi"] },
    "directional": { "enum": ["above","below","left_of","right_of","in_front_of","behind"] },
    "proximal":    { "enum": ["near","far","adjacent","next_to","facing"] },
    "viewer":      { "type": "string" }
  },
  "if":   { "required": ["directional"] },
  "then": { "required": ["viewer"] }
}
```

**SHACL.** `vss:DirectionalNeedsViewerShape` raises a violation when `vso:directional` is present without `vso:viewer`. Negative fixture: [`tests/fixtures/bad_no_viewer.ttl`](../tests/fixtures/bad_no_viewer.ttl). The shape checks presence (`sh:minCount 1`) and that the viewer is a `vso:CameraView`; it does not cap the count, so C5's "exactly one" is a spec-level requirement that no validator checks today. A viewer on a purely topological fact is permitted — the implication runs directional ⇒ viewer, not the converse.

### 5.8 Mereology

| Predicate | Description | OWL characteristics |
|---|---|---|
| `vso:partOf` | x is part of y | `owl:TransitiveProperty`; inverse of `hasPart` |
| `vso:hasPart` | y has part x | `owl:TransitiveProperty`; inverse of `partOf` |
| `vso:properPartOf` | x is a proper part of y | sub-property of `partOf`, irreflexive |
| `vso:overlaps` | x and y share a part | symmetric |
| `vso:disjoint` | x and y share no part | symmetric |

### 5.9 Causal and Allen interval

#### Causal

`vso:causes`, `vso:enables`, `vso:prevents`, `vso:triggers` between Perdurants. Causal claims **SHOULD** be rare and high-confidence; producers SHOULD attach an `vso:Annotation` with confidence < 1.0 by default.

#### Allen interval (Perdurant ↔ Perdurant)

`allen:before`, `allen:after`, `allen:meets`, `allen:metBy`, `allen:overlaps`, `allen:overlappedBy`, `allen:starts`, `allen:startedBy`, `allen:during`, `allen:contains`, `allen:finishes`, `allen:finishedBy`, `allen:equals` — the thirteen base relations of Allen 1983 ([Appendix E](#appendix-e)). Inverses are declared in [`ontology/allen.ttl`](../ontology/allen.ttl); `owl:TransitiveProperty` is asserted on exactly the members that compose with themselves (`before/after`, `during/contains`, `starts/startedBy`, `finishes/finishedBy`, `equals`), so `meets` and `overlaps` carry no transitivity axiom. As with RCC-8, the composition table itself is out of scope. Each of the thirteen carries a `skos:closeMatch` to its W3C OWL-Time counterpart (`time:intervalBefore` …).

#### Design note — why not reuse the `time:` and `geo:` IRIs directly

VSON declares its own `rcc:` and `allen:` terms instead of asserting OWL-Time and GeoSPARQL properties, for two different reasons:

- **RCC-8 (`geo:`).** GeoSPARQL models its RCC-8 terms as **binary object properties between features** (`:a geo:rcc8ntpp :b`). VSON models them as **enumerated values on a reified `vso:SpatialFact`** (`:sf vso:rcc rcc:NTPP`), because the fact node is what carries the viewer, the figure/ground asymmetry, and any `vso:Annotation` (§5.11). Dropping `geo:rcc8ntpp` in as a predicate would mean abandoning the reification pattern — and with it the C5 viewer guarantee and per-fact confidence.
- **Allen (`time:`).** These *are* object properties in VSON, so the shape matches; the typing does not. OWL-Time types its interval relations on `time:ProperInterval`, whereas VSON types them on `vso:Perdurant` — a node that carries a lemma and thematic roles and need not be given any interval extent at all. Asserting `time:intervalBefore` between two Perdurants would entail that both are proper intervals — a commitment VSON does not make and its documents do not warrant.

So the bridge is advisory rather than substitutive: each VSON relation individual (RCC-8) and each VSON relation property (Allen) carries a `skos:closeMatch` to its GeoSPARQL / OWL-Time counterpart. `skos:closeMatch` records the shared reading and imports **no** OWL entailment — a consumer that wants GeoSPARQL or OWL-Time triples must rewrite them itself, and no VSON gate checks that rewrite. Both alignment sets live in [`ontology/rcc8.ttl`](../ontology/rcc8.ttl) and [`ontology/allen.ttl`](../ontology/allen.ttl).

#### What the OWL 2 RL layer actually infers

"OWL 2 RL" in this stack is a small, concrete set of entailments, not a general reasoning claim. `vson validate` and `make check` materialize the OWL 2 RL closure of (ontology + document) with `owlrl` and inspect it — [`tools/owlrl_check.py`](../tools/owlrl_check.py). What that buys, in practice:

- **Mereological transitivity.** `vso:partOf` and `vso:hasPart` are transitive and mutually inverse, and `vso:properPartOf` is a sub-property of `partOf`; so `hilt partOf sword`, `sword partOf knight` entails `hilt partOf knight`, and every assertion has its inverse materialized.
- **Temporal inverses and transitivity.** `allen:after owl:inverseOf allen:before` (and the other five inverse pairs), plus transitivity on the self-composing members listed above.
- **Symmetry.** `vso:overlaps`, `vso:disjoint`, and `allen:equals` are `owl:SymmetricProperty`, so one asserted direction yields both. The proximal values are *not* covered: `near`/`adjacent`/`next_to` are individuals valued on a fact, not properties, and their symmetry is produced at emission time by the VSON-X `&` form (two facts with figure and ground swapped) — no axiom does it.
- **Disjointness clashes.** `vso:Frame owl:disjointWith vso:Entity`, the `Endurant/Perdurant/Quality/Region` disjointness set, and the pairwise-disjoint Frame and Perdurant subtypes. A node dragged into two disjoint classes — typically by a property's `rdfs:domain` or `rdfs:range` — is reported as a clash.
- **Functional-property clashes.** `vso:individuation`, `vso:animacy`, `vso:countability`, `vso:dimension`, `vso:figure`, and `vso:ground` are `owl:FunctionalProperty`, so two values on one node collapse to `owl:sameAs` under OWL 2 RL's `prp-fp` rule. For the four trait/dimension properties that collapse is *detectable*, because their value sets are declared `owl:AllDifferent` — an entity with two `vso:individuation` values is reported. `owlrl_check.py` raises that contradiction itself, since `owlrl` 7.1.4 (the pinned floor) does not expand `owl:AllDifferent` into `owl:differentFrom`. `vso:figure` and `vso:ground` have no such distinctness declaration to violate, so two figures on one fact are quietly equated rather than reported.

What it does **not** buy: no spatial or temporal composition tables, no cardinality reasoning beyond the functional properties above, and nothing at all from the SHACL gate — that runs with `inference="rdfs"`, which never processes `owl:disjointWith`. The two gates are complementary, which is why `vson validate` runs both. Eight bridge properties are also left as untyped `rdf:Property` to admit mixed literal / IRI / quoted-triple objects, which places the full graph outside OWL 2 DL; the RL rule set still applies, since OWL 2 RL is specified as rules over arbitrary RDF graphs.

### 5.10 Geometry

| Predicate | Type | Description |
|---|---|---|
| `vso:bbox2d` | `xsd:string` `"x,y,w,h"`, normalized [0,1] | 2D bounding box |
| `vso:position3d` | `xsd:string` `"x,y,z"` | 3D position (if known) |
| `vso:scale3d` | `xsd:string` `"sx,sy,sz"` | 3D scale |
| `vso:rotation` | `xsd:string` quaternion or Euler | 3D orientation |
| `vso:occludes` | IRI ref → Entity | Foreground occluder |
| `vso:visibleFraction` | `xsd:decimal` in `[0,1]` | Visible fraction post-occlusion |

### 5.11 Annotation reification

Used for probability, source, confidence, or any meta-claim about a triple.

```turtle
:ann1 a vso:Annotation ;
    vso:annotatedSubject :sf1 ;
    vso:annotatedPredicate vso:directional ;
    vso:annotatedObject vso:above ;
    vso:probability "0.85"^^xsd:decimal ;
    vso:source "extractor:claude-opus-4-7" .
```

The RDF-star canonical form `<<:sf1 vso:directional vso:above>> vso:probability "0.85"` is equivalent and **SHOULD** be used when a Turtle-star parser is available. Both forms are conformant per §2.

### 5.12 Reserved + closed enumerations (full list)

Producers **MUST NOT** invent values for closed enumerations. Open dimensions (`venue`, `class`, free-form quality values) MAY take novel values; if uncertain, use `Unknown`.

| Enum | Closed values |
|---|---|
| `vso:individuation` | `Generic, Named, Kind, Skolem` |
| `vso:animacy` | `Agentive, Inert` |
| `vso:countability` | `Count, Mass, Collective` |
| `vso:affordance` | `Holdable, Wearable, Mountable, Container, Edible` (`vss:AffordanceShape`; multi-valued, so no `sh:maxCount`) |
| `vso:rcc` | `rcc:DC, rcc:EC, rcc:PO, rcc:EQ, rcc:TPP, rcc:NTPP, rcc:TPPi, rcc:NTPPi` |
| `vso:directional` | `above, below, left_of, right_of, in_front_of, behind` |
| `vso:proximal` | `near, far, adjacent, next_to, facing` (five values — `vss:ProximalValueShape`; VSON-X's `&` form admits only the first three) |
| `vso:dimension` | The twenty-one registered dimensions of §5.5.1 — closed *within the VSO namespace* only. Unlike the rows above, no shape enumerates them: a document-namespace dimension IRI stays conformant, and a `vso:`-namespace one outside the registry fails C2 rather than C3. |

---

## 6. JSON Schema and validation rules

VSON has **two layers of validation**:

| Layer | Tool | Scope | Failure mode |
|---|---|---|---|
| Structural (envelope shape) | JSON Schema | Wire payload only | rejects malformed envelopes |
| Semantic (graph well-formedness) | SHACL | Materialized RDF graph | rejects scenes that violate VSO constraints |

A document MUST pass both. JSON Schema alone is insufficient — it cannot express "directional needs viewer" or "Composition needs at least one depicts." SHACL is the load-bearing validator; JSON Schema is a fast structural pre-check.

### 6.1 The extractor envelope schema

**File:** [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json). Reproduced inline for §5-style cross-reference. The envelope is closed (`additionalProperties: false`): `scene_id`, `version`, `vson_p`, `vson_t`, and `conformance` are required keys, and any top-level key not listed below is a validation error.

#### `scene_id` *(string, required)*
Stable, URL-safe scene identifier. ≤64 chars, `[A-Za-z0-9_-]`.
```json
{ "type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$" }
```

#### `version` *(string, required)*
The VSON spec version: `"1.0"` (strict), `"1.0.5"` (v1.0 + caption renderer + Phase 0 ontology additions), or `"1.1"` (adds the VSON-X surface form and the partial validation profile). Backwards-compatible — every v1.0 envelope remains valid under newer spec versions.
```json
{ "enum": ["1.0", "1.0.5", "1.1"] }
```

#### `source` *(object, optional)*
Provenance of the scene. Producers **SHOULD** populate it for any non-hand-authored scene. The schema does not enforce this — `source` is optional unconditionally, and only `source.kind` is required once the object is present.
```json
{
  "type": "object",
  "required": ["kind"],
  "properties": {
    "kind":   { "enum": ["image","video_frame","synthetic","hand_authored"] },
    "uri":    { "type": "string", "format": "uri" },
    "sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
    "width_px":   { "type": "integer", "minimum": 1 },
    "height_px":  { "type": "integer", "minimum": 1 },
    "captured_at":{ "type": "string", "format": "date-time" }
  }
}
```

#### `vson_p` *(string, required as a key; conditionally non-empty)*
The Penman authoring text. The key is always required, but its minimum length is version-conditional:

- `version` ∈ {`"1.0"`, `"1.0.5"`} — `minLength: 3`. Penman is the source of truth.
- `version` = `"1.1"` — `vson_p` MAY be the empty string `""` when the authoring surface was VSON-X (back-conversion to Penman waits on `t2p` in v1.2). An `anyOf` then requires that **at least one** of `vson_p` / `vson_x` be non-empty.

```json
{ "type": "string" }
```
```json
{ "allOf": [
  { "if":   { "properties": { "version": { "enum": ["1.0", "1.0.5"] } } },
    "then": { "properties": { "vson_p": { "minLength": 3 } } } },
  { "if":   { "properties": { "version": { "const": "1.1" } } },
    "then": { "anyOf": [ { "properties": { "vson_p": { "minLength": 3 } } },
                         { "properties": { "vson_x": { "minLength": 3 } } } ] } }
] }
```

#### `vson_x` *(string, optional — v1.1+)*
The VSON-X (compact sigil-based) form. Populated when the authoring or extraction surface was VSON-X. Surface semantics: [`docs/vson-x-semantics.md`](./vson-x-semantics.md).
```json
{ "type": "string" }
```

#### `vson_t` *(string, required)*
Turtle 1.2 / Turtle-star derived from `vson_p` or `vson_x` via the reference transpiler. Always non-empty — this is the field a consumer parses when it wants triples.
```json
{ "type": "string", "minLength": 3 }
```
**Validation rule.** Compiling whichever authoring surface is populated MUST equal `vson_t` modulo blank-node renaming and triple ordering.

#### `graph` *(object, optional)*
UI-friendly projection: `{nodes: [...], edges: [...]}`. Lossy w.r.t. RDF-star annotations; consumers needing full fidelity MUST use `vson_t`.

#### `graph.nodes[*]` *(GraphNode array)*
```json
{
  "type": "object",
  "required": ["id", "kind"],
  "properties": {
    "id":   { "type": "string", "pattern": "^[A-Za-z_][\\w-]*$" },
    "kind": { "enum": ["Composition","SceneContext","VisualStyle","CameraView","PhysicalObject","Aggregate","Substance","Event","Process","Stative","Quality","SpatialFact","Annotation"] },
    "class":{ "type": "string" },
    "traits":{
      "type": "object",
      "properties": {
        "individuation":{ "enum": ["Generic","Named","Kind","Skolem"] },
        "animacy":      { "enum": ["Agentive","Inert"] },
        "countability": { "enum": ["Count","Mass","Collective"] },
        "affordance":   { "type": "array", "items": { "type": "string" } }
      }
    },
    "properties": { "type": "object" },
    "bbox2d":     { "type": "string" }
  }
}
```

#### `graph.edges[*]` *(GraphEdge array)*
```json
{
  "type": "object",
  "required": ["from", "to", "label"],
  "properties": {
    "from":  { "type": "string" },
    "to":    { "type": "string" },
    "label": { "type": "string" },
    "qualifiers": { "type": "object" }
  }
}
```

#### `conformance` *(object, required)*
SHACL report. `conforms` is always relative to the profile named in `profile`.

#### `conformance.profile` *(string enum, optional — v1.1+, default `"strict"`)*
Which shapes file produced the report: `"strict"` uses [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) (v1.0 byte-identical behaviour); `"relaxed"` uses [`shapes/vson-shapes-relaxed.ttl`](../shapes/vson-shapes-relaxed.ttl), which demotes the dimension-completeness constraints — viewer anchoring, the Event/Process/Stative lemma, Quality dimension+value, Quality modifier — to `sh:Warning` for authoring-time documents. Structural-integrity constraints stay `sh:Violation` in both profiles. As of v1.1 no shipped command selects the relaxed file (neither the Rust CLI nor the Python reference exposes a `--partial` flag); it is exercised by the shapes-gate test in `tests/`, and the field exists so that a producer which validates against it can say so.

**Consumer contract.** Consumers **MUST** inspect both `conforms` and `profile` to determine document status: `conforms=true` under the relaxed profile is **NOT** v1.0 conformance.
```json
{
  "type": "object",
  "required": ["conforms"],
  "properties": {
    "conforms": { "type": "boolean" },
    "profile":  { "enum": ["strict", "relaxed"], "default": "strict" },
    "violations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["message", "shape"],
        "properties": {
          "message":     { "type": "string" },
          "shape":       { "type": "string" },
          "focus_node":  { "type": "string" },
          "result_path": { "type": "string" },
          "severity":    { "enum": ["Violation","Warning","Info"] }
        }
      }
    }
  }
}
```

#### `extraction` *(object, optional)*
Producer-side metadata — model, prompt version, retry count, latency, token counts, overall confidence. Useful for telemetry; not normative.

### 6.2 Worked envelope example (image upload response)

```json
{
  "scene_id": "throne_room_01",
  "version": "1.0",
  "source": {
    "kind": "image",
    "uri": "https://example.org/uploads/throne_room.jpg",
    "sha256": "276f043f7971a3b965ee59811dc4663a4fc52f32f7173fcdffebcbc1a244ae71",
    "width_px": 1024,
    "height_px": 768,
    "captured_at": "2026-05-02T11:14:00Z"
  },
  "vson_p": "(scene / Composition :viewedBy (cam / CameraView :angle low :focalLength 35mm :framing medium_shot) :depicts (alice / PhysicalObject :individuation Named :animacy Agentive :countability Count :class Human))",
  "vson_t": "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n:scene a vso:Composition .\n:scene vso:viewedBy :cam .\n...",
  "graph": {
    "nodes": [
      { "id": "scene", "kind": "Composition" },
      { "id": "cam",   "kind": "CameraView", "properties": { "angle": "low", "focalLength": "35mm", "framing": "medium_shot" } },
      { "id": "alice", "kind": "PhysicalObject", "class": "Human",
        "traits": { "individuation": "Named", "animacy": "Agentive", "countability": "Count" } }
    ],
    "edges": [
      { "from": "scene", "to": "cam",   "label": "viewedBy" },
      { "from": "scene", "to": "alice", "label": "depicts"  }
    ]
  },
  "conformance": { "conforms": true },
  "extraction": {
    "model": "claude-opus-4-7",
    "prompt_version": "orchestrator-system@1.0",
    "shacl_retries": 0,
    "latency_ms": 4800,
    "input_tokens": 7421,
    "output_tokens": 1083,
    "confidence_overall": 0.91
  }
}
```

### 6.3 SHACL constraints — reference table

The SHACL shapes file is [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) — that file is what executes; this table is an informative index of its most load-bearing rows, not a complete listing. A disagreement between the two is resolved by the precedence order in §2, which ranks this document above the shapes: fix whichever side is wrong.

| Shape | Targets | Constraint | Negative fixture |
|---|---|---|---|
| `vss:CompositionShape` | `vso:Composition` | `sh:minCount 1` on `vso:depicts` | none (would target an empty Composition) |
| `vss:DirectionalNeedsViewerShape` | `vso:SpatialFact` with `vso:directional` | requires `vso:viewer` | [`bad_no_viewer.ttl`](../tests/fixtures/bad_no_viewer.ttl) |
| `vss:RccValueShape` | `vso:SpatialFact / vso:rcc` | `sh:in (rcc:DC rcc:EC ...)` — eight values | none |
| `vss:DirectionalValueShape` | `vso:SpatialFact / vso:directional` | `sh:in (vso:above ...)` — six values | none |
| `vss:ProximalValueShape` | `vso:SpatialFact / vso:proximal` | `sh:in (vso:near vso:far vso:adjacent vso:next_to vso:facing)` — five values | none |
| `vss:EventShape` | `vso:Event`, `vso:Process`, `vso:Stative` | exactly one `vso:lemma` (`xsd:string`) | [`bad_event_no_lemma.ttl`](../tests/fixtures/bad_event_no_lemma.ttl) |
| `vss:QualityShape` | `vso:Quality` | exactly one `vso:dimension` and one `vso:value` | none |
| `vss:FrameNotDepictedShape` | `vso:depicts` | object MUST NOT be `vso:Frame` | [`bad_frame_depicted.ttl`](../tests/fixtures/bad_frame_depicted.ttl) |
| `vss:SpatialFactShape` | `vso:SpatialFact` | requires `vso:figure` and `vso:ground` | none |

---

## 7. Exporters

| Target | Mapping | Status |
|---|---|---|
| Cypher / Neo4j | `:s :p :o` → `(s)-[r:p]->(o)`; `<<:s :p :o>> :q :v` → `r.q = v` | **shipped** in `vson export cypher` |
| Caption (English) | deterministic graph → English, template-driven, no LLM | **shipped** in `vson export caption` and the web studio (in-browser, same renderer) |
| FOL | reified nodes → Prolog-style first-order-logic facts | **shipped** in `vson export fol` and the web studio (in-browser, same renderer) |
| DOT / GraphML / Mermaid | nodes/edges → graph-viz formats | shipped in the web studio |
| AMR | `Event` → AMR predicate; `agent`/`patient`/`instrument` → `:ARG0`/`:ARG1`/`:instrument` | spec only |
| Visual Genome | `(s, p, o)` → VG relation row; `bbox2d` → VG bbox | spec only |
| Pixar USD | `CameraView` → `UsdGeomCamera`; `Composition` → USD Stage | spec only |
| JSON-LD | `@context` mapping VSO namespace | shipped (see [`tools/schema/vson-jsonld.schema.json`](../tools/schema/vson-jsonld.schema.json)) |
| SPARQL-star | direct (no mapping needed) | shipped |

---

## 8. Versioning and extension

- **IRI immutability.** All IRIs under `https://w3id.org/vson/v1/` are immutable. v2.0 will use `https://w3id.org/vson/v2/`. Concurrent versions can coexist. The rule binds from v1.2 forward, under the w3id host. It did not survive the host itself: the pre-v1.2 `https://vson.dev/v1/` names this clause used to cover were withdrawn, not aliased — see §5.1 for why that was the honest resolution and not a silent breach.
- **One historical exception.** `ontology/vso.ttl` keeps its `owl:priorVersion` under the legacy `vson.dev` host and carries a `LEGACY IRI` comment saying so. That string is the `owl:versionIRI` the prior release actually declared; rewriting it would assert a name that release never carried, which falsifies a record rather than migrating one. It is a record, not a resolvable name, and nothing dereferences it. [`scripts/check_legacy_iri.py`](../scripts/check_legacy_iri.py) pins it as the only legacy-host IRI in the repository outside prose that documents the migration or preserves a historical record; every other occurrence fails the build.
- **Backwards compatibility within v1.x.** v1.x MAY add classes, properties, and shapes. v1.x **MUST NOT** remove or rename existing terms, change cardinalities to be more restrictive, or change SHACL shapes in a way that invalidates previously-conformant documents.
- **Private extensions.** Authors MAY define private predicates under their own namespace. Private predicates SHOULD NOT shadow VSV terms. Documents using private predicates are **profile-specific**, not portable.
- **Closed vocabularies.** §5.12 lists closed enumerations. Producers **MUST NOT** invent values; consumers **MAY** treat unknown values as `Unknown`.

---

## 9. Examples gallery

Sixteen scenes, ascending in complexity. Every example SHACL-conforms (verified by `make check` and `make cli-check`). Each file is a standalone VSON-P document.

### 9.1 Minimal — single Entity

**File:** [`examples/gallery/01_minimal.vson`](../examples/gallery/01_minimal.vson)
**Demonstrates:** smallest SHACL-conformant document — Composition + Frame + one Entity.

```vson
(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing close_up)
   :viewedBy cam
   :depicts (apple / PhysicalObject
               :individuation Generic :animacy Inert :countability Count
               :class Apple))
```

### 9.2 + Quality (color)

**File:** [`examples/gallery/02_quality.vson`](../examples/gallery/02_quality.vson)
**Demonstrates:** `Quality` reification with `dimension`/`value`.

### 9.3 Spatial topology — RCC-8 only

**File:** [`examples/gallery/03_spatial_topology.vson`](../examples/gallery/03_spatial_topology.vson)
**Demonstrates:** `SpatialFact` with `rcc:EC` only — no viewer required because RCC-8 is symmetric.

### 9.4 Directional fact with mandatory viewer

**File:** [`examples/gallery/04_directional_with_viewer.vson`](../examples/gallery/04_directional_with_viewer.vson)
**Demonstrates:** viewer anchoring — `vso:directional` requires `vso:viewer` at the schema level.

### 9.5 Possession — Stative

**File:** [`examples/gallery/05_possession_stative.vson`](../examples/gallery/05_possession_stative.vson)
**Demonstrates:** `Stative` with `holder` and `theme` (durative state, not punctual event).

### 9.6 Event with three roles (agent + patient + instrument)

**File:** [`examples/gallery/06_event_with_instrument.vson`](../examples/gallery/06_event_with_instrument.vson)
**Demonstrates:** triadic action — the v0.1 dyadic-edge defect resolved by reification.

### 9.7 Ditransitive — give

**File:** [`examples/gallery/07_ditransitive.vson`](../examples/gallery/07_ditransitive.vson)
**Demonstrates:** `agent + theme + recipient`, aligning with AMR `:ARG0/:ARG1/:ARG2`.

### 9.8 Collective countability — crowd

**File:** [`examples/gallery/08_collective.vson`](../examples/gallery/08_collective.vson)
**Demonstrates:** `Aggregate` class, `countability=Collective`, single node for many individuals.

### 9.9 Mass / Substance — water pouring

**File:** [`examples/gallery/09_mass_substance.vson`](../examples/gallery/09_mass_substance.vson)
**Demonstrates:** `Substance` class, `countability=Mass`, durative `Process`.

### 9.10 Geometry — bbox2d

**File:** [`examples/gallery/10_geometry_bbox.vson`](../examples/gallery/10_geometry_bbox.vson)
**Demonstrates:** normalized 2D bounding boxes for layout-to-image consumers.

### 9.11 Canonical full scene — throne room

**File:** [`examples/gallery/11_throne_room.vson`](../examples/gallery/11_throne_room.vson) (mirrors [`examples/throne_room.vson`](../examples/throne_room.vson))
**Demonstrates:** every feature in this spec — Frames, Entities with full traits, Qualities, Events, Statives, SpatialFacts with viewers, named entities, the works.

### 9.12 Persona — cross-document identity (v1.1)

**File:** [`examples/gallery/12_persona.vson`](../examples/gallery/12_persona.vson)
**Demonstrates:** `vso:Persona` Frame with `vso:hasInvariant` Qualities; an Entity declares `vso:embodies` to inherit stable invariants across scenes while per-scene `vso:hasQuality` stays contingent.

### 9.13 Negation — reified Negation node

**File:** [`examples/gallery/13_negation.vson`](../examples/gallery/13_negation.vson)
**Demonstrates:** `vso:Negation` node over a reified `Annotation` statement (RDF 1.1-portable equivalent of the canonical `<<s p o>>` form).

### 9.14 Belief state — propositional attitude

**File:** [`examples/gallery/14_belief_state.vson`](../examples/gallery/14_belief_state.vson)
**Demonstrates:** `vso:BeliefState` with an `experiencer` and a reified proposition (`vss:BeliefStateShape` + `vss:AnnotationShape`).

### 9.15 Quantification — "every horse is brown"

**File:** [`examples/gallery/15_quantification.vson`](../examples/gallery/15_quantification.vson)
**Demonstrates:** `vso:Quantification` node with `quantifier` (closed list), `variable`, `qDomain`, and `scope` over reified Annotation nodes.

### 9.16 Annotation — confidence on thematic-role edges

**File:** [`examples/gallery/16_annotation.vson`](../examples/gallery/16_annotation.vson)
**Demonstrates:** `vso:Annotation` reification (RDF 1.1-portable) carrying `vso:confidence` on each annotated triple; equivalent to the RDF-star `<<s p o>> vso:confidence "0.95"` form.

### 9.17 VSON-X compact-syntax mirror — v1.1

Gallery scenes 01–11 plus `12_persona` have a graph-equivalent VSON-X form under [`examples/gallery-x/`](../examples/gallery-x/) (12 files). For example, `examples/gallery-x/11_throne_room.x.vson` produces an RDF graph isomorphic to `examples/gallery/11_throne_room.vson` (modulo blank-node identity for auto-anonymous reified nodes; see [`tools/vson_x/equiv.py`](../tools/vson_x/equiv.py)). `make x-check` runs the round-trip suite over the 11 pairs for scenes 01–11; `12_persona` has an X file but is not yet in the tested PAIRS list, and scenes 13–16 are Penman/Turtle only.

---

## 10. Reference implementations

| Implementation | Location | Scope | Tests |
|---|---|---|---|
| Python Penman transpiler | [`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py) | Penman → Turtle | 18 round-trip tests (18/18 ✓) |
| Python VSON-X parser (v1.1) | [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py) | VSON-X → Turtle, nine sigils, bearer-class dispatch | 16 lexer/parser/emitter + 11 gallery round-trip (27/27 ✓) |
| Caption renderer (v1.0.5) | [`tools/render/caption.py`](../tools/render/caption.py) | graph → English (deterministic, no LLM) | 11 fixture + determinism (11/11 ✓) |
| Rust CLI (`vson`) | [`cli/`](../cli) | `validate`, `convert p2t/x2t`, `export cypher/caption/fol` | 43 tests (25 lib unit + 6 error-contract + 9 integration + 3 golden ✓) |
| SHACL validator | `pyshacl` (shelled out by `vson validate`) | semantic well-formedness, strict profile (the relaxed profile ships as a shapes file; no command selects it yet) | 5 SHACL tests + 16 gallery passes |
| Bare-VLM extractor | [`tools/extractor/baseline/extract.py`](../tools/extractor/baseline/extract.py) | image → VSON-P | offline cassette test |
| Browser studio (v1.3) | [`web/`](../web) | runs the Python references above in a Pyodide worker, in the visitor's browser: transpile, two-gate validation, caption/FOL — no backend | offline worker-parity vitest byte-pins p2t, both gate verdicts, and caption/FOL against the CLI fixtures |
| Routing tables (single source of truth) | [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json) | shared by Python + Rust — inside the crate so `include_str!` stays within the crate root and `cargo package` can verify-build it | Rust embeds it at compile time, the Python reference reads the same file at import time; `make cli-check` proves the two agree |

A consumer is "VSON v1.2 reference-conformant" iff it accepts every document accepted by the Python references (`vson_penman.py` + `vson_x.py`) plus `pyshacl`, and rejects every document the references reject.

---

## 11. Migration from v0.1

| v0.1 construct | v1.0 form |
|---|---|
| `{id:class}` Object | `Entity` with `individuation=Generic` |
| `@id:class` Unique Object | `Entity` with `individuation=Named` |
| `[id:type]` Item | `PhysicalObject` with `affordance ⊇ {Holdable}` |
| `<id:k=v>` Attribute | `Quality` node (`dimension k`, `value v`); link via `vso:hasQuality` |
| `~id:scene{...}` | `SceneContext` Frame with typed properties |
| `%id:style{...}` | `VisualStyle` Frame |
| `$id:camera{...}` | `CameraView` Frame |
| `#id:composition{...}` | `Composition` (mereological root) |
| `[A:verb instrument=x]` edge | `Event` node + `vso:agent`/`vso:patient`/`vso:instrument` edges |
| `[P:on]` edge | `SpatialFact` with `vso:rcc` and/or `vso:directional` (+ `vso:viewer` if directional) |
| `[P:has]` edge to attribute | `vso:hasQuality` to `Quality` node |
| `[P:scopes]` from supplementary | `vso:framedBy` from Composition to Frame |
| `[P:contains]` | `vso:depicts` (Composition → Entity) or `vso:partOf` (mereology) |

There is no migrator tool. v0.1 documents must be migrated by hand using the table above.

---

## 12. Changelog

See [`spec/CHANGELOG.md`](../spec/CHANGELOG.md). Highlights since v0.1:

- Replaced ad-hoc notation with **layered RDF-star + OWL 2 RL + SHACL** stack (`VSO/VSV/VSON-T/VSON-S/VSON-P/VSON-X`).
- Reified Events / Processes / Statives as nodes; added a closed inventory of coarse VerbNet-style thematic roles (see PropBank/FrameNet for the finer-grained alternatives VSON deliberately avoids).
- Added `SpatialFact` with the **mandatory viewer for directional facts**: directional facts are viewer-anchored by schema — VSON commits to the relative frame of reference (Levinson 2003) and makes the anchor explicit and machine-checkable; intrinsic and absolute frames are out of scope for v1.x. Figure/ground asymmetry follows Talmy.
- Replaced four-fold sigil entity taxonomy with **trait-bundle model**: `individuation × animacy × countability × affordance`.
- Added `Annotation` reification class for RDF 1.1-portable probability/source/confidence.
- Published JSON-LD context, JSON Schemas, and the extractor envelope format (this document, §6).
- Shipped Rust CLI v0.1 (`vson validate`, `convert p2t`, `export cypher`) graph-isomorphic to the Python reference.

---

## 13. Teaching an AI image generator

VSON is one notation; the producers are vision-language models. To make a model speak VSON, give it the [`vson-extractor` skill](../skills/vson-extractor/SKILL.md) — a portable ~4 KB Markdown system prompt that distills the closed vocabulary, the five hard rules, and one worked example into a self-contained brief.

### 13.1 Layout

```
skills/vson-extractor/
├── SKILL.md          # the prompt body (paste into system / systemInstruction)
├── conformance.json  # 5-image acceptance fixture for certifying a model
└── README.md         # provider-specific snippets (Claude / GPT / Gemini / OpenRouter)
```

### 13.2 Provider snippets

Each major provider takes the skill body in a slightly different field; see the [skill README](../skills/vson-extractor/README.md) for working snippets against Anthropic, OpenAI, Gemini, OpenRouter, and the Anthropic Skills API. The studio at [`web/`](../web/) extracts with `SKILL.md` (the VSON-X skill when X notation is selected); the longer 18 KB orchestrator prompt is published on the studio's `/prompts` page for pipelines that want maximum first-try conformance on hard scenes.

### 13.3 Conformance test

A model claims VSON-extractor support if it conforms on first try (no SHACL repair) for at least 4 of the 5 fixtures listed in [`skills/vson-extractor/conformance.json`](../skills/vson-extractor/conformance.json). The studio's repair loop (max 2 retries) is for graceful degradation, not for the certification path.

### 13.4 Why the skill, not the orchestrator prompt?

The orchestrator prompt at [`tools/extractor/prompts/orchestrator-system.md`](../tools/extractor/prompts/orchestrator-system.md) is 18 KB. It includes upstream-tool routing, decision policies P1–P13, and a long worked example with bbox detections. That prompt is right when an extractor pipeline is feeding the model upstream tool outputs and you need maximum first-try conformance.

The skill is right when a third-party caller wants to read VSON directly from an image with no pipeline — the model has nothing but the picture and the skill body. It is one-sixth the token cost, targets ≥ 80% first-try conformance — the certification threshold in [`skills/vson-extractor/conformance.json`](../skills/vson-extractor/conformance.json); measured results are pending (see [`tools/extractor/baseline/results.md`](../tools/extractor/baseline/results.md)) — and is small enough that prompt-cache hit rates are irrelevant: at this size, every provider's input charge is a rounding error.

### 13.5 Public surface

The studio's "what is this" page is [`web/src/routes/about/+page.svelte`](../web/src/routes/about/+page.svelte), served at `/about` by any running studio. It is the canonical public-facing explanation; the spec (this document) is the canonical machine-readable contract. They should not drift.

---

## Appendix A — Consolidated JSON Schemas {#appendix-a}

### A.1 Extractor response envelope

The full schema lives at [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) and is normative. Its `$id` is `https://w3id.org/vson/v1/schema/vson-output.schema.json`.

The schema body is reproduced below. Producers MUST validate every emitted envelope against this schema; consumers MAY trust an envelope that already passed validation upstream.

> See [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) for the full text. Inlining it here would duplicate ~120 lines of JSON; the file is canonical.

### A.2 JSON-LD scene structural schema

Lives at [`tools/schema/vson-jsonld.schema.json`](../tools/schema/vson-jsonld.schema.json). Structural only; well-formedness is enforced by SHACL on the materialized graph, not by JSON Schema.

### A.3 SHACL shapes

Lives at [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl). Normative.

---

## Appendix B — Penman EBNF {#appendix-b}

```ebnf
document    = node ;
node        = "(" var [ "/" Concept ] role* ")" ;
role        = ":" name term ;
term        = node | var | literal ;
literal     = quoted-string | number | unit | bareword ;
quoted-string = '"' ( escape | ~['"' '\\'] )* '"' ;
escape      = '\\' . ;
number      = '-'? digit+ ( '.' digit+ )? ;
unit        = number letter+ ;          (* "35mm", "1.5x" *)
bareword    = letter ( letter | digit | '_' | '-' )* ;
var         = ID ;
Concept     = ID ;
name        = ID ;
ID          = letter ( letter | digit | '_' | '-' )* ;
letter      = 'A'..'Z' | 'a'..'z' | '_' ;
digit       = '0'..'9' ;
comment     = '#' ~[\n]* ;
```

Tokenization rules (informative):

1. Comments (`# ...` to EOL) are stripped.
2. Whitespace is insignificant.
3. UNIT (number+letters with no space) is recognized before bare NUM and bare ID.
4. Forward references are allowed; the emitter does a pre-pass to register declared variables.
5. Routing of bare IDs in object position depends on the parent role; see [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json).

---

## Appendix C — Class registry {#appendix-c}

Open registry. `vso:class` is an open dimension (§5.12): any bareword is conformant, and `Unknown` is the always-safe fallback. The list below is an **illustrative registry for the gallery's fantasy-scene domain** — a starting vocabulary sized for the kind of scene the examples depict, not a controlled vocabulary and not a canonical set. Extend it per domain, under your own namespace where you need term identity (§8); no validator checks membership in this list, so nothing here constrains a conformant document.

**People / agents.** `Human, Knight, Queen, King, Soldier, Woman, Man, Child, Merchant, Monk, Servant, Civilian, Peasant`

**Animals.** `Animal, Boar, Dog, Horse, Cat, Bird, Fish, Wolf, Deer`

**Wearables / regalia / weapons / tools.** `Crown, Hat, Helmet, Sword, Spear, Bow, Shield, Scroll, Torch, Cup, Bowl, Plate, Throne, Chair, Bed, Vessel, Weapon, Regalia, Tool`

**Architecture / nature.** `Tree, Rock, Pillar, Building, Castle, House, Furniture, Lamp, Door, Window`

**Sky / atmosphere.** `Cloud, Sun, Moon, Sky, Star`

**Substances.** `Water, Smoke, Fire, Blood, Stone`

**Aggregates / collectives.** `Group, Crowd, Flock, Herd`

**Special.** `Apple` (Quick Start canonical), `Unknown` (always conformant fallback).

---

## Appendix D — VSON-X grammar (normative) {#appendix-d}

This appendix is the single normative grammar for VSON-X. §4.3 is the overview; the per-key routing rationale — which bearer turns `*K V` into a Quality node and which into a direct property — is [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §3.

The grammar is reconciled against the reference parser [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py). Where an earlier draft of the grammar and the shipping parser disagreed, **the parser wins**; each such case is recorded in §D.9. The Rust port planned for v1.2 (§4.3) MUST accept exactly the language below.

### D.1 Notation

`{ x }` is zero or more `x`; `[ x ]` is an optional `x`; `|` is alternation; `A - B` is set difference; `"…"` is a literal; `(* … *)` is a comment. UPPERCASE names are terminals produced by the lexer (§D.2–D.3); lowercase names are syntactic productions (§D.5).

### D.2 Lexical productions

The lexer is a single scan over the source text. **Whitespace, including newlines, only separates tokens** — it carries no syntax. Comments are discarded with it. At each position the scanner tries the alternatives below in order; that ordering is what makes `35mm` one `UNIT` rather than a `NUM` followed by an `IDENT`, and `>>` one arrow rather than two.

| # | Token | Value carried | Note |
|---|---|---|---|
| 1 | `COMMENT` | — | `#` to end of line; discarded, never reaches the parser |
| 2 | `>>` | — | tried before `>` |
| 3 | `>` `~` `^` `*` `/` `@` `!` `&` | — | single-character sigils |
| 4 | `STRING` | the text between the quotes | the lexer does not decode `\` escapes; the emitter re-escapes the raw body for Turtle |
| 5 | `UNIT` | the whole token | tried before `NUM`; always emitted as a plain string literal (`50mm` → `"50mm"`) |
| 6 | `NUM` | the whole token | one token kind for both shapes below |
| 7 | `IDENT` | the whole token | |
| 8 | any other non-whitespace character | — | lexical error (§D.7) |

```ebnf
(* Lexical grammar. NEWLINE appears once, and only to terminate a comment;
   it is not a terminal in any syntactic production of §D.5. *)

COMMENT   = "#" { CHAR - NEWLINE } ;
STRING    = '"' { ( CHAR - ( '"' | "\" ) ) | ( "\" CHAR ) } '"' ;
UNIT      = NUM ALPHA_ { ALPHA_ | DIGIT | "-" } ;   (* "35mm", "1.5x" *)
NUM       = FLOAT | INT ;
INT       = [ "-" ] DIGIT { DIGIT } ;
FLOAT     = INT "." DIGIT { DIGIT } ;
IDENT     = ALPHA_ { ALPHA_ | DIGIT | "-" } ;
MOD       = IDENT - TRAIT_KEYWORD ;
ALPHA_    = "A".."Z" | "a".."z" | "_" ;
DIGIT     = "0".."9" ;
```

`INT` and `FLOAT` are the two shapes a `NUM` can take, not two token kinds: the lexer emits a single `NUM`, and the split is re-derived at emission time, where a `FLOAT` becomes `xsd:decimal` and an `INT` becomes `xsd:integer` (unless the role forces a string — §D.6).

`MOD` is the token after `~` in a `*K V ~M` tail. A `~` is read as a modifier prefix only when the very next token is an `IDENT` that is not a `TRAIT_KEYWORD`; otherwise the `~` is left where it is, and anywhere but the first token of the document that is a parse error.

### D.3 Closed token vocabularies

These terminals are closed. They restate, as token sets, the VSV enumerations of §5.12.

**`TRAIT_KEYWORD`** — 14 tokens, the union of the four trait axes of §5.12. Recognized only inside `entity_tail` (§D.5); in any other position these spellings are ordinary `IDENT`s.

| Axis (§5.12) | Tokens | Emits |
|---|---|---|
| individuation | `Generic`, `Named`, `Kind`, `Skolem` | `vso:individuation` |
| animacy | `Agentive`, `Inert` | `vso:animacy` |
| countability | `Count`, `Mass`, `Collective` | `vso:countability` |
| affordance | `Holdable`, `Wearable`, `Mountable`, `Container`, `Edible` | `vso:affordance` (repeatable) |

**`CONCEPT`** — 12 tokens admissible after `/`: `PhysicalObject`, `Aggregate`, `Substance`, `CameraView`, `VisualStyle`, `SceneContext`, `Persona`, `Quality`, `Event`, `Process`, `Stative`, `SpatialFact`. Domain classes (`Knight`, `Crown`, `Sword`) never appear here — they are values of `*class` (Appendix C). `FRAME_KIND` (`CameraView`, `VisualStyle`, `SceneContext`, `Persona`) is a semantic subset, not a separate terminal: the grammar admits any `CONCEPT` after a leading `/` and only the bearer dispatch of §4.3 distinguishes them (see §D.8).

**`RCC_TOKEN`** — 8 tokens, the local names of the §5.12 `vso:rcc` enum, written without the prefix: `DC`, `EC`, `PO`, `EQ`, `TPP`, `NTPP`, `TPPi`, `NTPPi`. The emitter re-attaches `rcc:` because `rcc` is listed under `role_value_to_rcc` and these eight under `rcc_values` in [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json).

**`DIR_TOKEN`** — 9 tokens accepted, 6 conformant. The six §5.12 `vso:directional` values `above`, `below`, `left_of`, `right_of`, `in_front_of`, `behind`, plus three camelCase aliases the shipping parser also accepts: `leftOf`, `rightOf`, `inFrontOf`. The aliases are passed through verbatim and emit `vso:leftOf` / `vso:rightOf` / `vso:inFrontOf`, which are **not** in `vss:DirectionalValueShape`'s `sh:in` list — a document using one parses and then fails SHACL. Producers **MUST** use the six snake_case spellings; the aliases are recorded here because they are in the shipped token set, not because they are permitted output.

**`SYM_LEMMA`** — 3 tokens: `near`, `far`, `adjacent`, the three symmetric members of the five-value `vso:proximal` enum of §5.12. An unlisted `&` lemma is a parse error.

The perdurant lemma tables (`>` / `>>`) are routing tables, not closed vocabularies: they are listed in §4.3, with their role signatures in [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §5.

### D.4 Item boundaries and lookahead

No production in §D.5 has a `NEWLINE` terminal. A composition body is a flat sequence of items — no block nesting, no indentation rule — and an item ends exactly where the next item's lead token begins. A declaration may therefore span many lines with arbitrary indentation, and a whole scene may equally be written on one line.

| Lead pattern | Item |
|---|---|
| `~ IDENT` | composition root; the document's first two tokens |
| `/ CONCEPT` | `frame_decl` |
| `^ IDENT` | `viewer_anchor` at composition level |
| `[ "@" ] IDENT "/"` | `entity_tail` |
| `[ "@" ] IDENT ">"` | `stative` |
| `[ "@" ] IDENT ">>"` | `event` |
| `[ "@" ] IDENT "!"` | `spatial_asym` |
| `[ "@" ] IDENT "&"` | `spatial_sym` |

**Lookahead budget.** The grammar needs two tokens at exactly one place — the handle position, where an `IDENT` is resolved against the token after it to choose among `entity_tail` / `stative` / `event` / `spatial_asym` / `spatial_sym`. An `@` prefix pushes the same decision one token further, so the worst case is three tokens; everywhere else one token suffices.

**Arglist termination.** Inside a perdurant `arglist`, a bare `IDENT` is a positional ref unless the token immediately after it is `/`, `>`, `>>`, `!`, or `&` — in which case the arglist ends and that `IDENT` begins the next item. An `@ IDENT` applies the same test one token further along. Any other token kind (`~`, `^`, `/`, end of input) also ends the arglist.

**`*K V` binds to the nearest open bearer.** Composition-level `kv` must sit between `~IDENT` and the first item. Once an item has started, every following `*` is consumed by that item's `kv` loop, so a `*layout triangular` written after an entity declaration becomes a Quality of that entity, not of the composition. This is a consequence of flat items plus greedy `kv` loops, and it is the one place where the ordering of a document changes its meaning.

### D.5 Syntactic productions

```ebnf
document       = composition ;
composition    = "~" IDENT { kv } { item } ;

item           = frame_decl | viewer_anchor | handle_item ;

frame_decl     = "/" CONCEPT [ "@" IDENT ] { kv } ;
viewer_anchor  = "^" IDENT ;

handle_item    = handle ( entity_tail | stative | event
                        | spatial_asym | spatial_sym ) ;
handle         = [ "@" ] IDENT ;

entity_tail    = "/" CONCEPT { TRAIT_KEYWORD | kv } ;   (* order-independent *)

stative        = ">"  IDENT arglist ;
event          = ">>" IDENT arglist ;
arglist        = { ref | kv } ;

spatial_asym   = "!" REL ref [ viewer_anchor ] { kv } ;
REL            = RCC_TOKEN | DIR_TOKEN ;
spatial_sym    = "&" SYM_LEMMA "&" ref ;

kv             = "*" IDENT value [ "~" MOD ] ;
value          = STRING | UNIT | NUM | ref ;
ref            = [ "@" ] IDENT ;
```

1. **`kv` is one production; its meaning is not.** What a `*K V` emits depends entirely on the bearer it sits inside — the dispatch table in §4.3, with rationale in [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §3. Grammar and dispatch are separate layers, which is why there is one rule here and six rows there.
2. **`@` is optional and meaningless in `ref` position.** `@sword` and `sword` denote the same node. `@` is load-bearing in exactly two places: at a `handle` that heads an `entity_tail`, where it selects the default individuation when no individuation `TRAIT_KEYWORD` is given (`@` → `vso:Named`, bare → `vso:Generic`); and in `frame_decl`, where it is the only admissible handle form (`/CameraView @cam` is well-formed, `/CameraView cam` is not).
3. **`/CameraView @cam` and `@cam /CameraView` are different items.** The first is a `frame_decl` and attaches via `vso:framedBy`. The second is a `handle_item` whose `entity_tail` happens to name a Frame concept: it attaches via `vso:depicts` and acquires a default `vso:individuation`. Only the first form is correct for a Frame.
4. **In `spatial_asym` the viewer anchor MUST precede the `{ kv }` tail.** `a ! EC b ^cam *dir above` is well-formed; `a ! EC b *dir above ^cam` is not — the `^cam` falls outside the item and becomes a composition-level `vso:viewedBy`, leaving the directional fact with no viewer, which is the parse error of §D.7. Only a `^` anchor satisfies that requirement; a literal `*viewer @cam` emits the triple but does not satisfy it.
5. **The only nesting is composition → items.** Quality, Stative, Event, Process and SpatialFact nodes are synthesised by the parser; they are never written with brackets, and their identity is a blank node (see [`tools/vson_x/equiv.py`](../tools/vson_x/equiv.py) for how round-trip equivalence treats them).

### D.6 Bare identifiers — literal or IRI

VSON-X carries no literal/IRI distinction on its surface: `value`'s `ref` alternative covers both `@sword` and `sword`, and `*manner gently` and `*instrument @sword` are the same shape. The distinction is made at emission time, by **role name**, against [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json) — the same table VSON-P consumes, so the two surfaces route identically and cannot drift.

| Order | Test (routing-tables.json key) | Result | Example |
|---|---|---|---|
| 1 | role ∈ `role_value_as_string` | Turtle string literal | `*manner gently` → `vso:manner "gently"` |
| 2 | name was declared as a node var | reentrant IRI ref | `*instrument @sword` → `vso:instrument :sword` |
| 3 | role ∈ `role_value_to_rcc` and name ∈ `rcc_values` | `rcc:` IRI | `! EC` → `vso:rcc rcc:EC` |
| 4 | role ∈ `role_value_to_vso` | `vso:` IRI | `*dir above` → `vso:directional vso:above` |
| 5 | otherwise | document-local IRI | `*class Knight` → `vso:class :Knight` |

`STRING` and `UNIT` always render as string literals. A `NUM` renders as `xsd:decimal` or `xsd:integer` unless its role is in `role_value_as_string`. A Quality's `vso:value` is not in any of the three lists, so a bareword quality value lands in rule 5 and becomes a document-local IRI — `*color red` → `vso:value :red`, which §5.5's "bareword/string/integer" admits.

### D.7 Parse-time error set

Every condition below aborts the parse. This is the complete set raised by the reference parser; nothing else is a parse error.

| Error | Raised when |
|---|---|
| `unexpected character: <c>` | lexer meets a non-whitespace character outside §D.2 |
| `expected <KIND>, got <tok>` | a required terminal is missing (e.g. `*` not followed by `IDENT`, or a `&` lemma with no closing `&`) |
| `unknown concept after /: <X>` | the token after `/` is not one of the 12 `CONCEPT`s |
| `unexpected lead token: <tok>` | a token at item position that is not `/`, `^`, `@`, or `IDENT` |
| `unexpected EOF after handle '<h>'` | input ends immediately after a handle |
| `after handle '<h>': expected '/', '>', '>>', '!', or '&', got <tok>` | a handle is followed by anything else |
| `modifier ~<M> not valid on direct property *<K>` | `~MOD` on the Composition's `*rendersAs` |
| `modifier ~<M> not valid on Frame direct property *<K>` | `~MOD` on a metadata-Frame `kv` (Persona `kv` does admit one) |
| `modifier ~<M> not valid on Entity direct property *<K>` | `~MOD` on one of the seven Entity direct keys |
| `modifier ~<M> not valid on thematic role *<K>` | `~MOD` on a perdurant arglist `kv` — v1.1 has no encoding for it |
| `lemma '<L>' is Event/Process; use '>>' instead of '>'` | `>` with a lemma in the Event or Process table |
| `lemma '<L>' is Stative; use '>' instead of '>>'` | `>>` with a lemma in the Stative table only |
| `too many positional arguments: lemma expects <n>, got <m>` | more positional refs than the lemma's signature has slots |
| `unknown spatial relation '<R>'` | the token after `!` is neither an `RCC_TOKEN` nor a `DIR_TOKEN` |
| `*dir value must be a directional bareword` / `*prox value must be a proximal bareword` | `*dir` / `*prox` given a `STRING`, `NUM` or `UNIT` value |
| `directional spatial fact requires a viewer anchor (^cam)` | a `!` fact carries a direction (as `REL` or as `*dir`) with no `^` anchor. The message's "§4.10.2" is [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §4.10.2 |
| `'<L>' is not a symmetric proximal lemma` | a `&` lemma outside `SYM_LEMMA` |
| `unexpected value token: <tok>` / `unexpected EOF in value` | a `kv` with no parsable value |

Two conditions are **warnings**, not errors: a `>` lemma absent from all three tables falls back to `holder` + `theme`, and a `>>` lemma absent from all three falls back to an Event with `agent` + `patient`. Both are written to stderr and neither changes the emitted graph.

### D.8 Accepted by the grammar, checked elsewhere

The grammar is deliberately thin. These are well-formed VSON-X and are caught — if at all — by SHACL (§2 C1–C9) rather than by the parser. Listing them is not an endorsement; a producer **MUST NOT** rely on any of them.

1. **Duplicate handle declarations.** Declaring `a /PhysicalObject` twice parses; both declarations emit onto the same IRI.
2. **Undeclared handles.** A ref to a handle that is never declared parses and emits a dangling IRI.
3. **Out-of-enum `*dir` / `*prox` values.** The parser checks only that the value is a bareword; `*dir sideways` parses and then fails `vss:DirectionalValueShape`. The same holds for the three camelCase `DIR_TOKEN` aliases of §D.3.
4. **Non-Frame concepts after a leading `/`.** `/PhysicalObject @x` parses and attaches via `vso:framedBy`, producing a `framedBy` edge to something that is not a `vso:Frame`.
5. **Viewer anchors.** Nothing checks that a `^` target is a declared `CameraView`, and a composition with zero or with several top-level `^` anchors parses. [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §4.10.1 specifies stricter rules and marks each as unimplemented.
6. **Arglist key names.** Any `IDENT` is accepted as a thematic-role key; `*frobnicate zzz` emits `vso:frobnicate :zzz`.
7. **`~MOD` on a SpatialFact `kv` other than `*dir` / `*prox`.** Accepted and then discarded — the modifier reaches no triple.
8. **Geometry value ranges.** `*bbox2d` is not range-checked at parse time.

### D.9 Reconciliation notes

Six differences between the pre-implementation grammar draft and the shipped parser. In each, the parser is authoritative and this appendix follows it.

| # | Draft said | Shipped parser does | Resolution |
|---|---|---|---|
| 1 | `composition = "~" IDENT { quality_kv } NEWLINE block` | newlines are stripped by the lexer; items are found by lead token | `NEWLINE` and `block` dropped; §D.4 is the item-boundary rule |
| 2 | `rel = RCC_TOKEN \| DIR_TOKEN` — suspected over-broad | `! above b ^cam` is accepted, emitting `vso:directional vso:above` and **no** `vso:rcc` | `DIR_TOKEN` kept in `REL`; the emitted triple is documented in §D.3 |
| 3 | `value = IDENT \| INT \| FLOAT \| UNIT \| STRING \| ref` | `IDENT` in value position *is* the `ref` alternative; `INT`/`FLOAT` are one `NUM` token | collapsed to `value = STRING \| UNIT \| NUM \| ref`; §D.6 covers what a bareword becomes |
| 4 | `item = … \| comment` | comments never reach the parser | `COMMENT` moved to §D.2, removed from `item` |
| 5 | `trait = TRAIT_KEYWORD (* §5.x; order-independent *)` | traits are recognized inline in the entity declaration loop | inlined into `entity_tail`; the dangling `§5.x` is now §5.12, enumerated in §D.3 |
| 6 | Frames accept `@id` or bare `id` | `frame_decl` accepts an `@` handle only | `frame_decl = "/" CONCEPT [ "@" IDENT ] { kv }`; see §D.5 note 2 |

---

## Appendix E — Related work and bibliography {#appendix-e}

VSON is an assembly of existing ideas, not a new theory. This appendix names the sources the rest of the document leans on and states, for each, exactly what VSON takes and what it leaves behind. Nothing here is an endorsement by, or an affiliation with, the cited authors or standards bodies; entries omit page numbers and DOIs rather than risk an unverified one.

### E.1 Spatial and temporal calculi

**Randell, D. A., Cui, Z., & Cohn, A. G. (1992). A Spatial Logic Based on Regions and Connection. *Proceedings of the 3rd International Conference on Principles of Knowledge Representation and Reasoning (KR'92)*, Morgan Kaufmann.**
VSON ships the eight RCC-8 base relation names as a closed value vocabulary for `vso:rcc` (§5.7) and stops there — the composition calculus, the JEPD axioms, and constraint propagation over region networks are all out of scope.

**Allen, J. F. (1983). Maintaining Knowledge about Temporal Intervals. *Communications of the ACM*, 26(11).**
Same posture on the temporal side: VSON declares the thirteen interval relations as properties between Perdurants with their inverses and the self-composing transitivity (§5.9), and ships no composition table.

**Cox, S., & Little, C. (eds.). *Time Ontology in OWL*. W3C Recommendation, 2017. Namespace `http://www.w3.org/2006/time#`.**
Every `allen:` property carries a `skos:closeMatch` to its OWL-Time counterpart; VSON does not use the `time:` IRIs directly because OWL-Time types them on `time:ProperInterval` while VSON types them on `vso:Perdurant` (§5.9 design note).

**Perry, M., & Herring, J. (eds.). *OGC GeoSPARQL — A Geographic Query Language for RDF Data*. Open Geospatial Consortium, 2012 (v1.0; later revised as v1.1). Namespace `http://www.opengis.net/ont/geosparql#`.**
GeoSPARQL defines the `geo:rcc8*` IRIs each `rcc:` individual close-matches; VSON keeps its own terms because GeoSPARQL models the relations as binary properties between features while VSON models them as values on a reified `vso:SpatialFact` (§5.9 design note).

### E.2 Space in language

**Talmy, L. (2000). *Toward a Cognitive Semantics* (2 vols.). MIT Press.**
The figure/ground asymmetry is the reason `vso:SpatialFact` has two distinct, non-interchangeable slots (`vso:figure`, `vso:ground`) instead of an unordered pair (§3.3).

**Levinson, S. C. (2003). *Space in Language and Cognition: Explorations in Cognitive Diversity*. Cambridge University Press.**
Levinson's three frames of reference are why C5 exists: VSON commits to the **relative** frame and forces every directional fact to name its viewer, leaving intrinsic and absolute frames out of scope for v1.x (§3.3).

### E.3 Upper ontology

**Masolo, C., Borgo, S., Gangemi, A., Guarino, N., & Oltramari, A. (2003). *WonderWeb Deliverable D18: Ontology Library (final)*. ISTC-CNR.**
The definitive DOLCE description; VSON's `Endurant / Perdurant / Quality / Region` top is **DOLCE-inspired** — it borrows the category names and the endurant/perdurant cut, and imports no DOLCE IRI or axiom (§3.1).

### E.4 Predicate-argument structure

**Kipper Schuler, K. (2005). *VerbNet: A Broad-Coverage, Comprehensive Verb Lexicon*. PhD dissertation, University of Pennsylvania.**
VSON's thematic-role inventory (§5.6) is VerbNet-style: coarse, frame-independent role labels shared across predicates — though VSON uses a small fixed subset and ships no verb-class lexicon.

**Palmer, M., Gildea, D., & Kingsbury, P. (2005). The Proposition Bank: An Annotated Corpus of Semantic Roles. *Computational Linguistics*, 31(1).**
The finer-grained alternative VSON deliberately avoids: PropBank numbers arguments per verb sense, which needs a per-predicate lexicon at extraction time — the numbering only reappears in the AMR exporter mapping (§7).

**Baker, C. F., Fillmore, C. J., & Lowe, J. B. (1998). The Berkeley FrameNet Project. *Proceedings of COLING-ACL 1998*.**
The other alternative VSON avoids: FrameNet's frame-specific role names (`Donor`, `Recipient`) are more expressive than a vision-language model can reliably assign from a still image.

**Banarescu, L., Bonial, C., Cai, S., Georgescu, M., Griffitt, K., Hermjakob, U., Knight, K., Koehn, P., Palmer, M., & Schneider, N. (2013). Abstract Meaning Representation for Sembanking. *Proceedings of the 7th Linguistic Annotation Workshop and Interoperability with Discourse (LAW VII), ACL*.**
AMR is where the Penman authoring pattern of VSON-P comes from — nested `(var / Concept :role target)` with reentrancy (§4.2) — and AMR is also an export target (§7); VSON's concepts and roles are its own.

### E.5 Scene graphs in vision

**Johnson, J., Krishna, R., Stark, M., Li, L.-J., Shamma, D. A., Bernstein, M. S., & Fei-Fei, L. (2015). Image Retrieval using Scene Graphs. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*.**
The paper that established the object/attribute/relationship scene-graph formulation VSON starts from; VSON's departure is to reify relationships as nodes so they can be viewer-anchored, negated, and annotated.

**Krishna, R., Zhu, Y., Groth, O., Johnson, J., Hata, K., Kravitz, J., Chen, S., Kalantidis, Y., Li, L.-J., Shamma, D. A., Bernstein, M. S., & Fei-Fei, L. (2017). Visual Genome: Connecting Language and Vision Using Crowdsourced Dense Image Annotations. *International Journal of Computer Vision*, 123(1).**
The reference corpus for dense scene-graph annotation and a listed export target (§7); its open-string predicates are what VSON's closed relation vocabularies (§5.12) are a reaction to.

**Hudson, D. A., & Manning, C. D. (2019). GQA: A New Dataset for Real-World Visual Reasoning and Compositional Question Answering. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*.**
GQA showed what a normalized, cleaned scene-graph vocabulary buys downstream — the argument for VSON's closed enumerations and SHACL gate, rather than post-hoc cleanup.

### E.6 Web standards VSON builds on or borrows patterns from

**Sanderson, R., Ciccarese, P., & Young, B. (eds.). *Web Annotation Data Model*. W3C Recommendation, 2017.**
The body/target separation is the same shape as `vso:Annotation` (§5.11); VSON keeps its own minimal class rather than adopting the model, because its targets are triples rather than media fragments.

**Lebo, T., Sahoo, S., & McGuinness, D. (eds.). *PROV-O: The PROV Ontology*. W3C Recommendation, 2013.**
The natural target for extractor provenance; VSON v1.1 records only a free-text `vso:source` on annotations and envelope-level `extraction` metadata (§6.1), so PROV-O alignment is future work, not a shipped feature.

---

*This document is normative. When it disagrees with another VSON artifact, resolve the conflict by the precedence order in §2 — this document ranks first, but a mismatch is a bug either way, not a licence to ignore the lower-ranked artifact.*
