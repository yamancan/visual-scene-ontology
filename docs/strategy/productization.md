# VSON — Productization Strategy

**Status:** Draft 1 · 2026-05-02
**Note (v1.2):** the `vson.dev` hostnames below were aspirational and never registered; the published namespace is `https://w3id.org/vson/` — see [`docs/vson.md`](../vson.md) §5.1.
**Readers:** founding team, design lead, eng lead, first 10 users
**Sibling docs:** `docs/strategy/brand.md`, `docs/strategy/roadmap.md` (forthcoming)

---

## 0. The premise

VSON v1.0 has shipped as an ontology + vocabulary + two concrete syntaxes + SHACL + a working transpiler. That is *infrastructure*, not a product. To productize we must answer:

1. **Whose hour are we saving, and how much of it?**
2. **What do they touch, and where does the magic happen in the first 60 seconds?**
3. **Why does the second-best alternative stay second-best?**

VSON's pitch in one sentence: **"Author, validate, and render scene-graph descriptions that flow lossless into AMR, Visual Genome, USD, and layout-to-image pipelines — without writing RDF by hand."** That is the job.

---

## 1. Personas (concrete; sized roughly by likely TAM)

| # | Persona | What they do today | What hurts | Where VSON inserts |
|---|---|---|---|---|
| **P1** | **Generation-pipeline engineer** at an image/video AI co (largest TAM in 2026) | Wires LLM → JSON-prompt → diffusion / Sora-class model. Tweaks prompt schemas weekly. | Schema drift; no validation; bbox + style + camera are bolted on; LLM hallucinates malformed JSON. | The IR between LLM and renderer; SHACL-validated; constrained-decoded. |
| **P2** | **Scene-data annotator / ML researcher** working with Visual Genome / Action Genome / GQA-style datasets | Hand-labels objects, attributes, relationships in spreadsheet-shaped tooling | Schema is implicit; IAA is bad; bbox + relation are decoupled tools | A unified canvas with bbox ⇄ source binding; IAA dashboard. |
| **P3** | **Director / creative technologist** at a studio (small TAM, high LTV) | Writes prose briefs that downstream artists/AI translate into shot lists | Translation layer is lossy; no machine-readable artifact between brief and shot | Prompt-driven scene authoring with a visual preview that round-trips with USD. |
| **P4** | **3D / animation pipeline TD** | Maintains USD stages; Camera & Style metadata scattered | No upstream notation that flows *into* USD cleanly | A USD-aligned authoring layer + diff/merge surface. |
| **P5** | **Game / interactive narrative designer** | Beat-level scene breakdowns in Notion/Articy | No structure; AI tools can't consume the breakdowns | Penman as the structured brief format; queryable. |

**Order of focus for v1: P1 → P2 → P3.** P1 is the wedge — the AI generation market is in a schema-shopping phase right now, late 2026, and a credible IR with validation wins the platform fight.

---

## 2. Product surfaces (what the user actually touches)

### 2.1 `vson` CLI — the foundation

A single statically-linked binary (Rust). No Python, no JVM. The unix-y interface engineers reach for first.

> **Target surface, not shipped state.** Today the binary ships `validate`,
> `convert p2t/x2t`, and `export cypher/caption/fol` (with `convert x2t` and
> the caption/FOL exporters shelling out to Python). `t2p` is a stub, and
> `init`, `query`, `render`, `generate`, `diff`, `lint`, and `serve` are
> planned, not yet implemented.

```
vson init <project>        scaffold .vson workspace + GH action + VS Code recs
vson validate <files...>   SHACL conformance; exit 1 on failure (CI-friendly)
vson convert p2t|t2p       Penman ↔ Turtle-star
vson export <fmt> <file>   cypher | amr | vg | usd | jsonld
vson query <file> "<sparql>"   SPARQL-star against the document
vson render <file> --kind bbox|3d|image  generate visual preview
vson generate "<prompt>" --model claude-opus-4-7  grammar-constrained LLM gen
vson diff a b              semantic diff (graph isomorphism modulo blank nodes)
vson lint                  opinionated style + smell checks beyond SHACL
vson serve --port 7878     local LSP + validator API for editor integrations
```

**Why it ships first:** P1 engineers will not accept a tool that requires a SaaS account. The CLI is the credibility test.

### 2.2 `vson-tools` VS Code extension

- Penman (`.vson`) syntax highlighting + folding.
- SHACL diagnostics in real time (squiggles), powered by `vson serve`.
- Hover docs on every VSO concept and SHACL shape; Cmd-click to definition.
- Code actions: "Add :patient", "Reify event", "Lift attribute to Quality".
- Tree view: Outline of Composition → Frame / depicts hierarchy.
- Side-by-side preview pane (bbox-only initially).
- Snippets: `event`, `quality`, `spatialfact`, `frame-stack`, `belief-state`.

### 2.3 **VSON Studio** — `studio.vson.dev` (the killer surface)

The web workspace. Where the design bar gets set. Detailed below in §3 and §4.

### 2.4 Hosted services

| Service | Purpose |
|---|---|
| `api.vson.dev/v1/validate` | POST a doc, get SHACL report. Free tier (100/day), pay-as-you-go above. |
| `api.vson.dev/v1/generate` | LLM with Lark-grammar-constrained decoding. Returns a guaranteed-parseable Penman doc. |
| `api.vson.dev/v1/render` | Bbox PNG / 3D USD / layout-to-image (GLIGEN-class). |
| `api.vson.dev/v1/convert` | Format conversion as a service. |
| `vson.dev` (resolves IRIs) | `https://vson.dev/v1/ontology#` content-negotiates Turtle / JSON-LD / HTML. |

### 2.5 Integrations

- **GitHub Action** — `vson-action@v1` runs `vson validate` on `.vson`/`.ttl` files in PRs.
- **Slack bot** — paste a VSON share link, get an inline rendered preview.
- **Figma plugin (one-way)** — Camera/Composition/Style metadata + rectangle bboxes export to a starter VSON.
- **Notion / Linear unfurl** — share links unfurl with the bbox preview.

---

## 3. VSON Studio — design principles

The studio is where the hour is saved. Six principles, stolen liberally from the NYC product-design canon (Linear · Figma · Arc · Vercel · Notion · Stripe).

### Principle 1 — Three-pane workspace, never a dashboard

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  ⌘   throne_room.vson · main · ✓ Validates · 151 triples              ⊕  ⋯     │  ← top bar (40px, single accent, no chrome)
├──────────────┬─────────────────────────────────────────┬─────────────────────────┤
│              │                                         │                         │
│  OUTLINE     │  SOURCE  ·  Penman ▾                    │  PREVIEW  ·  bbox ▾    │
│              │                                         │                         │
│  scene       │  (scene / Composition                   │   ┌────────────────┐    │
│  ├─ ctx      │     :framedBy (ctx / SceneContext       │   │                │    │
│  ├─ cam      │       :venue throne_room                │   │   👑           │    │
│  ├─ style    │       :atmosphere tense)                │   │   alice        │    │
│  ├─ alice    │     :framedBy (cam / CameraView         │   │      bob       │    │
│  ├─ bob      │       :angle low :focalLength 35mm)     │   │       ⚔️         │    │
│  ├─ boar     │     :depicts (alice / Person ...)       │   │                │    │
│  ├─ strike   │     :depicts (strike / Event            │   │       🐗→        │    │
│  └─ charge   │       :agent bob :patient boar          │   └────────────────┘    │
│              │       :instrument sword))               │                         │
│  4/4 shapes  │                                         │   bbox · 3D · image    │
│              │  Turtle ▸  JSON-LD ▸  Cypher ▸  AMR ▸    │   Render ▸              │
│              │                                         │                         │
├──────────────┴─────────────────────────────────────────┴─────────────────────────┤
│  ⚠ 0 issues  ·  151 triples  ·  18 inferred  ·  ⌘K palette                       │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Outline (left, 240px, collapsible):** structural tree. Each node carries an inline conformance dot (green/amber/red). Clicking jumps the source pane to the declaration.

**Source (center, fluid, source-of-truth):** Penman by default. Tabs at the bottom render Turtle, JSON-LD, Cypher, AMR — read-only views, regenerated live.

**Preview (right, fluid, fidelity-stepped):** bbox at instant render; 3D via USD bridge at ~1s; image via layout-to-image at ~4s.

The three are *bidirectional*: clicking Alice in the preview selects `:alice` in the source and the outline. Dragging Alice's bbox edits her geometry triple. This is the Figma move — single source of truth, multiple manipulable surfaces.

### Principle 2 — Command palette is primary navigation

⌘K opens the palette. Everything reachable from the menu is reachable from the palette. Examples:

- "Add Event between alice and bob"
- "Validate"
- "Export Cypher"
- "Insert RCC EC between crown and alice"
- "Compare with gold"
- "Run inference"
- "Switch to Turtle view"
- "Render image"

This is Linear's principle: the menu is for discovery; the palette is for fluency. Keyboard-first users never mouse.

### Principle 3 — Inline > modal

There are no modal dialogs. SHACL violations open the inspector tab, not a popup. Confirmations happen in the status bar with an undo grace window (Linear-style toast: *"Deleted alice. Undo (⌘Z)"*). Errors don't pop; they breathe.

### Principle 4 — Inspector replaces remembering vocabulary

A collapsible right rail (240px, hidden by default; ⌘. to toggle). When a node is selected, the inspector shows:

- **Declared:** the explicit triples on this node.
- **Inferred:** classes/properties derived by the OWL reasoner (e.g., `Endurant`, `facing(b, a)` from symmetry).
- **Conformance:** every SHACL shape this node is in scope of, with pass/fail.
- **Annotations:** RDF-star edge-annotations attached to triples sourced/sinked here.
- **Edit traits:** dropdowns/checkboxes for the trait bundle. Authors don't memorize `vso:individuation vso:Named` — they tick a box.

### Principle 5 — Generate is a citizen, not a button

A persistent prompt input docked to the source pane footer. Cursor-style:

> ⌘L `Add a tense atmosphere and three more retainers.`

The LLM (Anthropic Claude or open-weights Qwen-class) emits a constrained Penman *patch*. The patch shows as a diff overlay in the source pane — green inserts, red deletes — which the author accepts (⌘↵), rejects (⎋), or partially accepts (per-hunk ⌘.). SHACL re-validates after acceptance.

Constraint mechanism: Lark grammar for VSON-P + post-validate via SHACL. Failures auto-retry up to 3 times before surfacing.

### Principle 6 — Onboarding through artifacts, not videos

First-load: a real scene (`throne_room.vson`) with a 30-second guided tour using subtle highlight rings and three text bubbles:

1. *"This is the Source. Edit on the left, see structure on the right."* (rings on outline + preview)
2. *"This dot means SHACL conformance. Click to inspect."* (rings on a green dot)
3. *"Press ⌘K to do anything."* (palette opens; closes after 2s)

After dismiss, the user is editing the throne room. No video. No checklist. No "next" button. The user produces a meaningful artifact in their first 60 seconds.

---

## 4. Three canonical UI flows

### Flow A — P1 Engineer: integrate VSON into a generation pipeline

**Goal:** drop VSON between an LLM and a layout-to-image renderer in one afternoon.

*Target experience — several steps below (`brew install`, `vson init`, `validate -`, `vson generate`, `vson render`) depend on subcommands that are planned, not yet shipped; see §2.1.*

```
00:00  brew install vson         (or `cargo install vson-cli`)
00:30  vson init scenes
        → ./scenes/.vson/config.toml, .github/workflows/vson.yml,
          .vscode/extensions.json (recommends vson-tools)
01:00  Authors sample.vson in VS Code; live SHACL diagnostics work.
02:00  Pipes their LLM output through `vson validate -` → catches malformed runs.
03:00  Uses `vson generate --model claude-opus-4-7 "prompt"` → grammar-constrained
       Penman doc with ≥99% SHACL pass rate.
04:00  Renders via `vson render scene.ttl --kind image -o out.png`.
05:00  Pushes to GitHub. The action runs vson validate on the PR.

90 min total to a CI-validated, LLM-authored, image-rendering pipeline.
```

The wedge: *the LLM cannot emit invalid VSON*. That solves a P1-pain point that no current tooling solves cleanly.

### Flow B — P3 Director: prompt to image without code

**Goal:** Director with no engineering background generates a scene preview in 60 seconds.

```
T+00s   Lands on studio.vson.dev. No login. Sees a single prompt input
        centered like Linear's onboarding: "Describe a scene…"

T+05s   Types: "Knight Bob standing in front of a tense throne room at dusk,
                low-angle shot, oil painting style, with a charging boar."

T+06s   Hits ↵. Underline animates left-to-right under the prompt (no spinner).

T+09s   Studio's grammar-constrained LLM emits a Penman doc. Source pane fills
        with a 600ms typewriter animation. Preview pane simultaneously
        populates with bboxes as nodes resolve. Status bar: ✓ Validates.

T+12s   Director clicks "Render → image". Right pane swaps from bbox to a
        loading state (a faint scanning gradient). 4s later: photorealistic
        image fills.

T+18s   Director drags Alice's bbox to the left in the preview. Source pane
        updates the geometry triple. Image re-renders.

T+30s   ⌘S → share link copied. Pastes into Slack.
```

The "wow" sequence — prompt → preview → image → drag-edit → re-render — is what makes the demo viral.

### Flow C — P2 Annotator: label Visual Genome with IAA tracking

**Goal:** Five annotators label 200 images; the team sees pairwise agreement rise as the schema settles.

```
1. Annotator opens studio.vson.dev/annotate?dataset=vg.
2. Right pane: source image (loaded from VG). Center: empty Penman.
   Left: empty outline.
3. Annotator draws bboxes directly on the image. Each new box opens a tiny
   inline form (class + trait bundle). VSV class autocomplete, with
   reasoner-suggested affordance/animacy from the class.
4. Studio infers candidate Events, Statives, SpatialFacts from spatial
   adjacency + class signatures. Annotator accepts (⌘↵) or rejects (⎋)
   each suggestion.
5. ⌘N moves to the next image; previous one auto-saves.
6. /team/iaa dashboard shows pairwise Smatch F1 across annotators, refreshed
   every 50 images. Disagreement heatmap surfaces shape-level confusions.
7. Schema lead reviews the heatmap; tightens VSV vocabulary; agreement
   trends up.
```

### Flow detail: SHACL violation surfaces

A NYC designer would not bury validation. When a shape fails:

1. The squiggle in the source pane is a 1px wavy underline in amber-500 (warning) or red-500 (error). Hovering shows the shape's `sh:message` in a 240px tooltip with the offending value highlighted.
2. The status bar count updates: "⚠ 1 issue · ✓ 3 of 4 shapes pass".
3. ⌘. on the offending node opens the inspector's "Conformance" tab pre-filtered to the failing shape, with three suggested fixes:
   - *"Add :viewer ?cam"* (one click)
   - *"Remove :directional"* (one click)
   - *"Convert to :proximal"* (one click)

No modal. No sidebar redirect. No documentation hunt.

---

## 5. Design system

Drawing the brand and component vocabulary so design isn't relitigated per screen.

### 5.1 Type

- **UI:** Inter (variable; weights 400/500/600). Fallback: system-ui.
- **Source / mono:** JetBrains Mono Variable; weight 400/600.
- **Two sizes** in the workspace: 14px body, 12.5px secondary. Headings via weight + opacity, not size.

### 5.2 Color (soft dark, single accent)

| Token | Hex (dark) | Hex (light) | Use |
|---|---|---|---|
| `--bg` | `#0B0C0E` | `#FAFAF9` | canvas |
| `--surface` | `#15171A` | `#FFFFFF` | panes |
| `--border` | `#23262B` | `#E7E5E4` | hairlines |
| `--text` | `#F4F4F2` | `#0A0A0B` | primary text |
| `--text-2` | `#9CA0A7` | `#57534E` | secondary text |
| `--accent` | `#D97706` | `#B45309` | brand (warm amber — "scene") |
| `--success` | `#65A30D` | `#3F6212` | conformance pass |
| `--warning` | `#D97706` | `#B45309` | shape warnings |
| `--error` | `#DC2626` | `#991B1B` | shape failures |

One accent. No gradients in product chrome (only in render previews).

### 5.3 Motion

- 200ms cubic-out for pane / panel transitions.
- 100ms for hover transitions.
- No bouncy easing. No skeuomorphic shadows.
- Status bar pulses 1 cycle on conformance change.
- Preview re-render: 600ms cross-fade from old to new render.

### 5.4 Density

Linear-grade. 4px grid; 8/12/16/24/32 spacing. 32px header bars. 240px sidebars. No gratuitous whitespace; no cramped affordance.

### 5.5 Logo / mark

A single slanted diagonal with three stacked dots ascending — evoking the camera frame's vanishing point overlaid on RDF nodes. Stroke 1.5px. Fits in 16/24/32/48 sizes. Wordmark: "vson" lowercase Inter 600.

### 5.6 Voice

Terse. Technical. Calm. Never cute, never "AI-magical." Examples:

- ✗ "✨ Your scene looks great! Click here to keep going!"
- ✓ "Validates. 151 triples."

- ✗ "Oops! Something went wrong 😬"
- ✓ "Shape `EventShape` failed on `:strike`. Missing `vso:lemma`. (⌘. to inspect.)"

---

## 6. Roadmap (phased)

### Phase 0 — Stabilize (now → 4 weeks)

Goal: production-credible foundation.

- Rust `vson` CLI (replaces Python tool) with `validate / convert / export / query / render --kind bbox / lint`.
- Real Penman parser via Lark/PEG (or hand-rolled in Rust with `lalrpop`); replaces the reference Python transpiler.
- Public IRIs at `https://vson.dev/v1/...` with content negotiation.
- DOI / Zenodo archive of v1.0 ontology.
- `vson-tools` VS Code extension v0.1: highlighting + SHACL diagnostics via local `vson serve`.
- mdBook docs site at `vson.dev/docs` (per the format proposal).

**Exit criterion:** an external engineer installs the CLI, validates a scene, and exports Cypher in under 5 minutes from cold start.

### Phase 1 — Studio MVP (weeks 4–12)

Goal: the three-pane workspace that earns the "wow" demo.

- Web app at `studio.vson.dev`. Next.js + tRPC + Postgres + S3.
- Three-pane workspace (Outline / Source / Preview-bbox).
- Live SHACL diagnostics in source pane.
- Generate-from-prompt with constrained decoding (Anthropic + Qwen).
- Inspector for trait-bundle editing.
- Anonymous editing; share links generate ephemeral URLs.
- Render API: bbox PNG only. No 3D, no image-gen yet.
- Marketing site at `vson.dev` with three flows above as recorded demos.

**Exit criterion:** P1 engineer signs in, authors and validates a scene, in under 5 minutes.

### Phase 2 — Pipeline integrations (months 3–6)

Goal: be the IR between LLM and renderer.

- USD bridge: `vso:CameraView` → `UsdGeomCamera`; depicts → Stage prims. Bidirectional.
- AMR import/export with Smatch ≥ 0.95 round-trip.
- Visual Genome ingest: bbox-preserving conversion.
- Layout-to-image: hosted GLIGEN/ControlNet endpoint at `api.vson.dev/v1/render`.
- 3D preview pane (Three.js + USD-WebGL).
- GitHub Action `vson-action@v1`.
- Figma plugin (one-way Figma → VSON).

**Exit criterion:** at least three external generation pipelines have VSON in production.

### Phase 3 — Collaboration & teams (months 6–12)

Goal: workspace becomes multi-player.

- Versioned workspaces (Figma-style branches; CRDT on the abstract graph).
- Multi-cursor presence in source pane.
- Comment threads anchored to nodes.
- Org/team plans with SSO.
- IAA dashboard for annotation teams (Flow C).
- Public share-link unfurl in Slack/Notion/Linear.

**Exit criterion:** $50k MRR or 10 paying teams.

### Phase 4 — Ecosystem (months 12–18)

Goal: VSON conformance as a market signal.

- Vendor-neutral conformance suite — the **VSON Conformance Mark**.
- Annual conformance certification for downstream systems (USD pipelines, layout-to-image vendors, scene-graph datasets).
- Public schema-extension registry.
- Public corpus of validated scenes.
- LSP for non-VSCode editors.
- Standards-track submission to W3C as a community vocabulary.

**Exit criterion:** at least one major vendor (USD pipeline operator OR diffusion-model platform) ships VSON Conformance branding.

---

## 7. Pricing & business model

| Tier | Price | What you get |
|---|---|---|
| **Free** | $0 | CLI, all open-source artifacts, public studio editing, share links, 100 API validations / day. |
| **Studio Pro** | $20 / mo | Private workspaces, version history (90 days), unlimited validation API, render credits ($10 included), priority support. |
| **Team** | $100 / seat / mo | Multi-cursor, SSO, audit logs, IAA dashboard, unlimited version history, role permissions. |
| **Enterprise** | custom | On-prem validator, on-prem render, conformance certification, SLA, training. |
| **Open-source forever** | $0 | Ontology, vocabulary, SHACL shapes, spec, CLI, parsers — perpetual Apache-2.0. |

**Why this works:** the open core (ontology, CLI, parsers) is non-negotiable for credibility — engineers will not adopt a paywalled IR. The studio is where willingness-to-pay lives, because it saves real director / annotator hours. Render credits cover GPU costs at margin.

**No ads. No data sale. No telemetry beyond aggregate validation counts.**

---

## 8. Risks & mitigations

| # | Risk | Probability | Severity | Mitigation |
|---|---|---|---|---|
| R1 | Visual Genome triplet format wins by inertia. | Medium | High | Bidirectional VG import/export from day 0; meet users where they are. |
| R2 | USD becomes the de-facto layout-to-image standard. | Medium | Medium | Position VSON as the *authoring* surface for USD; ship USD bridge in Phase 2. |
| R3 | Studio reads as too engineer-flavored for P3. | High | Medium | Dual-mode UI: "Source" mode (P1/P2) vs "Direct" mode (P3, prompt + visual only, source pane hidden). |
| R4 | LLM-generated VSON is bad. | Medium | High | Constrained decoding via Lark grammar + SHACL post-validation + auto-retry. Publish failure rate as a public metric. |
| R5 | SHACL is too opaque for non-technical authors. | High | Medium | Every shape ships with a `sh:message` in plain English; the studio renders these as suggested-fix actions, not error codes. |
| R6 | Notation systems have low adoption velocity historically. | Medium | High | Don't sell "the notation"; sell "the IR that makes your LLM emit valid scene graphs". The notation is plumbing. |
| R7 | OWL/SHACL community sees VSON as competitive. | Low | Low | Position as an applied profile of W3C standards, not a replacement. Engage W3C Community Group early. |

---

## 9. Success metrics (what we measure each week)

| Metric | Target by end of Phase | Why |
|---|---|---|
| **Time-to-first-validated-scene** | < 5 min for new user | The activation event. |
| **`vson validate` calls / week** | > 10k by end of Phase 2 | Stickiness signal — IR is in pipelines. |
| **LLM-generated docs that pass SHACL on first try** | > 95% by end of Phase 1 | The "the LLM cannot emit invalid VSON" promise. |
| **Studio DAU / WAU** | > 0.4 by end of Phase 1 | Workspace usage, not one-off authoring. |
| **Round-trip Smatch vs AMR** | > 0.95 by end of Phase 2 | Lossless mapping promise. |
| **External pipelines using VSON** | ≥ 3 by end of Phase 2 | P1 wedge proof. |
| **Paying teams** | ≥ 10 by end of Phase 3 | Business proof. |
| **VSON-conformant vendor** | ≥ 1 by end of Phase 4 | Ecosystem proof. |

---

## 10. The 60-second elevator demo

Three beats:

**Beat 1 (0:00–0:15) — the prompt wedge.** The presenter says: "Watch what happens when an LLM tries to emit a scene description." Shows a competing JSON-prompt failing parse. Then: "Now watch this." Types a prompt into VSON Studio. Penman fills, bboxes pop. *"Validates. 151 triples."*

**Beat 2 (0:15–0:35) — the bidirectional surface.** Drags Alice's bbox. Source updates. Hits Render. Image appears. Drags again. New image. *"This is the same graph. The image, the bbox, the Penman, the Cypher tab — all four are projections of one truth."*

**Beat 3 (0:35–0:60) — the lossless flow.** Clicks Export → AMR. Pastes into a downstream NLP pipeline. Clicks Export → USD. Drags into a 3D viewer. Clicks Export → Cypher. Runs a SPARQL-star query: *"Find all events involving an Agentive Endurant in front of the camera." 1 result.* "VSON is the IR your pipeline already needed."

That's the deck. Three beats, sixty seconds, no buzzwords.
