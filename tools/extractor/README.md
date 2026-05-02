# VSON Extractor

Image → SHACL-conformant VSON document.

This module implements the staged pipeline described in [`docs/strategy/extractor-architecture.md`](../../docs/strategy/extractor-architecture.md). It is the production realization of "drag a JPEG, get a graph."

## Layout

```
tools/extractor/
├── README.md                              this file
├── prompts/
│   ├── orchestrator-system.md             master system prompt (cache-friendly)
│   ├── orchestrator-user-template.md      per-call user template
│   └── specialized/
│       ├── style-classifier.md            VLM zero-shot prompt for VisualStyle
│       ├── scene-classifier.md            VLM zero-shot prompt for SceneContext
│       ├── action-recognizer.md           VLM prompt for Event vs Stative inference
│       ├── quality-extractor.md           VLM prompt for per-entity Qualities
│       └── repair.md                      SHACL-failure repair prompt
├── pipeline/                              (forthcoming) Python orchestration
│   ├── stages/
│   │   ├── s0_input.py
│   │   ├── s1_frame.py
│   │   ├── s2_detect.py
│   │   ├── s3_traits.py
│   │   ├── s4_quality.py
│   │   ├── s5_spatial.py
│   │   ├── s6_action.py
│   │   ├── s7_orchestrate.py
│   │   ├── s8_validate.py
│   │   └── s9_audit.py
│   └── pipeline.py
└── tests/
    └── fixtures/                           50 image → gold VSON pairs (forthcoming)
```

## Why a system / user split

The system prompt (`orchestrator-system.md`) is **static across all extractions**. It carries:

- Role definition, output schema, VSV vocabulary, SHACL constraints, decision policies, worked example.

The user prompt (`orchestrator-user-template.md`) is **per-call**. It carries:

- The image, the upstream tool outputs (S1–S6 JSON blobs), the request id.

This split is deliberately **prompt-cache friendly** (Anthropic / OpenAI prompt caching): the static system prompt is cached once and reused; only the user prompt is paid per-call. At scale (millions of extractions/month), this is the difference between $50k/month and $5k/month in inference cost.

## Quickstart (local dev)

```bash
# Build a single extraction (placeholder — pipeline forthcoming)
python -m tools.extractor.pipeline.pipeline \
  --input examples/throne_room.jpg \
  --output /tmp/extracted.vson \
  --model claude-opus-4-7

# Validate the result
make -C ../.. shacl FILE=/tmp/extracted.vson

# Reverse-render audit
python -m tools.extractor.pipeline.stages.s9_audit \
  --vson /tmp/extracted.vson \
  --original examples/throne_room.jpg
```

## See also

- [`docs/strategy/extractor-architecture.md`](../../docs/strategy/extractor-architecture.md) — full architecture
- [`prompts/orchestrator-system.md`](./prompts/orchestrator-system.md) — the comprehensive prompt
- [`spec/vson-spec-v1.md`](../../spec/vson-spec-v1.md) — what the extractor emits
- [`shapes/vson-shapes.ttl`](../../shapes/vson-shapes.ttl) — what the emission must conform to
