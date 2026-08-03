# VSON — Visual Scene Ontology Notation, [v1.3](spec/CHANGELOG.md)

[![CI](https://github.com/yamancan/visual-scene-ontology/actions/workflows/ci.yml/badge.svg)](https://github.com/yamancan/visual-scene-ontology/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A vision-language model's description of an image is unvalidated prose: there is no schema it can violate, so nothing can reject one and no build can fail on it. VSON is a compact scene-graph notation in which every claim about an image — an object, a property, a spatial relation, an action — is instead a checkable graph assertion, gated by SHACL shapes (the W3C standard for validating graph structure). What ships today is that gate: `vson validate` exits non-zero on a scene graph that breaks the schema, and the web studio runs the same two checks in the browser. It checks the graph, not the picture — [§2.1](docs/vson.md#21-what-conformance-establishes) states exactly what a green result does and does not establish. Querying ships too: [`queries/`](queries/) holds 29 competency questions as SPARQL — 28 of them run by CI on every commit against the 17-document corpus and compared byte-for-byte with a frozen answer — and [§5.14.1](docs/vson.md#5141-what-the-questions-cover) maps each structural claim below to the questions that reach it, so "it is queryable" is a thing you can run rather than a thing this page asserts. Diffing two extraction runs ships too: `vson diff a b` aligns away the arbitrary names each run gave its nodes and reports triple-level precision, recall and F1 — overall and per layer, so a regression lands on *spatial* or *objects* instead of on one number ([§5.15](docs/vson.md#515-graph-agreement-vson-diff)). Agreement is not correctness — two runs that agree on the same hallucination score 1.0, and no image is read. VSON is built for image-generation pipelines, scene-graph and knowledge-representation researchers, and people evaluating VLM output, and it ships as a single-file spec, a Rust CLI, and a drop-an-image web studio.

Canonical namespace: **`https://w3id.org/vson/v1/`**. The canonical IRIs dereference: the [w3id redirect](https://github.com/perma-id/w3id.org/pull/6471) merged on 2026-07-31, so `https://w3id.org/vson/v1/ontology` resolves to the ontology, and shapes, JSON-LD context, and schemas resolve alongside it — served from [vson.pages.dev/v1/](https://vson.pages.dev/v1/ontology.ttl). `make live-check` re-verifies all eight names against the live services.

## graph in, English out — deterministic, no LLM

A scene in VSON-P, the Penman authoring syntax — [`examples/gallery/03_spatial_topology.vson`](examples/gallery/03_spatial_topology.vson):

```
# RCC-8 topological relation (no viewer needed for non-directional facts).
# Demonstrates: SpatialFact with rcc only (cat externally connected to mat).

(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing medium_shot)
   :viewedBy cam
   :depicts (cat / PhysicalObject
               :individuation Generic :animacy Agentive :countability Count
               :class Animal)
   :depicts (mat / PhysicalObject
               :individuation Generic :animacy Inert :countability Count
               :class Furniture)
   :hasFact (sf / SpatialFact
               :figure cat
               :ground mat
               :rcc EC))
```

`vson export caption` renders it with templates, not a model — byte-identical on every run, and checked in CI against [`tests/fixtures/captions/03_spatial_topology.txt`](tests/fixtures/captions/03_spatial_topology.txt):

```
Eye level medium shot, 50mm lens. An animal, and a furniture. The animal touches the furniture.
```

## What's in the box

A curated **visual-scene profile of RDF-star** with:

- a reified **Frame** taxonomy (`SceneContext` / `VisualStyle` / `CameraView` / `Composition` / `Persona`)
- a **trait-bundle entity model** (`individuation × animacy × countability × affordance`)
- a **`SpatialFact`** reification pattern (RCC-8 + Allen + frame-relative directionals with mandatory viewer)
- a closed **VSV** vocabulary: RCC-8 and Allen base-relation vocabularies (closed value sets on reified facts; composition-table reasoning out of scope), a closed inventory of coarse VerbNet-style thematic roles, mereology, and causation
- **three concrete syntaxes**: Turtle-star (VSON-T, canonical), Penman (VSON-P, authoring), and **VSON-X** (compact, sigil-based, LLM-optimized — new in v1.1)
- a deterministic **caption renderer** for image-generation models (graph → English, no LLM)
- **SHACL** gatekeeping with strict + relaxed profiles
- shipped **exporters**: Cypher / caption / FOL (CLI) and Cypher / DOT / GraphML / Mermaid / caption / FOL (web studio, all in-browser), plus a published JSON-LD form; spec-only mappings for AMR / Visual Genome / Pixar USD

VSON does not invent a parser, grammar, or formal semantics. It rides on:
- **RDF 1.2 / RDF-star** — abstract semantics
- **OWL 2 RL** — decidable reasoning fragment
- **SHACL** — well-formedness
- **SPARQL 1.1** — query ([`queries/`](queries/); the RDF-star spelling of §5.11 awaits SPARQL-star support in a pinned engine — [§5.14.2](docs/vson.md#5142-sparql-11-and-what-the-pack-defers))
- **RDFC-1.0** — canonical form, so "these two documents describe the same scene" is a byte comparison and not an opinion ([§4.6](docs/vson.md#46-denotation--when-two-documents-describe-the-same-scene))
- **Penman** — authoring concrete syntax (proven by AMR)

> **The canonical reference is [`docs/vson.md`](docs/vson.md)** — single-file RFC-style spec with Quick Start, per-field reference, JSON Schema, and the 16-scene example gallery.

## Layout

```
docs/vson.md      ★ Canonical single-file spec (Quick Start, reference, JSON Schema, gallery)
                    + vson-x-semantics.md (VSON-X surface semantics)
docs/strategy/    Productization plan, UI flows, extractor architecture
spec/             Historical normative spec (v1.0) + v0.1 deprecation record
ontology/         VSO TBox (OWL 2 RL) + VSV vocabulary
                  + alignments.ttl — skos:closeMatch/relatedMatch toward gUFO,
                  rdf:Statement, oa:, foaf: and a SKOS view of the six closed
                  value vocabularies. Imported by nothing, loaded by no gate.
shapes/           SHACL shapes for well-formedness
queries/          29 competency questions (SPARQL 1.1) + byte-frozen answers — make cq-check
examples/         Throne-room scene + gallery/ (16 scenes, minimal → complex)
                  + gallery-x/ (scenes 01–12 in VSON-X compact syntax)
tools/grammar/    The spec's own EBNF, extracted and executable — make grammar-check
                  + vson-x.gbnf, the llama.cpp constrained-decoding translation
cli/              `vson` Rust CLI (validate / verify --geometry / diff /
                  convert {p2t, x2t} / export {cypher, caption, fol})
                  + src/penman/routing-tables.json (single source of truth for both impls)
web/              Static SvelteKit studio — drop image, get scene graph; extraction
                  and two-gate verification run in the browser (BYOK OpenRouter + Pyodide)
tools/penman/     Reference Penman ↔ Turtle-star transpiler (Python)
tools/vson_x/     VSON-X compact-syntax parser + emitter + cross-syntax graph-equivalence
tools/render/     Deterministic graph → English caption renderer
tools/metrics/    Smatch graph agreement behind `vson diff` — per-layer precision/recall/F1
tools/canon.py    RDFC-1.0 canonical form — the §4.6 test for "the same scene", + frozen hashes
tools/schema/     JSON Schema files (extractor envelope + JSON-LD form)
vson/             `import vson` — the stable Python surface over tools/: validate() -> Verdict,
                  p2t/x2t, caption/FOL, diff, canonical form, a typed Envelope, and
                  validate_and_repair(chat_fn, image) — the studio's repair loop, no vendor SDK
tools/extractor/  Image-to-graph extractor — orchestrator prompts + bare-VLM baseline
skills/           Portable extractor skills (SKILL.md + conformance fixtures) — exercised by make x-skill-check
scripts/          Envelope check, smoke eval, deploy preflight
tests/            Round-trip and SHACL conformance tests
tests/conformance/ ★ The conformance test suite — an RDF manifest of documents and the
                    verdict each MUST get. Passing it is what claiming VSON v1
                    conformance means (§2.2) — make conformance
```

## Quick start

```bash
# Build the Rust CLI (~30s cold)
cd cli && cargo build --release && cd ..
make deps         # Python deps (rdflib, pyshacl, owlrl) — required for `vson validate`

# Validate the canonical scene
cli/target/release/vson validate examples/throne_room.ttl

# Transpile Penman -> Turtle
cli/target/release/vson convert p2t examples/throne_room.vson > /tmp/scene.ttl

# Transpile VSON-X compact syntax -> Turtle
cli/target/release/vson convert x2t examples/gallery-x/11_throne_room.x.vson > /tmp/scene.ttl

# Export to Cypher
cli/target/release/vson export cypher examples/throne_room.vson > scene.cypher

# Render an English caption for image-generation models
cli/target/release/vson export caption examples/throne_room.vson

# Compare two documents of "the same" scene — agreement per layer, no image read
cli/target/release/vson diff examples/throne_room.ttl examples/gallery/11_throne_room.vson

# Run all tests (Python + Rust)
make check        # 535 Python tests + 16-scene gallery + 2 schema parses
                  # includes the 29 frozen canonical hashes of §4.6
make conformance  # the 218-entry conformance suite — what claiming VSON v1 means
make cq-check     # the 28 executable competency questions vs their frozen answers
make grammar-check # Appendix B and Appendix D, extracted from the spec and run
make cli-check    # Rust tests + byte-strict & graph-iso parity vs Python ref
make x-check      # VSON-X gallery round-trip parity (12 pairs)
```

See [`docs/vson.md`](docs/vson.md) for the full spec, [`cli/README.md`](cli/README.md) for the CLI, and [`web/README.md`](web/README.md) for the studio.

## Python: `import vson`

The CLI is one consumer of the reference implementations. [`vson/`](vson/) is the other — a facade over [`tools/`](tools/) with a stable import path, typed results and its own exceptions, running the same three gates in the same order as `vson validate` and re-implementing nothing.

```bash
pip install -e .   # editable: the package reads skills/ and tools/schema/ from the checkout
```

```python
import vson

verdict = vson.validate("examples/throne_room.vson")  # a path or the text; .ttl / .vson / .x.vson
verdict.conforms, verdict.gate, verdict.messages      # True, None, []

vson.to_turtle(penman)          # p2t              vson.diff(a, b).f1         # agreement, §5.15
vson.from_x(vson_x)             # x2t              vson.canonical_hash(doc)   # §4.6
vson.caption(doc)               # graph → English, deterministic, no model in the loop
vson.fol(doc)                   # graph → predicate logic
```

### Image → validated envelope

`validate_and_repair` is the studio's emit → validate → feed-the-SHACL-messages-back loop as a library call. It takes **your** chat function and nothing else: no vendor SDK is imported, no API key is read, no environment variable is consulted, and whatever you pass as `image_or_doc` is forwarded to round 0 untouched and uninspected — bytes, a path, a base64 string, a list of content blocks.

```python
import vson

def chat(turn):                        # turn.round, turn.system, turn.user, turn.attachment
    ...                                # your model call, your key, your SDK
    return reply_text

result = vson.validate_and_repair(chat, image_or_doc=jpeg_bytes)
print(result.conforms, result.shacl_retries)          # e.g. True 1

envelope = result.to_envelope("kitchen_01", source=vson.Source(kind="image"))
assert envelope.errors() == []                        # valid against ENVELOPE_SCHEMA
```

`extraction.shacl_retries` has been in the envelope schema since v1.0, and until now only the studio could put a number in it. The loop is bounded at two repair rounds — the studio's own `MAX_REPAIR_RETRIES`, mirrored so live envelopes stay comparable with the baked demo corpus, and pinned against [`web/src/lib/extract/limits.ts`](web/src/lib/extract/limits.ts) by a test that reads it back.

`SKILL_PROMPT`, `SKILL_X_PROMPT`, the two repair templates and `ENVELOPE_SCHEMA` are read from [`skills/`](skills/) and [`tools/schema/`](tools/schema/) at import, not restated. `response_format()` / `tool_schema()` / `ollama_format()` wrap that schema in the OpenAI, Anthropic and Ollama shapes and do nothing else — no request, no client, no key.

**None of it reads an image.** A `conforms=True` verdict says the document is well-formed under the shapes, the ontology and the vocabulary — never that it describes the picture ([§2.1](docs/vson.md#21-what-conformance-establishes)).

## Use it from an agent

The loop above — emit, validate, feed the messages back, rewrite — is a tool call when the caller is an agent. `vson mcp` serves it as an [MCP](https://modelcontextprotocol.io) stdio server: JSON-RPC over stdin and stdout, no port, no host, no key.

```bash
claude mcp add vson -- python3 -m vson.mcp          # from a checkout
claude mcp add vson -- /path/to/vson mcp            # or the built binary, anywhere
```

Or check in [`.mcp.json`](.mcp.json), which this repository already does, so a session opened here is offered the server:

```json
{ "mcpServers": { "vson": { "command": "python3", "args": ["-m", "vson.mcp"] } } }
```

Four tools, and what each one actually returns:

| Tool | Give it | You get back |
|---|---|---|
| `vson_validate` | `document` (the text) or `path`; optional `syntax`, `profile` | the three gates' verdict as JSON — `conforms`, the `gate` that fired, and one finding per violation carrying the `sh:message` string, the shape, the focus node and the result path. A document that fails is a **result**, not an error: that JSON is the repair prompt |
| `vson_convert` | `direction: p2t\|x2t` and the document | the Turtle. No reverse direction exists ([§6.1](docs/vson.md#61-the-extractor-envelope-schema)) |
| `vson_export` | `format: caption\|fol\|cypher` and the document | the rendering, as text |
| `vson_skill_prompt` | optional `notation: p\|x` | [`skills/vson-extractor/SKILL.md`](skills/vson-extractor/SKILL.md), verbatim — the closed vocabulary, the trait bundles and the clauses, **before** the agent writes rather than after it is rejected |

Three things stated plainly, because a tool description is a promise:

- **`cypher` needs the binary.** That renderer exists only in the Rust CLI, and the server shells out to it rather than keeping a second copy. Under `vson mcp` it is always there; under `python3 -m vson.mcp` it works when a `vson` is on `PATH` or built in the checkout, and returns an error result saying so when it is not. `caption` and `fol` are pure Python.
- **No image, no network.** Every tool is [`vson/api.py`](vson/api.py) behind a JSON envelope. A green `vson_validate` is [§2.1](docs/vson.md#21-what-conformance-establishes)'s verdict and nothing more.
- **`path` reads your filesystem** with the server's own privileges — it is a local stdio server you started, the same trust boundary `vson validate` has always had.

[`vson/mcp.py`](vson/mcp.py) is standard library only and adds no dependency to this project; [§5.18](docs/vson.md#518-agent-tool-surface-vson-mcp) documents the MCP revisions it speaks, why the protocol is hand-rolled rather than taken from an SDK, and what it deliberately does not serve.

## Fail a build on it

The first sentence of this page says a VLM's prose cannot fail a build. Here is the build failing:

```yaml
# .github/workflows/scenes.yml
- uses: yamancan/visual-scene-ontology/.github/actions/validate@main
  with:
    files: 'scenes/**/*.vson'
```

Every violation becomes an annotation on the line that caused it — the SHACL shape that fired, on the Penman variable that declared the node — plus a table in the job summary. Nothing to install, no Marketplace listing, no token. [`.github/actions/validate/action.yml`](.github/actions/validate/action.yml) documents every input, and [CI runs the action against this repository's own gallery and its own bad fixture](.github/workflows/ci.yml) on every commit, because a gate nobody has seen go red is a gate nobody should trust.

While this repository is private, that `uses:` line resolves only for workflows allowed to read it; inside this repository the same action is `uses: ./.github/actions/validate`, which is the form CI exercises.

**The cost, stated up front:** there are no release binaries yet, so the action builds the CLI with `cargo` — about twenty seconds of compile time on a warm registry, removed on later runs by `Swatinem/rust-cache@v2` with `workspaces: cli`. That step disappears when binaries ship.

Locally, the same three gates run as a [pre-commit](https://pre-commit.com) hook:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/yamancan/visual-scene-ontology
    rev: main   # the hooks postdate the v1.3.0 tag — pin the first tag that carries them
    hooks:
      - id: vson-validate
```

And in any other pipeline, straight from the binary — exit 0 conformant, 1 a document that failed a gate, 2 no verdict:

```bash
vson validate --format sarif scenes/*.vson > vson.sarif   # SARIF 2.1.0, for any code scanner
cat scene.vson | vson validate --format json -            # stdin, one record per violation
```

[§5.16](docs/vson.md#516-machine-readable-validation-reports-vson-validate---format) is the report format: one record per violation carrying the shape, the focus node, the result path, the severity and — where it can be established rather than guessed — the source line. It checks the graph, not the picture ([§2.1](docs/vson.md#21-what-conformance-establishes)); a green build is not a claim about the image.

Run the studio locally:

```bash
cd web
pnpm install
pnpm dev --open
```

The studio is a **fully static site — no backend, no `.env`, no server key**. Demos and the 16-scene gallery run keyless at $0 from baked envelopes; live extraction of your own images runs on your own OpenRouter key, entered in the model picker, and the key goes browser → OpenRouter without ever touching a studio host. Verification runs in the browser too: a Pyodide worker executes two of the three gates `vson validate` runs (pyshacl SHACL, then owlrl OWL 2 RL), from the same source files, byte-pinned to the CLI in CI — the third, C2 vocabulary closure, is CLI-only. `make web-deploy` publishes `web/build` to Cloudflare Pages (`vson-studio.pages.dev`); the namespace host `vson.pages.dev` is a separate project.

## Contribution boundary

VSON's genuinely-new content (everything else is W3C/ISO):

1. **Frame taxonomy** as a first-class perspectival layer distinct from `Entity`.
2. **Trait-bundle entity model** — orthogonal axes replace the folk Object/Item/Unique/Attribute mess.
3. **`SpatialFact` with a viewer a validator enforces** — not a new idea, and this list said otherwise until v1.3. Reifying a spatial relation with required, asymmetric figure and ground slots is standardized practice: ISO 24617-7:2020 requires a link structure to carry a relation type and two arguments, and names those two `@figure` and `@ground` in its revised movement link; SemEval-2012's spatial-role-labeling task ran on the same pair under the names *trajector* and *landmark*. Anchoring a directional to a frame of reference is Levinson's analysis. What VSON commits to is narrower: **one** frame (the relative one) rather than an annotation of which frame is in use, and the anchor as a **structural obligation with an exit code** — C5 and `vss:DirectionalNeedsViewerShape` reject the document, where the prior schemes instruct the annotator. [Appendix E.7](docs/vson.md#appendix-e) states what each of them does that this does not, including the annotated corpora and published agreement studies VSON has neither of.
4. **Closed VSV vocabulary** curated for visual scenes.
5. **Penman authoring surface** tuned for VSV.
6. **VSON-X compact syntax** (v1.1) — nine prefix sigils, no brackets, LL(1), bearer-class dispatch for `*K V`. All 12 gallery scenes that have a VSON-X counterpart denote the same scene as their Penman twin under [§4.6](docs/vson.md#46-denotation--when-two-documents-describe-the-same-scene): identical RDFC-1.0 canonical N-Quads, frozen in [`tests/fixtures/canonical/hashes.txt`](tests/fixtures/canonical/hashes.txt).
7. **Persona / cross-document identity** (v1.1) — `vso:Persona` Frame + `vso:embodies` lets the same character appear in many scenes with consistent invariants.
8. **Deterministic caption renderer** — graph → English, template-driven, byte-identical CI fixtures.
9. **Exporter matrix** — shipped Cypher / caption / FOL (CLI) and DOT / GraphML / Mermaid / caption / FOL (web studio, in-browser) exporters, plus a published JSON-LD form; spec-only mappings for AMR / Visual Genome / USD.

## License

Apache-2.0.
