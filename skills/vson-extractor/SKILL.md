---
name: vson-extractor
description: Look at an image and emit a SHACL-conformant VSON-P (Penman) scene graph. One Composition node, frames, entities, qualities, spatial facts, events. No prose, no fences.
version: 1.0.0
license: Apache-2.0
inputs: [image]
outputs: [vson_p]
---

# VSON Extractor

Read an image, emit one VSON-P document. The first character of your reply is `(`. The last is `)`. Nothing else — no prose, no markdown fences, no commentary.

## Output grammar

```
node     := "(" var "/" Concept (":" role target)* ")"
target   := var | Concept | literal | node
var      := lowercase identifier (e.g. c, alice, sf1)
Concept  := PascalCase from the vocabulary below
role     := camelCase from the vocabulary below
literal  := bareword | "quoted string" | number | "0.32,0.18,0.16,0.62"
```

A bare `var` after declaration is a reentrancy (refers back to the prior node).

## Closed vocabulary (VSV)

Use only these tokens. Anything else fails SHACL.

**Concepts** — `Composition` `SceneContext` `VisualStyle` `CameraView` `PhysicalObject` `Aggregate` `Substance` `Event` `Process` `Stative` `Quality` `Region` `SpatialFact` `Annotation`

**Frame roles** — `framedBy` `depicts` `viewedBy` `rendersAs` `hasQuality`

**Trait values**
- `individuation` ∈ {`Generic`, `Named`, `Kind`, `Skolem`}
- `animacy` ∈ {`Agentive`, `Inert`}
- `countability` ∈ {`Count`, `Mass`, `Collective`}
- `affordance` ∈ {`Holdable`, `Wearable`, `Mountable`, `Container`, `Edible`}

**Quality dimensions** — `Color` `Weight` `Material` `Affect` `Age` `Role` `Size` `Layout` `Focal` `ActionState`

**Thematic roles (Event/Stative/Process)** — `agent` `patient` `theme` `instrument` `recipient` `source` `goal` `beneficiary` `experiencer` `stimulus` `location` `time` `manner` `cause` `result` `holder` `lemma`

**SpatialFact**
- structural: `figure` `ground` `viewer`
- `:rcc` ∈ {`DC`, `EC`, `PO`, `EQ`, `TPP`, `NTPP`, `TPPi`, `NTPPi`}
- `:directional` ∈ {`above`, `below`, `leftOf`, `rightOf`, `inFrontOf`, `behind`}
- `:proximal` ∈ {`near`, `far`, `adjacent`}

**Camera schema** — `angle` `focalLength` `framing` `cameraPosition`
**Style schema** — `aesthetic` `palette` `medium`
**Scene schema** — `venue` `atmosphere` `timeOfDay` `weather`
**Geometry** — `bbox2d` (string `"x,y,w,h"`, all in [0,1])

## Five hard rules

1. **Talmy viewer.** Every `SpatialFact` with `:directional` MUST also carry `:viewer cam` (the document's `CameraView`). No exceptions.
2. **Reify, don't edge-cram.** Actions are `Event` nodes with thematic roles. Spatial relations are `SpatialFact` nodes. Properties are `Quality` nodes. Never emit edges like `:strikes` or `:on`.
3. **Closed enums only.** Trait values, dimensions, RCC/directional/proximal values must be from the lists above. PascalCase a class name only if no listed class fits.
4. **Omit over hallucinate.** No upstream evidence → no triple. Never invent. Default `:individuation Generic`.
5. **Bbox normalized.** `:bbox2d "0.32,0.18,0.16,0.62"` — string literal, all four numbers in [0,1].

## Emission order

```
Composition → Frames (SceneContext, VisualStyle, CameraView)
            → Entities (PhysicalObject / Aggregate / Substance)
            → SpatialFacts
            → Events / Statives / Process
            → Annotations (only for low-confidence triples)
```

Within each group, top-down, left-to-right by bbox.

## Worked example (close_up of an apple)

```
(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing close_up)
   :viewedBy cam
   :depicts (apple / PhysicalObject :class Apple
               :individuation Generic :animacy Inert :countability Count
               :affordance Edible :affordance Holdable
               :bbox2d "0.30,0.32,0.40,0.42"
               :hasQuality (q1 / Quality :dimension Color :value red)))
```

A scene with a directional spatial relation:

```
:depicts (sf1 / SpatialFact
            :figure crown :ground alice
            :rcc EC :directional above :viewer cam)
```

## Self-check before emitting

1. Output starts with `(` and ends with `)`. No prose, no fences.
2. Every `:directional` SpatialFact has `:viewer cam`.
3. Every `Event` has `:lemma`. Every `Quality` has both `:dimension` and `:value`.
4. Every `:bbox2d` is `"x,y,w,h"` with all four in [0,1].
5. No bare predicate edges between entities — actions and spatial relations are nodes.

If any check fails, fix and re-emit. Never explain. Always emit.
