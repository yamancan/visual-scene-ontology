# Security Policy

## Supported versions

| Version | Supported                     |
| ------- | ----------------------------- |
| 1.4.x   | Yes — the current line        |
| ≤ 1.3.x | No — upgrade to the 1.4 line  |

One line is supported at a time and there are no backports. This project has
no known deployment other than the maintainer's own, so a fix ships as the next
patch of the current line rather than to a maintenance branch. If you are
pinned to an older version and cannot move, say so in the report and we will
work out what is practical.

## Reporting a vulnerability

Report privately — please do not open a public issue for an unfixed
vulnerability.

- **Email:** yamancandev@gmail.com
- **GitHub:** if private vulnerability reporting is enabled on this repository,
  the "Report a vulnerability" button under the Security tab works too.

Useful things to include: affected component (ontology/SHACL shapes, the Rust
`vson` CLI, the Python tooling, the GitHub Action or pre-commit hook, or the
web studio), version or commit, and the smallest input that reproduces the
issue.

## What to expect

This project is maintained by one person on a best-effort basis. There is no
paid on-call rotation and no guaranteed response SLA. Realistically: an
acknowledgement within about a week, and a fix timeline that depends on
severity and on how much of the stack the issue touches. If a week passes with
no reply, a follow-up email is welcome.

Fixes are released as a new patch of the current line, with the issue described
in `spec/CHANGELOG.md` once a fix is public. Credit is given to the reporter
unless anonymity is requested.

## What actually runs where

Read this before hunting: the shipped architecture has fewer moving parts than
most people expect, and several classic targets simply do not exist here.

- **The studio has no server.** `vson-studio.pages.dev` is a static build
  (`@sveltejs/adapter-static`, three prerendered pages, no API routes) served
  as files from Cloudflare Pages. There is no host process, no database, no
  session, and no operator API key. The v1.2 server relay — `$lib/server`,
  `hooks.server.ts`, the five `/api/*` routes and the `OPENROUTER_API_KEY` that
  fed them — was deleted in v1.3.0. A report premised on leaking a server-side
  key has no target here; there is no key and nothing to run it.
- **The visitor's key is the only key.** An OpenRouter key typed into the model
  picker is held in tab memory (`web/src/lib/byok.svelte.ts`) — no
  localStorage, no sessionStorage, no cookie, no query string — and is used to
  build an `Authorization: Bearer` header on requests the browser makes to
  `https://openrouter.ai` directly. It never reaches the studio's origin. A
  refresh forgets it.
- **The image goes browser → OpenRouter and nowhere else.** Nothing persists
  image bytes, because there is nothing to persist them to. Demos and the
  gallery are baked envelopes fetched as static files: no model call, no key.
- **Verification runs in the browser.** A Pyodide web worker executes this
  repository's own Python — pyshacl (Gate 1), then owlrl (Gate 2) — from
  wheels committed under `web/static/pyodide`. Running it makes no network
  request beyond the studio's own origin.
- **Response headers are generated at build time** by
  `web/scripts/gen-headers.js` and pinned by `web/tests/security-headers.test.ts`:
  `default-src 'self'`, `connect-src 'self' https://openrouter.ai`,
  `worker-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, and
  `script-src 'self' 'wasm-unsafe-eval'` plus one sha256 hash per inline
  SvelteKit bootstrap — alongside HSTS, `nosniff`, COOP/CORP, and a
  `Permissions-Policy` denying camera, microphone, geolocation, payment and USB.

## In scope

- **Anything that could take a visitor's key out of their tab**: script
  injection into a prerendered page, a widened `connect-src` or `script-src`, a
  dependency able to read module state and reach the network, or a build path
  that lets the generated CSP degrade without a test noticing.
- **Untrusted documents parsed by the CLI or the Python tooling** — VSON-P,
  VSON-X, Turtle, JSON envelopes: crashes, unbounded memory or time, path
  traversal, or anything that reads or writes outside the paths it was handed.
- **The composite action and the pre-commit hook**
  (`.github/actions/validate`, `.pre-commit-hooks.yaml`): both run over
  repository content on someone else's machine. An input that reaches a shell
  unquoted, or a path that escapes the workspace, is in scope.
- **A shape that accepts what it should reject.** Validation integrity is the
  product; a document that clears `vson validate` while breaking a normative
  C-rule is worth reporting. Name the rule.
- **The artifacts this repository serves**: the Pyodide wheels under
  `web/static/pyodide`, the pinned lockfiles, and the static documents at
  `vson.pages.dev/v1/` that the canonical `w3id.org/vson` names resolve to.

## Out of scope

- **A model describing an image incorrectly.** A green verdict is a statement
  about the graph, not about the picture (`docs/vson.md` §2.1). Extraction
  quality is a correctness issue — a normal issue is the right place.
- **What OpenRouter does with a request the browser sends it.** That is between
  the visitor, their key, and OpenRouter's terms. Use a key with a spend limit:
  every extraction, repair round and correction is the visitor's own spend.
- **The ontology and shapes as data.** Findings there are usually correctness
  bugs rather than vulnerabilities; a normal issue is fine for those. The one
  exception is the bypass case listed under "In scope" above.
- **Attacks that presuppose control of the machine already**, or that require a
  maintainer to merge hostile code into their own checkout.
