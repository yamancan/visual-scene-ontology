# Changelog

## v1.3.0 — 2026-07-31

The static studio release. The web studio drops its server entirely: no
backend process, no API routes, no operator API key — extraction goes from the
visitor's browser straight to OpenRouter on the visitor's own key, and
verification runs in the visitor's browser at CLI parity. **The envelope wire
format is unchanged at 1.2, and the ontology and namespace are unchanged**: no
class, property, shape, schema field, or IRI moves. v1.3 changes *where*
computation runs, not what a document or an envelope asserts.

- **Static-native studio.** `@sveltejs/adapter-node` is replaced by
  `@sveltejs/adapter-static` with strict prerender: the deploy artifact is a
  directory of files, published to a second Cloudflare Pages project
  (`vson-studio.pages.dev`) by a manual `make web-deploy` — no CI deploy step,
  no deploy secrets, and the `vson.pages.dev` namespace project is untouched.
  The entire server surface is deleted: the five `/api/*` routes,
  `hooks.server.ts`, and `$lib/server`, along with every runtime environment
  variable that fed them (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
  `OPENROUTER_ALLOWED_MODELS`, `PUBLIC_BASE_URL`, `RATE_LIMIT_MAX` /
  `RATE_LIMIT_WINDOW_S`, `VSON_BIN`, `BODY_SIZE_LIMIT`). Prompts and the
  skill manifest became compile-time constants of the bundle.
- **In-browser two-gate verification at CLI parity.** A Pyodide web worker
  mounts the repository's reference Python implementation — the Penman and
  VSON-X transpilers with the shared routing tables, the SHACL helper, the
  OWL RL check, the caption/FOL renderers, the shapes, and the vso/rcc8/allen
  ontology trio — and runs the same two gates in the same order as
  `vson validate`: pyshacl with `inference=rdfs` (Gate 1), then the owlrl
  OWL 2 RL consistency check (Gate 2, only when Gate 1 passes). Parity is
  pinned from both sides in CI: `make cli-check` now byte-compares Python vs
  Rust `p2t` over the full corpus (throne room + all 16 gallery scenes), and
  an offline worker vitest boots Pyodide from the committed wheels and asserts
  byte-equal `p2t` output against the committed Turtle golden, both gate
  verdicts on good and bad fixtures, and byte-equal caption/FOL output against
  the CI fixtures. Caption and FOL exports ship in the studio again through
  the same worker — the same renderers the CLI shells out to.
- **Direct BYOK, and a keyless behavior change.** The visitor's OpenRouter key
  is used to build an `Authorization` header on requests the browser makes
  directly to `openrouter.ai`; it is held in tab memory only and never touches
  the studio's origin — strictly stronger than the v1.2 relay, where the key
  transited the operator's server per request. The operator-key free tier is
  **removed**: with no server there is no server key, so live extraction of a
  new image now requires the visitor's own key. Demos, the 16-scene gallery,
  and byte-exact demo re-upload (a client-side sha256 short-circuit against
  the baked index) remain the keyless $0 path, unchanged. The per-IP rate
  limiter and the model allowlist died with the key they defended; the
  operational bounds live on client-side in one test-pinned module (≤ 2 repair
  rounds, unchanged correction caps), keeping live `shacl_retries` on the same
  ceiling as the baked corpus.
- **Generated hash-CSP, now covering static assets.** SvelteKit's nonce-mode
  CSP config and the hand-written inline theme script are both gone (the
  script moved verbatim to an external `static/theme-init.js`; `app.html`
  carries zero inline scripts). A post-build generator scans every emitted
  HTML page, sha256-hashes every remaining inline script (SvelteKit's own
  hydration bootstrap), fails the build if it finds none, and writes a
  Cloudflare Pages `_headers` file with one `Content-Security-Policy` covering
  **every** response — pages, static assets, and the validation worker script,
  which the v1.2 adapter-node hook never reached (the "gap" documented in the
  v1.2 `web/README.md` is closed). Two directive deltas from v1.2:
  `script-src` gains `'wasm-unsafe-eval'` (the worker's CSP comes from its own
  script's response headers, so this is what licenses wasm compilation) and
  `connect-src` gains `https://openrouter.ai`. HSTS joins the constant header
  set (Pages is always TLS), `/pyodide/*` is cached immutable, and COEP is
  deliberately absent — single-threaded Pyodide needs no SharedArrayBuffer.
  Hashes are recomputed from actual build output on every build, so CSP drift
  is impossible by construction.
- **Self-hosted Pyodide payload — zero third-party origins.** The Pyodide core
  runtime is copied at build time from the exact-pinned npm package into
  `/pyodide/`; the pure-Python wheels (rdflib, pyshacl, owlrl and their
  dependencies) are committed to the repository under a sha256 lock enforced
  by a test, and installed via `pyodide.loadPackage` with explicit same-origin
  URLs — no micropip, no PyPI, no CDN, at build time or at runtime. The layer
  is strictly demand-loaded: keyless visitors never download a byte of it; the
  first action that needs verification pulls ≈16 MB raw (compressed in
  transit) once per browser. If the
  runtime cannot boot on a device, the studio keeps the extracted document and
  reports validation as unavailable with CLI instructions.
- **Version markers.** Software markers move to 1.3.0 (`CITATION.cff`, the
  Python package, the Rust crate and its lock, the CLI strings, the web
  package, the studio's displayed version). The ontology documents'
  `owl:versionInfo`, both shapes profiles, the published landing page, and
  the envelope schema's version enum deliberately stay at 1.2 — the
  vocabulary, the namespace, and the wire format did not change, and
  `make site` still proves the landing page and `owl:versionInfo` agree.
  *Annotation, 2026-07-31: the version enum did not stay at 1.2. Holding it
  there left `docs/vson.md` §6.1 quoting `["1.0", "1.0.5", "1.1"]` against a
  schema that already admitted `"1.2"` — a §2 precedence violation, because
  this document outranks the schemas, so the stale copy was the highest-ranked
  artifact stating something false. Resolved in the artifact's favour: the enum
  and the conditional `allOf` clause beside it both now run through `"1.3"`, and
  new §8.1 states what the field claims (the spec document, not the vocabulary),
  which is why `owl:versionInfo` still does not move. Writing the test for that
  clause exposed a second defect in it: each `anyOf` branch used a bare
  `properties`, which an absent key satisfies vacuously, so an envelope with
  `vson_p: ""` and no `vson_x` passed the branch meant to demand `vson_x` —
  the one-surface rule the `$comment` describes was not being enforced at all.
  Both branches now carry `required`. This rejects only documents §6.1 and the
  schema's own `vson_p` description already declared non-conformant, and no
  shipped envelope is affected: all 21 baked envelopes are `version: "1.0"`,
  and none carries a short `vson_p`. `make fragment-check` compares the
  document against the schema from now on. The paragraph above stands as the
  record of what was decided at release.*

*Annotation, 2026-07-31 — the value-space sweep, and the clause that authorizes
it.* The entry above opens with "no class, property, shape, schema field, or
IRI moves". Shapes moved after it was written, and this records what and why.
`vso:bbox2d "banana"` and `vso:confidence "7.3"` were conformant VSON through
v1.2 — not because the specification permitted them, but because value spaces
`docs/vson.md` §5.4, §5.6, §5.10 and §5.11 define had never been transcribed
into a shape. New §8.2 states the rule for closing a gap like that inside v1.x:
a check may be added only when every document it newly rejects was already
non-conformant under a numbered clause or a §5/§6 value space, it must not
reject — or warn on — a document the specification permits, and every tightening
lands with a negative fixture, this entry, and the authorizing clause cited
where a reader of the failure will see it — the shape's own `sh:message`, or the
gate's module docstring. It says *check*, not *shape*, because one of the gaps
it closed is not shapeable. Closed under it: the `vso:bbox2d` grammar and the
three 3D geometry grammars (`vss:GeometryShape`), the `[0,1]` bounds on
`vso:probability` / `vso:confidence` / `vso:visibleFraction`
(`vss:ConfidenceRangeShape`), the snake_case `vso:lemma` pattern
(`vss:LemmaShape`), the `vso:class` / `vso:viewedBy` / `vso:rendersAs` caps, the
`0..1` caps on the three `SpatialFact` relation slots, and the two clause gaps
§2.1 named — C5's *exactly one* `vso:viewer` and C6's *exactly one* `vso:lemma`
on `vso:Process` and `vso:Stative`. Eleven `tests/fixtures/bad_*.ttl`, one per
constraint, each of which the v1.2 shapes accepted.

Closed under the same rule but off the shapes: **clause C2**. `docs/vson.md` §2
said, from v1.1 to v1.2, that `vson validate` "does not establish C2 — no tool
inspects a document for orphan VSO terms at validate time"; the only sweep was a
test over this repository's own corpus, so a third-party document could mint
`vso:Ambience`, pass clean and be non-conformant. `tools/c2_check.py` is now the
third gate, after SHACL and OWL 2 RL. It is not a shape and cannot be one:
deciding C2 needs the ontology's declared subjects, which a shapes file would
have to assume are in the data graph, and an undeclared IRI raises no OWL clash.
Nothing it rejects was ever conformant — C2 is what it enforces, verbatim — and
zero orphan terms were measured across `examples/`, the 16-scene gallery,
`examples/gallery-x` and all 21 baked envelopes before it landed. Fixture:
`tests/fixtures/bad_orphan_term.ttl`, the only `bad_*.ttl` that satisfies every
shape. The studio's Pyodide pipeline runs the first two gates and not this one;
`web/` now says so instead of claiming parity.

Declined under the same rule,
with the measurements recorded beside the shapes: the §5.3.1 / §5.3.3 value
lists (§5.12 carries none of them, and three shipped envelopes use
`timeOfDay "day"`, `atmosphere "cold"`, `atmosphere "clear"`) and Entity trait
completeness (51 entity/trait pairs across 6 shipped documents). Two ontology
edits ride along: `vso:properPartOf` is now `owl:IrreflexiveProperty`, which
§5.8's table has published since v1.0 and `tools/owlrl_check.py` now checks
(`owlrl` derives nothing from `prp-irp`), and `vso:bbox2d`'s comment, which
offered a pixel reading §5.4 and §5.10 never did, now says normalized — the §2
precedence order resolving a disagreement in the lower-ranked artifact.
`owl:versionInfo` moves to 1.3 in neither shapes file nor the ontology under
§8.1's model: no term, no IRI and no clause changed, only how much of the
existing contract the tooling executes. All 21 baked envelopes, the 16-scene
gallery and `examples/` still conform, byte-untouched.

## v1.2.0 — 2026-07-31

Namespace release. Every canonical VSON IRI moves off `https://vson.dev/` and
onto `https://w3id.org/vson/`, and for the first time the documents behind
those names are actually published. No class, property, cardinality, shape
severity, or envelope field changes: a v1.1 document becomes a v1.2 document
by rewriting its namespace and nothing else.

- **Canonical namespace is now `https://w3id.org/vson/v1/`.** `vson.dev` was
  never registered by this project — it was squattable by anyone, permanently
  non-dereferenceable, and dependent on one maintainer paying one registrar
  forever. w3id.org is the W3C Permanent Identifier Community Group's redirect
  service: free, community-maintained, and designed to keep resolving after
  any single maintainer stops paying attention. That permanence is the one
  property a namespace host must have and a private domain cannot promise. All
  five namespaces (`v1/ontology#`, `v1/rcc8#`, `v1/allen#`, `v1/shapes#`,
  `v1/shapes-relaxed`), both JSON Schema `$id`s, and the JSON-LD context IRI
  moved in a single commit. `cli/src/penman/routing-tables.json` is the sole
  mint site for both the Rust and Python emitters, so the move was three lines
  there plus a mechanical substitution everywhere the names were baked.
  *Annotation, 2026-07-31: those namespaces are unchanged, but the prefix the
  core vocabulary publishes for its namespace is. `vann:preferredNamespacePrefix`
  moved `"vso"` → `"vson"`: `vso:` belongs to the Vehicle Sales Ontology
  (`http://purl.org/vso/ns#`, in LOV with versions back to 2010-10-02), so the
  declaration shipped here asked consumers to rebind a prefix somebody else
  already publishes. No IRI moved and nothing migrates — every Turtle document
  still writes `@prefix vso:`, which is legal because a prefix is an
  abbreviation the parser expands away, and `tests/test_prefix_binding.py`
  re-serializes the whole corpus under both bindings to hold the graphs
  identical. The registration itself is drafted and unfiled
  (`publish/registry/prefix-cc.json`); `docs/vson.md` §5.1 records the choice.*
- **The old names are withdrawn, not aliased.** There is no `owl:sameAs`
  bridge, no redirect, and no shape that targets them: a document minted under
  the old host selects zero focus nodes against the v1.2 shapes and does not
  validate. Withdrawal is defensible here precisely because the legacy names
  had **zero external consumers** — they never dereferenced, so no third party
  could ever have resolved or cached them, and every producer and consumer of
  them lived in this repository. Aliasing would have preserved a name that was
  never real. See `docs/vson.md` §5.1 and §8.
- **One legacy IRI survives, deliberately.** `ontology/vso.ttl` keeps
  `owl:priorVersion <https://vson.dev/v1.1/ontology>` under a `LEGACY IRI`
  comment. That string is the `owl:versionIRI` the v1.1.1 release actually
  declared (`git show v1.1.1:ontology/vso.ttl`); rewriting it to w3id.org would
  assert a name that release never carried, falsifying a record instead of
  migrating one. It is a record, not a resolvable name, and nothing
  dereferences it. §8 states it as the one exception to IRI immutability, and
  the gate pins it at exactly one occurrence.
- **`vsv:` was never minted, and stays unminted.** The superseded
  `spec/vson-spec-v1.md` prefix table lists a `vsv:` prefix bound to a
  `.../v1/vocab#` namespace, but no ontology, shape, transpiler, schema, or
  example ever emitted a term under it — the closed value vocabularies live in
  the `vso:` namespace. It was left exactly where it is, in a historical
  document, and was deliberately excluded from the migration: re-minting it
  under the new host would have created, for the first time, a namespace that
  has never existed.
- **Two anti-vacuity gates, both landed before the rename.** SHACL selects
  focus nodes by IRI, so a half-migrated repository would have made every
  conformance gate vacuously green — zero focus nodes selected, `conforms=true`,
  nothing checked. `envelope-check` now reads the expected VSO namespace from
  the routing tables and requires each committed envelope to carry it, to parse
  to at least one `vso:Composition` (the shapes' actual target), and to name no
  legacy host; conformance alone is no longer accepted as evidence. `iri-check`
  (`scripts/check_legacy_iri.py`, wired into `make check` and therefore CI)
  scans every tracked file and fails on any occurrence of the withdrawn host
  outside an allowlist of historical documents, with exact pinned counts rather
  than upper bounds.
- **The namespace is published and dereferenceable.** `make site`
  (`scripts/build_site.py`) assembles the three ontology documents, both SHACL
  profiles, the JSON-LD context, both JSON Schemas, a landing page, and a
  Cloudflare Pages `_headers` file into the exact paths the IRIs name, and
  self-checks the result: every Turtle parses, every JSON parses, no served
  file names the withdrawn host, and the landing page's version equals
  `owl:versionInfo`. The surface is live at `https://vson.pages.dev/v1/`. The
  w3id redirect that makes the canonical IRIs themselves resolve is **pending
  review** at <https://github.com/perma-id/w3id.org/pull/6471>; until it
  merges, resolve the Pages URLs directly. The release does not depend on that
  PR — IRIs are names, and these names now have documents behind them either
  way.
  *Annotation, 2026-07-31: PR #6471 merged; the canonical names now resolve —
  `303` for the five namespace documents, `302` for the context and both schema
  `$id`s. The paragraph above stands as written, as the record of what was true
  at release; `make live-check` re-verifies the redirects (`docs/vson.md` §5.1).*
- **JSON-LD context shipped.** `ontology/context.jsonld` — the IRI §4.4 has
  named since v1.0 and which never existed — now exists: prefix bindings for
  `vso`/`rcc`/`allen`, an `@vocab`, and `@type: @id` declarations for the seven
  structural predicates. `tests/test_jsonld_context.py` requires every `@id` in
  it to resolve to a subject declared in `ontology/vso.ttl` and its namespaces
  to equal the routing tables'.
- **Envelope wire version `1.2`.** The schema's version enum admits `"1.2"`
  and the studio's four envelope constructors emit it. The envelope structure
  is unchanged from 1.1; what changes is the namespace of the IRIs inside
  `vson_t`. The `if`/`then` clause requiring at least one non-empty authoring
  surface was keyed to `"const": "1.1"` and is now keyed to
  `"enum": ["1.1", "1.2"]` — widening the version enum without that change
  would have silently switched the rule off for 1.2 envelopes. The preflight
  now asserts both directions for both versions: a valid X-mode envelope
  validates, and a surface-less one is rejected. The baked demo corpus keeps
  its historical `1.0`/`1.1` labels; those envelopes are real extractions and
  relabelling them would misstate their provenance.
- **Web studio: bring your own OpenRouter key.** A visitor can paste their own
  key into the model picker and spend it instead of the operator's. The key
  rides one request in an `x-openrouter-key` header, is passed to the upstream
  call and dropped — never stored, never logged, never echoed back — and on the
  client it lives in module memory for the lifetime of the tab only: no
  localStorage, no sessionStorage, no cookie, no URL. A malformed header is a
  400 rather than a silent fallback to the server's key.
- **Web studio: CSP and security response headers.** The studio previously had
  neither. Content-Security-Policy is declared in `svelte.config.js` in nonce
  mode (SvelteKit splices a per-response nonce; the hand-written FOUC guard in
  `app.html` carries `%sveltekit.nonce%`, so no hash can drift out of date),
  with `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, and
  `frame-ancestors 'none'`. Alongside it: `nosniff`, a strict-origin referrer
  policy, `X-Frame-Options: DENY`, a `Permissions-Policy` disabling
  camera/microphone/geolocation/payment/USB, COOP and CORP at `same-origin`,
  and HSTS on HTTPS requests only. One honest gap is documented in
  `web/README.md`: adapter-node's static file server answers before hooks run,
  so files under `static/` do not receive the response-header set (CSP is
  unaffected — it governs documents).
- **Release plumbing.** `jsonschema` is a declared dependency, so the preflight
  schema gate can no longer skip itself on an ImportError; version markers are
  synchronized at 1.2.0 across `CITATION.cff`, `pyproject.toml`, the Rust crate
  and its lockfile, the CLI's version strings, the ontology and shapes
  documents, the studio, and the published landing page.

## v1.1.1 — 2026-07-30

Editorial, verification, and packaging release. No wire-format or vocabulary
semantics change; documents valid under v1.1 remain valid.

- **Truthfulness pass** across every public surface: real editor attribution,
  measured-vs-target claims separated (the ≥80% extractor figure is a
  pre-registered target, not a result), Talmy/Levinson frame-of-reference
  attribution corrected, stale counts re-measured.
- **Spec**: Appendix D (normative VSON-X grammar, reconciled against the
  reference parser), Appendix E (related work + 16-entry bibliography), one
  numbered precedence clause; `docs/vson-x-semantics.md` translated to English
  and promoted to the normative VSON-X surface-semantics spec.
- **Ontology/shapes**: `vso:occurs` declared; six range-mirrored `sh:class`
  checks de-vacuated with `sh:not` guards backed by new disjointness axioms;
  full `rdfs:label`/`rdfs:comment` coverage; `skos:closeMatch` alignments to
  GeoSPARQL (RCC-8) and OWL-Time (Allen); Dimension registry closed at 21
  members, enforced by the C2 coverage test.
- **CLI**: `export cypher` emits one valid `CREATE` statement; `validate` runs
  both CI gates (SHACL + OWL 2 RL consistency) with an honest 0/1/2 exit-code
  contract; Python shell-out consolidated into `python_bridge.rs`; the crate
  now passes `cargo package` (routing tables moved into the crate at
  `cli/src/penman/routing-tables.json`, still the single source for both
  implementations).
- **Python**: `pyproject.toml` packaging, absolute imports (no `sys.path`
  hacks), ruff lint gate wired into `make check` and CI; VSON-X parser rejects
  modifiers on thematic roles loudly instead of dropping them silently.
- **Web studio**: OpenRouter proxy hardened (per-IP rate limit, model
  allowlist, payload caps), client-side downscale for large uploads, failure
  paths surfaced honestly, listbox/overlay accessibility; `BODY_SIZE_LIMIT`
  deploy requirement documented.
- **Hygiene**: `CITATION.cff`, `SECURITY.md`, `CONTRIBUTING.md`, dependabot;
  gitignore negations un-lose four normative markdown files; unverifiable
  image-license assertions removed. The lookbook demo was withdrawn pending
  provenance documentation.

## v1.1 — 2026-05-07

### VSON-X (compact concrete syntax)

A third concrete syntax alongside Penman (VSON-P) and Turtle-star (VSON-T).
Optimized for LLM emission and human authoring — nine prefix sigils, no
brackets, no significant newlines (every construct opens with a lead sigil;
one construct per line is emission convention, not grammar).

**Term reassignment.** In the superseded `spec/vson-spec-v1.md` draft,
"VSON-X" named the exporter layer. v1.1 reassigns the name to this compact
sigil syntax; exporters are now §7 of `docs/vson.md` and carry no layer
acronym of their own.

| Sigil | Kind | Example |
|---|---|---|
| `~` | Composition root | `~scene` |
| `/` | Concept marker | `/PhysicalObject`, `/CameraView` |
| `@` | Named/Skolem handle | `@alice`, `@cam` |
| `*` | Quality kv / direct property | `*color red`, `*angle eye_level` |
| `>` | Stative role-edge | `@bob > hold sword` |
| `>>` | Event/Process role-edge | `@bob >> strike boar *instrument sword` |
| `!` | Asymmetric SpatialFact | `crown ! EC @alice ^cam *dir above` |
| `&` | Symmetric SpatialFact (2 emissions) | `a & near & b` |
| `^` | Viewer anchor | `^cam` |

- Bearer-class dispatch for `*K V`: Frames take direct properties,
  Entities reify Quality nodes (with seven special direct-property
  exceptions: `class`, `bbox2d`, `position3d`, `scale3d`, `rotation`,
  `visibleFraction`, `embodies`).
- Symmetric-by-construction: `&` emits two SpatialFact nodes with
  figure/ground swapped — closes v0.1's asymmetry-by-fiat bug.
- LL(1) grammar; lead-token rule allows multi-line items without
  significant whitespace.
- Round-trip parity: scenes 01–11 have VSON-X counterparts under
  `examples/gallery-x/N.x.vson` whose RDF graph is equivalent (modulo
  blank-node identity for auto-anonymous reified nodes) to their Penman
  counterparts. A `12_persona` X file also exists (round-trip coverage
  pending); scenes 13–16 are Penman/Turtle only.

### Persona / cross-document identity

- New ontology classes and properties: `vso:Persona`, `vso:embodies`,
  `vso:hasInvariant`.
- New SHACL shapes: `vss:PersonaShape`, `vss:EmbodimentConsistencyShape`
  (Warning severity).
- VSON-X handles Personas as Frames: `/Persona @alice_id *hair auburn …`,
  referenced from Entities via `*embodies @alice_id`.

### Caption and FOL renderers

- `tools/render/caption.py`: deterministic graph → English caption,
  fully template-driven, no LLM.
- `tools/render/fol.py`: deterministic graph → Prolog-style
  first-order-logic facts.
- `vson export caption <file>` and `vson export fol <file>` CLI
  subcommands (both Rust shell-outs to the Python renderers).
- Studio "Caption" export tab.
- Frozen ground-truth caption fixtures under `tests/fixtures/captions/`
  for byte-identical CI.

### SHACL profiles

- `shapes/vson-shapes-relaxed.ttl`: authoring-time profile with
  `vss:DirectionalNeedsViewerShape`, the Event/Process/Stative lemma,
  `vss:QualityShape` dimension+value, and `vss:QualityModifierShape`
  demoted to `sh:Warning`.
- The relaxed profile ships as a shapes file only. No `--partial` flag
  exists in the Rust CLI or the Python reference, and no producer emits
  `conformance.profile: "relaxed"` yet; the file is exercised by the
  shapes-gate test in `tests/`.
- `vson validate` is byte-identical to v1.0 (strict profile).

### Ontology gap fixes

- Declared `vso:class` (Entity → IRI) and `vso:modifier` (Quality →
  string), both of which were used in examples but never declared.
- Removed `owl:SymmetricProperty` markings from `vso:near` / `far` /
  `adjacent` / `nextTo` / `facing` — they're values of `vso:proximal`,
  not predicates, so the inference fired on zero triples.

### Tooling

- `tools/vson_x/` package: tokenizer + parser + emitter + cross-syntax
  graph-equivalence helper (`equiv.py`).
- `tools/vson_ast.py`: shared AST types between Penman and VSON-X.
- `vson convert x2t <file.x.vson>` CLI subcommand.
- `make x-check` runs the VSON-X gallery round-trip suite (11 pairs).
- Schema versioning: `tools/schema/vson-output.schema.json` accepts
  `version` ∈ {1.0, 1.0.5, 1.1} and adds optional `vson_x` and
  `conformance.profile` fields.

### Tests

Counts below are as of the v1.1.0 tag; the suite has since grown — run
`make check` and `make cli-check` for current counts.

- 48 Python tests (was 17): + 24 VSON-X (lexer / parser / emitter /
  round-trip), + 7 caption renderer.
- Rust CLI tests expanded across the lib-unit, integration, and golden
  suites.

### Backwards compatibility

- All v1.0 documents validate unchanged under `vson validate`.
- `examples/throne_room.vson` and the original 11 v1.0 gallery scenes
  remain byte-identical; the full 16-scene gallery is SHACL-conformant.
- The v1.0 envelope schema continues to validate (additive change only).

## v1.0.5 — interim

Interim envelope version admitted on the wire: v1.0 plus the caption renderer
and the Phase 0 ontology additions (`vso:class`, `vso:modifier`, `Persona`),
per the `version` field description in
`tools/schema/vson-output.schema.json`. No standalone release notes were kept.

## v1.0 — 2026-05-01 (initial)

Complete redesign. **v0.1 deprecated.**

### Architecture
- Layered specification on RDF-star, OWL 2 RL, SHACL, SPARQL-star.
- Two concrete syntaxes: Turtle-star (VSON-T, canonical) and Penman (VSON-P, authoring).
- Reference Penman ↔ Turtle-star transpiler (stdlib-only Python).

### Ontology (VSO)
- DOLCE-inspired top: `Endurant` / `Perdurant` / `Quality` / `Region`, with `Frame` disjoint from `Entity`.
- Trait-bundle entity model: `individuation × animacy × countability × affordance` orthogonal axes — replaces the v0.1 four-fold sigil mess.
- `Frame` taxonomy: `SceneContext` / `VisualStyle` / `CameraView` / `Composition`.
- Reified-event encoding for actions (fixes v0.1's dyadic-edge defect for arity ≥ 3, modifiers, negation, quantification).
- `SpatialFact` reification with mandatory `viewer` for directionals: directional facts are viewer-anchored by schema — VSON commits to the relative frame of reference (Levinson 2003) and makes the anchor explicit and machine-checkable; intrinsic and absolute frames are out of scope for v1.x. Figure/ground asymmetry follows Talmy.
- RCC-8 spatial topology (8 base relations, JEPD).
- Allen interval algebra (13 base relations with declared inverses and transitivity).
- Schema.org-aligned thematic-role vocabulary on `Event`/`Process`/`Stative`.
- Causal predicates (`causes` / `enables` / `prevents` / `triggers`) distinct from agent-action edges.
- Modal / propositional-attitude classes (`BeliefState`).
- Geometry properties (`bbox2d` / `position3d` / `scale3d` / `rotation` / `occludes`).
- Annotation reification (RDF 1.1-portable equivalent of RDF-star quoted-triple syntax).

### Validation (VSON-S)
- SHACL shapes for `Composition`, `Event`, `Process`, `Stative`, `Quality`, `SpatialFact`, `Negation`.
- `vss:DirectionalNeedsViewerShape` enforces viewer anchoring for directional facts.
- `vss:RccValueShape` constrains RCC-8 values to the eight base relations.
- `vss:FrameNotDepictedShape` keeps the perspectival layer disjoint from depicted entities.
- Trait-property value shapes constrain each trait axis to its published vocabulary.

### Tooling
- Reference Penman parser/emitter with reentrancy, role-routing, RCC/Allen namespace dispatch, and unit-literal handling.
- Makefile target `check` runs ontology parse + Penman round-trip + SHACL conformance + tests.
- 16 tests passing (12 transpiler + 4 SHACL).

### Removed (v0.1 deprecations)
- Eight bracket sigils (`{}` `[]` `<>` `~%$#@`) replaced by Turtle-star and Penman.
- The `K∈{A,P}` edge discriminator, replaced by typed reified nodes (`Event` for action, `Stative` for state, `SpatialFact` for spatial).
- The `void` reserved id (intransitive actions just omit `vso:patient`).
- The decl-vs-ref `:`-presence rule (Turtle's IRI/blank-node rules supersede).
- The folk Object/Item/Unique/Attribute taxonomy (replaced by trait bundles).

### Migration
- Spec section §10 documents v0.1 → v1.0 construct mapping.
