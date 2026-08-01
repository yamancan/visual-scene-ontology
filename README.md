# VSON — Visual Scene Ontology Notation, [v1.3](spec/CHANGELOG.md)

[![CI](https://github.com/yamancan/visual-scene-ontology/actions/workflows/ci.yml/badge.svg)](https://github.com/yamancan/visual-scene-ontology/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A vision-language model's description of an image is unvalidated prose: there is no schema it can violate, so nothing can reject one and no build can fail on it. VSON is a compact scene-graph notation in which every claim about an image — an object, a property, a spatial relation, an action — is instead a checkable graph assertion, gated by SHACL shapes (the W3C standard for validating graph structure). What ships today is that gate: `vson validate` exits non-zero on a scene graph that breaks the schema, and the web studio runs the same two checks in the browser. It checks the graph, not the picture — [§2.1](docs/vson.md#21-what-conformance-establishes) states exactly what a green result does and does not establish; querying a corpus of scenes and diffing two extraction runs are where this is headed, not things it ships. VSON is built for image-generation pipelines, scene-graph and knowledge-representation researchers, and people evaluating VLM output, and it ships as a single-file spec, a Rust CLI, and a drop-an-image web studio.

Canonical namespace: **`https://w3id.org/vson/v1/`**. The canonical IRIs dereference: the [w3id redirect](https://github.com/perma-id/w3id.org/pull/6471) merged on 2026-07-31, so `https://w3id.org/vson/v1/ontology` resolves to the ontology, and shapes, JSON-LD context, and schemas resolve alongside it — served from [vson.pages.dev/v1/](https://vson.pages.dev/v1/ontology.ttl). `make live-check` re-verifies all eight names against the live services.

## graph in, English out — deterministic, no LLM

A scene in VSON-P, the Penman authoring syntax — [`examples/gallery/03_spatial_topology.vson`](examples/gallery/03_spatial_topology.vson):

```
# RCC-8 topological relation (no viewer needed for non-directional facts).
# Demonstrates: SpatialFact with rcc only (cat externally connected to mat).

(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing medium_shot)
   :viewedBy cam
   :depicts (cat / PhysicalObject
               :individuation Generic :animacy Agentive :countability Count
               :class Animal)
   :depicts (mat / PhysicalObject
               :individuation Generic :animacy Inert :countability Count
               :class Furniture)
   :hasFact (sf / SpatialFact
               :figure cat
               :ground mat
               :rcc EC))
```

`vson export caption` renders it with templates, not a model — byte-identical on every run, and checked in CI against [`tests/fixtures/captions/03_spatial_topology.txt`](tests/fixtures/captions/03_spatial_topology.txt):

```
Eye level medium shot, 50mm lens. An animal, and a furniture. The animal touches the furniture.
```

## What's in the box

A curated **visual-scene profile of RDF-star** with:

- a reified **Frame** taxonomy (`SceneContext` / `VisualStyle` / `CameraView` / `Composition` / `Persona`)
- a **trait-bundle entity model** (`individuation × animacy × countability × affordance`)
- a **`SpatialFact`** reification pattern (RCC-8 + Allen + frame-relative directionals with mandatory viewer)
- a closed **VSV** vocabulary: RCC-8 and Allen base-relation vocabularies (closed value sets on reified facts; composition-table reasoning out of scope), a closed inventory of coarse VerbNet-style thematic roles, mereology, and causation
- **three concrete syntaxes**: Turtle-star (VSON-T, canonical), Penman (VSON-P, authoring), and **VSON-X** (compact, sigil-based, LLM-optimized — new in v1.1)
- a deterministic **caption renderer** for image-generation models (graph → English, no LLM)
- **SHACL** gatekeeping with strict + relaxed profiles
- shipped **exporters**: Cypher / caption / FOL (CLI) and Cypher / DOT / GraphML / Mermaid / caption / FOL (web studio, all in-browser), plus a published JSON-LD form; spec-only mappings for AMR / Visual Genome / Pixar USD

VSON does not invent a parser, grammar, or formal semantics. It rides on:
- **RDF 1.2 / RDF-star** — abstract semantics
- **OWL 2 RL** — decidable reasoning fragment
- **SHACL** — well-formedness
- **SPARQL-star** — query
- **Penman** — authoring concrete syntax (proven by AMR)

> **The canonical reference is [`docs/vson.md`](docs/vson.md)** — single-file RFC-style spec with Quick Start, per-field reference, JSON Schema, and the 16-scene example gallery.

## Layout

```
docs/vson.md      ★ Canonical single-file spec (Quick Start, reference, JSON Schema, gallery)
                    + vson-x-semantics.md (VSON-X surface semantics)
docs/strategy/    Productization plan, UI flows, extractor architecture
spec/             Historical normative spec (v1.0) + v0.1 deprecation record
ontology/         VSO TBox (OWL 2 RL) + VSV vocabulary
shapes/           SHACL shapes for well-formedness
examples/         Throne-room scene + gallery/ (16 scenes, minimal → complex)
                  + gallery-x/ (scenes 01–11 plus 12_persona in VSON-X compact syntax)
cli/              `vson` Rust CLI (validate / convert {p2t, x2t} / export {cypher, caption, fol})
                  + src/penman/routing-tables.json (single source of truth for both impls)
web/              Static SvelteKit studio — drop image, get scene graph; extraction
                  and two-gate verification run in the browser (BYOK OpenRouter + Pyodide)
tools/penman/     Reference Penman ↔ Turtle-star transpiler (Python)
tools/vson_x/     VSON-X compact-syntax parser + emitter + cross-syntax graph-equivalence
tools/render/     Deterministic graph → English caption renderer
tools/schema/     JSON Schema files (extractor envelope + JSON-LD form)
tools/extractor/  Image-to-graph extractor — orchestrator prompts + bare-VLM baseline
skills/           Portable extractor skills (SKILL.md + conformance fixtures) — exercised by make x-skill-check
scripts/          Envelope check, smoke eval, deploy preflight
tests/            Round-trip and SHACL conformance tests
```

## Quick start

```bash
# Build the Rust CLI (~30s cold)
cd cli && cargo build --release && cd ..
make deps         # Python deps (rdflib, pyshacl, owlrl) — required for `vson validate`

# Validate the canonical scene
cli/target/release/vson validate examples/throne_room.ttl

# Transpile Penman -> Turtle
cli/target/release/vson convert p2t examples/throne_room.vson > /tmp/scene.ttl

# Transpile VSON-X compact syntax -> Turtle
cli/target/release/vson convert x2t examples/gallery-x/11_throne_room.x.vson > /tmp/scene.ttl

# Export to Cypher
cli/target/release/vson export cypher examples/throne_room.vson > scene.cypher

# Render an English caption for image-generation models
cli/target/release/vson export caption examples/throne_room.vson

# Run all tests (Python + Rust)
make check        # 70 Python tests + 16-scene gallery + 2 schema parses
make cli-check    # Rust tests + byte-strict & graph-iso parity vs Python ref
make x-check      # VSON-X gallery round-trip parity (11 pairs; 12_persona pending)
```

See [`docs/vson.md`](docs/vson.md) for the full spec, [`cli/README.md`](cli/README.md) for the CLI, and [`web/README.md`](web/README.md) for the studio.

Run the studio locally:

```bash
cd web
pnpm install
pnpm dev --open
```

The studio is a **fully static site — no backend, no `.env`, no server key**. Demos and the 16-scene gallery run keyless at $0 from baked envelopes; live extraction of your own images runs on your own OpenRouter key, entered in the model picker, and the key goes browser → OpenRouter without ever touching a studio host. Verification runs in the browser too: a Pyodide worker executes the same two gates as `vson validate` (pyshacl SHACL, then owlrl OWL 2 RL), byte-pinned to the CLI in CI. `make web-deploy` publishes `web/build` to Cloudflare Pages (`vson-studio.pages.dev`); the namespace host `vson.pages.dev` is a separate project.

## Contribution boundary

VSON's genuinely-new content (everything else is W3C/ISO):

1. **Frame taxonomy** as a first-class perspectival layer distinct from `Entity`.
2. **Trait-bundle entity model** — orthogonal axes replace the folk Object/Item/Unique/Attribute mess.
3. **`SpatialFact` with mandatory viewer for directionals** — directional facts are viewer-anchored by schema. VSON commits to the relative frame of reference (Levinson 2003) with an explicit, machine-checkable anchor; figure/ground asymmetry follows Talmy.
4. **Closed VSV vocabulary** curated for visual scenes.
5. **Penman authoring surface** tuned for VSV.
6. **VSON-X compact syntax** (v1.1) — nine prefix sigils, no brackets, LL(1), bearer-class dispatch for `*K V`. Round-trips graph-equivalent to Penman across the 11 gallery scenes that have a VSON-X counterpart (12 files; 12_persona pending round-trip coverage).
7. **Persona / cross-document identity** (v1.1) — `vso:Persona` Frame + `vso:embodies` lets the same character appear in many scenes with consistent invariants.
8. **Deterministic caption renderer** — graph → English, template-driven, byte-identical CI fixtures.
9. **Exporter matrix** — shipped Cypher / caption / FOL (CLI) and DOT / GraphML / Mermaid / caption / FOL (web studio, in-browser) exporters, plus a published JSON-LD form; spec-only mappings for AMR / Visual Genome / USD.

## License

Apache-2.0.
