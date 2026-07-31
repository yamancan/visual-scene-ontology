# VSON v1.0 — Specification

**Status:** Superseded by docs/vson.md (v1.1, 2026-05-07). Retained for historical reference; do not cite it as the current spec.
**Note:** in this historical document, **VSON-X** names the exporter layer (§8 below). v1.1 reassigned VSON-X to the compact sigil syntax, and exporters are now §7 of `docs/vson.md`.
**Namespace:** the `https://vson.dev/…` IRIs below are the names v1.0 actually published, retained here unchanged as the record; v1.2 remints every VSON namespace under `https://w3id.org/vson/` and withdraws these — see `docs/vson.md` §5.1.
**Author:** Yamancan (github.com/yamancan)
**Supersedes:** v0.1 (deprecated; see `spec/vson-spec-v0.1-deprecated.md`)

---

## 1. Scope

VSON specifies how to encode a visual scene — its entities, qualities, spatial layout, events, perspectival framing, and authorial annotations — as an **RDF-star graph** conforming to a published ontology and validated by published SHACL shapes.

VSON is **not a new notation**. It is a layered specification:

```
VSON-X     Exporters: Cypher · AMR · Visual Genome · USD · JSON-LD
VSON-S     SHACL shapes (well-formedness)
VSON-T     Canonical concrete syntax: Turtle-star
VSON-P     Authoring concrete syntax: Penman (AMR-style nested)
VSV        Closed vocabulary (predicates, role names, dimensions)
VSO        Ontology (TBox) — OWL 2 RL; DOLCE-inspired top-level taxonomy
           (Endurant / Perdurant / Quality / Region)
RDF-star   Abstract semantics (W3C RDF 1.2)
```

## 2. Conformance

A document is a **conformant VSON v1.0 document** iff:

1. It is a syntactically valid Turtle-star (VSON-T) or Penman-VSON (VSON-P) document.
2. It imports the VSO ontology and VSV vocabulary IRIs.
3. It validates against the VSON-S SHACL shapes.
4. Every `vso:Composition` it declares has at least one `vso:depicts` edge.

The keywords MUST, SHOULD, MAY are interpreted per RFC 2119.

## 3. Namespaces

| Prefix | IRI                                  |
|--------|--------------------------------------|
| `vso:` | `https://vson.dev/v1/ontology#`      |
| `vsv:` | `https://vson.dev/v1/vocab#`         |
| `vss:` | `https://vson.dev/v1/shapes#`        |
| `rcc:` | `https://vson.dev/v1/rcc8#`          |
| `allen:` | `https://vson.dev/v1/allen#`       |
| `owl:` | `http://www.w3.org/2002/07/owl#`     |
| `rdf:` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `rdfs:`| `http://www.w3.org/2000/01/rdf-schema#` |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#`  |
| `sh:`  | `http://www.w3.org/ns/shacl#`        |

## 4. Core ontology (VSO, normative summary)

### 4.1 Top-level taxonomy (DOLCE-inspired)

The four top categories below take their names and the endurant/perdurant cut from DOLCE (Masolo, Borgo, Gangemi, Guarino & Oltramari 2003, *WonderWeb Deliverable D18: Ontology Library (final)*, ISTC-CNR). They are *inspired* by it, not aligned with it: no DOLCE IRI is imported and no DOLCE axiom is asserted. See `docs/vson.md` Appendix E for the full bibliography.

```
vso:Entity
├─ vso:Endurant
│   ├─ vso:PhysicalObject
│   ├─ vso:Aggregate
│   └─ vso:Substance
├─ vso:Perdurant
│   ├─ vso:Event       (punctual / completable)
│   ├─ vso:Process     (durative)
│   └─ vso:Stative     (gaze, hold, wear, believe)
├─ vso:Quality
└─ vso:Region

vso:Frame              (perspectival layer; NOT an Entity)
├─ vso:SceneContext
├─ vso:VisualStyle
├─ vso:CameraView
└─ vso:Composition     (mereological root; named graph)

vso:SpatialFact        (reified spatial relation, with viewer)
vso:Negation           (reified negated statement)
vso:Quantification
vso:BeliefState        (reified propositional attitude)
```

### 4.2 Trait properties (replace v0.1 four-fold sigil mess)

Orthogonal axes attached to `vso:Entity`:

- `vso:individuation` ∈ { `vso:Generic`, `vso:Named`, `vso:Kind`, `vso:Skolem` }
- `vso:animacy` ∈ { `vso:Agentive`, `vso:Inert` }
- `vso:countability` ∈ { `vso:Count`, `vso:Mass`, `vso:Collective` }
- `vso:affordance` ⊆ { `vso:Holdable`, `vso:Wearable`, `vso:Mountable`, `vso:Container`, `vso:Edible`, … }

A "v0.1 Item" is a `PhysicalObject` with `affordance ⊇ {Holdable}`.
A "v0.1 Unique Object" is any `Entity` with `individuation = Named`.

### 4.3 Property characteristics

VSV declares standard OWL property characteristics; the reasoner derives closure:

- `vso:nextTo`, `vso:facing`, `vso:adjacent` — `owl:SymmetricProperty`
- `vso:partOf` — `owl:TransitiveProperty`; `owl:inverseOf vso:hasPart`
- `vso:before`, `vso:after` — `owl:TransitiveProperty`; mutually `owl:inverseOf`
- All Allen and RCC-8 inverses are declared.

## 5. Vocabulary (VSV, normative)

### 5.1 Spatial — RCC-8 + directional + proximal

| Group | Predicates |
|---|---|
| Topological (RCC-8) | `rcc:DC` `rcc:EC` `rcc:PO` `rcc:EQ` `rcc:TPP` `rcc:NTPP` `rcc:TPPi` `rcc:NTPPi` |
| Directional (frame-relative) | `vso:above` `vso:below` `vso:leftOf` `vso:rightOf` `vso:inFrontOf` `vso:behind` |
| Proximal | `vso:near` `vso:far` `vso:adjacent` |

**Directional predicates appear only on `vso:SpatialFact` nodes that ALSO carry a `vso:viewer` referencing a `vso:CameraView`.** Bare directional triples are non-conformant. Directional facts are viewer-anchored by schema — VSON commits to the relative frame of reference (Levinson 2003) and makes the anchor explicit and machine-checkable; intrinsic and absolute frames are out of scope for v1.x. Figure/ground asymmetry follows Talmy 2000. The RCC-8 names are those of Randell, Cui & Cohn 1992, taken as a closed value vocabulary rather than as the composition calculus; full citations are in `docs/vson.md` Appendix E.

### 5.2 Temporal — Allen interval algebra

The thirteen base relations of Allen 1983, again as names with inverses rather than as the composition table (see `docs/vson.md` Appendix E):

`allen:before` `allen:after` `allen:meets` `allen:metBy` `allen:overlaps` `allen:overlappedBy` `allen:starts` `allen:startedBy` `allen:during` `allen:contains` `allen:finishes` `allen:finishedBy` `allen:equals`

### 5.3 Thematic roles

A closed inventory of coarse VerbNet-style thematic roles (Kipper Schuler 2005); PropBank's per-sense argument numbering (Palmer, Gildea & Kingsbury 2005) and FrameNet's frame-specific role names (Baker, Fillmore & Lowe 1998) are the finer-grained alternatives VSON deliberately avoids. Citations in `docs/vson.md` Appendix E.

Used on `vso:Event` and `vso:Process`:
`vso:agent` `vso:patient` `vso:theme` `vso:instrument` `vso:recipient` `vso:source` `vso:goal` `vso:beneficiary` `vso:experiencer` `vso:stimulus` `vso:location` `vso:time` `vso:manner` `vso:cause` `vso:result`

Used on `vso:Stative`:
`vso:experiencer` `vso:stimulus` `vso:theme` `vso:holder`

### 5.4 Other relation groups

| Group | Predicates |
|---|---|
| Mereology | `vso:partOf` `vso:hasPart` `vso:properPartOf` `vso:overlaps` `vso:disjoint` |
| Possession (stative) | `vso:holds` `vso:wears` `vso:owns` `vso:carries` |
| Causal | `vso:causes` `vso:enables` `vso:prevents` `vso:triggers` |
| Modal / attitudinal | `vso:believes` `vso:intends` `vso:perceives` |
| Frame attachment | `vso:framedBy` `vso:depicts` `vso:rendersAs` `vso:viewedBy` `vso:hasQuality` |
| Geometry | `vso:bbox2d` `vso:position3d` `vso:scale3d` `vso:rotation` `vso:occludes` `vso:visibleFraction` |

## 6. Reification patterns

Anything modifiable, negatable, quantifiable, or referable is a node:

| Phenomenon | Pattern |
|---|---|
| Action | `Event` node + thematic-role edges |
| Property | `Quality` node with `dimension`/`value`; bearer linked via `hasQuality` |
| Spatial relation | `SpatialFact` node with `figure`/`ground`/`rcc`/`directional`/`viewer` |
| Negation | `Negation` node with `negatedStatement <<s p o>>` |
| Belief | `BeliefState` node with `experiencer`/`proposition <<s p o>>` |
| Quantification | `Quantification` node with `quantifier`/`variable`/`domain`/`scope <<s p o>>` |
| Probability | RDF-star quoted-triple annotation `<<s p o>> vso:probability "0.7"` (canonical) **or** reified `vso:Annotation` node with `annotatedSubject/Predicate/Object` (RDF 1.1 portable) |
| Coreference | `owl:sameAs` |

## 7. Concrete syntaxes

### 7.1 VSON-T (canonical, machine)

VSON-T is **Turtle 1.2 with RDF-star** (`<< s p o >>` quoted triples). No syntactic deviation from W3C Turtle-star.

### 7.2 VSON-P (authoring, human)

VSON-P is a Penman-style nested concrete syntax. Form:

```
node ::= "(" var "/" ConceptIRI ( ":" role target )* ")"
target ::= var | ConceptIRI | literal | node
```

Each VSON-P node compiles to:
1. A blank node (or named IRI if the variable is `:foo`-prefixed) typed by `ConceptIRI`.
2. One triple `<bnode> <role> <target>` per role. Targets are recursively compiled.
3. Reentrancy: bare variables (without `/`) refer to a previously-declared node.

A VSON-P document MUST round-trip with VSON-T modulo blank-node renaming and triple ordering.

## 8. Exporters (VSON-X)

| Target | Mapping (sketch) |
|---|---|
| Cypher / Neo4j | `:s :p :o` → `(s)-[r:p]->(o)` ; `<<:s :p :o>> :q :v` → `r.q = v` |
| AMR | `vso:Event` → AMR predicate ; `vso:agent` → `:ARG0` ; `vso:patient` → `:ARG1` ; `vso:instrument` → `:instrument` |
| Visual Genome | `(s, p, o)` → VG relation row ; `vso:bbox2d` → VG bbox |
| Pixar USD | `vso:CameraView` → `UsdGeomCamera` Prim with schema attrs ; `vso:Composition` → USD Stage |
| JSON-LD | `@context` mapping the VSO IRI namespace |
| SPARQL-star | direct (no mapping needed) |

## 9. Compatibility, versioning, and extension

- VSON v1.0 IRIs are **immutable**. Future versions use `https://vson.dev/v2/...` IRIs.
- Authors MAY extend VSV with private predicates under their own namespace; private predicates SHOULD NOT shadow VSV terms.
- Documents using only VSV core terms are **portable**; documents using extensions are **profile-specific**.

## 10. Migration from v0.1

| v0.1 construct | v1.0 form |
|---|---|
| `{id:class}` Object | `Entity` with `individuation = Generic` |
| `@id:class` Unique Object | `Entity` with `individuation = Named` |
| `[id:type]` Item | `PhysicalObject` with `affordance ⊇ {Holdable}` |
| `<id:k=v>` Attribute | `Quality` node with `dimension k` and `value v`; bearer linked via `hasQuality` |
| `~id:scene{...}` | `SceneContext` with typed properties |
| `%id:style{...}` | `VisualStyle` with typed properties |
| `$id:camera{...}` | `CameraView` with typed properties |
| `#id:composition{...}` | `Composition` (mereological root) |
| `[A:verb instrument=x]` edge | `Event` node + `vso:agent` / `vso:patient` / `vso:instrument` edges |
| `[P:on]` edge | `SpatialFact` with `vso:rcc` and/or `vso:directional` (+ `vso:viewer` if directional) |
| `[P:has]` edge to attribute | `vso:hasQuality` to `Quality` node |
| `[P:scopes]` from supplementary | `vso:framedBy` from `Composition` to `Frame` subtype |
| `[P:contains]` | `vso:depicts` (Composition → Entity) or `vso:partOf` (mereology) |

There is no migrator tool. v0.1 documents must be migrated by hand using the table above.
