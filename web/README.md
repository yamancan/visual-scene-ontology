# vson web — drop image, graph out

SvelteKit MVP. Stateless. One page, one endpoint. No DB, no auth, no sessions.

## Run

```bash
# from the repo root
cd cli && cargo build --release && cd ..   # one-time, ~30s cold
pip install pyshacl rdflib                 # required by `vson validate`

cd web
pnpm install
cp .env.example .env
# add OPENROUTER_API_KEY to .env (https://openrouter.ai/keys)
pnpm dev --open
```

Drop a JPEG or PNG. ~10s later the same page renders graph + Penman source + conformance.

## Stack

- SvelteKit 2 · Svelte 5 (runes) · Tailwind 4 · adapter-node
- d3-force + raw SVG (no graph library)
- Custom primitives, no shadcn / bits-ui
- Native fetch to OpenRouter (no SDK)
- Server shells out to `cli/target/release/vson` for transpile + SHACL validate

## Architecture

```
browser                                      server (+server.ts)
  pick image                                    /api/extract (POST)
    ↓                                             body: {image_b64, mime}
  POST /api/extract  ─────────────────────────►   ↓
                                                  OpenRouter chat completions
                                                  (Anthropic Claude Opus by default;
                                                   OPENROUTER_MODEL overrides)
                                                  ↓
                                                  spawn vson convert p2t / validate
                                                  ↓
                                                  build VsonEnvelope per
  ◄────────────────────── envelope JSON           tools/schema/vson-output.schema.json
  render in $state — no client storage
```

Refresh = clean slate. Persistent share links land in Phase 1.5.

## Wire format

`POST /api/extract` body:

```json
{
  "image_b64": "<raw base64, no data:URL prefix>",
  "mime": "image/jpeg",
  "source_uri": "optional"
}
```

Response: see [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) — the canonical contract, mirrored at [src/lib/types.ts](src/lib/types.ts).

## Env

- `OPENROUTER_API_KEY` — **required**.
- `OPENROUTER_MODEL` — default `anthropic/claude-opus-4.6`. Any vision-capable model on OpenRouter works.
- `VSON_BIN` — default `../cli/target/release/vson`. Override if installed elsewhere.
- `PUBLIC_BASE_URL` — used as `HTTP-Referer` on OpenRouter calls.

## Demo strip

`static/demos/manifest.json` controls the curated thumbnails below the dropzone. Drop a jpeg/png in `static/demos/` and add an entry. Empty manifest hides the strip.

## Verify

```bash
pnpm check     # svelte-check (0 errors)
pnpm build     # production build
pnpm preview   # serve build
```

## Deploy

`@sveltejs/adapter-node` produces `build/` you can run with `node build`. Works on any VPS, Fly.io, Railway, Render. The Rust `vson` binary must be present at `VSON_BIN`, and `pyshacl` + `rdflib` must be on `PATH`.
