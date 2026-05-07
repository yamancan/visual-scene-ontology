# Changelog

## v1.1 — 2026-05-07

### VSON-X (compact concrete syntax)

A third concrete syntax alongside Penman (VSON-P) and Turtle-star (VSON-T).
Optimized for LLM emission and human authoring — eight prefix sigils, no
brackets, line-significant.

| Sigil | Kind | Example |
|---|---|---|
| `~` | Composition root | `~scene` |
| `/` | Concept marker | `/PhysicalObject`, `/CameraView` |
| `@` | Named/Skolem handle | `@alice`, `@cam` |
| `*` | Quality kv / direct property | `*color red`, `*angle eye_level` |
| `>` | Stative role-edge | `@bob > hold sword` |
| `>>` | Event/Process role-edge | `@bob >> strike boar *instrument sword` |
| `!` | Asymmetric SpatialFact | `crown ! EC @alice ^cam *dir above` |
| `&` | Symmetric SpatialFact (2 emissions) | `a & near & b` |
| `^` | Viewer anchor | `^cam` |

- Bearer-class dispatch for `*K V`: Frames take direct properties,
  Entities reify Quality nodes (with seven special direct-property
  exceptions: `class`, `bbox2d`, `position3d`, `scale3d`, `rotation`,
  `visibleFraction`, `embodies`).
- Symmetric-by-construction: `&` emits two SpatialFact nodes with
  figure/ground swapped — closes v0.1's asymmetry-by-fiat bug.
- LL(1) grammar; lead-token rule allows multi-line items without
  significant whitespace.
- Round-trip parity: every gallery scene has an `examples/gallery-x/N.x.vson`
  form whose RDF graph is equivalent (modulo blank-node identity for
  auto-anonymous reified nodes) to its Penman counterpart.

### Persona / cross-document identity

- New ontology classes and properties: `vso:Persona`, `vso:embodies`,
  `vso:hasInvariant`.
- New SHACL shapes: `vss:PersonaShape`, `vss:EmbodimentConsistencyShape`
  (Warning severity).
- VSON-X handles Personas as Frames: `/Persona @alice_id *hair auburn …`,
  referenced from Entities via `*embodies @alice_id`.

### Caption renderer

- `tools/render/caption.py`: deterministic graph → English caption,
  fully template-driven, no LLM.
- `vson export caption <file>` CLI subcommand (Rust shell-out).
- Studio "Caption" export tab.
- 11 frozen ground-truth fixtures under `tests/fixtures/captions/` for
  byte-identical CI.

### SHACL profiles

- `shapes/vson-shapes-relaxed.ttl`: authoring-time profile with
  `vss:DirectionalNeedsViewerShape`, `vss:EventShape lemma`, and
  `vss:QualityShape` demoted to `sh:Warning`.
- `vson validate --partial <file>` opts into the relaxed profile.
- Default `vson validate` is byte-identical to v1.0 (strict profile).

### Ontology gap fixes

- Declared `vso:class` (Entity → IRI) and `vso:modifier` (Quality →
  string), both of which were used in examples but never declared.
- Removed `owl:SymmetricProperty` markings from `vso:near` / `far` /
  `adjacent` / `nextTo` / `facing` — they're values of `vso:proximal`,
  not predicates, so the inference fired on zero triples.

### Tooling

- `tools/vson_x/` package: tokenizer + parser + emitter + cross-syntax
  graph-equivalence helper (`equiv.py`).
- `tools/vson_ast.py`: shared AST types between Penman and VSON-X.
- `vson convert x2t <file.x.vson>` CLI subcommand.
- `make x-check` runs the VSON-X gallery round-trip suite (11 pairs).
- Schema versioning: `tools/schema/vson-output.schema.json` accepts
  `version` ∈ {1.0, 1.0.5, 1.1} and adds optional `vson_x` and
  `conformance.profile` fields.

### Tests
- 48 Python tests (was 17): + 24 VSON-X (lexer / parser / emitter /
  round-trip), + 7 caption renderer.
- 10 Rust tests (was 9): + 1 `convert x2t` golden.

### Backwards compatibility

- All v1.0 documents validate unchanged under `vson validate`.
- `examples/throne_room.vson` and the 11-scene gallery remain
  byte-identical and SHACL-conformant.
- The v1.0 envelope schema continues to validate (additive change only).

## v1.0 — 2026-05-01 (initial)

Complete redesign. **v0.1 deprecated.**

### Architecture
- Layered specification on RDF-star, OWL 2 RL, SHACL, SPARQL-star.
- Two concrete syntaxes: Turtle-star (VSON-T, canonical) and Penman (VSON-P, authoring).
- Reference Penman ↔ Turtle-star transpiler (stdlib-only Python).

### Ontology (VSO)
- DOLCE-aligned top: `Endurant` / `Perdurant` / `Quality` / `Region`, with `Frame` disjoint from `Entity`.
- Trait-bundle entity model: `individuation × animacy × countability × affordance` orthogonal axes — replaces the v0.1 four-fold sigil mess.
- `Frame` taxonomy: `SceneContext` / `VisualStyle` / `CameraView` / `Composition`.
- Reified-event encoding for actions (fixes v0.1's dyadic-edge defect for arity ≥ 3, modifiers, negation, quantification).
- `SpatialFact` reification with mandatory `viewer` for directionals (resolves Talmy figure/ground construal-dependence at the schema level).
- RCC-8 spatial topology (8 base relations, JEPD).
- Allen interval algebra (13 base relations with declared inverses and transitivity).
- Schema.org-aligned thematic-role vocabulary on `Event`/`Process`/`Stative`.
- Causal predicates (`causes` / `enables` / `prevents` / `triggers`) distinct from agent-action edges.
- Modal / propositional-attitude classes (`BeliefState`).
- Geometry properties (`bbox2d` / `position3d` / `scale3d` / `rotation` / `occludes`).
- Annotation reification (RDF 1.1-portable equivalent of RDF-star quoted-triple syntax).

### Validation (VSON-S)
- SHACL shapes for `Composition`, `Event`, `Process`, `Stative`, `Quality`, `SpatialFact`, `Negation`.
- `vss:DirectionalNeedsViewerShape` enforces Talmy resolution.
- `vss:RccValueShape` constrains RCC-8 values to the eight base relations.
- `vss:FrameNotDepictedShape` keeps the perspectival layer disjoint from depicted entities.
- Trait-property value shapes constrain each trait axis to its published vocabulary.

### Tooling
- Reference Penman parser/emitter with reentrancy, role-routing, RCC/Allen namespace dispatch, and unit-literal handling.
- Makefile target `check` runs ontology parse + Penman round-trip + SHACL conformance + tests.
- 16 tests passing (12 transpiler + 4 SHACL).

### Removed (v0.1 deprecations)
- Eight bracket sigils (`{}` `[]` `<>` `~%$#@`) replaced by Turtle-star and Penman.
- The `K∈{A,P}` edge discriminator, replaced by typed reified nodes (`Event` for action, `Stative` for state, `SpatialFact` for spatial).
- The `void` reserved id (intransitive actions just omit `vso:patient`).
- The decl-vs-ref `:`-presence rule (Turtle's IRI/blank-node rules supersede).
- The folk Object/Item/Unique/Attribute taxonomy (replaced by trait bundles).

### Migration
- Spec section §10 documents v0.1 → v1.0 construct mapping.
