# vson web — drop image, graph out

SvelteKit studio over the VSON toolchain. Stateless: no DB, no auth, no sessions. Three pages — `/` (studio), `/about`, `/prompts` — and five endpoints: `/api/extract`, `/api/correct`, `/api/models`, `/api/export`, `/api/skills`.

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

Drop a JPEG or PNG. ~10s later the same page renders graph + notation source + conformance. Fix what the model got wrong and re-run the correction through the same validator.

## Stack

- SvelteKit 2 · Svelte 5 (runes) · Tailwind 4 · adapter-node
- `@xyflow/svelte` canvas for the relationship graph; the bounding-box overlay on the source image is percentage-positioned DOM, and the only SVG is inline icons
- Custom primitives, no shadcn / bits-ui
- Native fetch to OpenRouter (no SDK)
- Server shells out to `cli/target/release/vson` for transpile + SHACL validate

## Architecture

```
browser                                 server
──────────────────────────────────────────────────────────────────────────────
ModelPicker    ──GET  /api/models───►   OpenRouter model list, cached 10 min,
               ◄──── picker rows ────    vision-input rows only

DemoStrip      ──GET  /demos/*.json─►   baked envelope on disk — no model call,
               ◄──── envelope JSON ──    renders with no API key set. A POST
                                         carrying the same sha256 hits the same
                                         cache server-side, so curl can't
                                         bypass it either.

Dropzone       ──POST /api/extract──►   per-IP rate limit  (hooks.server.ts)
 {image_b64, mime,                       → model id checked against the catalog
  model, prompt}                         → OpenRouter chat completions
                                           prompt: skill | skill-x | full
                                         → vson convert p2t   (x2t in X mode)
                                         → vson validate      (SHACL)
                                         → violations? repair prompt, ≤2 retries
               ◄──── envelope JSON ──    shaped by
                                         tools/schema/vson-output.schema.json

EntityCard     ──POST /api/correct──►   per-IP rate limit, then the same
 staged edits   {notation, source,       transpile → validate → repair loop —
                 corrections[], model}   but the prompt is "apply these fixes to
               ◄──── envelope JSON ──    this document", not "re-extract"

ExportRow      ──POST /api/export───►   caption + FOL render through the vson
               ◄──── text ───────────    binary; cypher / graphml / dot /
                                         mermaid are pure JS

NotationToggle ──GET  /api/skills───►   skill manifest + versions, and whether
ExportRow      ◄──── manifest ───────    the X skill shipped on this server
                                         (/prompts renders the same manifest
                                          from a +page.server.ts load, no fetch)

ScenePanel                              view modes — client-side only, no fetch:
                                          Inspect  image + entity list (default)
                                          Graph    xyflow canvas + spatial facts
                                          Source   VSON-P/X · Turtle · conformance
```

The envelope lives in `$state` and dies on refresh — nothing is persisted server-side, so there are no share links. `localStorage` holds four preferences only: model, notation, layout mode, theme.

VSON-X is the line-oriented notation (`prompt: "skill-x"`, `notation: "x"`). It is served only when the X skill file is present; otherwise those requests get a 503 and `/api/skills` reports it unavailable.

## Wire format

`POST /api/extract` body:

```json
{
  "image_b64": "<raw base64, no data:URL prefix>",
  "mime": "image/jpeg",
  "source_uri": "optional",
  "model": "optional openrouter id, e.g. anthropic/claude-sonnet-4.6",
  "prompt": "skill | skill-x | full",
  "sha256": "optional — demo-cache lookup key"
}
```

`POST /api/correct` body: `{ notation: "p" | "x", source, corrections[], sceneNote?, model?, image_b64?, mime? }`.

Response for both: see [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) — the canonical contract, mirrored at [src/lib/types.ts](src/lib/types.ts).

Limits, all rejected with a 400 and a one-line message: `image_b64` ≤ 8M chars (≤ 5 MB decoded), `source` ≤ 64 KB, ≤ 50 corrections of ≤ 2 KB each, exported `vson_p` / `vson_x` ≤ 64 KB. Unknown model ids are rejected against the cached OpenRouter catalog; if that list is briefly unreachable the check degrades to a shape check so a provider blip doesn't lock users out.

## Env

Read at runtime via `$env/dynamic/private`.

- `OPENROUTER_API_KEY` — **required to serve visitors who bring no key of their own.** A request that carries neither this nor an `x-openrouter-key` header (see [Bring your own key](#bring-your-own-key)) fails with `no API key: set OPENROUTER_API_KEY or supply your own` (500). Cached demos are served before any key is read, so those work with neither.
- `OPENROUTER_MODEL` — default `google/gemini-2.5-flash`. Used when a request names no model.
- `OPENROUTER_ALLOWED_MODELS` — optional comma-separated id allowlist. Unset means any vision model OpenRouter serves. When set it narrows both the picker and what `/api/extract` and `/api/correct` accept.
- `RATE_LIMIT_MAX` — POSTs to `/api/extract` + `/api/correct` per IP per window. Default `10`; `0` disables the limiter.
- `RATE_LIMIT_WINDOW_S` — window length in seconds. Default `600`.
- `VSON_BIN` — default `../cli/target/release/vson`. Override if installed elsewhere.
- `PUBLIC_BASE_URL` — used as `HTTP-Referer` on OpenRouter calls.
- `BODY_SIZE_LIMIT` — **`8M` is required for a `node build` deploy.** `@sveltejs/adapter-node` defaults to `512K`, which 413s any upload over ~380 KB before the route runs. `vite dev` ignores it, so this only bites in production.

## Bring your own key

The model picker's panel has an optional key field. A visitor-supplied
OpenRouter key is held **in browser memory only** (`src/lib/byok.svelte.ts` —
no localStorage, no cookie; a refresh forgets it) and rides each
`/api/extract` / `/api/correct` request as an `x-openrouter-key` header. The
server uses it for that request's upstream calls instead of
`OPENROUTER_API_KEY`, then drops it — it is never stored, logged, or echoed
back. The key does transit the server per request (TLS), so visitors who do
not want to trust the operator should not use the field; either way, use a
key with a spend limit (openrouter.ai → Keys → credit limit). Rate limiting
and the model allowlist apply to BYOK requests unchanged.

## Response headers

The studio renders model output as markup, so the policy worth having is the one
that stops injected markup becoming injected script.

**CSP** is declared in [`svelte.config.js`](svelte.config.js) because SvelteKit
builds the header itself, splicing in a per-response nonce:

```
default-src 'self'; worker-src 'self'; connect-src 'self'; img-src 'self' data:;
object-src 'none'; script-src 'self' 'nonce-…'; style-src 'self' 'unsafe-inline';
style-src-attr 'unsafe-inline'; base-uri 'self'; form-action 'self';
frame-ancestors 'none'
```

Nonce mode, not hash mode: the FOUC guard in [`src/app.html`](src/app.html) is
hand-written, and a hash would drift silently the first time someone edited it.
The guard carries `nonce="%sveltekit.nonce%"`, which doubles as a tripwire —
SvelteKit throws at build time if a page is ever marked prerenderable, because a
nonce cannot be baked into a static file.

Two relaxations, both deliberate:

- `style-src 'unsafe-inline'` — Svelte emits component styles as inline
  `<style>` elements. Repeated as `style-src-attr` because `style-src` does not
  cover `style=""` attributes, which is how the bbox overlay positions itself.
- `img-src data:` — the dropzone previews through `FileReader.readAsDataURL` and
  the entity crops re-use that data URL. `blob:` is **not** listed: `download()`
  navigates an `<a download>` to a blob URL, which no fetch directive governs.

**Constant headers**, from [`src/lib/server/security-headers.ts`](src/lib/server/security-headers.ts),
applied in [`src/hooks.server.ts`](src/hooks.server.ts) to both exits — the
normal response and the 429 early return: `x-content-type-options: nosniff`,
`referrer-policy: strict-origin-when-cross-origin`, `x-frame-options: DENY`,
`permissions-policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()`,
`cross-origin-opener-policy: same-origin`, `cross-origin-resource-policy: same-origin`.

`strict-transport-security` is added only when the request arrived over
`https:`, so a dev server cannot pin `localhost` to HTTPS in your browser for a
year. Behind a TLS-terminating proxy you need `ORIGIN=https://…` (or
`PROTOCOL_HEADER=x-forwarded-proto`) for that check to see the real scheme.

### The gap

`@sveltejs/adapter-node` serves `static/` and `_app/immutable/` through sirv,
**before** hooks run. Fonts, demo images and hashed bundles therefore come back
with a `Content-Type` and nothing else — no nosniff, no CORP. Only responses the
SvelteKit handler produces get the constant headers. If that matters for a given
deployment, add them at the reverse proxy, which sees every response.

CSP is unaffected: it governs documents, and every document is rendered by the
handler. Two related facts, so nobody hunts for a bug: JSON API responses carry
the constant headers but no CSP (SvelteKit attaches CSP to page renders only, and
a JSON body is not a document), and the policy ships as a response header with no
`<meta http-equiv>` twin, because SvelteKit only emits the meta tag when
prerendering and nothing here is prerendered.

[`tests/security-headers.test.ts`](tests/security-headers.test.ts) pins the
directive set, the nonce wiring, and the exact header key set. It cannot prove a
browser accepts the policy — check the console against a real `node build` for
that.

## Demo strip

`static/demos/manifest.json` controls the curated thumbnails below the dropzone. Drop a jpeg/png in `static/demos/` and add an entry. Empty manifest hides the strip. An entry with an `envelope_path` renders from the baked JSON instead of calling a model — `scripts/bake-demos.ts` produces those, `scripts/reindex-demos.ts` rebuilds the sha256 index the server-side cache reads.

## Verify

```bash
pnpm check     # svelte-check (0 errors)
pnpm lint      # prettier --check + eslint
pnpm test      # vitest, one run
pnpm build     # production build
pnpm preview   # serve build
```

## Deploy

`@sveltejs/adapter-node` produces `build/` you can run with `node build`. Works on any VPS, Fly.io, Railway, Render. Alongside it:

- **`BODY_SIZE_LIMIT=8M`.** The adapter's `512K` default rejects most photos with a 413 before SvelteKit routes the request, and the error looks like an app bug, not a config one. 8M is the pair for the 8M-char `image_b64` cap.
- The Rust `vson` binary present at `VSON_BIN`, plus `pyshacl` + `rdflib` on `PATH`.
- Behind a reverse proxy, set `ADDRESS_HEADER=x-forwarded-for` (and `XFF_DEPTH`). Otherwise every request appears to come from the proxy and the whole internet shares one rate-limit bucket.
- Rate-limit state is in-memory and per process: N replicas allow N× the configured budget. Single box, or move to a shared store first.
