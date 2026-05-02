# Visual Scene Ontology (VSON) v1.0

A curated **visual-scene profile of RDF-star** with:

- a reified **Frame** taxonomy (`SceneContext` / `VisualStyle` / `CameraView` / `Composition`)
- a **trait-bundle entity model** (`individuation × animacy × countability × affordance`)
- a **`SpatialFact`** reification pattern (RCC-8 + Allen + frame-relative directionals with mandatory viewer)
- a closed **VSV** vocabulary (RCC-8, Allen interval algebra, PropBank/FrameNet thematic roles, mereology, causation)
- a Penman-style **authoring surface** (VSON-P) round-tripping to canonical Turtle-star (VSON-T)
- **SHACL** gatekeeping
- published **exporters** to Cypher, AMR, Visual Genome, Pixar USD, JSON-LD

VSON does not invent a parser, grammar, or formal semantics. It rides on:
- **RDF 1.2 / RDF-star** — abstract semantics
- **OWL 2 RL** — decidable reasoning fragment
- **SHACL** — well-formedness
- **SPARQL-star** — query
- **Penman** — authoring concrete syntax (proven by AMR)

> **The canonical reference is [`docs/vson.md`](docs/vson.md)** — single-file RFC-style spec with Quick Start, per-field reference, JSON Schema, and the 11-scene example gallery.

## Layout

```
docs/vson.md      ★ Canonical single-file spec (Quick Start, reference, JSON Schema, gallery)
docs/strategy/    Productization plan, UI flows, extractor architecture
spec/             Historical normative spec (v1.0) + v0.1 deprecation record
ontology/         VSO TBox (OWL 2 RL) + VSV vocabulary
shapes/           SHACL shapes for well-formedness
examples/         Throne-room scene + gallery/ (11 scenes, minimal → complex)
cli/              `vson` Rust CLI (validate / convert / export cypher)
web/              SvelteKit studio — drop image, get scene graph (stateless, OpenRouter)
tools/penman/     Reference Penman ↔ Turtle-star transpiler (Python)
                  + routing-tables.json (single source of truth for both impls)
tools/schema/     JSON Schema files (extractor envelope + JSON-LD form)
tools/extractor/  Image-to-graph extractor — orchestrator prompts + bare-VLM baseline
tests/            Round-trip and SHACL conformance tests
```

## Quick start

```bash
# Build the Rust CLI (~30s cold)
cd cli && cargo build --release && cd ..
pip install pyshacl rdflib   # required for `vson validate`

# Validate the canonical scene
cli/target/release/vson validate examples/throne_room.ttl

# Transpile Penman -> Turtle
cli/target/release/vson convert p2t examples/throne_room.vson > /tmp/scene.ttl

# Export to Cypher
cli/target/release/vson export cypher examples/throne_room.vson > scene.cypher

# Run all tests (Python + Rust)
make check        # 17 Python tests + 11-scene gallery + 2 schema parses
make cli-check    # 19 Rust tests + graph-iso parity vs Python ref
```

See [`docs/vson.md`](docs/vson.md) for the full spec, [`cli/README.md`](cli/README.md) for the CLI, and [`web/README.md`](web/README.md) for the studio.

Run the studio locally:

```bash
cd web && pnpm install && pnpm dev --open
```

## Contribution boundary

VSON v1.0's genuinely-new content (everything else is W3C/ISO):

1. **Frame taxonomy** as a first-class perspectival layer distinct from `Entity`.
2. **Trait-bundle entity model** — orthogonal axes replace the folk Object/Item/Unique/Attribute mess.
3. **`SpatialFact` with mandatory viewer for directionals** — schema-level resolution of Talmy construal-dependence.
4. **Closed VSV vocabulary** curated for visual scenes.
5. **Penman authoring surface** tuned for VSV.
6. **Exporter matrix** — Cypher / AMR / Visual Genome / USD / JSON-LD as published mappings.

## License

Apache-2.0.
