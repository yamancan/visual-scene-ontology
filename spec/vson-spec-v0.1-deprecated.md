# VSON v0.1 (DEPRECATED — superseded by v1.0)

> **Status:** Deprecated 2026-05-01. Do not use for new work. Retained for migration reference.
>
> **Why deprecated:** v0.1 was a parallel reinvention of RDF-star + AMR + a sliver of USD with worse parseability, no formal semantics, no axioms, no validator, no query language, and a folk-ontology entity taxonomy that conflated three orthogonal axes (individuation, animacy, affordance). Three independent reviews (philosopher / engineering critic / prior-art researcher) identified the dyadic-edge-with-qualifier action encoding as the deepest defect — arity-≥3 actions, action modification, negation, and quantification were unrepresentable.
>
> **Migration:** see [`vson-spec-v1.md`](./vson-spec-v1.md) §10 for v0.1 → v1.0 construct mapping.

---

## Reserved sigils (historical)

| Sigil   | Kind                | Replaced by (v1.0)                                         |
|---------|---------------------|------------------------------------------------------------|
| `{ }`   | Object              | `vso:Entity` with `vso:individuation vso:Generic`          |
| `@`     | Unique Object       | `vso:Entity` with `vso:individuation vso:Named`            |
| `[ ]`   | Item                | `vso:PhysicalObject` with `vso:affordance vso:Holdable`    |
| `< >`   | Attribute           | `vso:Quality` node + `vso:hasQuality` edge                 |
| `~`     | Scene               | `vso:SceneContext`                                         |
| `%`     | Style               | `vso:VisualStyle`                                          |
| `$`     | Camera              | `vso:CameraView`                                           |
| `#`     | Composition         | `vso:Composition`                                          |
| `-[K:L]->` (K∈{A,P}) | edge discriminator  | reified nodes: `Event`, `Stative`, `SpatialFact`           |
| `void`  | intransitive sentinel | (omit `vso:patient`)                                     |

## Why each construct was removed

- **`<…>` overloaded** between Attribute decl/ref and inline kv-list — not LL(1).
- **`-[` trigraph** collided with bracketed values; no escape grammar.
- **`(S,K,L,T)` tuple uniqueness** silently collapsed differing qualifier sets — lossy.
- **Eight sigils** carried no precedent in any serious KR system; broke compatibility with RDF, OWL, Cypher, AMR.
- **Action-as-edge-label** broke Davidsonian event semantics (cf. Davidson 1967, Parsons 1990).
- **Asymmetry-by-fiat** falsified genuinely symmetric relations (`next_to`, `facing`, `near`).
- **Attributes-as-sinks** blocked adjective stacking ("dark red", "very heavy").
- **Composition-as-mereology-and-frame** conflated extensional with intensional.
- **Folk taxonomy** baked discourse-relative uniqueness (Alice = `@`, boar = `{`) into the type system.

## What v0.1 got right (preserved in v1.0)

1. **First-class scene metadata kinds** — Camera/Style/Composition as nodes-with-scope-edges. v1.0 promotes these to a full `Frame` taxonomy (also adds `SceneContext`).
2. **Action/Proposition edge discriminator** — empirically validated by Action Genome's attention/spatial/contact split. v1.0 keeps the distinction but moves it from edge-label discriminator to typed reified nodes (`Event` for action, `Stative` for stative, `SpatialFact` for spatial).
3. **Sigil-per-kind for at-a-glance reading** — preserved in VSON-P (Penman) authoring surface, where concept names like `/Event`, `/Stative`, `/SpatialFact`, `/Quality` give the same readable kind-prefix without bespoke parsing.
