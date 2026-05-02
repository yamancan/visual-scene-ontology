# Orchestrator — User Message Template

> The per-call user message. Templated; values filled in by the pipeline at S7.

---

```
{{IMAGE_ATTACHMENT}}

# UPSTREAM EVIDENCE

## S1 — Frame layer

camera:
  angle: {{camera.angle}}
  focalLength: {{camera.focalLength}}
  framing: {{camera.framing}}
  cameraPosition: {{camera.cameraPosition_optional}}
  lookAt: {{camera.lookAt_optional}}

style:
  aesthetic: {{style.aesthetic}}
  palette: {{style.palette}}
  medium: {{style.medium}}
  confidence: {{style.confidence}}

scene:
  venue: {{scene.venue}}
  atmosphere: {{scene.atmosphere}}
  timeOfDay: {{scene.timeOfDay}}
  weather: {{scene.weather_optional}}
  confidence: {{scene.confidence}}

composition_layout: {{layout.value}}    # one of {triangular, central, rule_of_thirds, golden_spiral, symmetric}

## S2 — Detected entities

{{#each detections}}
  - id: {{id}}
    class: {{class}}            # PascalCase; from VSV class registry or extension
    bbox2d: {{bbox.normalized}}  # "x,y,w,h" in [0,1]
    confidence: {{confidence}}
{{/each}}

## S3 — Trait derivations (already applied per class table)

{{#each traits}}
  - id: {{id}}
    individuation: {{individuation}}
    animacy: {{animacy}}
    countability: {{countability}}
    affordance: {{affordance}}
{{/each}}

## S4 — Per-entity qualities (extracted from crops)

{{#each qualities}}
  - entity: {{entity_id}}
    qualities:
      {{#each qs}}
      - dimension: {{dimension}}
        value: {{value}}
        confidence: {{confidence}}
      {{/each}}
{{/each}}

## S5 — Spatial topology (depth-derived)

{{#each spatial_facts}}
  - figure: {{figure}}
    ground: {{ground}}
    rcc: {{rcc_optional}}
    directional: {{directional_optional}}
    proximal: {{proximal_optional}}
    confidence: {{confidence}}
{{/each}}

## S6 — Action / Stative candidates

{{#each actions}}
  - kind: {{kind}}            # Event | Stative | Process
    lemma: {{lemma}}
    {{#each roles}}
    {{role_name}}: {{value}}
    {{/each}}
    confidence: {{confidence}}
{{/each}}

## METADATA

request_id: {{request_id}}
extracted_at: {{timestamp}}
upstream_models:
  detector: {{detector_model_id}}
  depth: {{depth_model_id}}
  style: {{style_model_id}}
  action: {{action_model_id}}

# YOUR TASK

Emit one VSON-P Penman document conforming to the system prompt's rules.
Output begins with `(` and ends with `)`. Nothing else.
```
