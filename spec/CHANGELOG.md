# Changelog

## v1.1.1 — 2026-07-30

Editorial, verification, and packaging release. No wire-format or vocabulary
semantics change; documents valid under v1.1 remain valid.

- **Truthfulness pass** across every public surface: real editor attribution,
  measured-vs-target claims separated (the ≥80% extractor figure is a
  pre-registered target, not a result), Talmy/Levinson frame-of-reference
  attribution corrected, stale counts re-measured.
- **Spec**: Appendix D (normative VSON-X grammar, reconciled against the
  reference parser), Appendix E (related work + 16-entry bibliography), one
  numbered precedence clause; `docs/vson-x-semantics.md` translated to English
  and promoted to the normative VSON-X surface-semantics spec.
- **Ontology/shapes**: `vso:occurs` declared; six range-mirrored `sh:class`
  checks de-vacuated with `sh:not` guards backed by new disjointness axioms;
  full `rdfs:label`/`rdfs:comment` coverage; `skos:closeMatch` alignments to
  GeoSPARQL (RCC-8) and OWL-Time (Allen); Dimension registry closed at 21
  members, enforced by the C2 coverage test.
- **CLI**: `export cypher` emits one valid `CREATE` statement; `validate` runs
  both CI gates (SHACL + OWL 2 RL consistency) with an honest 0/1/2 exit-code
  contract; Python shell-out consolidated into `python_bridge.rs`; the crate
  now passes `cargo package` (routing tables moved into the crate at
  `cli/src/penman/routing-tables.json`, still the single source for both
  implementations).
- **Python**: `pyproject.toml` packaging, absolute imports (no `sys.path`
  hacks), ruff lint gate wired into `make check` and CI; VSON-X parser rejects
  modifiers on thematic roles loudly instead of dropping them silently.
- **Web studio**: OpenRouter proxy hardened (per-IP rate limit, model
  allowlist, payload caps), client-side downscale for large uploads, failure
  paths surfaced honestly, listbox/overlay accessibility; `BODY_SIZE_LIMIT`
  deploy requirement documented.
- **Hygiene**: `CITATION.cff`, `SECURITY.md`, `CONTRIBUTING.md`, dependabot;
  gitignore negations un-lose four normative markdown files; unverifiable
  image-license assertions removed. The lookbook demo was withdrawn pending
  provenance documentation.

## v1.1 — 2026-05-07

### VSON-X (compact concrete syntax)

A third concrete syntax alongside Penman (VSON-P) and Turtle-star (VSON-T).
Optimized for LLM emission and human authoring — nine prefix sigils, no
brackets, no significant newlines (every construct opens with a lead sigil;
one construct per line is emission convention, not grammar).

**Term reassignment.** In the superseded `spec/vson-spec-v1.md` draft,
"VSON-X" named the exporter layer. v1.1 reassigns the name to this compact
sigil syntax; exporters are now §7 of `docs/vson.md` and carry no layer
acronym of their own.

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
- Round-trip parity: scenes 01–11 have VSON-X counterparts under
  `examples/gallery-x/N.x.vson` whose RDF graph is equivalent (modulo
  blank-node identity for auto-anonymous reified nodes) to their Penman
  counterparts. A `12_persona` X file also exists (round-trip coverage
  pending); scenes 13–16 are Penman/Turtle only.

### Persona / cross-document identity

- New ontology classes and properties: `vso:Persona`, `vso:embodies`,
  `vso:hasInvariant`.
- New SHACL shapes: `vss:PersonaShape`, `vss:EmbodimentConsistencyShape`
  (Warning severity).
- VSON-X handles Personas as Frames: `/Persona @alice_id *hair auburn …`,
  referenced from Entities via `*embodies @alice_id`.

### Caption and FOL renderers

- `tools/render/caption.py`: deterministic graph → English caption,
  fully template-driven, no LLM.
- `tools/render/fol.py`: deterministic graph → Prolog-style
  first-order-logic facts.
- `vson export caption <file>` and `vson export fol <file>` CLI
  subcommands (both Rust shell-outs to the Python renderers).
- Studio "Caption" export tab.
- Frozen ground-truth caption fixtures under `tests/fixtures/captions/`
  for byte-identical CI.

### SHACL profiles

- `shapes/vson-shapes-relaxed.ttl`: authoring-time profile with
  `vss:DirectionalNeedsViewerShape`, the Event/Process/Stative lemma,
  `vss:QualityShape` dimension+value, and `vss:QualityModifierShape`
  demoted to `sh:Warning`.
- The relaxed profile ships as a shapes file only. No `--partial` flag
  exists in the Rust CLI or the Python reference, and no producer emits
  `conformance.profile: "relaxed"` yet; the file is exercised by the
  shapes-gate test in `tests/`.
- `vson validate` is byte-identical to v1.0 (strict profile).

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

Counts below are as of the v1.1.0 tag; the suite has since grown — run
`make check` and `make cli-check` for current counts.

- 48 Python tests (was 17): + 24 VSON-X (lexer / parser / emitter /
  round-trip), + 7 caption renderer.
- Rust CLI tests expanded across the lib-unit, integration, and golden
  suites.

### Backwards compatibility

- All v1.0 documents validate unchanged under `vson validate`.
- `examples/throne_room.vson` and the original 11 v1.0 gallery scenes
  remain byte-identical; the full 16-scene gallery is SHACL-conformant.
- The v1.0 envelope schema continues to validate (additive change only).

## v1.0.5 — interim

Interim envelope version admitted on the wire: v1.0 plus the caption renderer
and the Phase 0 ontology additions (`vso:class`, `vso:modifier`, `Persona`),
per the `version` field description in
`tools/schema/vson-output.schema.json`. No standalone release notes were kept.

## v1.0 — 2026-05-01 (initial)

Complete redesign. **v0.1 deprecated.**

### Architecture
- Layered specification on RDF-star, OWL 2 RL, SHACL, SPARQL-star.
- Two concrete syntaxes: Turtle-star (VSON-T, canonical) and Penman (VSON-P, authoring).
- Reference Penman ↔ Turtle-star transpiler (stdlib-only Python).

### Ontology (VSO)
- DOLCE-inspired top: `Endurant` / `Perdurant` / `Quality` / `Region`, with `Frame` disjoint from `Entity`.
- Trait-bundle entity model: `individuation × animacy × countability × affordance` orthogonal axes — replaces the v0.1 four-fold sigil mess.
- `Frame` taxonomy: `SceneContext` / `VisualStyle` / `CameraView` / `Composition`.
- Reified-event encoding for actions (fixes v0.1's dyadic-edge defect for arity ≥ 3, modifiers, negation, quantification).
- `SpatialFact` reification with mandatory `viewer` for directionals: directional facts are viewer-anchored by schema — VSON commits to the relative frame of reference (Levinson 2003) and makes the anchor explicit and machine-checkable; intrinsic and absolute frames are out of scope for v1.x. Figure/ground asymmetry follows Talmy.
- RCC-8 spatial topology (8 base relations, JEPD).
- Allen interval algebra (13 base relations with declared inverses and transitivity).
- Schema.org-aligned thematic-role vocabulary on `Event`/`Process`/`Stative`.
- Causal predicates (`causes` / `enables` / `prevents` / `triggers`) distinct from agent-action edges.
- Modal / propositional-attitude classes (`BeliefState`).
- Geometry properties (`bbox2d` / `position3d` / `scale3d` / `rotation` / `occludes`).
- Annotation reification (RDF 1.1-portable equivalent of RDF-star quoted-triple syntax).

### Validation (VSON-S)
- SHACL shapes for `Composition`, `Event`, `Process`, `Stative`, `Quality`, `SpatialFact`, `Negation`.
- `vss:DirectionalNeedsViewerShape` enforces viewer anchoring for directional facts.
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
