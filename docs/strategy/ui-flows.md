# VSON Studio — UI Flows (detailed)

Companion to [`productization.md`](./productization.md). This file expands the three canonical flows into frame-level interaction specs that an engineer can implement and a designer can prototype against.

> **Design lineage we're stealing from:** Linear (palette, density, status bar), Figma (bidirectional source/visual), Arc (sidebar choreography), Notion (artifact-as-onboarding), Cursor (Cmd-K inline AI), Vercel (deploy-as-narrative), Stripe (typographic restraint).

---

## Layout reference

```
─────────────────────────────────────────────────────────────────────────────
TOP BAR (40px)
  vson · file.vson · branch · ✓ Validates · 151 triples ·     ⊕  ⌘K  ⋯
─────────────────────────────────────────────────────────────────────────────
OUTLINE (240px)   │   SOURCE (fluid)            │   PREVIEW (fluid)
                  │                             │
  scene           │   Penman ▾   ⌘L Generate    │   bbox · 3D · image
  ├─ ctx          │                             │
  ├─ cam          │   (scene / Composition      │   ┌──────────────────┐
  ├─ alice        │      :framedBy ...          │   │                  │
  ├─ bob          │      :depicts (alice ...)   │   │   bbox preview   │
  ├─ strike       │      :depicts (strike ...)) │   │                  │
  └─ charge       │                             │   └──────────────────┘
                  │   Turtle ▸ JSON-LD ▸ Cypher │   ⌘E Render
                  │                             │
─────────────────────────────────────────────────────────────────────────────
STATUS BAR (24px)
  ⚠ 0  ·  151 triples  ·  18 inferred  ·  Smatch 0.94 vs gold  ·  ⌘K
─────────────────────────────────────────────────────────────────────────────
```

Inspector panel slides in from the right (240px) on ⌘. — never modal, always alongside.

---

## Flow A — Engineer integrates VSON (the wedge)

**Persona:** P1 (generation-pipeline engineer). **Surface:** CLI + VS Code, not Studio. **Goal:** ship a SHACL-validated LLM-driven generator in one afternoon.

### Frame-by-frame

| T | Surface | Interaction | Reaction |
|---|---|---|---|
| 00:00 | terminal | `brew install vson` | binary lands; `vson --version` returns `1.0.0` |
| 00:30 | terminal | `vson init scenes && cd scenes` | scaffolds `ontology/`, `shapes/`, `examples/throne_room.vson`, `.vscode/extensions.json`, `.github/workflows/vson.yml` |
| 01:00 | VS Code | open `examples/throne_room.vson`; toolbar prompts to install `vson-tools` | one-click install; LSP starts |
| 01:30 | VS Code | edits Alice's age trait | live SHACL passes; status item *"✓ Validates · 151 triples"* updates within 100ms |
| 02:00 | VS Code | introduces a deliberate violation: removes `:lemma` from `strike` Event | red squiggle on `strike` line; hover shows `EventShape failed: missing vso:lemma`; ⌘. shows three quick-fixes |
| 03:00 | terminal | `vson generate --model claude-opus-4-7 "queen Alice receiving a delegation" > new.vson` | grammar-constrained LLM emits a Penman doc; `vson validate new.vson` returns 0 |
| 04:00 | terminal | `vson export cypher new.vson \| neo4j-shell` | Cypher imports cleanly into Neo4j |
| 04:30 | terminal | `vson render new.vson --kind image -o new.png` | 4s wait; PNG written |
| 05:00 | GitHub | pushes a PR | `vson-action@v1` runs `vson validate **/*.vson`; PR check goes green |

**Time-to-first-value: 5 minutes.** This is the activation event for P1.

### Critical UX details

- **The CLI never asks for an account.** Auth is for hosted services only.
- **`vson init` is opinionated.** It scaffolds the GitHub action, the VS Code recommendation, the `.vson/config.toml`, and an example file. New users don't read docs to configure; they read the scaffolded files.
- **Diagnostic latency budget: 100ms** from keystroke to squiggle. The LSP runs SHACL incrementally on the changed subgraph, not the whole document. Engineering must hit this number.
- **`vson generate` returns a guaranteed-parseable document.** This is the magic claim. Implementation: Lark grammar + Anthropic-class model with constrained decoding + SHACL post-validation + auto-retry up to 3 times. We publish the success rate.

---

## Flow B — Director writes a scene (the wow demo)

**Persona:** P3 (creative director / non-engineer). **Surface:** Studio web app. **Goal:** prompt → image → tweak → share, in 60 seconds.

### Frame-by-frame

| T | What you see | What happens |
|---|---|---|
| **0.0s** | studio.vson.dev. Empty canvas. Single centered prompt input. Cursor pre-focused. Subtle copy: *"Describe a scene…"* | First-load — no login, no menu, no "Sign up." |
| **5.0s** | Director types: *"Knight Bob standing in front of a tense throne room at dusk, low-angle shot, oil painting style, with a charging boar."* Hits ↵. | Prompt animates from centered to docked-bottom. The three-pane workspace fades in around it (200ms cubic-out). |
| **5.5s** | Status bar: `Generating…` with a 1px scanning underline left-to-right. | Studio calls `/api/v1/generate` with the prompt; LLM streams Penman tokens. |
| **8.0s** | Source pane fills typewriter-style with the Penman doc (600ms total animation). Preview pane simultaneously shows bboxes appearing as nodes resolve. | Streaming render: every Composition / Frame / Entity node triggers an outline + bbox update. |
| **8.6s** | Status bar: `✓ Validates · 87 triples · 0.4s`. | SHACL pass. Outline shows 9 nodes. |
| **10.0s** | Director clicks `Render → image` (top-right of preview). | Right pane swaps to image fidelity. Preview shows a faint scanning gradient. |
| **14.0s** | Photorealistic image fills. | Layout-to-image renderer (hosted GLIGEN-class) returned. |
| **16.0s** | Director hovers Alice in the image. Preview overlays a hairline bbox on Alice. The corresponding line in Source is highlighted. The Outline scrolls to her. | Bidirectional selection. |
| **18.0s** | Director drags Alice's bbox to the left. Source updates her geometry triple in real time. | Geometry edit; bbox preview updates instantly; image NOT re-rendered yet. |
| **22.0s** | Director clicks Render. Image re-generates with Alice on the left. | Re-render in 4s. |
| **30.0s** | ⌘S → toast: *"Saved. Share link copied."* Director ⌘V into Slack. | Ephemeral share link active for 7 days; named link requires sign-in. |

**Time-to-share: 30 seconds.** That's the wow.

### Critical UX details

- **No spinner.** Loading states use scanning underlines, not spinners — Linear / Vercel restraint.
- **Streaming is mandatory.** LLM token-stream → Penman → triples → bboxes → outline. The user sees structure forming, not a black-box wait.
- **Bidirectional selection is the killer feature.** Source ⇄ Preview ⇄ Outline. Implemented via a single shared selection store keyed by node IRI.
- **Drag-to-edit.** Bbox handles in the preview update geometry triples in source. Direct manipulation on the visual surface beats form-based editing every time (this is the Figma move).
- **Anonymous-first.** Sign-in is gated behind named saves and team features. The first session is friction-free.
- **No tutorial overlay.** First-time users see one tooltip: *"Press ⌘K to do anything"*. That's it.

---

## Flow C — Annotator labels Visual Genome (the depth play)

**Persona:** P2 (annotator / ML researcher). **Surface:** Studio annotation mode. **Goal:** label 200 images with high IAA.

### Frame-by-frame

| Step | Pane state | Interaction |
|---|---|---|
| 1 | Loads `studio.vson.dev/annotate?dataset=vg`. | Three-pane shifts to annotation layout: left = Outline, center = image canvas with bbox tools, right = Source (Penman). |
| 2 | Selects the rectangle tool (R). Draws a bbox around the boar. | Studio opens an inline class selector docked under the bbox. VSV class list filtered by visual classifier suggestions ("boar 0.91", "pig 0.07"). |
| 3 | Picks `Boar`. Studio auto-emits in source: `(b1 / PhysicalObject :class Boar :individuation Generic :animacy Agentive ...)`. Reasoner suggests `affordance`/`countability` defaults from the class. | Outline gains a `b1 · Boar` entry. |
| 4 | Annotator presses `E` to open Event mode. Drags from `b1` (boar) to `bob` (already labeled) → suggests `(charge / Event :agent b1 :goal bob)`. | Penman patch shown as diff overlay; ⌘↵ accepts. |
| 5 | Status bar: `✓ Validates · 23 triples · 1 of 200 (0.5%)`. Smatch with gold annotation displayed if available: `Smatch vs gold: 0.83`. | Live IAA against gold. |
| 6 | ⌘N moves to next image. Auto-save. | Optimistic save to local IndexedDB; sync to server in background. |
| 7 | After 50 images, the team's `/team/iaa` dashboard shows pairwise Smatch heatmap. Annotator hovers a low-agreement cell to see disputed scenes. | Cohort dashboard, Linear-clean. |
| 8 | Schema lead clicks a frequently-disputed shape; opens shape-level metrics. Tightens VSV vocabulary; pushes update. All annotators see the new constraint live. | Schema-as-code, deployed. |

### Critical UX details

- **Bbox tool first, source second.** Annotators draw before they type. Source is generated, not authored.
- **VSV autocomplete is reasoner-augmented.** When the user picks `Boar`, the reasoner pre-fills `affordance`, `countability`, default `animacy`. The annotator confirms or overrides.
- **Suggested triples are diffs, not auto-applied.** Every reasoner suggestion is reviewable; nothing lands in the graph without an explicit accept.
- **IAA is real-time.** Smatch against gold and pairwise across annotators updates live. Disagreement is the schema's signal.
- **Schema changes are hot.** A schema lead pushes a tightened SHACL constraint; the team sees re-validation results within seconds. This is what makes the annotation phase iterate fast.

---

## Cross-cutting interaction details

### Selection model

A single global selection store (per workspace) keyed by node IRI:
- Click in any pane → selects node → all panes reflect.
- Shift-click → multi-select.
- ⌘-click → open inspector + select.
- Esc → clear.

### Inspector tabs (right rail, ⌘.)

When a node is selected:

```
┌─ INSPECTOR ────────────────────────────┐
│  :alice  ·  PhysicalObject              │
├─ Declared ─────────────────────────────┤
│  individuation : Named                  │
│  animacy       : Agentive               │
│  countability  : Count                  │
│  hasQuality    : 3 qualities ▸          │
├─ Inferred (OWL) ───────────────────────┤
│  vso:Endurant                           │
│  vso:Entity                             │
├─ Conformance ──────────────────────────┤
│  ✓ EntityShape                          │
│  ✓ HasQualityShape                      │
├─ Annotations ──────────────────────────┤
│  none                                   │
└────────────────────────────────────────┘
```

Click *Declared* row → edit inline. Click *Inferred* row → trace which axiom produced it (provenance link to ontology). Click *Conformance* row → see the SHACL shape source.

### Command palette (⌘K)

Three-section palette:
1. **Actions** — Generate, Render, Validate, Export, Format, Reify Event, Lift Quality.
2. **Navigate** — node by name, file by name, recent.
3. **Insert** — VSO classes, shapes, examples (insertable scaffolds).

Fuzzy matching, recency-biased. Recent actions surface above name matches (Linear-style).

### Status bar

24px, monospace 12px, single accent. Sections (left to right):
- Conformance dot + count.
- Triple count (declared + inferred).
- Smatch vs gold (if a gold scene is bound).
- Last save time.
- Right-aligned: ⌘K hint.

Pulses 1 cycle on conformance change. Color shifts from neutral (`text-2`) to `success`/`warning`/`error` for 1.2s, then settles back.

### Empty states

Empty studio canvas: a single centered prompt input plus three small thumbnails of starter scenes ("Throne Room · Marketplace · Spaceship Bridge"). No "Get Started" button — the prompt input *is* the start.

Empty inspector when no selection: a single line — *"Select a node to inspect."* — at 50% opacity. No artwork.

### Keyboard map (subset)

| Shortcut | Action |
|---|---|
| `⌘K` | command palette |
| `⌘.` | toggle inspector |
| `⌘L` | focus generate prompt |
| `⌘E` | render preview |
| `⌘R` | re-validate (force) |
| `⌘S` | save / generate share link |
| `⌘/` | cycle preview fidelity (bbox / 3D / image) |
| `⌘↵` | accept generate / suggestion diff |
| `⎋` | reject diff / clear selection |
| `R` (in annotate mode) | rectangle tool |
| `E` (in annotate mode) | event-link tool |

Discoverability: `?` opens a transparent overlay with the full keymap (Linear-style).

### Accessibility

- All actions reachable from the palette and via keyboard.
- Squiggles never the only signal — also reflected in outline and inspector.
- Color-coded states pair with shape glyphs (✓ ⚠ ✕).
- 4.5:1 contrast everywhere; 7:1 for body text.
- Screen-reader: source pane announces SHACL state; selection changes are aria-live.
- Reduced-motion respected; transitions degrade to 0ms.

---

## What we are *not* building (yet)

To stay disciplined, an explicit non-goals list:

- A graphical node-link editor for the graph. (The source pane *is* the editor; the bbox preview is the manipulable visual. A node-link spaghetti view loses to source-of-truth Penman every time.)
- A SPARQL-star query builder UI. Engineers write SPARQL.
- A 3D modeling surface. Studio composes USD via VSON; it does not edit USD geometry.
- A CMS / asset library. Scenes live in workspaces; assets live in the user's storage of choice.
- Real-time multiplayer in Phase 1. (Phase 3.)

---

## What ships first (Phase 1 P0 wireframes to implement)

1. Three-pane workspace (Outline · Source-Penman · Preview-bbox).
2. Live SHACL diagnostics in source pane.
3. Generate-from-prompt with constrained decoding.
4. Inspector for trait-bundle editing.
5. Anonymous editing + ephemeral share links.
6. Command palette (⌘K).
7. Status bar with conformance + triple count.

That's it. Everything in this doc beyond those seven is Phase 2+.
