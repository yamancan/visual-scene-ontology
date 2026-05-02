# Bare-VLM Baseline Measurement

A 1-day side-quest answering: **how good is Claude Opus 4.7, alone, with our v1.0 orchestrator prompt, at emitting SHACL-conformant VSON-P from a bare image?**

The number gates the Phase 2 detector pipeline. Read [`results.md`](results.md) for the pre-registered decision rule.

## Run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python extract.py --live --images images/
```

Writes `results.csv` (one row per image) and prints `n` and `shacl_first_try` rate.

## Ablations

```bash
for variant in no_worked_example no_shacl_section no_decision_policies; do
  python extract.py --live --images images/ \
    --prompt ablations/$variant.md \
    --out results_${variant}.csv
done
```

## CI

The offline cassette test in [`tests/extractor/test_baseline_smoke.py`](../../../tests/extractor/test_baseline_smoke.py) exercises the plumbing without an API call. Live measurement is **manual, local, developer-run** — never on CI.

## Cost & latency

- ~$0.05–$0.15/call at Opus 4.7 with cached system prompt (output is the driver at $75/Mtok).
- 20 images × 4 prompt variants = 80 calls ≈ $4–12.
- Sprint API budget: **$15** (headroom for repair retries).
- Latency: P50 4–8s cached, 6–12s on cold-start cache miss.
