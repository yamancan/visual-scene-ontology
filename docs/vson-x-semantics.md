# VSON-X — Surface Semantics (normative)

| Field | Value |
|---|---|
| Status | Normative for VSON-X surface semantics, v1.2 stable |
| Date | 2026-07-31 |
| Scope | Bearer dispatch, sigil → graph mapping, lemma aspect routing, and the ontology and shape declarations VSON-X depends on. The grammar itself lives in [`docs/vson.md`](./vson.md) Appendix D. |
| Companion | [`docs/vson.md`](./vson.md) (canonical v1.2 spec) · [`ontology/vso.ttl`](../ontology/vso.ttl) (TBox) · [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) (validation) · [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py) (reference parser) |

The keywords **MUST**, **MUST NOT**, **SHOULD**, **MAY** are interpreted per RFC 2119 as updated by RFC 8174 — that is, only when they appear in all capitals.

This document is normative **for VSON-X surface semantics**. It sits second in the precedence order defined in [`docs/vson.md`](./vson.md) §2: below `docs/vson.md`, above the shapes, the ontology, and the JSON Schemas.

---

## 0. Why this document exists

VSON-X is the third concrete syntax for the same RDF graph (alongside VSON-T Turtle-star and VSON-P Penman). A grammar alone does not determine the graph a VSON-X document denotes; seven questions had to be answered before a parser could be written:

1. Whether `/X` means a kind (`vso:X` IRI) or a domain class (`*class X`).
2. Whether `/Camera` is canonical or an alias for `/CameraView`.
3. What `*key` routes to on different bearer classes.
4. Whether `&` symmetry actually produces a symmetric graph.
5. Whether `--partial` mode breaks v1.0 backward compatibility.
6. Whether the caption renderer consumes the AST or the RDF graph.
7. Lemma → kind aspect routing for `>` vs `>>`.

This document answers them, and v1.1 shipped against those answers. Where the reference parser [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py) does something other than what a section specifies, the parser is authoritative and the gap is marked inline — this document describes semantics, not aspirations.

---

## 1. Concept declarations — `/X`

Closed list of canonical kinds. Domain class strings (Knight, Woman, Crown) NEVER appear after `/`; they are values of `*class`.

| Surface | RDF kind | Penman equivalent |
|---|---|---|
| `~scene` (root sigil + handle) | `vso:Composition` | `(scene / Composition ...)` |
| `/PhysicalObject` | `vso:PhysicalObject` | `(x / PhysicalObject ...)` |
| `/Aggregate` | `vso:Aggregate` | `(x / Aggregate ...)` |
| `/Substance` | `vso:Substance` | `(x / Substance ...)` |
| `/CameraView` | `vso:CameraView` | `(c / CameraView ...)` |
| `/VisualStyle` | `vso:VisualStyle` | `(s / VisualStyle ...)` |
| `/SceneContext` | `vso:SceneContext` | `(c / SceneContext ...)` |
| `/Persona` (new v1.1) | `vso:Persona` | `(p / Persona ...)` |
| `/Quality` (rare; usually inline `*K V`) | `vso:Quality` | `(q / Quality ...)` |
| `/Event` (rare; usually inline `>>`) | `vso:Event` | `(e / Event ...)` |
| `/Process` (rare; usually inline `>>`) | `vso:Process` | `(p / Process ...)` |
| `/Stative` (rare; usually inline `>`) | `vso:Stative` | `(s / Stative ...)` |
| `/SpatialFact` (rare; usually inline `!`/`&`) | `vso:SpatialFact` | `(sf / SpatialFact ...)` |

**Decision**: no domain-class aliases (`/Woman`, `/Knight`, `/Camera`) in v1.1. Aliases deferred to v1.2 if proven valuable.

**Rationale**: aliases require a second namespace lookup table that diverges from the ontology. Canonical-only keeps VSON-X parser identical to Penman for kind dispatch.

---

## 2. Trait routing — barewords

Bareword keywords appear after the kind, before `*K V` qualities. Order-independent, all optional.

| Keyword set | Maps to | IRI emitted |
|---|---|---|
| `Generic, Named, Skolem, Kind` | `vso:individuation` | `vso:Generic`, `vso:Named`, `vso:Skolem`, `vso:Kind` |
| `Agentive, Inert` | `vso:animacy` | `vso:Agentive`, `vso:Inert` |
| `Count, Mass, Collective` | `vso:countability` | `vso:Count`, `vso:Mass`, `vso:Collective` |
| `Holdable, Wearable, Mountable, Container, Edible` | `vso:affordance` (multi-valued) | `vso:Holdable` etc. |

### 2.1 Default policy (extractor MAY apply, parser does NOT auto-detect)

| Trait | If absent | Note |
|---|---|---|
| `vso:individuation` | extractor SHOULD set `Skolem` | "anonymous distinct individual" matches image-extracted entities better than `Generic`. Penman skill defaulted to `Generic`; this is updated guidance. |
| `vso:animacy` | extractor SHOULD set per class registry lookup | `Person/Knight/Animal` → `Agentive`; `Crown/Sword` → `Inert` |
| `vso:countability` | extractor SHOULD default to `Count` | unless class is in `Substance/Aggregate` |

The parser auto-defaults exactly one axis: individuation. A handle-headed entity declaration with no individuation `TRAIT_KEYWORD` gets `vso:Named` when the handle is `@`-prefixed and `vso:Generic` when it is bare. Animacy, countability and affordance are never inferred — absence in source is absence in graph.

#### 2.1.1 Trait completeness is a producer obligation, not a shape

The four trait axes are required by [`docs/vson.md`](./vson.md) §5.4, and **no shape enforces that requirement**. There is no `vss:EntityShape`. The three functional axes are constrained by `vss:IndividuationShape`, `vss:AnimacyShape` and `vss:CountabilityShape`, and affordance by `vss:AffordanceShape`; all four use `sh:targetSubjectsOf` on their own property, so they pin the value set and (for the first three) `sh:maxCount 1` *where the property appears*, and say nothing where it is absent. An Entity carrying none of the four passes SHACL under both profiles.

That resolves the question this section used to leave open. The gallery was never non-conformant, and no shape was softened to make it conform: all 16 scenes in [`examples/gallery/`](../examples/gallery/) now declare countability, and [`examples/throne_room.vson`](../examples/throne_room.vson) does too, because completeness is good authoring — not because a shape rejects the alternative. Closing the gap at the shape layer would be a breaking change for every v1.0 document that omits a trait, so v1.1 does not attempt it.

VSON-X authors SHOULD therefore declare all four keywords explicitly for image-extracted Entities (matching the §2.1 extractor guidance); nothing downstream will remind them.

---

## 3. `*key` routing — bearer-class dispatch

Bearer class determines whether `*K V` becomes a Quality node, direct property, or thematic role. Closed table.

### 3.1 On metadata Frames (CameraView, VisualStyle, SceneContext)

`*K V` → direct triple `:K V` on the Frame node.

**Note**: Composition and Persona are Frames but NOT included here:
- **Composition** `*K V` (e.g., `~scene *layout triangular *focal center`) routes to Quality node via `vso:hasQuality` (matches v1.0 semantics: Composition.hasQuality for Layout/Focal). See §3.2.3.
- **Persona** `*K V` routes to Quality via `vso:hasInvariant`. See §3.5.

| `*K V` | Triple emitted | Where |
|---|---|---|
| `*angle eye_level` | `cam vso:angle "eye_level"` | CameraView |
| `*focalLength 50mm` | `cam vso:focalLength "50mm"` | CameraView |
| `*framing wide_shot` | `cam vso:framing "wide_shot"` | CameraView |
| `*cameraPosition front_left` | `cam vso:cameraPosition "front_left"` | CameraView |
| `*aesthetic photographic` | `style vso:aesthetic "photographic"` | VisualStyle |
| `*palette neutral` | `style vso:palette "neutral"` | VisualStyle |
| `*medium photograph` | `style vso:medium "photograph"` | VisualStyle |
| `*venue studio_concrete` | `ctx vso:venue "studio_concrete"` | SceneContext |
| `*atmosphere neutral` | `ctx vso:atmosphere "neutral"` | SceneContext |
| `*timeOfDay daytime` | `ctx vso:timeOfDay "daytime"` | SceneContext |
| `*weather indoor` | `ctx vso:weather "indoor"` | SceneContext |

### 3.2 On Entities (PhysicalObject, Aggregate, Substance) — Quality dispatch

`*K V` → fresh `Quality` blank node + `vso:hasQuality` edge from bearer.

| `*K V` | Expansion |
|---|---|
| `*color red` | `(q / Quality :dimension Color :value red)` |
| `*color red ~dark` | `(q / Quality :dimension Color :value red :modifier dark)` |
| `*color dark_red` | `(q / Quality :dimension Color :value dark_red)` |
| `*material gold` | `(q / Quality :dimension Material :value gold)` |
| `*affect joyful` | `(q / Quality :dimension Affect :value joyful)` |
| `*age young_adult` | `(q / Quality :dimension Age :value young_adult)` |
| `*size large` | `(q / Quality :dimension Size :value large)` |
| `*role queen` | `(q / Quality :dimension Role :value queen)` |
| `*weight heavy ~very` | `(q / Quality :dimension Weight :value heavy :modifier very)` |

#### 3.2.1 Closed dimensions

`Color, Material, Affect, Age, Role, Size, Weight, Enchantment, Layout, Focal, Pose, ActionState, Amount, Hair, Hairstyle, Skin, Eyewear, Headwear, Outfit, Fit`.

`Hair` covers color/length compound values (`blonde, brunette, auburn_long, black_short`); `Hairstyle` covers cut/style (`bob, braided, ponytail`). `Skin` covers tone/complexion. Both `Hair` and `Skin` are added in v1.1 to support fashion/portrait extraction without falling to open-dimension warnings.

Dimension names are PascalCase; the parser derives them mechanically from the `*key` (`*action_state` → `ActionState`), so a novel key silently produces a novel dimension. **Nothing rejects or warns on one.** `vss:QualityShape` constrains only that a Quality carries exactly one `vso:dimension` and one `vso:value`; no shape holds a dimension vocabulary, so an open dimension is as conformant as a closed one. Keeping to the list above is a producer obligation, and a `Hair` / `Skin` axis was added in v1.1 rather than left open precisely so that fashion and portrait extraction would not drift into private vocabulary. An extension namespace for stable open dimensions is v1.2 work.

#### 3.2.2 Adjective stacking

Both forms valid:
- `*color dark_red` — lexicalized compound (single value token, snake_case).
- `*color red ~dark` — value + adverbial modifier (gradable).

Convention: `~M` for gradable modifiers (`very, slightly, somewhat, mostly`); `_` joining for lexicalized compounds (`dark_red, navy_blue, pale_yellow`).

#### 3.2.3 Composition `*K V` — also Quality dispatch

`*K V` placed on the Composition root — after `~handle`, before the first item — emits a Quality node linked via `vso:hasQuality`:

```
~scene *layout triangular *focal center
  /CameraView @cam ...
  ...
```

Expansion:
```turtle
:scene a vso:Composition ;
       vso:hasQuality [ a vso:Quality ; vso:dimension vso:Layout ; vso:value "triangular" ] ;
       vso:hasQuality [ a vso:Quality ; vso:dimension vso:Focal ; vso:value "center" ] .
```

Recommended dimensions for Composition: `Layout, Focal, Symmetry, Balance, Mood`. Open dimensions are unchecked here too, per §3.2.1.

**Position is load-bearing.** The grammar is `composition = "~" IDENT { kv } { item }` ([`docs/vson.md`](./vson.md) Appendix D §D.5), and each item's own `kv` loop is greedy, so a `*K V` written after the first item attaches to that item, not to the Composition. `~scene *layout triangular` puts a Layout Quality on the scene; the same `*layout triangular` written below an entity declaration puts it on the entity. Newlines do not change this — only ordering does.

#### 3.2.4 Composition `*rendersAs` — special direct property

Composition has one direct-property exception that takes a ref value (not Quality):

```
~scene *layout triangular *rendersAs @style
  /VisualStyle @style *aesthetic oil_painting *palette warm
  ...
```

| `*K V` on Composition | Triple emitted |
|---|---|
| `*rendersAs @style` | `:scene vso:rendersAs <style>` (direct property to ref) |

This designates which `framedBy` VisualStyle is the dominant aesthetic (matches [`docs/vson.md`](./vson.md) §5.2). Closed list of Composition direct-property keys (v1.1): `rendersAs` only. All other `*K V` on Composition routes to Quality (§3.2.3).

### 3.3 On Entities — special direct properties (NOT Quality)

Closed exception list. These `*K V` keys ALWAYS emit direct properties on the Entity, never Quality nodes.

| `*K V` | Triple emitted |
|---|---|
| `*class Knight` | `entity vso:class :Knight` — a document-local IRI, not a string; see §8.1 |
| `*bbox2d "0.04,0.10,0.22,0.88"` | `entity vso:bbox2d "0.04,0.10,0.22,0.88"` |
| `*position3d "1.0,2.0,3.0"` | `entity vso:position3d "1.0,2.0,3.0"` |
| `*scale3d "1.0,1.0,1.0"` | `entity vso:scale3d "1.0,1.0,1.0"` |
| `*rotation "..."` | `entity vso:rotation "..."` |
| `*visibleFraction 0.85` | `entity vso:visibleFraction "0.85"^^xsd:decimal` |
| `*embodies @alice_id` | `entity vso:embodies <alice_id>` (Persona link) |

**Closed list**: parser MUST treat these 7 keys as direct properties. Any other `*K V` on Entity → Quality dispatch (§3.2).

### 3.4 In Perdurant arglist (Event, Process, Stative)

`*K V` after the lemma in `>` or `>>` form → thematic role. V can be ref (`@id`) or literal.

| `*K V` | Triple emitted |
|---|---|
| `*instrument @sword` | `event vso:instrument <sword>` |
| `*manner forceful` | `event vso:manner "forceful"` |
| `*goal @castle` | `event vso:goal <castle>` |
| `*recipient @bob` | `event vso:recipient <bob>` |
| `*beneficiary @child` | `event vso:beneficiary <child>` |
| `*source @forest` | `event vso:source <forest>` |
| `*location @throne_room` | `event vso:location <throne_room>` |
| `*time dawn` | `event vso:time :dawn` — `time` is not a string-valued role, so the bareword becomes a document-local IRI (§3.6) |
| `*cause @charge_event` | `event vso:cause <charge_event>` |
| `*result @death` | `event vso:result <death>` |

This list is the recommended role set, not a closed vocabulary the parser polices: any `IDENT` is accepted as a thematic-role key and emitted verbatim (`*frobnicate zzz` → `event vso:frobnicate :zzz`). Producers **MUST** stay inside the list; an unlisted role emits a VSO term that does not exist, which [`docs/vson.md`](./vson.md) §2 C2 forbids. What the parser *does* reject in this position is a `~M` modifier — v1.1 has no encoding for a modified thematic role.

### 3.5 On Persona — invariant Quality

`*K V` on `/Persona` declaration becomes a Quality linked via `vso:hasInvariant` (NOT `hasQuality`).

| `*K V` on Persona | Expansion |
|---|---|
| `*hair auburn` | `(q / Quality :dimension Hair :value auburn)` linked via `hasInvariant` |
| `*eye green` | similar |
| `*build athletic` | similar |
| `*age young_adult` | similar |

These are cross-document identity invariants. A scene Entity's `hasQuality` values MUST NOT contradict the `hasInvariant` values of the Persona it embodies on the same dimension — SHACL `vss:EmbodimentConsistencyShape` (§8) reports a contradiction as a warning.

### 3.6 Value can be a ref — and the surface does not distinguish

An early draft wrote `value = IDENT | INT | FLOAT | UNIT | STRING`, which omitted refs. The shipped surface is `value = STRING | UNIT | NUM | ref` with `ref = [ "@" ] IDENT` ([`docs/vson.md`](./vson.md) Appendix D §D.5).

The important correction is stronger than "refs are allowed". **The surface carries no literal/IRI distinction at all.** `@sword` and `sword` produce the same AST node, and the `@` is decoration in value position. Whether a bareword ends up as a Turtle string literal, an `rcc:`/`vso:` IRI, or a document-local IRI is decided at emission time by *role name*, against [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json) — the same table VSON-P consumes. `docs/vson.md` Appendix D §D.6 gives the five-step precedence.

So the table below is authoring guidance, not a parser check — the parser does not reject a ref in any of these positions:

| Bearer context | Ref meaningful in `*K V` value? | What actually happens |
|---|---|---|
| §3.1 Frame (CameraView, VisualStyle, SceneContext) | No | all eleven Frame property keys of §3.1 are in `role_value_as_string`, so a ref there renders as a string literal |
| §3.2 Entity Quality dispatch | No | the Quality's `vso:value` role is in no routing list, so a bareword becomes a document-local IRI — unless it collides with a declared handle, in which case it becomes a reentrant ref to that node |
| §3.3 Entity special properties | Only `*embodies @persona_id` | `*class` also emits a document-local IRI (§8.1) |
| §3.4 Perdurant arglist | Yes | refs and literals both, per role |
| §3.5 Persona invariant | No | same as §3.2 |

### 3.7 Lexical conventions — line continuation and item boundaries

This section is the rationale. The normative form of the rule, with the lookahead budget and the arglist-termination test, is [`docs/vson.md`](./vson.md) Appendix D §D.4.

VSON-X uses **lead-token detection** for item boundaries, NOT physical line breaks. Newlines within an item are whitespace; the parser identifies item starts by recognizing top-level lead tokens.

#### 3.7.1 Lead tokens

An item starts when one of these patterns is recognized at the parser's top-level state:

| Lead pattern | Item kind |
|---|---|
| `~ IDENT` | Composition root (must be document's first item) |
| `@ IDENT /` (handle + slash) | entity_decl (Named/Skolem) |
| `IDENT /` (bareword + slash) | entity_decl (Generic) |
| `/ IDENT` (slash at item start, no preceding handle) | frame_decl |
| `^ IDENT` (at top level, not inside spatial_asym) | viewer_anchor |
| `(@ IDENT \| IDENT) >` (ref + single arrow) | stative |
| `(@ IDENT \| IDENT) >>` (ref + double arrow) | event |
| `(@ IDENT \| IDENT) !` | spatial_asym |
| `(@ IDENT \| IDENT) &` | spatial_sym |

A comment is not an item: `#` to end-of-line is discarded by the lexer and never reaches the parser (§3.7.5). Nothing excludes a `SYM_LEMMA` or `RCC_TOKEN` spelling from the bareword-handle position either — `near /PhysicalObject` is a well-formed entity declaration, because those two token sets are recognized only after `&` and `!` respectively.

#### 3.7.2 Within-item whitespace

Inside an item (between its lead token and the next lead token), all whitespace including newlines is treated as a single token separator. This permits multi-line items with arbitrary indentation:

```
@m1 /PhysicalObject Skolem Agentive
    *class Woman
    *bbox2d "0.04,0.10,0.22,0.88"
    *hair blonde
    *skin light
```

is equivalent to:

```
@m1 /PhysicalObject Skolem Agentive *class Woman *bbox2d "0.04,0.10,0.22,0.88" *hair blonde *skin light
```

#### 3.7.3 Indentation

Indentation is **purely cosmetic**. The parser does NOT track indentation levels or use them for nesting. The only nesting is the implicit `Composition → block` from `~root`; everything else is flat top-level items.

#### 3.7.4 Two-token lookahead

Two lead patterns share their first token:
- `@IDENT /` (entity_decl) vs `@IDENT >` (stative)
- `IDENT /` (entity_decl) vs `IDENT >` (stative)

The parser MUST use 2-token lookahead at handle position to distinguish. This is the single point where the grammar is not LL(1); with an `@` prefix the same decision sits one token further along, so the worst case is three tokens ([`docs/vson.md`](./vson.md) Appendix D §D.4).

#### 3.7.5 Comments and empty lines

`#` to end-of-line is a comment, stripped before lexing. Empty lines and whitespace-only lines are skipped. Comments are valid anywhere a token break would be valid.

---

## 4. Sigil semantics — exact graph mapping

### 4.1 `~handle` — Composition root

Single Composition node, IRI `:handle`. Block contents are children.

```
~scene
  ...children...
```

### 4.2 `@id` — Named/Skolem entity declaration

First occurrence at head of `entity_decl` declares; later bare `@id` references same node.

The `@` prefix carries NO automatic individuation. Author/extractor sets explicitly via traits:
- `@alice /PhysicalObject Named *class Knight` — proper name
- `@m1 /PhysicalObject Skolem *class Woman` — anonymous distinct individual
- `@x42 /PhysicalObject` — no individuation (validation warns)

### 4.3 bare `id` — Generic entity declaration

```
boar /PhysicalObject Generic Agentive *class Boar
```

Convention: lowercase bareword. Same reentrancy rules as `@id`.

### 4.3.1 `@id` on Frames — handle marker only

When `@id` appears on a Frame declaration (`/CameraView @cam`, `/VisualStyle @style`, `/SceneContext @ctx`, `/Persona @alice_id`, `/Composition` via `~handle`), the `@` carries **no individuation semantics**. Frames are not Entities (`vso:Frame owl:disjointWith vso:Entity`); `vso:individuation` is undefined on them.

The `@` prefix on Frame handles is purely a syntactic marker for human readability; it produces no `vso:individuation` triple at compile time.

It is, however, the **only** admissible handle form on a `frame_decl`. `/CameraView cam` is not the bare-id equivalent of `/CameraView @cam` — a bareword there cannot be told apart from a trait keyword without more lookahead, so the parser leaves it, generates an anonymous handle for the Frame, and then fails on `cam` as a malformed item. A Frame that needs no handle may omit it entirely (`/VisualStyle *aesthetic photographic`); a Frame that will be referenced later (`^cam`, `*rendersAs @style`) MUST use `@id`.

Note also that `@cam /CameraView` is a different item from `/CameraView @cam`: the handle-led form is an entity declaration that happens to name a Frame concept, so it attaches via `vso:depicts` and picks up a default `vso:individuation`. Only the slash-led form produces `vso:framedBy`.

### 4.4 Composition edge for SpatialFact / Event / Stative

The `!`, `&`, `>`, `>>` items emit reified nodes that attach to the Composition. **VSON-X parser default**: every reified perdurant or spatial node is attached via `vso:depicts`.

```
@bob >> strike @boar    →    :scene vso:depicts (e / Event :lemma strike :agent bob :patient boar)
@crown ! EC @alice ^cam →    :scene vso:depicts (sf / SpatialFact :figure crown :ground alice :rcc EC :viewer cam)
```

**Rationale**: v1.0 [docs/vson.md](./vson.md) §5.2 admits both `vso:depicts` and `vso:occurs` for perdurants, and SpatialFacts are observed to use either `vso:depicts` or `vso:hasFact` in canonical examples (e.g., [examples/throne_room.vson](../examples/throne_room.vson) uses `:depicts` for SpatialFact; [examples/gallery/04_directional_with_viewer.vson](../examples/gallery/04_directional_with_viewer.vson) uses `:hasFact`). VSON-X collapses to a single edge (`vso:depicts`) for parser simplicity. Both target edges remain valid in VSON-P/T; conversion is lossy in this single dimension (round-trip from a `:hasFact`-using Penman through VSON-X yields a `:depicts` Penman, which is conformant but not byte-identical).

### 4.5 `*K V` and `*K V ~M` — quality/property kv

Bearer-class dispatch per §3. A `~M` tail adds `vso:modifier "M"` to the emitted Quality; it is valid only where `*K V` emits a Quality (§3.2, §3.5). A modifier on a direct property (`*angle eye_level ~slightly`) or on a thematic role is a parse error. The one exception is a `*K V` on a SpatialFact other than `*dir` / `*prox`: there a `~M` is accepted and then discarded, reaching no triple.

### 4.6 `>` — Stative arrow

```
@bob > hold @sword *manner gently
```

Emits:
```
(s / Stative
  :lemma hold
  :holder bob
  :theme sword
  :manner gently)
```

LHS routes to slot determined by lemma table (§5). Default: `holder`. Positional pos[0] (here `@sword`) routes per lemma table; for `hold`, pos[0] = `theme`.

### 4.7 `>>` — Event/Process arrow

```
@bob >> strike @boar *instrument @sword *manner forceful
```

Emits Event or Process based on lemma table (§5):
```
(e / Event
  :lemma strike
  :agent bob
  :patient boar
  :instrument sword
  :manner forceful)
```

LHS default → `agent`. Positional pos[0] per lemma table.

### 4.8 `!` — Asymmetric SpatialFact

```
@crown ! EC @alice ^cam *dir above
```

Emits ONE SpatialFact:
```
(sf / SpatialFact
  :figure crown
  :ground alice
  :rcc EC
  :directional above
  :viewer cam)
```

A viewer anchor is MANDATORY whenever the fact carries a direction — either as a `*dir` tail or as a directional relation in the `REL` slot (`@crown ! above @alice ^cam`, which emits `vso:directional` and no `vso:rcc`). Omitting it is a parse-level error, mirroring SHACL `vss:DirectionalNeedsViewerShape`.

The `^cam` MUST come after the ground ref and **before** the `*K V` tail. `@crown ! EC @alice *dir above ^cam` does not parse: the anchor falls outside the item, becomes a composition-level `vso:viewedBy`, and the fact is left directional with no viewer. Only a `^` anchor satisfies the requirement — a literal `*viewer @cam` emits the triple but does not.

### 4.9 `&` — Symmetric SpatialFact

```
@ada & near & @beth
```

Emits TWO SpatialFact nodes (figure↔ground swapped):
```
(sf1 / SpatialFact :figure ada :ground beth :proximal near)
(sf2 / SpatialFact :figure beth :ground ada :proximal near)
```

**This is the symmetry decision**: 2 SpatialFact emit. Reasoning:
- Current ontology's `vso:proximal` is a property whose values are IRIs (`vso:near`, `vso:far`). Not predicates. `owl:SymmetricProperty` declarations on `vso:near` etc. fire on no triples (dead code).
- Refactoring `vso:near` to be a direct Entity↔Entity predicate would break SpatialFact reification discipline (current spec §3.4 reifies all spatial relations).
- Emitting 2 SpatialFacts preserves reification AND symmetry semantics. Cost: 2× node count for symmetric facts.

**Symmetric lemma list (closed, v1.1)**: `near, far, adjacent`.

These are a subset of the `vso:proximal` closed enum, which as shipped holds **five** values — `near, far, adjacent, next_to, facing` ([docs/vson.md](./vson.md) §5.12, `vss:ProximalValueShape`). `&` form maps to a `vso:proximal` value.

**Excluded from v1.1 symmetric list** (these are legal `vso:proximal` values in the graph; they are simply not `&` lemmas):
- `next_to`, `nextTo` — `vso:next_to` is a proximal value, but VSON-X routes "next to" through `& adjacent &` in v1.1 rather than adding a second near-synonymous symmetric lemma. Admitting it is a v1.2 decision.
- `facing`, `facing_each_other` — `facing` is gaze direction (asymmetric, use `!` form with custom predicate); `facing_each_other` (mutual gaze) requires either ontology refactor or new `vso:SymmetricSpatialFact` class (v1.2).

For "next to" semantics in v1.1, use `& adjacent &` (accepts touching/proximal proximity). For "facing each other," fall back to two asymmetric `!` facts with `*dir in_front_of` (one for each viewer perspective).

### 4.10 `^id` — viewer anchor

Two syntactic contexts, distinguished by lead-token position:

#### 4.10.1 Composition-level (`vso:viewedBy`)

A `^X` appearing as a top-level item in the Composition block (NOT inside a spatial_asym) attaches to the Composition node:

```
~scene
  /CameraView @cam *angle eye_level
  ^cam                                # top-level item → :scene vso:viewedBy :cam
  /VisualStyle *aesthetic photographic
```

**Constraints (specified here; enforcement status noted per row)**:

No SHACL shape constrains `vso:viewedBy` on a `vso:Composition` — `vss:CompositionShape` only requires `vso:depicts`, and spec §2 C5 is the *directional-SpatialFact* rule enforced by `vss:DirectionalNeedsViewerShape` (see §4.10.2), not a composition-level one. The rules below are therefore VSON-X parser rules, and as of v1.1 the reference parser [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py) implements none of them.

| Rule | Behavior | Implemented in the reference parser? |
|---|---|---|
| Exactly one top-level `^X` per Composition | Required. Nothing at the graph layer backs this up; it is a VSON-X authoring discipline that keeps every X document ready for a directional fact. | **No** — a Composition with no `^X` parses and emits. |
| Multiple top-level `^X` items | Parse error: "duplicate viewer anchor at composition level". | **No** — each anchor emits its own `vso:viewedBy` triple. |
| Zero top-level `^X` (Composition without viewer) | Parse error in strict mode; `--partial` mode admits with `sh:Warning`. | **No** — accepted in both modes. |
| Referenced handle is not a declared `CameraView` | Parse error: "viewer anchor must reference a CameraView". | **No** — the handle is emitted unchecked. |
| `^X` appearing before any `/CameraView` declaration | Allowed — forward reference resolved in parser pre-pass (matches §7 reentrancy rule). | Yes. |
| `^X` referencing an undeclared handle | Parse error after pre-pass: "undeclared handle in viewer anchor". | **No** — emitted as a dangling reference. |

Closing these gaps is v1.2 parser work. Until then, `docs/vson.md` §5.2 describes the shipped behaviour and this table describes the target.

#### 4.10.2 SpatialFact-level (`vso:viewer`)

A `^X` appearing inside a `spatial_asym` item (after the ground ref, before the optional `*K V` tail) attaches to that SpatialFact:

```
@crown ! EC @alice ^cam *dir above              # ^cam scoped to this SpatialFact
```

**Constraints**:

| Rule | Behavior |
|---|---|
| Required iff `*dir` present | Parser-level fail-fast (mirrors `vss:DirectionalNeedsViewerShape`). Symmetric/topological-only facts (`! EC` with no `*dir`) need no viewer. |
| Optional otherwise | A `! EC` with `^cam` and no `*dir` is valid; viewer attaches but isn't constrained. |
| Multiple `^X` in one spatial_asym | Parse error: "max one viewer per spatial fact". |
| Viewer must be a declared CameraView | Same constraint as §4.10.1. |

#### 4.10.3 Disambiguation rule

When a `^X` token is encountered, the parser checks whether it is in `spatial_asym` parsing state (i.e., between the ground ref and the next item's lead token):
- If yes → §4.10.2 (SpatialFact-level).
- If no → §4.10.1 (Composition-level item).

This means `^X` immediately after a complete `spatial_asym` (which has already consumed `figure ! rel ground`) is treated as Composition-level, not SpatialFact-level. To attach a viewer to a spatial fact, place `^X` BEFORE any post-ground item starts.

---

## 5. Lemma → kind table (aspect routing)

Sigil + lemma determines node kind. The table below is transcribed from `STATIVE_LEMMAS`, `EVENT_LEMMAS` and `PROCESS_LEMMAS` in [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py); the "positional slots" column is the exact slot list, and supplying more positional refs than a lemma has slots is a parse error (`too many positional arguments`). Extra arguments always remain available as named `*K V` roles (§3.4).

| Lemma | `>` form | `>>` form | LHS slot | Positional slots |
|---|---|---|---|---|
| hold | Stative | error | holder | theme |
| wear | Stative | error | holder | theme |
| carry | Stative | error | holder | theme |
| own | Stative | error | holder | theme |
| sit | Stative | error | holder | (none) |
| stand | Stative | error | holder | (none) |
| lie | Stative | error | holder | (none) |
| lean | Stative | error | holder | (none) |
| look_at | Stative | error | experiencer | stimulus |
| gaze_at | Stative | error | experiencer | stimulus |
| see | Stative | error | experiencer | stimulus |
| hear | Stative | error | experiencer | stimulus |
| know | Stative | error | experiencer | stimulus |
| believe | Stative | error | experiencer | stimulus |
| intend | Stative | error | experiencer | stimulus |
| run | error | Process | agent | (none) |
| walk | error | Process | agent | (none) |
| swim | error | Process | agent | (none) |
| fly | error | Process | agent | (none) |
| dance | error | Process | agent | (none) |
| burn | error | Process | patient | (none) |
| bleed | error | Process | patient | (none) |
| flow | error | Process | agent | (none) |
| pour | error | Process | agent | theme |
| strike | error | Event | agent | patient |
| throw | error | Event | agent | theme |
| fall | error | Event | patient | (none) |
| give | error | Event | agent | theme, recipient |
| send | error | Event | agent | theme, recipient |
| arrive | error | Event | agent | (none) |
| depart | error | Event | agent | (none) |
| break | error | Event | agent | patient |
| catch | error | Event | agent | patient |
| drop | error | Event | agent | patient |
| charge | error | Event | agent | patient |

The `(none)` rows take no positional argument at all: a goal or source for `run`, `arrive` or `depart` is written as `*goal @castle` / `*source @forest`, not positionally.

### 5.1 Open lemma policy

The three lists are routing tables, not a closed vocabulary. A lemma in none of them is admitted with a parse warning on stderr and takes a default signature:
- `>` form → Stative with `lemma=X, holder=LHS, theme=pos[0]`
- `>>` form → Event with `lemma=X, agent=LHS, patient=pos[0]`

The warning never changes the emitted graph. v1.2 may extend the tables empirically based on extractor data.

### 5.2 Sigil mismatch policy

Both mismatches are hard errors — the parser does not silently re-route a sigil, in either direction:

- `>>` with a Stative-only lemma (`@bob >> hold @sword`) → `lemma 'hold' is Stative; use '>' instead of '>>'`.
- `>` with an Event- or Process-only lemma (`@bob > strike @boar`) → `lemma 'strike' is Event/Process; use '>>' instead of '>'`.

An earlier draft of this section had the first case emit a Stative with a warning. It does not; failing loudly keeps the aspect that the author wrote and the aspect that lands in the graph from ever diverging.

### 5.3 Ditransitive (give-style) parsing

`@alice >> give @book @bob` → `(e / Event :lemma give :agent alice :theme book :recipient bob)`.

Two positional refs after lemma when lemma table specifies `theme + recipient`. Order: theme first, recipient second.

For unfamiliar lemmas with multi-arg semantics: use explicit `*K V`:
`@alice >> donate @book *recipient @library`.

---

## 6. Geometry routing

`*bbox2d` (canonical), no `*box` alias.

```ebnf
bbox2d_value = '"' float ',' float ',' float ',' float '"'
```

All four values are normalized to `[0,1]` — `x, y, width, height` in the frame's coordinate space ([`docs/vson.md`](./vson.md) §5.4). This is a producer obligation: **no tool checks it.** The parser treats `*bbox2d` as an opaque string-valued direct property, and there is no `vss:BboxShape` in the shapes layer. A malformed bbox round-trips and conforms.

Other geometry keys (`position3d`, `scale3d`, `rotation`) follow the same string-literal pattern and are likewise unchecked.

---

## 7. Reentrancy & forward references

Authoring rules:

- A handle is declared exactly once, at head position (`entity_decl`, `frame_decl`, or the Composition root).
- A reference (`@id` or bare `id`) MAY precede its declaration — forward references resolve.
- A handle MUST NOT be declared twice.
- A handle used as a role argument MUST be declared somewhere in the document.

Enforcement, as shipped: **only the first two hold mechanically.** The VSON-X parser is a single forward pass that builds an AST; the two-pass structure lives in the shared emitter ([`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py)), whose `collect_declared` pre-pass registers every variable introduced with a concept before any triple is written — which is what makes forward references work, for VSON-P and VSON-X alike.

Nothing rejects the other two. A duplicate declaration emits both declarations onto the same IRI; an undeclared handle emits a dangling document-local IRI, and because it was never declared it also loses the reentrancy routing of Appendix D §D.6 rule 2. Both are producer errors that no gate catches — closing them is v1.2 parser work, listed with the other unimplemented checks in §4.10.1.

---

## 8. Ontology and shape declarations VSON-X depends on

These declarations are normative and live in [`ontology/vso.ttl`](../ontology/vso.ttl) (§8.1–§8.4) and [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) (§8.5). They shipped in v1.1; the snippets below are the contract each one carries, and the files are canonical if the two ever differ.

### 8.1 `vso:class`

`vso:class` is declared as a plain `rdf:Property`, deliberately, because its object is not consistently a literal or consistently an IRI.

The reason is the shared bare-ID routing of Appendix D §D.6: the role `class` is in none of the three routing lists of [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json), so a bareword value falls through to the default and is emitted as an IRI in the document namespace — `*class Knight` and Penman's `:class Knight` both produce `vso:class :Knight`, not `vso:class "Knight"`. An author who writes a quoted string gets a string literal instead. Both forms are in the wild, and both round-trip.

Typing the property as `owl:DatatypeProperty` would make every bareword document inconsistent under OWL RL; typing it as `owl:ObjectProperty` would do the same to every quoted-string document. Changing the emitter to pick one form would be a breaking change for the other. `rdf:Property` formalizes the duality instead of pretending it away:

```turtle
vso:class a rdf:Property ;
    rdfs:domain vso:Entity ;
    rdfs:comment "Domain-class designation from open registry (Knight, Crown, Sword, Woman, ...). Open vocabulary; values are typically IRIs in the document namespace (e.g., <document#Knight>) when emitted from bareword input, but xsd:string literals are also conformant. Range deliberately unconstrained (rdf:Property, not owl:DatatypeProperty/ObjectProperty) to admit both forms." .
```

### 8.2 `vso:modifier`

For Quality stacking (§3.2.2).

```turtle
vso:modifier a owl:DatatypeProperty ;
    rdfs:domain vso:Quality ;
    rdfs:range xsd:string ;
    rdfs:comment "Optional adverbial modifier (e.g., 'dark' on color, 'very' on weight). Snake_case bareword." .
```

### 8.3 Persona class and properties

```turtle
vso:Persona a owl:Class ;
    rdfs:subClassOf vso:Frame ;
    rdfs:label "Persona" ;
    rdfs:comment "Cross-document identity carrier. Links scene Entities to stable identity invariants (hair, build, etc.). Persona IRIs MAY be shared across multiple VSON documents." .

vso:embodies a owl:ObjectProperty ;
    rdfs:domain vso:Entity ;
    rdfs:range vso:Persona ;
    rdfs:comment "Entity embodies (instantiates) a Persona in this scene." .

vso:hasInvariant a owl:ObjectProperty ;
    rdfs:domain vso:Persona ;
    rdfs:range vso:Quality ;
    rdfs:comment "Invariant Quality of the Persona — stable across embodiments. Contrast with vso:hasQuality which is contingent per scene." .
```

### 8.4 No SymmetricProperty declarations on proximal values

v1.0 declared `vso:near`, `vso:far`, `vso:adjacent`, `vso:nextTo` and `vso:facing` as `owl:ObjectProperty, owl:SymmetricProperty`. They are not predicates — they are values of `vso:proximal` — so the `owl:SymmetricProperty` characteristic fired on zero triples. The declarations are gone as of v1.1: the five are individuals, and symmetry is handled at emission time by the two-node expansion of §4.9. `owl:SymmetricProperty` survives in [`ontology/vso.ttl`](../ontology/vso.ttl) only on `vso:overlaps` and `vso:disjoint`, which really are predicates.

### 8.5 Shape declarations in [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl)

#### `vss:PersonaShape`

```turtle
vss:PersonaShape a sh:NodeShape ;
    sh:targetClass vso:Persona ;
    sh:property [
        sh:path vso:hasInvariant ;
        sh:minCount 1 ;
        sh:message "Persona MUST declare at least one hasInvariant Quality."
    ] .
```

#### `vss:EmbodimentConsistencyShape`

```turtle
vss:EmbodimentConsistencyShape a sh:NodeShape ;
    sh:targetClass vso:Entity ;
    sh:sparql [
        sh:select """
            SELECT $this ?invariantDim ?embodiedQ ?invariantValue ?embodiedValue WHERE {
                $this vso:embodies ?persona .
                ?persona vso:hasInvariant ?invariantQ .
                ?invariantQ vso:dimension ?invariantDim ; vso:value ?invariantValue .
                $this vso:hasQuality ?embodiedQ .
                ?embodiedQ vso:dimension ?invariantDim ; vso:value ?embodiedValue .
                FILTER (?invariantValue != ?embodiedValue)
            }
        """
    ] ;
    sh:severity sh:Warning ;
    sh:message "Entity hasQuality value contradicts embodied Persona's hasInvariant on the same dimension." .
```

Severity = Warning (not Violation) per §10 partial-mode policy — embodiment conflicts often arise from extractor noise, not authoring errors.

### 8.6 Profile system for partial mode

**Strict profile** (default): [shapes/vson-shapes.ttl](../shapes/vson-shapes.ttl) — unchanged from v1.0. `vss:CompositionShape, vss:DirectionalNeedsViewerShape, vss:EventShape, vss:QualityShape, vss:FrameNotDepictedShape, vss:SpatialFactShape, vss:RccValueShape` all `sh:Violation`.

**Relaxed profile** (new): `shapes/vson-shapes-relaxed.ttl` — imports strict, overrides:
- `vss:DirectionalNeedsViewerShape` → `sh:Warning`
- `vss:EventShape` (lemma constraint) → `sh:Warning`
- `vss:QualityShape` (dimension/value constraints) → `sh:Warning`
- `vss:EmbodimentConsistencyShape` → `sh:Warning` (already)

`sh:Violation` retained on:
- `vss:CompositionShape` (depicts ≥1) — semantic floor
- `vss:FrameNotDepictedShape` — semantic layer correctness
- `vss:SpatialFactShape` (figure + ground required) — node well-formedness
- `vss:RccValueShape` (closed enum) — vocab correctness
- `vss:PersonaShape` — node well-formedness

`vson validate` (default) loads the strict profile — byte-identical to v1.0 conformance behavior. The `--partial` switch specified here is **not implemented**: as of v1.1 the relaxed file ships, but no `vson validate` flag (Rust CLI or Python reference) selects it, so nothing loads it outside the shapes-gate test in `tests/`. Wiring the flag is v1.2 work.

### 8.7 Schema versioning

[`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) accepts `version` ∈ {`1.0`, `1.0.5`, `1.1`}, carries an optional `vson_x` string, and defaults `conformance.profile` to `"strict"`.

The `vson_p` rule landed differently from the Phase 0 sketch. `vson_p` and `vson_t` remain required *keys*, but back-conversion to Penman (`t2p`) did not ship in v1.1, so a VSON-X envelope carries `vson_p: ""`. The schema therefore keeps `minLength: 3` on `vson_p` only for `version` ∈ {`1.0`, `1.0.5`}, and for `1.1` requires an `anyOf`: at least one of `vson_p` / `vson_x` non-empty. `vson_x` is populated when the surface form was VSON-X. See [`docs/vson.md`](./vson.md) §6.1 for the field-by-field reference.

### 8.8 Conformance semantics with profiles

`conformance.conforms` reflects validation outcome **within the chosen profile**. Profile is independent of `version`; same document text MAY be validated under either profile.

| profile | `conforms = true` means |
|---|---|
| `strict` (default) | No `sh:Violation` triggered. v1.0 byte-identical semantics. |
| `relaxed` | No `sh:Violation` triggered (warnings allowed and listed in report). |

The set of shapes is identical across profiles; only `sh:severity` differs:

| Shape | Strict severity | Relaxed severity |
|---|---|---|
| `vss:CompositionShape` (depicts ≥ 1) | Violation | Violation |
| `vss:FrameNotDepictedShape` | Violation | Violation |
| `vss:SpatialFactShape` (figure + ground) | Violation | Violation |
| `vss:RccValueShape` | Violation | Violation |
| `vss:PersonaShape` (hasInvariant ≥ 1) | Violation | Violation |
| `vss:DirectionalNeedsViewerShape` | Violation | **Warning** |
| `vss:EventShape` (lemma required) | Violation | **Warning** |
| `vss:QualityShape` (dim + value) | Violation | **Warning** |
| `vss:EmbodimentConsistencyShape` | Warning | Warning |

**Consumer contract**: clients MUST inspect both `conforms` AND `profile` to determine document status. `conforms=true, profile="relaxed"` is NOT equivalent to v1.0 conformance — it MAY have warnings that strict mode would treat as violations.

**Backward-compat guarantee**: every v1.0 document that previously had `conforms=true` continues to have `conforms=true` under both profiles in v1.1 — no shape was made more restrictive, only some were softened in relaxed.

**Default behavior**: `vson validate file.vson` uses the strict profile (byte-identical to v1.0). The `--partial` form is specified, not shipped — see §8.6.

---

## 9. Parser dispatch

`.vson` file: peek first non-whitespace, non-comment character.

| First char | Syntax |
|---|---|
| `(` | VSON-P (Penman) |
| `~` | VSON-X |
| `@` followed by `prefix ` | VSON-T (Turtle 1.2) |
| Other | parse error |

`.ttl` file: always VSON-T (regardless of first char).

VSON-X documents MUST NOT begin with `(` after stripping comments and whitespace. The grammar guarantees this: the root sigil is `~`, and it is the document's first token.

**Not implemented as a shared table.** There is no `tools/vson_dispatch.py`, no `cli/src/dispatch.rs`, and no `dispatch` block in [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json). In v1.1 the caller states the surface form by choosing a subcommand — `vson convert p2t` versus `vson convert x2t` — so nothing sniffs a `.vson` file's first character. The table above is the rule a future single-entry-point dispatcher MUST implement; centralizing it the way the routing tables are centralized is v1.2 work.

---

## 10. Caption renderer interface

`tools/render/caption.py` signature:

```python
def render(graph: rdflib.Graph) -> str: ...
```

Renderer consumes RDF graph (post-transpilation), NOT AST. Single renderer serves both VSON-P and VSON-X surface forms — graph is syntax-independent.

CLI: `vson export caption file.vson` flow:
1. Detect syntax via dispatcher.
2. Transpile to Turtle (existing path for P; new for X).
3. Load Turtle into rdflib.Graph.
4. Call renderer.

### 10.1 Acceptance criteria — separated

| Criterion | Mechanism | Frequency |
|---|---|---|
| **CI determinism** | every scene in `examples/gallery/` renders byte-identical to its `tests/fixtures/captions/<stem>.txt` fixture — 16 scenes as of v1.1, and `tests/test_caption_renderer.py` fails if any scene lacks a fixture, so the two stay in step | Every commit |
| **Generation faithfulness** | 30-image triple A/B (`direct VSON / caption-pipeline / plain prompt`) with CLIP image-image similarity | Specified, not built — no harness for it ships in this repository, and no VSON artifact claims a number from it |

CI test failure = renderer bug. A generation-faithfulness drop = the renderer template needs improvement. These are separate gates on purpose: conflating them would let a template regression hide behind a green CI run, or a fixture churn look like a quality change.

---

## 11. Lookbook canonical example

Every semantic decision in this document applied to one scene. It parses under the reference parser and emits the 8 SpatialFact nodes §11.2 predicts.

```vson-x
~lookbook
  /CameraView @cam *angle eye_level *focalLength 50mm *framing wide_shot
  ^cam
  /VisualStyle *aesthetic photographic *palette neutral *medium photograph
  /SceneContext *venue studio_concrete *atmosphere neutral

  @m1 /PhysicalObject Skolem Agentive *class Woman *bbox2d "0.04,0.10,0.22,0.88"
    *hair blonde *skin light
  @m2 /PhysicalObject Skolem Agentive *class Woman *bbox2d "0.24,0.13,0.18,0.78"
    *hair blonde *skin light
  @m3 /PhysicalObject Skolem Agentive *class Woman *bbox2d "0.40,0.10,0.22,0.90"
    *hair brunette *skin light
  @m4 /PhysicalObject Skolem Agentive *class Woman *bbox2d "0.58,0.13,0.20,0.80"
    *hair blonde *skin light
  @m5 /PhysicalObject Skolem Agentive *class Woman *bbox2d "0.76,0.11,0.22,0.88"
    *hair brunette *skin light

  @blz_blk /PhysicalObject Generic Inert Wearable *class Blazer
    *color black *fit oversized
  @bag_blk /PhysicalObject Generic Inert Holdable *class Handbag
    *color black *material crocodile_leather
  @swt_lim /PhysicalObject Generic Inert Wearable *class Sweater
    *color lime_green *fit oversized
  @bag_pnk /PhysicalObject Generic Inert Holdable *class Handbag
    *color pink *size mini

  @m1 > wear @blz_blk
  @m1 > hold @bag_blk
  @m4 > wear @swt_lim
  @m4 > hold @bag_pnk

  @m1 > stand
  @m2 > stand
  @m3 > stand
  @m4 > stand
  @m5 > stand

  @m1 & adjacent & @m2
  @m2 & adjacent & @m3
  @m3 & adjacent & @m4
  @m4 & adjacent & @m5
```

### 11.1 Token economy — what is actually measured

The example above is **177** whitespace-separated tokens. Transpiled with [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py) it emits 222 triples and **908** whitespace-separated tokens of VSON-T, so on this scene VSON-X is about 19% of the canonical Turtle.

There is no VSON-P counterpart to compare against: no Turtle → Penman back-converter ships (§8.7), and this scene was authored in VSON-X. **So no VSON-X-versus-VSON-P ratio is claimed here.** The "~30% of Penman" figure from the initial design was extrapolated from one hand-written pair and should not be cited; a real ratio needs a corpus measurement over `examples/gallery/` and `examples/gallery-x/`, which has not been run.

### 11.2 Symmetry expansion check

`@m1 & adjacent & @m2` emits TWO SpatialFact nodes per §4.9 (figure↔ground swapped, both with `vso:proximal vso:adjacent`). Total in this scene: 4 symmetric pairs × 2 = 8 SpatialFact nodes. Asymmetric `!` would emit 4 nodes — 2× cost is the symmetry tax.

If 2× cost becomes a problem, future optimization: dedicated `vso:SymmetricSpatialFact` class with `vso:between` (multi-valued) replacing `figure`/`ground`. Out of scope v1.1.

---

## 12. Out of scope (deliberately deferred to v1.2)

### 12.1 VSON-X surface gaps (deferred)

- Domain-class aliases (`/Woman` → `/PhysicalObject *class Woman`).
- Open dimension extension namespace.
- Polysemous lemma disambiguation (e.g., `stand` posture vs `stand_up` action).
- VSON-X surface for **Negation**, **BeliefState**, **Annotation** (currently VSON-P/T only via reified node decl `/Negation`, `/BeliefState`, `/Annotation`).
- VSON-X surface for **Causal** (`:causes`, `:enables`, `:prevents`, `:triggers` between Perdurants). Currently only via VSON-P container role `:causal (X :causes Y)`.
- VSON-X surface for **Allen temporal** (`:before`, `:meets`, `:during`, etc.). Currently only via VSON-P container role `:temporal (X :before Y)`.
- VSON-X surface for **Mereology** (`:partOf`, `:hasPart`, `:overlaps`, `:disjoint`). Currently only via VSON-P direct edges (no VSON-X sigil).
- Symmetric `next_to`, `facing_each_other` lemmas (require ontology refactor; v1.1 supports `near, far, adjacent` only).

### 12.2 Tooling deferrals

- LLM caption polish (`vson export caption --polish`).
- Native Rust caption renderer (v1.1 uses Python via shell-out).
- Cross-document Persona registry validation tooling (v1.1 ships the Persona ontology + SHACL only).
- `t2x` Turtle → VSON-X transpiler (Rust).
- Source-iso lossless round-trip (Penman blank-node names like `q1`, `sf1` → VSON-X anonymous → Penman would re-generate names like `_q42`; only graph-iso is promised).
- `vso:depicts` vs `vso:hasFact`/`vso:occurs` round-trip (VSON-X parser collapses to `:depicts`; original distinction lost; see §4.4).

---

## 13. Release gates — closed

The staged Phase 0 → A → A.5 → B gates that governed the VSON-X build are closed with v1.1. The mechanical ones are now verified continuously by `make x-check` (gallery round-trip parity against Penman) and `make x-skill-check` (skill conformance over the `examples/gallery-x/` corpus); both run on every push in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), so this section needs no checklist to stay honest.

Three gate items did not ship as written. None is tracked here — each is documented where a reader would look for it: the `--partial` validate flag (§8.6), the shared syntax dispatcher (§9), and the generation-faithfulness metric, which was never built (§10.1).

---

*This document is normative for VSON-X surface semantics. It does not carry independent authority over the rest of VSON: conflicts with any other VSON artifact are resolved by the precedence order in [`docs/vson.md`](./vson.md) §2, which ranks this document second. Where this document specifies a parser rule that the reference parser does not yet implement, the gap is called out inline (see §4.10.1) rather than left for the reader to discover.*
