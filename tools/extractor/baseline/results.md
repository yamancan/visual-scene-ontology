# Bare-VLM Baseline — Pre-Registration & Results

> **Status:** pre-registered, not yet measured. The decision rule below is
> committed *before* any live API call so the conclusion cannot be
> retrofit. Run `python tools/extractor/baseline/extract.py --live --images
> tools/extractor/baseline/images/` once the image set is in place.

## Hypothesis

> Given the v1.0 orchestrator system prompt (`tools/extractor/prompts/orchestrator-system.md`)
> and a bare image (no upstream tool evidence), Claude Opus 4.7 (`claude-opus-4-7`)
> emits a VSON-P document that:
> 1. parses with the reference Penman parser, and
> 2. passes SHACL conformance against `shapes/vson-shapes.ttl` + `ontology/*.ttl`,
> on first try, at rate `p̂` over `n=20` diverse images.

## Pre-registered decision rule

`p̂` is the SHACL-pass-on-first-try rate. CI is the 95% Wilson interval.

| Branch | Condition | Implication |
|---|---|---|
| **A — Skip detector spend** | `p̂ ≥ 0.80` and `CI_lower ≥ 0.65` | Bare VLM is good enough. Fold the bare-VLM call into the Studio MVP as the `vson generate` backbone. Cancel Phase 2 detector pipeline. |
| **B — Targeted detectors** | `0.50 ≤ p̂ < 0.80` | Build only S2 (open-set detection) and S5 (depth) as Phase 2 work; skip S1/S4/S6 ML stages. |
| **C — Full pipeline justified** | `p̂ < 0.50` | Architecture justified as designed; staged S0–S9 pipeline goes to Phase 2 backlog with empirical confidence. |

### Ablation gate

Three ablations (`ablations/no_worked_example.md`, `no_shacl_section.md`, `no_decision_policies.md`) run on the same 20 images. **If any ablation shifts pass rate by > 15 percentage points, the prompt — not single-VLM-ness — is the bottleneck; do NOT use the bare-VLM rate as evidence for/against the pipeline.** Re-run after prompt iteration before deciding.

## Image manifest (n=20)

10 photographic CC0 (Unsplash) + 10 stylized (stablestudio.dev, owned). Filled in once curation completes.

### Photographic (10)

| # | Filename | Source | License | Description |
|---|---|---|---|---|
| 1 | `throne_room.jpg` | TBD | CC0 | canonical happy-path indoor |
| 2 | `kitchen_busy.jpg` | TBD | CC0 | sparse evidence; Aggregates |
| 3 | `street_crowd.jpg` | TBD | CC0 | Collective countability stress test |
| 4 | `water_pouring.jpg` | TBD | CC0 | Substance / Mass |
| 5 | `empty_room.jpg` | TBD | CC0 | adversarial: emit minimal valid doc |
| 6 | `forest_path.jpg` | TBD | CC0 | outdoor + natural lighting |
| 7 | `single_apple.jpg` | TBD | CC0 | thin-evidence path |
| 8 | `crowd_action.jpg` | TBD | CC0 | dense + action |
| 9 | `pet_calm.jpg` | TBD | CC0 | animal + Affect dimension |
| 10 | `bookshelf.jpg` | TBD | CC0 | many static objects |

### Stylized (10)

| # | Filename | Source | License | Description |
|---|---|---|---|---|
| 11 | `ai_anime_battle.png` | stablestudio.dev | owned | AI anime + action |
| 12 | `ai_oil_landscape.png` | stablestudio.dev | owned | painterly outdoor |
| 13 | `ai_cyberpunk_street.png` | stablestudio.dev | owned | high-saturation aesthetic |
| 14 | `ai_studio_ghibli_meadow.png` | stablestudio.dev | owned | Ghibli-style classifier check |
| 15 | `ai_pixel_dungeon.png` | stablestudio.dev | owned | low-resolution stylized |
| 16 | `ai_3d_render_kitchen.png` | stablestudio.dev | owned | 3d_render aesthetic |
| 17 | `ai_concept_art_castle.png` | stablestudio.dev | owned | concept_art aesthetic |
| 18 | `ai_watercolor_market.png` | stablestudio.dev | owned | watercolor + crowd |
| 19 | `ai_noir_street.png` | stablestudio.dev | owned | monochrome / high-contrast |
| 20 | `ai_vector_garden.png` | stablestudio.dev | owned | flat illustration |

## Results table (filled by `extract.py`)

| image | shacl_first_try | shacl_after_retries | retries | latency_ms | input_tokens | output_tokens |
|---|---|---|---|---|---|---|
| _(pending live run)_ | | | | | | |

## Conclusion (filled in after measurement)

_(One paragraph; record which branch fired and how the ablations moved.)_
