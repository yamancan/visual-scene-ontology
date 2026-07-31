# vson-extractor-x skill

A ~7 KB system prompt that teaches any vision-capable LLM to emit SHACL-conformant VSON-X (compact, sigil-based) scene graphs from an image. Same RDF graph as `vson-extractor`, different surface syntax — nine prefix sigils, no brackets, one construct per line by convention.

- [SKILL.md](./SKILL.md) — the prompt.
- [conformance.json](./conformance.json) — the 5-image acceptance fixture (matches vson-extractor, swap output type only).

License: Apache-2.0, matching the VSO ontology.

## Why VSON-X over VSON-P

- Lower token count for the same graph (~30-40% on dense scenes).
- One-construct-per-line emission maps cleanly to vision-LLM output patterns (sigils carry kind; newlines are convention, not grammar).
- Same closed VSV (concepts, dimensions, RCC8, thematic roles) — round-trip lossless to Turtle and Penman (modulo the single `vso:depicts` edge collapse for SpatialFact, see `docs/vson-x-semantics.md` §4.4).

Pick `vson-extractor` (Penman) for parser-rich pipelines that already speak AMR-style nesting; pick `vson-extractor-x` for compact emission and downstream caption rendering.

## Use it

The skill body is plain Markdown — paste it as the system prompt for the model and feed an image with the user message "Emit the document."

### Anthropic (Claude)

```ts
const SKILL = await readFile('skills/vson-extractor-x/SKILL.md', 'utf8');

await client.messages.create({
  model: 'claude-opus-4-7',
  system: [{ type: 'text', text: SKILL, cache_control: { type: 'ephemeral' } }],
  messages: [{
    role: 'user',
    content: [
      { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: b64 } },
      { type: 'text', text: 'Emit the document.' }
    ]
  }]
});
```

`cache_control: ephemeral` caches the 7 KB prompt across a 5-minute window so subsequent calls pay ~10% of the input-token cost on the cached prefix.

### OpenAI (GPT-4o / GPT-5)

```ts
await openai.chat.completions.create({
  model: 'gpt-4o',
  messages: [
    { role: 'system', content: SKILL },
    { role: 'user', content: [
      { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${b64}` } },
      { type: 'text', text: 'Emit the document.' }
    ]}
  ]
});
```

### OpenRouter

OpenRouter speaks OpenAI-format. Use the OpenAI snippet with the OpenRouter endpoint and any vision model id (`anthropic/claude-opus-4-7`, `openai/gpt-5`, `google/gemini-2.5-flash`).

## Validate the output

The skill emits a VSON-X document. Round-trip it via the Rust CLI:

```bash
echo "$VSON_X" > /tmp/scene.x.vson
vson convert x2t /tmp/scene.x.vson | vson validate
```

Or use the studio (`web/`) with the notation toggle set to VSON-X: drop the image, the X document renders with reverse-highlight selection sync.

## Conformance

A model claims `vson-extractor-x` support if:

- ≥ 4/5 of the [conformance.json](./conformance.json) fixtures emit `conforms: true` on first try (no repair retry).
- The Talmy-gate fixture (`street`) MUST conform — directional facts require `^cam` viewer.

The studio's repair loop (max 2 retries) is for graceful degradation, not the certification path. The repair-x prompt at `tools/extractor/prompts/specialized/repair-x.md` watches for Penman drift (model regressing to `(scene ...)` mid-fix) and aborts after two failed retries rather than auto-switching notations, to keep telemetry clean.

## Empirical baseline (Phase D smoke)

| Metric | Target | Source |
|---|---|---|
| Surface parseability (sigil balance, ~scene first line) | ≥ 7/10 | `scripts/d_smoke_eval.sh` |
| SHACL strict conformance | ≥ 7/10 | same |
| Talmy directional gate (`street.jpg`) | MUST pass | same |
| Mass countability gate (`kitchen.jpg`) | SHOULD pass | same |
| Corpus conformance over `examples/gallery-x/*.x.vson` | 100% | `make x-skill-check` |

If smoke drops below threshold, iterate on SKILL.md and re-run; do not relax the corpus gate.
