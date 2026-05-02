# VSON v1.0 — Visual Scene Ontology Notation

**Specification, Quick Start, Reference, JSON Schema, and Example Gallery — single document, RFC-style.**

| Field | Value |
|---|---|
| Status | v1.0 stable |
| Date | 2026-05-02 |
| Editors | VSON Working Group |
| Source repo | this repository (root: `visual-scene-ontology/`) |
| Normative source | this document; `ontology/*.ttl`; `shapes/vson-shapes.ttl`; `tools/schema/*.json` |
| Companion artifacts | `cli/` (Rust binary), `tools/penman/` (Python reference), `examples/gallery/` (11 scenes) |

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** are interpreted per RFC 2119.

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
9. [Examples gallery (11 scenes)](#9-examples-gallery)
10. [Reference implementations](#10-reference-implementations)
11. [Migration from v0.1](#11-migration-from-v01)
12. [Changelog](#12-changelog)
13. [Teaching an AI image generator](#13-teaching-an-ai-image-generator)
14. [Appendix A — Consolidated JSON Schemas](#appendix-a)
15. [Appendix B — Penman EBNF](#appendix-b)
16. [Appendix C — Class registry](#appendix-c)

---

## 1. Quick Start

### 1.1 What you upload, what you get back

```
        ┌──────────┐    image bytes      ┌──────────────┐    JSON envelope    ┌────────────┐
        │  client  │ ──────────────────▶ │  extractor   │ ──────────────────▶ │  consumer  │
        │ (UI / API)│                    │ (vson generate)│                  │ (graph view,│
        └──────────┘                     └──────────────┘                     │ Cypher,    │
                                                                              │ USD, ...)  │
                                                                              └────────────┘
```

The envelope is a single JSON document conforming to [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json). It carries:

- `vson_p` — Penman authoring text (canonical artifact);
- `vson_t` — Turtle 1.2 / Turtle-star (machine canonical, derivable from `vson_p`);
- `graph` (optional) — `{nodes, edges}` projection for UI clients;
- `conformance.conforms` — SHACL pass/fail.

### 1.2 Install

```bash
git clone <repo> && cd visual-scene-ontology
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
# @prefix vso:   <https://vson.dev/v1/ontology#> .
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

If the `Conforms: True` line printed, the document is a valid VSON v1.0 scene. **You are done with Quick Start.** The rest of this document is reference material.

### 1.4 First image → graph (preview)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python tools/extractor/baseline/extract.py --live --images path/to/image.jpg
# emits results.csv with one row per image:
#   image, shacl_first_try, shacl_after_retries, retries, latency_ms, ...
```

The runner returns a SHACL-conformant `vson_p` string per image. To produce the full envelope from §1.1, wrap that string with the metadata fields described in §6. A reference wrapper is planned for v0.2 (`vson generate <image>`).

---

## 2. Conformance

A document is a **conformant VSON v1.0 document** iff all of the following hold:

| # | Requirement |
|---|---|
| C1 | It is a syntactically valid VSON-T (Turtle 1.2 / Turtle-star) **or** VSON-P (Penman) document per §4. |
| C2 | All IRIs it asserts under the VSO namespace resolve to a class or property declared in [`ontology/vso.ttl`](../ontology/vso.ttl), [`ontology/rcc8.ttl`](../ontology/rcc8.ttl), or [`ontology/allen.ttl`](../ontology/allen.ttl) — no orphan VSO terms. |
| C3 | Its triple set passes SHACL validation against [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) with `inference="rdfs"` and no violations. |
| C4 | Every `vso:Composition` declared in the document carries at least one `vso:depicts` edge. |
| C5 | Every `vso:SpatialFact` carrying a `vso:directional` predicate **MUST** also carry exactly one `vso:viewer` referencing a `vso:CameraView` (Talmy resolution). |
| C6 | Every `vso:Event`, `vso:Process`, and `vso:Stative` carries exactly one `vso:lemma` literal. |
| C7 | Every `vso:Quality` carries exactly one `vso:dimension` and one `vso:value`. |
| C8 | If `vso:rcc` appears, its value **MUST** be one of `rcc:DC`, `rcc:EC`, `rcc:PO`, `rcc:EQ`, `rcc:TPP`, `rcc:NTPP`, `rcc:TPPi`, `rcc:NTPPi`. |
| C9 | `vso:depicts` **MUST NOT** target a `vso:Frame`; frames attach via `vso:framedBy`. |

**Producer conformance.** A producer (extractor, generator, CLI) is conformant iff every document it emits satisfies C1–C9, validated by SHACL before emission.

**Consumer conformance.** A consumer is conformant iff it accepts every document satisfying C1–C9 without modification, and rejects (or flags) documents that do not.

**Verification.** The reference verifier is `cli/target/release/vson validate <file>`. Exit code 0 means conformant; exit code 1 means non-conformant.

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

### 3.3 Talmy resolution (directional facts)

"The lamp is to the left of the chair." Left from whose vantage? Without a viewer, the assertion is ambiguous. **VSON enforces an explicit viewer at the schema level**: any `vso:SpatialFact` carrying a `vso:directional` value **MUST** also carry exactly one `vso:viewer` pointing at a `vso:CameraView`. Symmetric/topological facts (`rcc:EC`, `rcc:DC`) do not need a viewer.

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

VSON has two surface syntaxes that share one abstract graph.

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

The reference transpiler is [`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py); the Rust port is [`cli/src/penman/`](../cli/src/penman/). Both consume [`tools/penman/routing-tables.json`](../tools/penman/routing-tables.json) as their single source of truth, so they cannot drift.

### 4.3 JSON-LD form

A VSON document MAY be exchanged as JSON-LD bound to context `https://vson.dev/v1/context.jsonld`. Structural skeleton in [`tools/schema/vson-jsonld.schema.json`](../tools/schema/vson-jsonld.schema.json). Well-formedness is enforced by SHACL on the materialized graph, not by JSON Schema alone.

### 4.4 Image-extractor envelope (the Quick Start payload)

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
| `vso:`   | `https://vson.dev/v1/ontology#` | Core ontology and vocabulary |
| `vss:`   | `https://vson.dev/v1/shapes#`   | SHACL shape names |
| `rcc:`   | `https://vson.dev/v1/rcc8#`     | RCC-8 base relations |
| `allen:` | `https://vson.dev/v1/allen#`   | Allen interval relations |
| `xsd:`   | `http://www.w3.org/2001/XMLSchema#` | Datatypes |
| `rdf:`   | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` | RDF |
| `rdfs:`  | `http://www.w3.org/2000/01/rdf-schema#` | RDFS |
| `sh:`    | `http://www.w3.org/ns/shacl#`   | SHACL |
| `:`      | `https://example.org/scenes/anonymous#` (default; consumers MAY override) | Document-local |

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

#### `vso:viewedBy` *(IRI ref → CameraView, required, exactly 1)*
The composition's primary viewer. Required because directional `SpatialFact`s reference a viewer that **MUST** exist in the document.
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

### 5.4 `vso:PhysicalObject` (and `vso:Aggregate`, `vso:Substance`)

Concrete entities in the scene. Subtypes share trait axes; differ only in countability defaults and inferred class.

**Required traits (every Entity)**

#### `vso:individuation` *(IRI, required, exactly 1)*
One of `vso:Generic`, `vso:Named`, `vso:Kind`, `vso:Skolem`.
```json
{ "enum": ["Generic", "Named", "Kind", "Skolem"] }
```
**SHACL.** `vss:EntityShape` requires `sh:minCount 1`, `sh:maxCount 1`, `sh:in (vso:Generic vso:Named vso:Kind vso:Skolem)`.

#### `vso:animacy` *(IRI, required, exactly 1)*
One of `vso:Agentive`, `vso:Inert`. Agents — humans, animals, animated mechanisms — get `Agentive`. Inanimate matter — furniture, vegetation, weapons-at-rest — gets `Inert`.

#### `vso:countability` *(IRI, required, exactly 1)*
One of `vso:Count`, `vso:Mass`, `vso:Collective`. Substances are Mass; Aggregates are Collective; otherwise Count.

#### `vso:class` *(string bareword or IRI, required, exactly 1)*
Domain class — see Appendix C registry. Use `Unknown` rather than guessing.

**Optional traits/edges**

#### `vso:affordance` *(IRI, optional, 0..n)*
Subset of `{Holdable, Wearable, Mountable, Container, Edible, ...}`. Reasoner-friendly; consumers MAY use it to filter.

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
| `vso:dimension` | IRI in VSO | yes (1) | One of `Color, Weight, Material, Affect, Age, Role, Size, Enchantment, ActionState, Layout, Focal, ...` | `vss:QualityShape` requires exactly 1 |
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
**SHACL.** `vss:EventShape` (and the Process/Stative variants) require `sh:datatype xsd:string; sh:minCount 1; sh:maxCount 1` on `vso:lemma`.

**Thematic roles (zero or more, depending on class)**

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

| Field | Type | Required | Description | Validation |
|---|---|---|---|---|
| `vso:figure` | IRI ref → Entity | yes (1) | The thing being located | `vss:SpatialFactShape` |
| `vso:ground` | IRI ref → Entity | yes (1) | The reference frame | `vss:SpatialFactShape` |
| `vso:rcc` | IRI in `rcc:` | no (0..1) | One of `DC, EC, PO, EQ, TPP, NTPP, TPPi, NTPPi` | `vss:RccValueShape` |
| `vso:directional` | IRI in VSO | no (0..1) | `above, below, left_of, right_of, in_front_of, behind` | requires viewer |
| `vso:proximal` | IRI in VSO | no (0..1) | `near, far, adjacent` | none |
| `vso:viewer` | IRI ref → CameraView | conditional | **REQUIRED iff `vso:directional` is present** | `vss:DirectionalNeedsViewerShape` |

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
    "proximal":    { "enum": ["near","far","adjacent"] },
    "viewer":      { "type": "string" }
  },
  "if":   { "required": ["directional"] },
  "then": { "required": ["viewer"] }
}
```

**SHACL.** `vss:DirectionalNeedsViewerShape` raises a violation when `vso:directional` is present without `vso:viewer`. Negative fixture: [`tests/fixtures/bad_no_viewer.ttl`](../tests/fixtures/bad_no_viewer.ttl).

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

`allen:before`, `allen:after`, `allen:meets`, `allen:metBy`, `allen:overlaps`, `allen:overlappedBy`, `allen:starts`, `allen:startedBy`, `allen:during`, `allen:contains`, `allen:finishes`, `allen:finishedBy`, `allen:equals`. Inverses and transitivity are declared in [`ontology/allen.ttl`](../ontology/allen.ttl).

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
| `vso:rcc` | `rcc:DC, rcc:EC, rcc:PO, rcc:EQ, rcc:TPP, rcc:NTPP, rcc:TPPi, rcc:NTPPi` |
| `vso:directional` | `above, below, left_of, right_of, in_front_of, behind` |
| `vso:proximal` | `near, far, adjacent` |

---

## 6. JSON Schema and validation rules

VSON has **two layers of validation**:

| Layer | Tool | Scope | Failure mode |
|---|---|---|---|
| Structural (envelope shape) | JSON Schema | Wire payload only | rejects malformed envelopes |
| Semantic (graph well-formedness) | SHACL | Materialized RDF graph | rejects scenes that violate VSO constraints |

A document MUST pass both. JSON Schema alone is insufficient — it cannot express "directional needs viewer" or "Composition needs at least one depicts." SHACL is the load-bearing validator; JSON Schema is a fast structural pre-check.

### 6.1 The extractor envelope schema

**File:** [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json). Reproduced inline for §5-style cross-reference.

#### `scene_id` *(string, required)*
Stable, URL-safe scene identifier. ≤64 chars, `[A-Za-z0-9_-]`.
```json
{ "type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$" }
```

#### `version` *(string, required)*
The constant `"1.0"` for v1.0.
```json
{ "const": "1.0" }
```

#### `source` *(object, optional)*
Provenance of the scene. Required when `kind != "hand_authored"`.
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

#### `vson_p` *(string, required)*
The canonical authoring text — Penman.
```json
{ "type": "string", "minLength": 3 }
```

#### `vson_t` *(string, required)*
Turtle 1.2 / Turtle-star derived from `vson_p` via the reference transpiler.
```json
{ "type": "string", "minLength": 3 }
```
**Validation rule.** `parse(vson_p) -> emit_turtle()` MUST equal `vson_t` modulo blank-node renaming and triple ordering.

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
SHACL report.
```json
{
  "type": "object",
  "required": ["conforms"],
  "properties": {
    "conforms": { "type": "boolean" },
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
    "sha256": "9c3a...e7f1",
    "width_px": 1024,
    "height_px": 768,
    "captured_at": "2026-05-02T11:14:00Z"
  },
  "vson_p": "(scene / Composition :viewedBy (cam / CameraView :angle low :focalLength 35mm :framing medium_shot) :depicts (alice / PhysicalObject :individuation Named :animacy Agentive :countability Count :class Human))",
  "vson_t": "@prefix vso: <https://vson.dev/v1/ontology#> .\n:scene a vso:Composition .\n:scene vso:viewedBy :cam .\n...",
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

The SHACL shapes file is [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl). The shapes are normative; this table is informative.

| Shape | Targets | Constraint | Negative fixture |
|---|---|---|---|
| `vss:CompositionShape` | `vso:Composition` | `sh:minCount 1` on `vso:depicts` | none (would target an empty Composition) |
| `vss:DirectionalNeedsViewerShape` | `vso:SpatialFact` with `vso:directional` | requires `vso:viewer` | [`bad_no_viewer.ttl`](../tests/fixtures/bad_no_viewer.ttl) |
| `vss:RccValueShape` | `vso:SpatialFact / vso:rcc` | `sh:in (rcc:DC rcc:EC ...)` | none |
| `vss:EventShape` | `vso:Event`, `vso:Process`, `vso:Stative` | exactly one `vso:lemma` (`xsd:string`) | [`bad_event_no_lemma.ttl`](../tests/fixtures/bad_event_no_lemma.ttl) |
| `vss:QualityShape` | `vso:Quality` | exactly one `vso:dimension` and one `vso:value` | none |
| `vss:FrameNotDepictedShape` | `vso:depicts` | object MUST NOT be `vso:Frame` | [`bad_frame_depicted.ttl`](../tests/fixtures/bad_frame_depicted.ttl) |
| `vss:SpatialFactShape` | `vso:SpatialFact` | requires `vso:figure` and `vso:ground` | none |

---

## 7. Exporters

| Target | Mapping | Status (v1.0) |
|---|---|---|
| Cypher / Neo4j | `:s :p :o` → `(s)-[r:p]->(o)`; `<<:s :p :o>> :q :v` → `r.q = v` | **shipped** in `vson export cypher` |
| AMR | `Event` → AMR predicate; `agent`/`patient`/`instrument` → `:ARG0`/`:ARG1`/`:instrument` | spec only |
| Visual Genome | `(s, p, o)` → VG relation row; `bbox2d` → VG bbox | spec only |
| Pixar USD | `CameraView` → `UsdGeomCamera`; `Composition` → USD Stage | spec only |
| JSON-LD | `@context` mapping VSO namespace | shipped (see [`tools/schema/vson-jsonld.schema.json`](../tools/schema/vson-jsonld.schema.json)) |
| SPARQL-star | direct (no mapping needed) | shipped |

---

## 8. Versioning and extension

- **IRI immutability.** All IRIs under `https://vson.dev/v1/` are immutable. v2.0 will use `https://vson.dev/v2/`. Concurrent versions can coexist.
- **Backwards compatibility within v1.x.** v1.x MAY add classes, properties, and shapes. v1.x **MUST NOT** remove or rename existing terms, change cardinalities to be more restrictive, or change SHACL shapes in a way that invalidates previously-conformant documents.
- **Private extensions.** Authors MAY define private predicates under their own namespace. Private predicates SHOULD NOT shadow VSV terms. Documents using private predicates are **profile-specific**, not portable.
- **Closed vocabularies.** §5.12 lists closed enumerations. Producers **MUST NOT** invent values; consumers **MAY** treat unknown values as `Unknown`.

---

## 9. Examples gallery

Eleven scenes, ascending in complexity. Every example SHACL-conforms (verified by `make check` and `make cli-check`). Each file is a standalone VSON-P document.

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
**Demonstrates:** Talmy resolution — `vso:directional` requires `vso:viewer` at the schema level.

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

---

## 10. Reference implementations

| Implementation | Location | Scope | Tests |
|---|---|---|---|
| Python reference transpiler | [`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py) | Penman ↔ Turtle, normalizer | 12 unit, 4 SHACL, 1 smoke (17/17 ✓) |
| Rust CLI (`vson`) | [`cli/`](../cli) | `validate`, `convert p2t`, `export cypher` | 12 unit, 7 integration (19/19 ✓) |
| SHACL validator | `pyshacl` (shelled out by `vson validate`) | semantic well-formedness | 4 SHACL tests + 11 gallery passes |
| Bare-VLM extractor | [`tools/extractor/baseline/extract.py`](../tools/extractor/baseline/extract.py) | image → VSON-P | offline cassette test |
| Routing tables (single source of truth) | [`tools/penman/routing-tables.json`](../tools/penman/routing-tables.json) | shared by Python + Rust | embedded via `include_str!` |

A consumer is "VSON v1.0 reference-conformant" iff it accepts every document accepted by the Python reference transpiler + `pyshacl`, and rejects every document the reference rejects.

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

A reference migrator implementation is planned for v1.1 (`tools/migrate_v01.py`).

---

## 12. Changelog

See [`spec/CHANGELOG.md`](../spec/CHANGELOG.md). Highlights since v0.1:

- Replaced ad-hoc notation with **layered RDF-star + OWL 2 RL + SHACL** stack (`VSO/VSV/VSON-T/VSON-S/VSON-P/VSON-X`).
- Reified Events / Processes / Statives as nodes; added thematic roles aligned with PropBank/FrameNet/schema.org.
- Added `SpatialFact` with the **mandatory viewer for directional facts** (Talmy resolution).
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

Each major provider takes the skill body in a slightly different field; see the [skill README](../skills/vson-extractor/README.md) for working snippets against Anthropic, OpenAI, Gemini, OpenRouter, and the Anthropic Skills API. The studio at [`web/`](../web/) defaults to `SKILL.md`; pass `?prompt=full` to opt back to the longer 18 KB orchestrator prompt for maximum first-try conformance on hard scenes.

### 13.3 Conformance test

A model claims VSON-extractor support if it conforms on first try (no SHACL repair) for at least 4 of the 5 fixtures listed in [`skills/vson-extractor/conformance.json`](../skills/vson-extractor/conformance.json). The studio's repair loop (max 2 retries) is for graceful degradation, not for the certification path.

### 13.4 Why the skill, not the orchestrator prompt?

The orchestrator prompt at [`tools/extractor/prompts/orchestrator-system.md`](../tools/extractor/prompts/orchestrator-system.md) is 18 KB. It includes upstream-tool routing, decision policies P1–P13, and a long worked example with bbox detections. That prompt is right when an extractor pipeline (`vson generate`) is feeding the model upstream tool outputs and you need maximum first-try conformance.

The skill is right when a third-party caller wants to read VSON directly from an image with no pipeline — the model has nothing but the picture and the skill body. It is one-sixth the token cost, conforms on the gallery set ≥ 80% of the time, and is small enough that prompt-cache hit rates are irrelevant: at this size, every provider's input charge is a rounding error.

### 13.5 Public surface

The studio's "what is this" page lives at [`/about`](https://studio.vson.dev/about). It is the canonical public-facing explanation; the spec (this document) is the canonical machine-readable contract. They should not drift.

---

## Appendix A — Consolidated JSON Schemas {#appendix-a}

### A.1 Extractor response envelope

The full schema lives at [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) and is normative. Its `$id` is `https://vson.dev/v1/schema/vson-output.schema.json`.

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
5. Routing of bare IDs in object position depends on the parent role; see [`tools/penman/routing-tables.json`](../tools/penman/routing-tables.json).

---

## Appendix C — Class registry {#appendix-c}

Open registry — extensions MAY add domain classes under their own namespace, but the values listed below are the v1.0 canonical set.

**People / agents.** `Human, Knight, Queen, King, Soldier, Woman, Man, Child, Merchant, Monk, Servant, Civilian, Peasant`

**Animals.** `Animal, Boar, Dog, Horse, Cat, Bird, Fish, Wolf, Deer`

**Wearables / regalia / weapons / tools.** `Crown, Hat, Helmet, Sword, Spear, Bow, Shield, Scroll, Torch, Cup, Bowl, Plate, Throne, Chair, Bed, Vessel, Weapon, Regalia, Tool`

**Architecture / nature.** `Tree, Rock, Pillar, Building, Castle, House, Furniture, Lamp, Door, Window`

**Sky / atmosphere.** `Cloud, Sun, Moon, Sky, Star`

**Substances.** `Water, Smoke, Fire, Blood, Stone`

**Aggregates / collectives.** `Group, Crowd, Flock, Herd`

**Special.** `Apple` (Quick Start canonical), `Unknown` (always conformant fallback).

---

*This document is normative. Discrepancies between this document and the ontology / shapes / schema files are bugs to be fixed against this document.*
