---
name: vson-extractor-x
description: Look at an image and emit a SHACL-conformant VSON-X compact-syntax scene graph. Nine prefix sigils, no brackets, one construct per line. Same VSV vocabulary as vson-extractor.
version: 1.0.0
license: Apache-2.0
inputs: [image]
outputs: [vson_x]
---

# VSON-X Extractor

Read an image, emit one VSON-X document. The first line MUST start with `~scene`. No prose, no markdown fences, no Penman parens. Distilled view; the normative source is `docs/vson-x-semantics.md` — when in conflict, the spec wins.

## Nine sigils

| Sigil | Role |
|---|---|
| `~` | Composition root (line 1) |
| `/` | Concept declaration |
| `@` | Named/Skolem entity (decl + ref); first occurrence declares, later bare reuse |
| `*` | Property kv — bearer-class dispatch (see below) |
| `>` | Stative arrow `lhs > lemma rhs` |
| `>>` | Event/Process arrow `lhs >> lemma rhs` |
| `!` | Asymmetric SpatialFact `figure ! REL ground [^viewer] [*dir D]` |
| `&` | Symmetric SpatialFact `a & lemma & b` (closed lemma list) |
| `^` | Viewer anchor (Composition-level OR scoped to `!` SpatialFact) |

## Closed VSV

**Concepts after `/`** — `PhysicalObject Aggregate Substance CameraView VisualStyle SceneContext Persona Quality Event Process Stative SpatialFact Annotation`. Domain classes (`Knight, Apple`) NEVER appear after `/`; they are values of `*class`.

**Trait keywords** (bareword, after kind, order-independent)
- individuation: `Generic Named Skolem Kind` (default `Skolem` for image-extracted entities)
- animacy: `Agentive Inert`
- countability: `Count Mass Collective`
- affordance: `Holdable Wearable Mountable Container Edible`

**Quality dimensions** — `Color Material Affect Age Role Size Weight Enchantment Layout Focal Pose ActionState Amount Hair Hairstyle Skin Eye Eyewear Headwear Outfit Fit`.

**Frame schema** (direct properties on Frame) — CameraView: `angle focalLength framing cameraPosition`. VisualStyle: `aesthetic palette medium`. SceneContext: `venue atmosphere timeOfDay weather`.

**Entity special direct keys** (NOT Quality) — `class bbox2d position3d scale3d rotation visibleFraction embodies`. Any other `*K V` on Entity → Quality.

**Thematic roles** (`*K V` after lemma) — `agent patient theme instrument recipient source goal beneficiary experiencer stimulus location time manner cause result holder`. Value can be `@ref` or literal.

**SpatialFact** — RCC8: `DC EC PO EQ TPP NTPP TPPi NTPPi`. directional: `above below left_of right_of in_front_of behind`. Symmetric `&` lemma (closed): `near far adjacent`.

## Bearer-class dispatch for `*K V`

| Bearer | `*K V` becomes |
|---|---|
| `~scene` (Composition) | Quality via `hasQuality` (dims `Layout Focal Symmetry Balance Mood`); ONE direct exception: `*rendersAs @style` |
| `/CameraView`, `/VisualStyle`, `/SceneContext` | Direct property using that frame's schema keys |
| `/Persona` | Quality via `hasInvariant` |
| `/PhysicalObject`, `/Aggregate`, `/Substance` | Quality via `hasQuality`, EXCEPT 7 special keys above which are direct |
| Arglist after `>` or `>>` | Thematic role on the Stative/Event/Process |

Composition's structural relations (`framedBy`, `depicts`, `viewedBy`, `hasFact`, `occurs`) are expressed via STRUCTURAL SIGILS — never as `*K V` on `~scene`.

## Lemma → kind table (closed)

| Lemma | Sigil | Kind | LHS | pos[0] |
|---|---|---|---|---|
| hold, wear, carry, own | `>` | Stative | holder | theme |
| sit, stand, lie, lean | `>` | Stative | holder | — |
| look_at, gaze_at, see, hear, know, believe, intend | `>` | Stative | experiencer | stimulus |
| run, walk, swim, fly, dance, flow | `>>` | Process | agent | (goal optional) |
| burn, bleed | `>>` | Process | patient | — |
| pour | `>>` | Process | theme | (recipient optional) |
| strike, break, catch, drop, charge | `>>` | Event | agent | patient |
| throw, give, send | `>>` | Event | agent | theme (+ recipient) |
| fall | `>>` | Event | patient | — |
| arrive, depart | `>>` | Event | agent | (goal/source optional) |

Wrong sigil for lemma = error (e.g., `@bob > strike @boar` is invalid; strike is `>>`).

## Five hard rules

1. **Talmy viewer.** Every `!` SpatialFact carrying `*dir` MUST have `^cam` BEFORE the `*dir` token. Pure topology (`! EC` no `*dir`) needs no viewer.
2. **Closed enums only.** Concepts, trait values, dimensions, frame schema keys, RCC/directional values come from the lists above.
3. **Reify, don't edge-cram.** Actions → `>`/`>>`. Spatial relations → `!`/`&`. Properties → `*K V`. No flat predicates.
4. **Symmetric `&` is closed.** Only `near far adjacent` after `&`. Anything else → use `!`.
5. **Omit over hallucinate.** No evidence → no triple. Bbox optional; if emitted, `"x,y,w,h"` all four in [0,1].

## Worked examples (verbatim from gallery-x)

Minimal — `01_minimal.x.vson`:
```
~scene
  /CameraView @cam *angle eye_level *focalLength 50mm *framing close_up
  ^cam
  apple /PhysicalObject Inert Count *class Apple
```

Directional with viewer (Talmy gate) — `04_directional_with_viewer.x.vson`:
```
~scene
  /CameraView @cam *angle eye_level *focalLength 35mm *framing wide_shot
  ^cam
  lamp /PhysicalObject Inert Count *class Lamp
  chair /PhysicalObject Inert Count *class Furniture
  lamp ! DC chair ^cam *dir left_of
```

Full complexity — `11_throne_room.x.vson`:
```
~scene *layout triangular *focal center *rendersAs @style
  /SceneContext *venue throne_room *atmosphere tense *timeOfDay dusk
  /VisualStyle @style *aesthetic oil_painting *palette warm *medium canvas
  /CameraView @cam *angle low *focalLength 35mm *framing medium_shot
  ^cam

  @alice /PhysicalObject Named Agentive Count *class Human *affect joyful *age 30 *role queen
  @bob /PhysicalObject Named Agentive Count *class Human *role knight *affect focused
  boar /PhysicalObject Generic Agentive Count *class Animal *affect angry *action_state charging
  crown /PhysicalObject Generic Inert Count *class Regalia *material gold *enchantment glowing
  sword /PhysicalObject Generic Inert Count *class Weapon *material steel

  @bob >> strike boar *instrument sword
  boar >> charge @bob
  @alice > look_at boar
  @bob > hold sword

  boar ! DC @bob ^cam *dir in_front_of
  crown ! EC @alice ^cam *dir above
```

## Emission order

```
~scene [*K V on Composition]
  /SceneContext ...
  /VisualStyle @style ...
  /CameraView @cam ...
  ^cam                              (Composition viewer)

  <entity decls, top-down by bbox>

  <Statives, Events, Processes:  > / >>>

  <SpatialFacts:  ! / &>
```

## Self-check before emitting

1. First character is `~`. No fences, no prose, no `(`.
2. Exactly one top-level `^cam` referencing a declared `/CameraView`.
3. Every `!` carrying `*dir` has `^cam` before `*dir`.
4. Every `>>` lemma is in EVENT/PROCESS rows; every `>` lemma is in STATIVE rows.
5. Every `&` lemma is in `{near, far, adjacent}`.
6. `*K V` on Frames uses only that frame's schema keys.
7. `*class V` value is a domain class (e.g. `Knight`), not a VSV concept (`PhysicalObject`).

If any check fails, fix and re-emit. Never explain. Always emit.
