# vson-extractor skill

A portable, ~4 KB system prompt that teaches any vision-capable LLM to emit SHACL-conformant VSON-P (Penman) scene graphs from an image.

- [SKILL.md](./SKILL.md) — the prompt.
- [conformance.json](./conformance.json) — the 5-image acceptance fixture.

License: Apache-2.0, matching the VSO ontology.

## Use it

The skill body is plain Markdown — paste it as the system prompt for the model and feed an image with the user message "emit the document".

### Anthropic (Claude)

```ts
const SKILL = await readFile('skills/vson-extractor/SKILL.md', 'utf8');

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

`cache_control: ephemeral` lets Anthropic cache the 4 KB prompt across a 5-minute window, so subsequent calls in the same conversation pay ~10% of the input-token cost on the cached prefix.

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

### Google (Gemini)

```ts
await model.generateContent({
  systemInstruction: SKILL,
  contents: [{
    role: 'user',
    parts: [
      { inlineData: { mimeType: 'image/jpeg', data: b64 } },
      { text: 'Emit the document.' }
    ]
  }]
});
```

### OpenRouter (any of the above)

OpenRouter speaks OpenAI-format. Use the OpenAI snippet above with the OpenRouter endpoint and a model id like `google/gemini-2.5-flash`, `anthropic/claude-opus-4-7`, or `openai/gpt-5`.

### Anthropic Skills API

When uploading via the Skills API, this directory is the entire skill: the agent reads `SKILL.md` as the prompt body and `conformance.json` as the certification fixture.

## Validate the output

The skill emits a Penman document. Round-trip it with the Rust CLI:

```bash
echo "$VSON_P" | vson convert --to ttl | vson validate --shapes shapes/vson-shapes.shacl.ttl
```

Or use the studio (`web/`): drop the image, copy the rendered penman, paste into another model's input — they should agree on the same graph.

## Conformance

A model that claims VSON-extractor support passes if:

- ≥ 4/5 of the [conformance.json](./conformance.json) fixtures emit `conforms: true` on first try.
- No repair retry needed for ≥ 4/5.

Studio's repair loop (max 2 retries) is for graceful degradation, not the certification path.
