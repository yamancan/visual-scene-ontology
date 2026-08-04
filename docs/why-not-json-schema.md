# Why not just a JSON schema?

Because most of the time you should, and this page is about the rest of the time.

If your extractor emits one object per image — a caption, a category, a handful of
attributes — a pydantic model handed to a structured-output endpoint is the right
tool, it costs you nothing, and VSON would be ceremony. The argument below is not
that JSON Schema is weak. It is that JSON Schema validates **one tree in
isolation**, and a scene is a **graph**: relations name objects by handle, a
direction is only meaningful relative to a viewpoint, and the legality of a slot
depends on what the node at the other end of a reference turns out to be. Every
constraint on this page that JSON Schema cannot express is an instance of that one
fact.

Four of them are named, each with the exact SHACL shape that expresses it and the
exact checked-in document that JSON Schema accepts and a `vson` gate rejects — the
gate named every time, because three of the four are `vson validate` and the fourth
deliberately is not. Run the commands. They are the argument.

---

## The short answer

| The constraint | JSON Schema | VSON |
|---|---|---|
| 1. A directional relation needs a viewer, and the viewer must be a camera | the *presence* half is expressible (`dependentRequired`); **the referent half is not** — a string cannot be followed to the node it names | `vss:DirectionalNeedsViewerShape` — [`bad_no_viewer.ttl`](../tests/fixtures/bad_no_viewer.ttl), [`directional_viewer_is_entity.ttl`](../tests/conformance/data/directional_viewer_is_entity.ttl) |
| 2. A Composition depicts **at least one Entity** | `minItems: 1` counts array members; it cannot ask whether any member is an Entity rather than a frame | `vss:CompositionShape` + `vss:FrameNotDepictedShape` — [`composition_no_depicts.ttl`](../tests/conformance/data/composition_no_depicts.ttl), [`bad_frame_depicted.ttl`](../tests/fixtures/bad_frame_depicted.ttl) |
| 3. Closed value sets, dispatched on the **bearer** and open outside the VSON namespace | `enum` closes a set at one position in the tree; it cannot condition on the class of the node carrying the slot, and it cannot be closed for one namespace and open for another | `vss:HasQualityShape`, the C2 gate — [`bad_frame_bears_quality.ttl`](../tests/fixtures/bad_frame_bears_quality.ttl), [`bad_orphan_term.ttl`](../tests/fixtures/bad_orphan_term.ttl) |
| 4. Figure and ground are not interchangeable on a reified fact | the two keys are required and that is the whole of it; nothing compares the two nodes they name | `vss:SpatialFactShape` + `vson verify --geometry`, `vson diff` — [`geometry_inconsistent_directional.ttl`](../tests/fixtures/geometry_inconsistent_directional.ttl) |

The specification states the first two in a single sentence, in [§6](vson.md#6-json-schema-and-validation-rules): *"JSON Schema alone is insufficient — it cannot express 'directional needs viewer' or 'Composition needs at least one depicts.'"* This page is that sentence with the receipts attached.

---

## What a P1 writes today

This is not a strawman. It is the model a competent engineer ships: pydantic v2,
`Literal` types for the closed vocabularies, ids for the cross-references,
`extra="forbid"` so the model cannot invent keys, and a `@model_validator` for the
rule the schema cannot carry.

```python
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

Animacy   = Literal["agentive", "inert"]
Topology  = Literal["DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPi", "NTPPi"]
Direction = Literal["above", "below", "left_of", "right_of", "in_front_of", "behind"]
Proximity = Literal["near", "far", "adjacent", "next_to", "facing"]


class Attribute(BaseModel):
    """One (dimension, value) pair: color=crimson, material=gold."""
    model_config = ConfigDict(extra="forbid")
    dimension: str
    value: str


class SceneObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="Unique handle. Relations refer to objects by it.")
    category: str
    animacy: Animacy
    bbox: Optional[tuple[float, float, float, float]] = Field(
        default=None, description="Normalized x, y, w, h, each in [0,1]."
    )
    attributes: list[Attribute] = Field(default_factory=list)


class Camera(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    angle: Literal["eye_level", "low_angle", "high_angle", "birds_eye", "worms_eye"]
    framing: Literal["extreme_close_up", "close_up", "medium_shot", "wide_shot"]


class Relation(BaseModel):
    """One spatial claim about two objects, named by id."""
    model_config = ConfigDict(extra="forbid")
    subject: str
    object: str
    topology: Optional[Topology] = None
    direction: Optional[Direction] = None
    proximity: Optional[Proximity] = None
    viewer: Optional[str] = Field(
        default=None, description="Camera id. Required when direction is set."
    )

    @model_validator(mode="after")
    def directional_needs_viewer(self) -> "Relation":
        if self.direction is not None and self.viewer is None:
            raise ValueError("a directional relation needs a viewer")
        if not (self.topology or self.direction or self.proximity):
            raise ValueError("a relation needs at least one of topology/direction/proximity")
        return self


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cameras: list[Camera] = Field(min_length=1)
    objects: list[SceneObject] = Field(min_length=1)
    relations: list[Relation] = Field(default_factory=list)
```

`Scene.model_json_schema()` is what you hand a structured-output endpoint. It is
good, and it is doing real work.

### What that already buys you, stated fairly

- **The closed vocabularies are enforced at the token level, not after the fact.**
  `Literal[...]` becomes `enum`, and a constrained decoder compiled from that schema
  — Outlines, XGrammar, llguidance, llama.cpp GBNF — makes `"direction": "aboove"`
  *unemittable* rather than merely invalid. That is strictly better than validating
  afterwards, and VSON does not disagree with it: this repository ships
  [`tools/grammar/vson-x.gbnf`](../tools/grammar/vson-x.gbnf), generated from the
  spec's own EBNF, for exactly the same reason. Constrained decoding and graph
  validation are complements. They answer different questions.
- **Required keys, cardinalities, conditional requirements, discriminated unions,
  numeric bounds and string patterns are all expressible** — `required`,
  `minItems`, `dependentRequired`, `if`/`then`, `oneOf` with a discriminator,
  `minimum`/`maximum`, `pattern`. Do not let anyone tell you JSON Schema is a type
  annotation. It is a constraint language, and within one tree it is a good one.
- **It costs nothing.** No new dependency, no new file format, no second artifact to
  keep in sync, and every vendor accepts it.

### And here is the first thing to notice

`Scene.model_json_schema()` **does not contain the `@model_validator`**. Checked:
the emitted schema carries no `dependentRequired`, and no trace of the string
`needs a viewer`. `Relation.required` is `["subject", "object"]` and nothing more.

That validator is Python. It runs in your process, after the model has already
emitted the tokens, over your field names. The endpoint never sees it, so it
cannot constrain generation. The consumer of your JSON never sees it either, so
they cannot re-run your gate without importing your package. This is the real
axis of the comparison, and the rest of the page returns to it.

---

## Where the tree stops

Every JSON document below was checked twice: with `Scene.model_validate(...)`, and
independently against `Scene.model_json_schema()` using `jsonschema`'s Draft
2020-12 validator, which never sees the `@model_validator` at all. Both accepted
every one of them. (Method: the model above, pasted verbatim, under pydantic
2.11.7 / jsonschema 4.25.1 / CPython 3. The documents on this page are the exact
inputs — re-run it.) Each is the JSON transliteration of a checked-in `.ttl`
fixture that `vson` rejects.

SHACL shapes below are quoted from [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl);
`# …` marks an elided comment block. Console output is verbatim, with `[…]`
marking elided lines.

### 1. A directional relation needs a viewer — and the viewer must be a camera

`left_of` is not a property of two regions. It is a property of two regions **and a
viewpoint**: the same pair of objects is `left_of` from the camera and `right_of`
from a character standing opposite. VSON makes the anchor mandatory
([C5](vson.md#2-conformance), [§3.3](vson.md#33-viewer-anchoring-directional-facts))
so that a directional claim is decidable at all.

```turtle
vss:DirectionalNeedsViewerShape a sh:NodeShape ;
    sh:targetSubjectsOf vso:directional ;
    sh:property [
        sh:path vso:viewer ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:class vso:CameraView ;
        # …
        sh:not [ sh:class vso:Entity ] ;
        sh:message "Directional spatial facts require exactly one vso:viewer for construal disambiguation (C5), and that viewer must be a CameraView, never an Entity."
    ] .
```

**Concede the first half.** `dependentRequired: {"direction": ["viewer"]}` expresses
"if `direction` is present, `viewer` must be present", in pure JSON Schema, no
Python. The model above does it in a validator only because pydantic will not emit
`dependentRequired` for you.

**The half that has no expression.** `viewer` is a *string*. JSON Schema has no way
to follow it. Nothing in the vocabulary — `$ref` resolves schemas, not instance
data — can ask whether that string names a declared node, or what kind of node it
names. Both of these are schema-valid:

```json
{"subject": "a", "object": "b", "direction": "above", "viewer": "c"}
{"subject": "a", "object": "b", "direction": "above", "viewer": "ghost"}
```

In the first, `c` is another depicted object — an anchor that is in the picture
rather than looking at it. In the second, `ghost` is nothing at all. VSON rejects
the first outright:

```console
$ vson validate tests/conformance/data/directional_viewer_is_entity.ttl
Validation Report
Conforms: False
Results (1):
Constraint Violation in NotConstraintComponent (http://www.w3.org/ns/shacl#NotConstraintComponent):
	Severity: sh:Violation
	Source Shape: [ … sh:not [ sh:class vso:Entity ] ; sh:path vso:viewer ]
	Focus Node: :sf
	Value Node: :c
	Result Path: vso:viewer
	Message: Directional spatial facts require exactly one vso:viewer for construal disambiguation (C5), and that viewer must be a CameraView, never an Entity.
FAIL tests/conformance/data/directional_viewer_is_entity.ttl (shacl)
one or more files failed validation
```

and the missing-viewer case fires the same shape's `sh:minCount`:

```console
$ vson validate tests/fixtures/bad_no_viewer.ttl
Validation Report
Conforms: False
Results (1):
Constraint Violation in MinCountConstraintComponent (http://www.w3.org/ns/shacl#MinCountConstraintComponent):
	[…]
	Focus Node: :sf
	Result Path: vso:viewer
	Message: Directional spatial facts require exactly one vso:viewer for construal disambiguation (C5), and that viewer must be a CameraView, never an Entity.
FAIL tests/fixtures/bad_no_viewer.ttl (shacl)
one or more files failed validation
```

Both are entries in the conformance suite — `t:validate-neg-directional-viewer-entity`
and `t:validate-neg-directional-viewer-min` in
[`tests/conformance/manifest.ttl`](../tests/conformance/manifest.ttl) — so a second
implementation is held to the same verdict.

### 2. A Composition depicts at least one **Entity**

```turtle
vss:CompositionShape a sh:NodeShape ;
    sh:targetClass vso:Composition ;
    sh:property [
        sh:path vso:depicts ;
        sh:minCount 1 ;
        sh:message "A Composition must depict at least one Entity (vso:depicts)."
    ] ;
    # … three further sh:property blocks (framedBy, viewedBy, rendersAs) … .

vss:FrameNotDepictedShape a sh:NodeShape ;
    sh:targetObjectsOf vso:depicts ;
    sh:not [ sh:class vso:Frame ] ;
    sh:message "vso:depicts must point to an Entity, not a Frame. Use vso:framedBy for the perspectival layer." .
```

**Concede the count.** `Field(min_length=1)` on `objects` emits `"minItems": 1`.
"At least one member" is expressible.

**The word that is not expressible is *Entity*.** VSON separates the depicted world
from the perspectival layer: a camera, a visual style, a scene context and a persona
are `vso:Frame`s, they attach with `vso:framedBy`, and `vso:depicts` **MUST NOT**
target one ([C9](vson.md#2-conformance)). A JSON array is a bag of members; asking
whether any member is a depicted thing rather than a frame means classifying the
members, and the members are wherever the model put them. This is schema-valid and
satisfies `minItems: 1`:

```json
{
  "cameras": [{"id": "cam", "angle": "eye_level", "framing": "medium_shot"}],
  "objects": [{"id": "cam", "category": "camera", "animacy": "inert"}],
  "relations": []
}
```

One object. Count satisfied. Nothing depicted — the scene's only "object" is the
apparatus that took the picture. VLMs do this: asked for the objects in an image
they return the frame, the border, the watermark, the photographer.

```console
$ vson validate tests/conformance/data/composition_no_depicts.ttl
Constraint Violation in MinCountConstraintComponent (…#MinCountConstraintComponent):
	[…]
	Focus Node: :scene
	Result Path: vso:depicts
	Message: A Composition must depict at least one Entity (vso:depicts).
FAIL tests/conformance/data/composition_no_depicts.ttl (shacl)

$ vson validate tests/fixtures/bad_frame_depicted.ttl
Constraint Violation in NotConstraintComponent (…#NotConstraintComponent):
	[…]
	Source Shape: vss:FrameNotDepictedShape
	Focus Node: :cam
	Value Node: :cam
	Message: vso:depicts must point to an Entity, not a Frame. Use vso:framedBy for the perspectival layer.
FAIL tests/fixtures/bad_frame_depicted.ttl (shacl)
```

### 3. Closed value sets — and which bearer may carry them

This is the constraint where JSON Schema is closest to winning, so state the win
first: `Literal[...]` → `enum` is exactly right for a fixed value list, and a
grammar compiled from it beats validation outright. VSON's own value sets are
closed the same way:

```turtle
vss:RccValueShape a sh:NodeShape ;
    sh:targetSubjectsOf vso:rcc ;
    sh:property [
        sh:path vso:rcc ;
        sh:in ( rcc:DC rcc:EC rcc:PO rcc:EQ rcc:TPP rcc:NTPP rcc:TPPi rcc:NTPPi ) ;
        sh:message "vso:rcc value must be one of the eight RCC-8 relations."
    ] .
```

Two things about closure do not fit inside an `enum`.

**(a) Which bearer may carry the slot at all.** A quality is borne by something that
can have qualities — an Entity, or the Composition itself for compositional
qualities like `Layout` and `Focal`. A camera cannot be crimson. The dispatch is on
the *class of the bearer*, and the bearer is a node reached by reference:

```turtle
vss:HasQualityShape a sh:NodeShape ;
    sh:targetSubjectsOf vso:hasQuality ;
    sh:or ( [ sh:class vso:Entity ] [ sh:class vso:Composition ] ) ;
    sh:message "Only a QualityBearer (an Entity, or a Composition bearing compositional qualities) may carry vso:hasQuality." .
```

Schema-valid, and wrong:

```json
{
  "cameras": [{"id": "cam", "angle": "eye_level", "framing": "medium_shot"}],
  "objects": [{"id": "cam", "category": "camera", "animacy": "inert",
               "attributes": [{"dimension": "color", "value": "blue"}]}],
  "relations": []
}
```

```console
$ vson validate tests/fixtures/bad_frame_bears_quality.ttl
Constraint Violation in OrConstraintComponent (…#OrConstraintComponent):
	[…]
	Source Shape: vss:HasQualityShape
	Focus Node: :cam
	Value Node: :cam
	Message: Only a QualityBearer (an Entity, or a Composition bearing compositional qualities) may carry vso:hasQuality.
FAIL tests/fixtures/bad_frame_bears_quality.ttl (shacl)
```

You *can* prevent this by construction in a pydantic model — put `attributes` on
`SceneObject` and not on `Camera`, and a camera cannot bear one. That works exactly
as long as your model keeps cameras and objects in separate keys. The moment the
output is a heterogeneous node list — which is what a scene *graph* is, and what a
VLM emits when the same array holds everything it saw — the guarantee is gone,
because the discriminator is a value the model chose, not a position in the tree.

**(b) Closure that holds for one namespace and not another.** The 21-dimension
registry ([§5.5](vson.md#55-vsoquality)) is closed *within* the VSON namespace and
deliberately open outside it: a pipeline MAY mint `:Ambience` under its own
namespace and stay conformant, and MUST NOT mint `vso:Ambience`. An `enum` cannot
say that — it is extensional, so it is either closed against your extension or not
closed at all. Nor does SHACL carry it; the shapes file says why, in the comment
beside `vss:QualityShape`:

> No `sh:in` on `vso:dimension`, deliberately — and this is the one place a reader
> will look for it. […] An `sh:in` listing the registry members would reject those
> documents, which §8 forbids.

It is decided instead by [`tools/c2_check.py`](../tools/c2_check.py), the third gate
`vson validate` runs, because deciding it needs the set of terms the *ontology*
declares — which is not in the document and not derivable from it:

```console
$ vson validate tests/fixtures/bad_orphan_term.ttl
  ORPHAN tests/fixtures/bad_orphan_term.ttl
      <https://w3id.org/vson/v1/ontology#Ambience> is asserted but declared in no ontology file
c2-closure: orphan VSO term detected (C2).
FAIL tests/fixtures/bad_orphan_term.ttl (c2)
one or more files failed validation
```

The conditional half is inside the same fixture. A few lines above the rejected
`vso:Ambience`, the same lamp bears `:q_local a vso:Quality ; vso:dimension :Layout`
— a dimension minted in the document's own namespace — and nothing objects to it.
One file, one gate, both halves of the closure.

And one thing an `enum` gives up that is easy to miss: `"above"` is a string whose
meaning lives in your prompt. `vso:above` is a name in a namespace that
dereferences — `https://w3id.org/vson/v1/ontology` answers with the ontology that
declares it — so a consumer who has never read your prompt can look up what you
meant, and a second pipeline can use the same name and mean the same thing.

### 4. Figure and ground are not interchangeable

A spatial claim in VSON is a **reified node**, not a triple in a list: a
`vso:SpatialFact` with one figure, one ground, an anchor, and up to one value from
each of three closed relation families.

```turtle
vss:SpatialFactShape a sh:NodeShape ;
    sh:targetClass vso:SpatialFact ;
    sh:property [
        sh:path vso:figure ; sh:minCount 1 ; sh:maxCount 1 ;
        sh:nodeKind sh:BlankNodeOrIRI
    ] ;
    sh:property [
        sh:path vso:ground ; sh:minCount 1 ; sh:maxCount 1 ;
        sh:nodeKind sh:BlankNodeOrIRI
    ] ;
    sh:or (
        [ sh:property [ sh:path vso:rcc ;         sh:minCount 1 ] ]
        [ sh:property [ sh:path vso:directional ; sh:minCount 1 ] ]
        [ sh:property [ sh:path vso:proximal ;    sh:minCount 1 ] ]
    ) ;
    # … plus sh:maxCount 1 on each of vso:rcc, vso:directional and vso:proximal …
    sh:message "SpatialFact must specify at least one of vso:rcc, vso:directional, or vso:proximal." .
```

**Concede the structure.** Required `subject`, required `object`, at-least-one-of
three optional relation slots — `required` plus `anyOf` says all of that. JSON
Schema is fine here.

**What it cannot reach is the asymmetry itself,** because the asymmetry is a claim
about the two nodes the two keys *name*, and JSON Schema never leaves the tree. It
cannot compare `subject` with `object` — there is no equality constraint across
instance locations, so `{"subject": "sign", "object": "sign", "direction": "left_of"}`
is schema-perfect. And it certainly cannot compare their boxes. This is
schema-valid and false:

```json
{
  "cameras": [{"id": "cam", "angle": "eye_level", "framing": "wide_shot"}],
  "objects": [
    {"id": "door", "category": "door", "animacy": "inert", "bbox": [0.10, 0.30, 0.30, 0.60]},
    {"id": "sign", "category": "sign", "animacy": "inert", "bbox": [0.70, 0.35, 0.15, 0.10]}
  ],
  "relations": [
    {"subject": "sign", "object": "door", "direction": "left_of", "viewer": "cam"}
  ]
}
```

The sign's centroid is at x = 0.775 and the door's at x = 0.25. The document says
`left_of`. Its own numbers say the opposite. Because the fact is reified and
anchored, that contradiction is *decidable* — and note where it is decided. This
document is a **conformant VSON document**: `vson validate` exits 0 on it, because
no numbered clause ever required a direction to agree with a box, and [§8.2](vson.md#82-tightening-enforcement-within-v1x)
forbids inventing one inside v1.x. It is `vson verify --geometry`, a separate
check with a separate verdict, that reads the rectangles:

```console
$ vson verify --geometry tests/fixtures/geometry_inconsistent_directional.ttl
  INCONSISTENT tests/fixtures/geometry_inconsistent_directional.ttl  [2 relation(s): 1 consistent; 1 inconsistent]
      inconsistent  sf_sign_door vso:directional vso:left_of  figure sign "0.70,0.35,0.15,0.10"  ground door "0.10,0.30,0.30,0.60"
          left_of holds exactly when the figure's centroid sits further left (smaller x) than the ground's; here the figure's is 0.775 and the ground's is 0.25.
geometry-consistency: 1 asserted relation(s) contradicted by the document's own geometry. No image was read.
FAIL tests/fixtures/geometry_inconsistent_directional.ttl (geometry)
one or more files assert a relation their own geometry contradicts. No image was read; this is not a conformance verdict (docs/vson.md §5.13).
```

Note what made that possible: the mandatory viewer from constraint 1. "Further
left" is meaningless until you say *left from where*, and the fact carries its
anchor, so the rule can be stated once and executed
([§5.13](vson.md#513-geometry-consistency-vson-verify---geometry)).

The asymmetry is also *measurable*. [`vson diff`](vson.md#515-graph-agreement-vson-diff)
aligns two extraction runs and scores them per layer;
[`tests/fixtures/diff/run_b.ttl`](../tests/fixtures/diff/run_b.ttl) is
`run_a.ttl` with the figure and ground swapped (among other changes), and the swap
shows up where it belongs:

```console
$ vson diff tests/fixtures/diff/run_a.ttl tests/fixtures/diff/run_b.ttl
vson diff — Smatch graph agreement (docs/vson.md §5.15)
  a  tests/fixtures/diff/run_a.ttl  (23 triples)
  b  tests/fixtures/diff/run_b.ttl  (26 triples)
  alignment: seed 0, 5 restarts

  layer              match      a      b  precision   recall       F1
  objects                4      4      4     1.0000   1.0000   1.0000
  attributes             7      8      8     0.8750   0.8750   0.8750
  spatial                3      6      6     0.5000   0.5000   0.5000
    viewer-blind         3      5      5     0.6000   0.6000   0.6000
  frames                 5      5      8     1.0000   0.6250   0.7692
  events                 0      0      0          —        —        —
  other                  0      0      0          —        —        —
  overall               19     23     26     0.8261   0.7308   0.7755
smatch: the two documents differ (F1 0.7755). Agreement between two documents, not evidence about the image.
tests/fixtures/diff/run_a.ttl and tests/fixtures/diff/run_b.ttl are not the same graph. This is agreement between two documents; no image was read and neither document is thereby correct (docs/vson.md §2.1).
```

A regression lands on **spatial**, not on one aggregate number. Two JSON blobs
whose relation lists disagree about direction give you a diff of two strings —
and only after you have solved the problem `vson diff` solves first, which is that
two independent runs give the same objects different ids and a textual diff is
therefore worthless. The tool's own last line is the honest caveat: agreement
between two documents is not evidence about the image.

**Stated honestly:** VSON's SHACL layer does *not* reject `figure = ground` either —
no shape constrains the two to be different, and you can read that off the shape
quoted above. That case is caught by the geometry gate, and only when both nodes
carry a `vso:bbox2d`. Where a check does not exist, this page says so.

---

## The actual argument: where the check lives

The comparison is not "can this constraint be checked" — arbitrary Python checks
anything. It is **where the check lives**, and who can run it.

| | JSON Schema | Your pydantic validators | VSON SHACL shapes |
|---|---|---|---|
| Reaches the decoder (can prevent the bad token) | **yes** — compile it to a grammar | no — runs after generation | no — runs after generation |
| Runs without your code | **yes** — any JSON Schema validator | no — it is your package | **yes** — any SHACL engine |
| Crosses a reference to another node | **no** | yes — you write the lookup | **yes** — that is what shapes are |
| Constrains a node by the class of its bearer | **no** | yes — you write the dispatch | **yes** — `sh:targetSubjectsOf` + `sh:class` |
| Travels with the data | as a `$id` you host | **no** | as an IRI that dereferences |
| Language-neutral | yes | no — Python | yes |

Three of those rows are a clean win for JSON Schema and it deserves them — nothing
here reaches the decoder the way a compiled grammar does. The rows that decide the
argument are the two in the middle and "travels with the data": a pydantic
validator is a private, monolingual, non-transferable gate, and a published SHACL
shape is a public one. When the party receiving your scene graph is a different
team, a different service, next quarter, or a reviewer asking how you knew the
output was well-formed, "run `vson validate`" is an answer and "import our package"
is a dependency.

That is also why the constraints are not just documented: they are a
[conformance suite](../tests/conformance/manifest.ttl) of documents and the verdict
each one must get, which is what makes a *second* implementation possible at all
([§2.2](vson.md#22-claiming-conformance--the-test-suite)).

---

## The alternatives, and where each one wins

Named honestly. Several of these are better than VSON for the job they are for.

- **pydantic + a vendor structured-output mode (Instructor, `response_format`,
  tool schemas).** The default, and correct when the output is a **record**: one
  object, flat-ish fields, no cross-references, retries cheap. Zero new concepts.
  If this describes your extractor, stop here.
- **Outlines / XGrammar / llguidance / llama.cpp GBNF.** Constrained decoding
  against weights you control. Wins when you want **zero retries**: the schema
  becomes a grammar and the invalid token is never sampled. Not a rival — VSON
  ships a GBNF for its compact syntax for the same reason. Use both.
- **BAML.** A schema language with its own type system, its own prompt-and-type
  colocation, and generated clients in several languages. Wins when the contract
  must hold **across services written in different languages** and you want one
  place to change it.
- **Vendor JSON / structured-output modes for image models.** Wins when **the model
  owns the schema** — layout, region or bounding-box modes where the provider's own
  format is what the model was trained to emit. Adopting theirs beats translating
  into yours.
- **A property graph (Neo4j, Cypher) with your own constraints.** Wins when you
  already run the database and the constraints can be enforced at write time. VSON
  exports Cypher (`vson export cypher`) precisely so this is a destination rather
  than a competitor.
- **VSON.** Wins when the output is a **graph** whose constraints are **relational
  and viewer-relative**: a slot whose legality depends on the node it points at, a
  value vocabulary that has to mean the same thing in someone else's pipeline, an
  agreement metric that has to survive both runs renaming every node, and a gate a
  consumer can re-run without importing your code.

---

## When VSON is the wrong choice

- **One object per image, no relations.** A pydantic model is smaller, faster to
  write, and enforced at decode time. Use it.
- **Nothing outside your pipeline reads the output.** Portability is most of what
  you are paying for. If the reader is always your own process, a private model is
  cheaper.
- **You need prose.** VSON has no field for a paragraph of description. It renders
  captions *out* of a graph deterministically; it does not carry free text in.
- **You cannot add a SHACL engine to the consumer.** The gate is `rdflib` + a SHACL
  engine (or the Rust CLI, which shells to them). That is a real dependency and a
  real cost. The studio runs two of the three gates in a browser through Pyodide,
  which is the cheapest form of that cost, not the absence of it.
- **What you actually need is "is this description true of the picture".**
  Validation is not that, and this project says so in its own normative text
  ([§2.1](vson.md#21-what-conformance-establishes)): a green `vson validate` is a
  statement about the graph, not about the image. `vson verify --geometry` is a
  partial answer — it catches a document contradicted by its own boxes, and reads
  no pixels. If you need groundedness, you need ground truth, and neither a JSON
  schema nor a SHACL shape is going to give it to you.

---

## Run every claim on this page

From a checkout, after `cd cli && cargo build --release && cd .. && make deps`:

```bash
V=cli/target/release/vson

# 1. directional needs a viewer, and the viewer must be a camera
$V validate tests/fixtures/bad_no_viewer.ttl                             # exit 1, shacl
$V validate tests/conformance/data/directional_viewer_is_entity.ttl      # exit 1, shacl

# 2. a Composition depicts at least one Entity
$V validate tests/conformance/data/composition_no_depicts.ttl            # exit 1, shacl
$V validate tests/fixtures/bad_frame_depicted.ttl                        # exit 1, shacl

# 3. closed value sets, bearer dispatch, namespace-conditional closure
$V validate tests/fixtures/bad_frame_bears_quality.ttl                   # exit 1, shacl
$V validate tests/fixtures/bad_orphan_term.ttl                           # exit 1, c2

# 4. figure/ground asymmetry on a reified fact
$V validate       tests/fixtures/geometry_inconsistent_directional.ttl   # exit 0 — conformant
$V verify --geometry tests/fixtures/geometry_inconsistent_directional.ttl # exit 1 — and false
$V diff tests/fixtures/diff/run_a.ttl tests/fixtures/diff/run_b.ttl      # spatial F1 0.5000

# and all of it at once, as the verdict a second implementer must reproduce
make conformance
```

Every fixture named above is an entry in
[`tests/conformance/manifest.ttl`](../tests/conformance/manifest.ttl) carrying the
shape that must fire and the verdict that must come back, so none of these outputs
is a claim this page is making on its own recognisance.
