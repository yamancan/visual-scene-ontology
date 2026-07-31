# vson web — drop image, graph out

Static SvelteKit studio over the VSON toolchain — **zero backend**. Three prerendered pages — `/` (studio), `/about`, `/prompts` — and no API routes: extraction, correction, verification, and export all run in the visitor's browser. The deploy artifact is a directory of files on Cloudflare Pages (`vson-studio.pages.dev`, a second Pages project on the same account; `vson.pages.dev` stays purely the namespace host and is untouched by studio deploys).

Stateless as before — no DB, no auth, no sessions — but now also **serverless in the literal sense**: there is no process to operate, rate-limit, or leak into.

## Run

```bash
cd web
pnpm install
pnpm dev --open
```

No `.env`, no API key setup: **no server key exists**. The demo thumbnails and the 16-scene gallery render baked envelopes at $0 with no key at all. To extract your own images, paste your OpenRouter key into the model picker — see [Bring your own key](#bring-your-own-key).

The Rust CLI and Python toolchain are **not** required to run the studio; the browser carries its own copy of the reference Python implementation (below). You only need them for `make` gates and CLI work.

## Stack

- SvelteKit 2 · Svelte 5 (runes) · Tailwind 4 · `@sveltejs/adapter-static` (strict prerender, no fallback — every route is static HTML or the build fails)
- `@xyflow/svelte` canvas for the relationship graph; the bounding-box overlay on the source image is percentage-positioned DOM, and the only SVG is inline icons
- Custom primitives, no shadcn / bits-ui
- Native fetch from the browser straight to OpenRouter (no SDK, no relay)
- A Pyodide web worker runs the reference Python toolchain in the browser: Penman/VSON-X → Turtle transpile, two-gate validation, caption/FOL render

## Architecture

Everything below happens in the visitor's browser. The only network peers are the studio's own origin (static files) and `openrouter.ai` (only when the visitor extracts with their own key).

```
ModelPicker    lazy GET on first open ──► openrouter.ai/api/v1/models
                                          vision-input rows only, cached for
                                          the tab; catalog failure degrades to
                                          the default model, never blocks

DemoStrip      GET /demos/…json  ───────► same-origin baked envelope — no
                                          model call, renders with no key

Dropzone       sha256 (crypto.subtle) of the dropped bytes, checked against
               /demos/envelopes/index.json:
                 demo hit → baked envelope, $0, byte-exact re-upload included
                 miss     → chat completion ──► openrouter.ai (visitor's key)
                            → worker p2t (x2t in X mode)      [Pyodide]
                            → Gate 1 pyshacl + Gate 2 owlrl   [Pyodide]
                            → violations? repair prompt, ≤ 2 rounds

CorrectionBar  same transpile → validate → repair loop, but the prompt is
               "apply these fixes to this document", not "re-extract"

ExportRow      cypher / mermaid / graphml / dot: pure TS, in-page
               caption / FOL: the worker, same renderers as the CLI

ScenePanel     view modes — Inspect · Graph · Source, client-side only
```

The envelope lives in `$state` and dies on refresh — nothing is persisted anywhere, so there are no share links. `localStorage` holds four preferences only: model, notation, layout mode, theme.

VSON-X is the line-oriented notation. Its availability is a compile-time fact of the bundle (`$lib/prompts/meta.ts` checks for the X skill file at build time) — there is no server to report otherwise.

## In-browser verification

The validation worker (`src/lib/validate/`) mounts the repo's reference Python implementation into a Pyodide filesystem: `tools/penman/vson_penman.py` with `cli/src/penman/routing-tables.json` (the same single-source routing tables the Rust CLI compiles in), the VSON-X parser, `shacl_helper` + `owlrl_check`, the caption/FOL renderers, `shapes/vson-shapes.ttl`, and the vso/rcc8/allen ontology trio — exactly the merge set `vson validate` uses. `validate()` runs the same two gates in the same order as the CLI: Gate 1 is pyshacl over the shapes with `inference=rdfs`; Gate 2 is the owlrl OWL 2 RL consistency check, run only when Gate 1 passes.

Parity with the CLI is pinned from both sides in CI:

- `make cli-check` byte-compares Python vs Rust `p2t` output over the full corpus (`examples/throne_room.vson` + all 16 gallery scenes), so the emitter the worker runs is byte-identical to the one the CLI ships;
- `tests/worker-parity.test.ts` boots Pyodide offline in Node from the committed wheels and asserts `p2t(throne_room.vson)` byte-equals `examples/throne_room.ttl`, both gates' verdicts on good and bad fixtures, and byte-equal caption/FOL output against the CI fixtures.

The Python runtime is **fully self-hosted — zero third-party origins**. The core (`pyodide.mjs`, `pyodide.asm.mjs`, `pyodide.asm.wasm`, `python_stdlib.zip`, `pyodide-lock.json`) is copied at build time from the exact-pinned `pyodide` npm package into `/pyodide/` (`vite.config.ts`). The pure-Python wheels — rdflib, pyshacl, owlrl, and their dependencies — are **committed** under `static/pyodide/wheels/` with sha256s in `wheels.lock.json`, enforced by `tests/wheels-lock.test.ts`. Install is `pyodide.loadPackage` with explicit same-origin URLs: no micropip, no resolver, no PyPI, no CDN — every CI run and every visitor installs byte-identical files from git.

Costs, honestly: the layer is strictly demand-loaded — keyless/demo visitors never download a byte of it. The first action that needs verification pulls ≈16 MB of runtime raw — 13.5 MB core (the 9.2 MiB WebAssembly interpreter dominates) plus 2.4 MB of wheels; compression shrinks the transfer — served under `/pyodide/*` with `Cache-Control: immutable`, so it is paid at most once per browser. Warm, Gate 1 lands in ~0.2 s and the UI shows it immediately with a quiet "consistency check running…" line until Gate 2 (~3 s) finalizes the verdict. If the runtime cannot boot on a device (wasm blocked, out of memory), the studio keeps the extracted document, reports validation as unavailable, and points at `vson validate` locally — never a spinner.

## Bring your own key

The model picker's panel has an optional key field. A visitor-supplied OpenRouter key is held **in browser memory only** (`src/lib/byok.svelte.ts` — no localStorage, no cookie; a refresh forgets it) and is used to build the `Authorization` header on requests the **browser makes directly to `openrouter.ai`**. The key — and the image — never touch the studio's host: there is no host process, and the CSP's `connect-src` allows only the studio origin and `openrouter.ai`. This is strictly stronger than the v1.2 relay, where the key transited the operator's server per request. Still: use a key with a spend limit (openrouter.ai → Keys → credit limit) — every extraction, repair round, and correction is your own spend.

Failure taxonomy, shown verbatim in the dropzone: `401` key not accepted · `402` out of credits · `429` provider rate limit · network unreachable.

## Envelope contract

There is no HTTP API anymore, but the envelope contract is unchanged: live extractions assemble the same JSON envelope the v1.2 server did — **wire version `1.2`**, per [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) (mirrored at [src/lib/types.ts](src/lib/types.ts)) — byte-compatible with the baked demo corpus, including `shacl_retries`, token/latency metadata, and the X-mode `vson_p: ""` sentinel. v1.3 changed *where* computation runs, not what an envelope asserts.

The bounds the old server enforced live on in one commented client module, [`src/lib/extract/limits.ts`](src/lib/extract/limits.ts), pinned by unit tests: ≤ 2 repair rounds, correction source ≤ 64 KB, ≤ 50 corrections of ≤ 2 KB each. They now protect the visitor's spend, verdict latency, and `shacl_retries` comparability with the baked corpus rather than an operator's bill.

## Retired environment (v1.2 → v1.3)

Every runtime environment variable is gone with the server that read it:

| Variable | Fate |
| --- | --- |
| `OPENROUTER_API_KEY` | No server key exists. Visitors bring their own; demos/gallery need none. |
| `OPENROUTER_MODEL` | Compile-time `DEFAULT_MODEL` in `src/lib/openrouter/client.ts`. |
| `OPENROUTER_ALLOWED_MODELS` | Defended the operator's paid key; died with it. The structural model-id check survives as advisory only. |
| `PUBLIC_BASE_URL` | Literal build-time `HTTP-Referer` (`https://vson-studio.pages.dev`). |
| `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW_S` | Nothing left to rate-limit — the visitor spends their own key. |
| `VSON_BIN` | No shell-out; the reference Python toolchain runs in the Pyodide worker. |
| `BODY_SIZE_LIMIT` | adapter-node body cap; no body ever reaches a server. |

## Response headers

The CSP and security headers are **generated from the actual build output** by [`scripts/gen-headers.js`](scripts/gen-headers.js), the second step of `pnpm build`. It scans every emitted HTML page, sha256-hashes every inline script (SvelteKit's per-page hydration bootstrap — `app.html` itself contains zero inline scripts since the theme-init script was externalized to `static/theme-init.js`), **fails the build if it finds none** (an empty scan means the scan broke, and shipping its CSP would block hydration site-wide), and writes `build/_headers` with one `Content-Security-Policy` covering **every** response — pages, static assets, and the worker script, which the old adapter-node hook never reached.

The policy: `default-src 'self'`; `script-src 'self' 'wasm-unsafe-eval'` + the computed hashes; `connect-src 'self' https://openrouter.ai`; `worker-src 'self'`; `img-src 'self' data:`; `style-src`/`style-src-attr` `'unsafe-inline'` (Svelte inline component styles; the bbox overlay's `style=""` positioning); `object-src 'none'`; `base-uri 'self'`; `form-action 'self'`; `frame-ancestors 'none'` — spec-effective because it ships as a real header, not a meta tag. Alongside it: nosniff, strict-origin referrer policy, `X-Frame-Options: DENY`, a locked-down `Permissions-Policy`, COOP/CORP `same-origin`, HSTS (Pages is always TLS), and immutable caching on `/pyodide/*`.

Two facts worth stating plainly: a dedicated worker's CSP comes from its own script's response headers, so the `/*` rule is what licenses wasm compilation inside the Pyodide worker; and COEP is deliberately absent — single-threaded Pyodide needs no SharedArrayBuffer. Because hashes are recomputed from build output on every build, drift between the CSP and what SvelteKit emits is impossible by construction. [`tests/security-headers.test.ts`](tests/security-headers.test.ts) pins the generator directly (hashing, directive set, the zero-inline-scripts canary) — CI runs `pnpm test` before `pnpm build`, so the test never reads build output. `pnpm dev` serves no CSP; smoke against the real header stack with `npx wrangler pages dev build`.

## Demo strip

`static/demos/manifest.json` controls the curated thumbnails below the dropzone. Every entry carries an `envelope_path` to a baked envelope with genuine extraction provenance — clicking a thumbnail fetches static JSON, never a model. The sha256 index (`static/demos/envelopes/index.json`) is consumed client-side: re-uploading the exact demo bytes short-circuits to the baked envelope before any key is consulted. The baked corpus is byte-frozen; nothing in the studio can re-extract a demo or spend a visitor's key on a demo click — an entry without an `envelope_path` is skipped with a `console.error`, by design.

## Verify

```bash
pnpm check     # svelte-check (0 errors)
pnpm lint      # prettier --check + eslint
pnpm test      # vitest, one run (includes the offline Pyodide parity suite)
pnpm build     # vite build + gen-headers.js → fully static build/ + _headers
```

## Deploy

`pnpm build` emits a self-contained `build/` — static HTML, hashed assets, `/pyodide/*`, and `_headers`. Deploy is manual, from the repo root:

```bash
make web-deploy   # frozen-lockfile install + build + wrangler pages deploy
                  #   → Cloudflare Pages project "vson-studio"
```

First time on a new account: `npx wrangler pages project create vson-studio`. There is no CI deploy step and no deploy secrets — the same manual discipline as the namespace project. No env vars to set anywhere: the artifact is complete as built.
