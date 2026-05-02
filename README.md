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

## Layout

```
spec/         VSON v1.0 specification
ontology/     VSO TBox (OWL 2 RL) + VSV vocabulary
shapes/       SHACL shapes for well-formedness
examples/     Throne-room scene in VSON-T (Turtle-star) and VSON-P (Penman)
tools/penman/ Reference Penman ↔ Turtle-star transpiler (Python)
tests/        Round-trip and SHACL conformance tests
```

## Quick start

```bash
# Round-trip the throne-room example
python3 tools/penman/vson_penman.py to-turtle examples/throne_room.vson > /tmp/round.ttl
diff <(python3 tools/penman/vson_penman.py normalize examples/throne_room.ttl) \
     <(python3 tools/penman/vson_penman.py normalize /tmp/round.ttl)

# Validate against SHACL (requires pyshacl)
pyshacl -s shapes/vson-shapes.ttl -e ontology/vso.ttl examples/throne_room.ttl
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
