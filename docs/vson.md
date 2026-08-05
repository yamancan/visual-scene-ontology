# VSON v1.3 — Visual Scene Ontology Notation

**Specification, Quick Start, Reference, JSON Schema, and Example Gallery — single document, RFC-style.**

| Field | Value |
|---|---|
| Status | v1.3 stable — vocabulary unchanged from v1.2 (`owl:versionInfo` stays `1.2`); see §8.1 |
| Date | 2026-07-31 |
| Editors | Yamancan (github.com/yamancan) |
| Source repo | this repository (root: `visual-scene-ontology/`) |
| Normative source | this document; `docs/vson-x-semantics.md`; `shapes/vson-shapes.ttl`; `ontology/*.ttl`; `tools/schema/*.json` — ranked in §2 |
| Companion artifacts | `cli/` (Rust binary), `tools/penman/` (Python reference), `examples/gallery/` (16 scenes) |

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** are interpreted per RFC 2119 as updated by RFC 8174 — that is, only when they appear in all capitals.

**Layer names.** `VSO` is the OWL ontology (`ontology/*.ttl`). `VSV` is the closed value vocabularies VSO declares: RCC-8 relations, Allen relations, the directional and proximal values, and the thematic roles — §5.12 lists the enumerations that are closed to producer invention. `VSON-S` is the SHACL shapes layer (`shapes/vson-shapes.ttl`). `VSON-T`, `VSON-P`, and `VSON-X` are the three concrete syntaxes of §4.

---

## Table of contents

1. [Quick Start (image → graph in 60 seconds)](#1-quick-start)
2. [Conformance](#2-conformance)
3. [Concepts](#3-concepts)
4. [Concrete syntaxes](#4-concrete-syntaxes)
5. [Spec reference (per-field)](#5-spec-reference)
6. [JSON Schema and validation rules](#6-json-schema-and-validation-rules)
7. [Exporters](#7-exporters)
8. [Versioning and extension](#8-versioning-and-extension)
9. [Examples gallery (16 scenes)](#9-examples-gallery)
10. [Reference implementations](#10-reference-implementations)
11. [Migration from v0.1](#11-migration-from-v01)
12. [Changelog](#12-changelog)
13. [Teaching an AI image generator](#13-teaching-an-ai-image-generator)
14. [Appendix A — Consolidated JSON Schemas](#appendix-a--consolidated-json-schemas)
15. [Appendix B — Penman EBNF](#appendix-b--penman-ebnf)
16. [Appendix C — Example class profile](#appendix-c--example-class-profile)
17. [Appendix D — VSON-X grammar (normative)](#appendix-d--vson-x-grammar-normative)
18. [Appendix E — Related work and bibliography](#appendix-e--related-work-and-bibliography)

---

## 1. Quick Start

### 1.1 What you upload, what you get back

```
┌────────────┐    image bytes      ┌────────────────┐   JSON envelope     ┌──────────────────┐
│   client   │ ──────────────────▶ │   extractor    │ ──────────────────▶ │     consumer     │
│ (UI / API) │                     │ (web studio /  │                     │ (graph view,     │
│            │                     │  OpenRouter)   │                     │ Cypher, caption) │
└────────────┘                     └────────────────┘                     └──────────────────┘
```

The envelope is a single JSON document conforming to [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json). It carries:

- `vson_p` — Penman authoring text (the canonical authoring artifact; **MAY** be the empty string in a v1.1-or-later envelope whose surface was VSON-X — see §6.1);
- `vson_x` (optional, v1.1+) — the compact sigil form, populated when VSON-X was the authoring surface;
- `vson_t` — Turtle 1.2 / Turtle-star (machine canonical, derivable from whichever authoring surface is populated);
- `graph` (optional) — `{nodes, edges}` projection for UI clients;
- `conformance.conforms` — SHACL pass/fail, always read together with `conformance.profile` (§6.1).

### 1.2 Install

```bash
git clone https://github.com/yamancan/visual-scene-ontology.git && cd visual-scene-ontology
pip install pyshacl rdflib                       # SHACL validator
cd cli && cargo build --release && cd ..         # Rust CLI (~30s cold)
```

### 1.3 First valid output in under 60 seconds

```bash
cli/target/release/vson validate examples/gallery/01_minimal.vson
# Validation Report
# Conforms: True
# OK  examples/gallery/01_minimal.vson

cli/target/release/vson convert p2t examples/gallery/01_minimal.vson
# @prefix vso:   <https://w3id.org/vson/v1/ontology#> .
# @prefix :      <https://example.org/scenes/anonymous#> .
# :scene a vso:Composition .
# :cam a vso:CameraView .
# :cam vso:angle "eye_level" .
# ...

cli/target/release/vson export cypher examples/gallery/01_minimal.vson
# CREATE (scene:Composition {id: 'scene'});
# CREATE (cam:CameraView {id: 'cam'});
# SET cam.angle = 'eye_level';
# ...
```

If the `Conforms: True` line printed, the document is a valid VSON v1.3 scene. **You are done with Quick Start.** The rest of this document is reference material.

### 1.4 First image → graph (preview)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python tools/extractor/baseline/extract.py --live --images path/to/image.jpg
# emits results.csv with one row per image:
#   image, shacl_first_try, shacl_after_retries, retries, latency_ms, ...
```

The studio at [`web/`](../web/) is a static site with no backend: extraction goes from the visitor's browser straight to OpenRouter on the visitor's own key, and validation runs in the browser too — a Pyodide worker executes two of the three gates `vson validate` runs (pyshacl SHACL, then owlrl OWL 2 RL), from the same source files, byte-pinned to the CLI in CI. The third, C2 vocabulary closure (§2), is CLI-only for now, so the studio's verdict is a strict subset of the CLI's. This baseline eval runner calls the Anthropic API directly.

The runner returns a SHACL-conformant `vson_p` string per image. To produce the full envelope from §1.1, wrap that string with the metadata fields described in §6. A reference wrapper (`vson generate <image>`) is planned for a future CLI release; the `cli/` crate versions independently of this spec.

---

## 2. Conformance

A document is a **conformant VSON v1.3 document** iff all of the following hold. C1–C9 are unchanged from v1.2 — a conformant v1.2 document is a conformant v1.3 document, and the reverse, because nothing below moved (§8.1):

| # | Requirement |
|---|---|
| C1 | It is a syntactically valid VSON-T (Turtle 1.2 / Turtle-star) **or** VSON-P (Penman) document per §4. |
| C2 | All IRIs it asserts under the VSO namespace resolve to a class or property declared in [`ontology/vso.ttl`](../ontology/vso.ttl), [`ontology/rcc8.ttl`](../ontology/rcc8.ttl), or [`ontology/allen.ttl`](../ontology/allen.ttl) — no orphan VSO terms. |
| C3 | Its triple set passes SHACL validation against [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) with `inference="rdfs"` and no violations. |
| C4 | Every `vso:Composition` declared in the document carries at least one `vso:depicts` edge. |
| C5 | Every `vso:SpatialFact` carrying a `vso:directional` predicate **MUST** also carry exactly one `vso:viewer` referencing a `vso:CameraView` (viewer anchoring — see §3.3). |
| C6 | Every `vso:Event`, `vso:Process`, and `vso:Stative` carries exactly one `vso:lemma` literal. |
| C7 | Every `vso:Quality` carries exactly one `vso:dimension` and one `vso:value`. |
| C8 | If `vso:rcc` appears, its value **MUST** be one of `rcc:DC`, `rcc:EC`, `rcc:PO`, `rcc:EQ`, `rcc:TPP`, `rcc:NTPP`, `rcc:TPPi`, `rcc:NTPPi`. |
| C9 | `vso:depicts` **MUST NOT** target a `vso:Frame`; frames attach via `vso:framedBy`. |

**Producer conformance.** A producer (extractor, generator, CLI) is conformant iff every document it emits satisfies C1–C9, validated by SHACL before emission.

**Consumer conformance.** A consumer is conformant iff it accepts every document satisfying C1–C9 without modification, and rejects (or flags) documents that do not.

**Claiming conformance.** An implementation claims VSON v1 conformance **by passing the conformance test suite** — [`tests/conformance/manifest.ttl`](../tests/conformance/manifest.ttl), run by `make conformance`. §2.2 defines the claim, what passing the suite establishes, and what it does not. Through v1.3.0 §10 defined a conformant consumer as one that "accepts every document accepted by the Python references plus `pyshacl`": a definition that cannot be checked without running this project's own code, that makes every accident of those implementations normative, and that no second implementer can satisfy except by imitation. §2.2 replaces it. A conformance claim that names no suite run is a claim about C1–C9 that nothing checked, and this specification does not recognize it.

**Verification.** The reference verifier is `cli/target/release/vson validate <file>`. Exit code 0 establishes C1–C9: it parses the document, runs SHACL, and — since v1.3 — runs the C2 vocabulary-closure sweep as a third gate ([`tools/c2_check.py`](../tools/c2_check.py)), which rejects any VSON-namespace IRI the three ontology files do not declare. Exit code 1 means at least one of those failed; the `FAIL` line names which gate. Through v1.2 exit 0 established C1 and C3–C9 only, and C2 was covered by a test that swept this repository's own corpus — a document from anywhere else could mint `vso:Ambience`, pass `vson validate` clean, and be non-conformant. Two things exit 0 still does not establish, neither of them a numbered clause: another verifier's "conformant" verdict says nothing about the OWL 2 RL closure, which no clause requires and which this verifier happens to compute as its second gate (§2.1); and no verdict from any tool says the document corresponds to the image. A third is deliberately not among `validate`'s gates at all — whether a document's spatial relations agree with the `vso:bbox2d` rectangles it asserts beside them. That is `vson verify --geometry` (§5.13), and a document that fails it is still conformant. The same verdict is available in a form a program can act on — one record per violation, with the shape, the focus node and, where it can be established, the line — under `--format json` and `--format sarif` (§5.16); the format changes what a run says and never what it decides.

**Normative precedence.** VSON's normative content is spread across five artifacts. When two of them disagree, the higher entry wins:

1. **this document** (`docs/vson.md`) — the contract;
2. [`docs/vson-x-semantics.md`](./vson-x-semantics.md) — for VSON-X surface semantics only (bearer dispatch, sigil routing, lemma aspect routing);
3. [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) — the SHACL shapes (VSON-S);
4. [`ontology/vso.ttl`](../ontology/vso.ttl), [`ontology/rcc8.ttl`](../ontology/rcc8.ttl), [`ontology/allen.ttl`](../ontology/allen.ttl) — the ontology (VSO/VSV);
5. [`tools/schema/*.json`](../tools/schema/) — the JSON Schemas for the wire envelope and the JSON-LD form.

Any conflict between two entries in this list is a bug. Resolve it by changing the lower-ranked artifact, or — if the lower-ranked artifact is right and this document is wrong — by fixing this document. Do not route around the disagreement.

### 2.1 What conformance establishes

Conformance is not one property. C1–C9 name three separable ones, checked by three different mechanisms, and a passing result establishes only what the mechanism that produced it examined.

| Construct | Mechanism | Clauses |
|---|---|---|
| **Syntactic well-formedness** | the parser for the surface the document is written in — VSON-T (§4.1), VSON-P (§4.2, Appendix B), VSON-X (§4.3, Appendix D) | C1 |
| **Structural well-formedness** | SHACL over [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) at `inference="rdfs"` | C3–C9 |
| **Internal consistency** | the OWL 2 RL closure of the document plus the TBox, checked for disjointness clashes ([`tools/owlrl_check.py`](../tools/owlrl_check.py)) | none — see below |

**Syntactic well-formedness.** The bytes parse into one RDF graph under the surface the document declares. A conformant document **MUST** parse (C1). Parsing establishes nothing about what the resulting graph says: a document asserting `vso:rcc "banana"` is syntactically well-formed, and so is one that describes the same object twice under two names.

**Structural well-formedness.** The parsed graph satisfies the shapes — the required edges are present, the cardinalities hold, the closed vocabularies of §5.12 are respected, and a directional fact carries its viewer (§3.3). A conformant document **MUST** satisfy C3–C9 with no violation. This is a statement about graph shape and about the value spaces §5 defines, and about nothing else: a value no shape constrains is unexamined, and a structurally well-formed document **MAY** carry any of them. Where a clause is stated more tightly than the shape that enforces it, the clause is the requirement and the shape is incomplete. Through v1.2 that gap was wide — a bounding box, a confidence and a lemma were all unexamined, so `vso:bbox2d "banana"` and `vso:confidence "7.3"` passed, and two clause gaps were open on top: C5's *exactly one* `vso:viewer` and C6's *exactly one* `vso:lemma` on `vso:Process` and `vso:Stative` were enforced as *at least one*. v1.3 closed all of them under §8.2 without changing a clause. What remains unexamined is listed there too: the §5.3.1 / §5.3.3 value lists, Entity trait completeness (§5.4), and the free-form `vso:value` literal.

**Internal consistency.** The OWL 2 RL closure of the document together with the ontology contains no individual inferred into two classes VSO declares disjoint. This is the document's agreement with itself and with the TBox, and it is the one construct **no numbered clause requires**: C1–C9 do not mention it, while `vson validate` runs it as its second gate — the SHACL gate runs at `inference="rdfs"`, which does not process `owl:disjointWith` and therefore cannot see those clashes. A document **MAY** satisfy C1–C9 and still be OWL 2 RL inconsistent. A verifier **SHOULD** run this gate too, and a consumer **MUST NOT** read "conformant" as meaning the closure was computed.

C2 belongs to none of the three. It is a **vocabulary-closure** property — no orphan VSO terms — and it is a question about the *ontology*, not about the document's graph: deciding it needs the set of terms VSO declares, which is neither in the shapes nor derivable from the document. That is why no shape carries it and no OWL rule reports it (an undeclared IRI is perfectly consistent; it is merely not VSON's). Since v1.3 `vson validate` decides it directly, as a third gate ([`tools/c2_check.py`](../tools/c2_check.py)) sweeping every triple position for a VSON-namespace IRI the three ontology files never declare. The gate reads *declared* in the weakest sense the clause admits — the ontology states anything at all about the term — which makes it, if anything, more permissive than C2 as written ("a class or property"): individuals such as `vso:above` and `rcc:DC` are declared terms here. That direction is the safe one; §8.2 forbids the other. A verifier that runs only SHACL establishes C1 and C3–C9 and **MUST NOT** report C2.

**None of the three establishes correspondence to the image.** Nothing in this specification reads pixels. A document asserting a red cube left of a blue sphere, describing a photograph that contains neither, parses, satisfies every shape, and has a clash-free closure: fully conformant, entirely false. Producers, consumers, exporters, and user interfaces **MUST NOT** describe a conformant document as accurate, correct, faithful, or verified against the image, and **MUST NOT** present a passing result as evidence that a claim about the depicted scene is true. A tool reporting one pass/fail verdict **SHOULD** name the constructs it checked.

**The absent construct is groundedness** — the property that each assertion in a document corresponds to what the image depicts. VSON v1.x defines no groundedness check, ships no groundedness evidence, and makes no groundedness claim. Establishing it would take at least two things this repository does not have:

1. **A geometry consistency decision.** Where a document already carries the geometry of §5.10, agreement between that geometry and the relations asserted over it is decidable *inside the document*: a `vso:bbox2d` rectangle bounds the region it is asserted of, which is enough to refute a claim of containment or contact that the two rectangles cannot support, and their centroids under the viewer's `vso:CameraView` decide the directional values §3.3 anchors. A document whose `vso:rcc` contradicts its own boxes is ungrounded in a way that needs no image to detect. **Since v1.3 this one is checked** — §5.13 defines the decision procedures and `vson verify --geometry` runs them. It is a separate command and not a `validate` gate, because it decides no numbered clause: a document that fails it is still conformant.
2. **Ground truth for what geometry cannot decide.** Class, dimension values, lemmas, thematic roles, and frame attributions do not follow from boxes. Evidence for those means comparison against human annotation over a fixed image set, with a published protocol and a reported inter-annotator agreement figure. No such corpus, protocol, or figure exists in this repository. What v1.3 adds is the **instrument** and not the measurement: §5.15 defines the triple-level agreement metric such a figure would be computed *with*, and `vson diff` runs it. A metric is not evidence — the corpus, the protocol and the annotators are still absent, and an agreement number between two model runs says nothing about either one's correspondence to the image.

The second does not exist, so groundedness does not. **Verified** in VSON means *verified against the schema* — and, where §5.13 can reach, that a document does not contradict its own geometry. Neither is a reading of the picture, and any stronger claim is unsupported by anything this project ships.

### 2.2 Claiming conformance — the test suite

An implementation **claims VSON v1 conformance by passing the conformance test suite**. The suite is [`tests/conformance/manifest.ttl`](../tests/conformance/manifest.ttl), an RDF manifest in the form of the [W3C SHACL test suite](https://w3c.github.io/data-shapes/data-shapes-test-suite/): every entry names an input document (`mf:action`) and the verdict that document **MUST** get (`mf:result`). A claimant **MUST** state the suite version it ran (`owl:versionInfo` on the manifest), the entries it did not pass, and the engine it ran them with. A claim naming no version is not checkable and **MUST NOT** be published.

**Why this and not the reference implementations.** Through v1.3.0 §10 defined reference-conformance as agreement with `vson_penman.py`, `vson_x.py` and `pyshacl`. That definition has three defects a specification cannot carry: it is unfalsifiable without this repository, it promotes every bug and every undocumented tolerance of the reference to normative status, and it gives a second implementer no target except imitation. The suite is the repair — a list of documents and verdicts that any implementation in any language can be run against, including this one.

**The five test types.** SHACL's own suite has vocabulary for one of them, so four are declared locally in [`tests/conformance/vocabulary.ttl`](../tests/conformance/vocabulary.ttl) under `https://w3id.org/vson/v1/conformance#`.

| Type | `mf:action` | `mf:result` |
|---|---|---|
| `vsont:ParsePTest` | a VSON-P source (§4.2, Appendix B) | `vsont:Accepted`, or the reference parser's rejection message |
| `vsont:ParseXTest` | a VSON-X source (§4.3, Appendix D) | `vsont:Accepted`, or the §D.7 row identifier it **MUST** be rejected at |
| `vsont:ValidationTest` | a document plus a shapes graph | a `sh:ValidationReport` with `sh:conforms` and, per result, `sh:sourceShape` / `sh:focusNode` / `sh:resultPath` / `sh:sourceConstraintComponent` / `sh:resultSeverity` |
| `vsont:EquivalenceTest` | one or more documents | the RDFC-1.0 canonical hash of §4.6 all of them **MUST** have |
| `vsont:ExportTest` | a document plus an exporter (§7) | the byte-frozen output |

Four properties of the pinning are normative, because an implementation has to know what it is being held to.

1. **A result names its *named* source shape.** VSON-S states its cardinality and value-space constraints as `sh:property` blank nodes nested inside named node shapes, and a blank node has no identity across runs. A result is therefore matched against the nearest named ancestor shape. An implementation whose report names the inner property shape is not non-conformant; the suite resolves upward before comparing.
2. **Expected results are exhaustive.** A document pinned with one `sh:result` **MUST** produce exactly one. A shape that fires more often than the manifest says is a failure, which is the only way an over-broad shape gets caught at all.
3. **Where the focus node is a blank node**, `vsont:focusNodeKind` is pinned instead of an identity the transpiler mints per parse.
4. **A §D.7 identifier is checked, not trusted.** The runner extracts §D.7's own message column out of this document at run time and requires the raised message to match exactly one row. A manifest cannot pin a row this specification does not define, and a row whose message moves here moves there in the same commit.

**What passing establishes.** Exactly what §2.1 says the three constructs establish, over the documents in the manifest — and nothing about documents outside it. The suite is a lower bound on correctness: it is a finite list, and an implementation that passes every entry may still disagree with this specification on a document nobody wrote down. It reads no image, and §2.1's prohibition is unchanged: a passing suite run is not evidence that any document corresponds to any picture.

**Per-clause coverage.** The table below is **generated** from the manifest by `python3 -m tools.conformance_runner --coverage-table` and compared against this copy on every run, so this section cannot claim coverage the suite lacks. It gives counts rather than identifiers, because a row listing a hundred test names is a row nobody reads; `--coverage-map` prints the other half — every clause and section with the entry ids that cover it, from the same fields, so the two cannot disagree. The table is scoped to C1–C9 and the numbered §5/§6 subsections; entries also tag §2.1, §3.x, §4.x, §7, §9.x and the appendices, and the map shows those rows too. `+` counts entries whose expected verdict is acceptance or conformance, `−` counts entries that **MUST** be rejected. **Enforced by** is derived from the negative entries: it names the gate that actually does the rejecting, and a row with no negative entry reads `no gate` — the specification says something about that section and nothing in the conformance surface refuses a document that contradicts it.

<!-- conformance-coverage:begin -->
| Clause / section | Entries | + | − | Enforced by |
|---|---|---|---|---|
| C1 | 104 | 73 | 31 | parser |
| C2 | 32 | 30 | 2 | C2 gate |
| C3 | 73 | 38 | 35 | SHACL + C2 gate |
| C4 | 31 | 30 | 1 | SHACL |
| C5 | 9 | 5 | 4 | SHACL |
| C6 | 11 | 7 | 4 | SHACL |
| C7 | 7 | 5 | 2 | SHACL |
| C8 | 6 | 5 | 1 | SHACL |
| C9 | 4 | 3 | 1 | SHACL |
| §5.1 | 1 | 0 | 1 | C2 gate |
| §5.2 | 9 | 4 | 5 | SHACL |
| §5.3 | 5 | 3 | 2 | SHACL |
| §5.4 | 10 | 7 | 3 | SHACL |
| §5.5 | 9 | 4 | 5 | SHACL + C2 gate |
| §5.6 | 14 | 6 | 8 | SHACL |
| §5.7 | 10 | 4 | 6 | SHACL |
| §5.8 | 1 | 1 | 0 | no gate |
| §5.9 | 1 | 1 | 0 | no gate |
| §5.10 | 8 | 4 | 4 | SHACL |
| §5.11 | 13 | 7 | 6 | SHACL |
| §5.12 | 14 | 5 | 9 | SHACL + C2 gate |
| §5.13 | 3 | 3 | 0 | no gate |
| §5.14 | 0 | 0 | 0 | — |
| §5.15 | 0 | 0 | 0 | — |
| §5.16 | 0 | 0 | 0 | — |
| §5.17 | 0 | 0 | 0 | — |
| §5.18 | 0 | 0 | 0 | — |
| §6.1 | 0 | 0 | 0 | — |
| §6.2 | 0 | 0 | 0 | — |
| §6.3 | 0 | 0 | 0 | — |
<!-- conformance-coverage:end -->

**What is not covered, and why.** Eight numbered sections have no entry, and the reason is the same for all of them: they do not state a property of a *document*. §5.14 (competency questions), §5.15 (graph agreement), §5.16 (machine-readable reports) and §5.18 (the MCP tool surface) constrain what a *tool* does, and are gated by `make cq-check`, `tests/test_smatch.py`, `tests/test_validate_report.py` and `tests/test_mcp_server.py`. §5.17 (external alignment) constrains an artifact no gate loads and no document can violate — a conformant document is conformant whether or not the alignment layer exists — and is gated by `tests/test_alignments.py`. §6.1 and §6.2 are the extractor envelope's JSON Schema, whose corpus is gated by `make envelope-check` — a JSON-Schema test type is a possible v1.4 addition and does not exist. §6.3 is a reference table of the shapes, not a constraint. Two further gaps are properties of the artifacts rather than of the suite, and are recorded where they live: `vss:DepictsEntityShape` is **vacuous** under C3's `inference="rdfs"` — `vso:depicts` declares `rdfs:range vso:Entity`, so the RDFS closure asserts the very type the shape checks, no document can fail it, and the manifest records it under `vsont:CoverageExemptions` with an entry pinning that a depicted `vso:SpatialFact` conforms; and Appendix B declares **no numbered parse-error set**, so VSON-P rejections are pinned by the reference parser's message where VSON-X rejections are pinned by a §D.7 identifier. The second is a weaker guarantee by exactly the amount this specification is weaker.

**One engine.** The suite runs against one SHACL implementation, `pyshacl`, which is also the one the reference verifier uses. That is a real limit on what a passing run means: it establishes that the *shapes* accept and reject these documents *as pyshacl reads them*, not that a second implementation reads them the same way. The runner carries an `--engine` seam and a documented adapter protocol for exactly that reason, and `--engine <name>` for an unregistered name exits 2 rather than falling back — a run that did not cross-validate never reports that it did. No second adapter ships: every available implementation (Apache Jena, RDF4J, TopBraid) needs a JVM and a downloaded distribution, which `make check` may not assume on a contributor's machine. The slot is open and the gap is stated rather than papered over.

**Adding entries inside v1.x.** §8.2 governs. An entry may be added when the verdict it pins is one this specification already requires; an entry that would make a previously-conformant document fail is the tightening §8.2 forbids, whatever severity it pins. The suite's own version (`owl:versionInfo`, `1.0.0` at v1.3) moves on its minor when entries are added and on its major when a pinned verdict changes meaning.


---

## 3. Concepts

### 3.1 The five node kinds

| Kind | Examples | Purpose |
|---|---|---|
| **Frame** | `Composition`, `SceneContext`, `CameraView`, `VisualStyle` | Perspectival, authorial, or stylistic context. Scopes other content. |
| **Entity** | `PhysicalObject`, `Aggregate`, `Substance` | What the scene is "about" — depicted things. |
| **Quality** | dimension/value pair | Reified property (`color=red`, `affect=joyful`, `material=gold`). |
| **Perdurant** | `Event`, `Process`, `Stative` | Reified action/state. Carries thematic roles. |
| **SpatialFact** | viewer + figure + ground + RCC + directional | Reified spatial relation; directional facts require a viewer. |

Underneath those five kinds, [`ontology/vso.ttl`](../ontology/vso.ttl) declares a **DOLCE-inspired top-level taxonomy** — `vso:Endurant` / `vso:Perdurant` / `vso:Quality` / `vso:Region`, declared pairwise disjoint — after Masolo et al. 2003 ([Appendix E](#appendix-e--related-work-and-bibliography)). *Inspired*, not aligned: VSON reuses the four category names and the endurant/perdurant cut, but hangs all four under `vso:Entity` (DOLCE puts regions under `Abstract`), imports no DOLCE IRI, and asserts no DOLCE axiom. Nothing in this document depends on a DOLCE reasoner.

### 3.2 Trait-bundle entity model

A v0.1 "Object" / "Item" / "Unique Object" / "Attribute" sigil mess is replaced by four orthogonal trait axes attached to every Entity:

```
individuation × animacy × countability × affordance
```

Translate:

| v0.1 idea | v1.0 trait bundle |
|---|---|
| "Generic object" | `individuation=Generic, animacy=Inert, countability=Count` |
| "Named character (Alice)" | `individuation=Named, animacy=Agentive, countability=Count` |
| "A handful of grain" | `individuation=Generic, countability=Mass` (Substance) |
| "A holdable item" | any class with `affordance ⊇ {Holdable}` |

### 3.3 Viewer anchoring (directional facts)

"The lamp is to the left of the chair." Left from whose vantage? Without a viewer, the assertion is ambiguous. **VSON enforces an explicit viewer at the schema level**: any `vso:SpatialFact` carrying a `vso:directional` value **MUST** also carry exactly one `vso:viewer` pointing at a `vso:CameraView`. Symmetric/topological facts (`rcc:EC`, `rcc:DC`) do not need a viewer.

Directional facts are viewer-anchored by schema — VSON commits to the relative frame of reference (Levinson 2003) and makes the anchor explicit and machine-checkable; intrinsic and absolute frames are out of scope for v1.x. Figure/ground asymmetry follows Talmy 2000: `vso:figure` is the located thing, `vso:ground` the reference thing, and the two slots are not interchangeable. Both citations are in [Appendix E](#appendix-e--related-work-and-bibliography). (Shapes, tests, and tooling comments in this repository call the constraint "Talmy resolution" for historical reasons; the mechanism is the one described here.)

**What is new here, stated narrowly.** Neither half of this design is an invention of this project, and earlier drafts of this document and of the README implied otherwise. Reifying a spatial relation with distinct, required figure and ground slots is standardized practice: ISO 24617-7:2020 requires a link structure to carry a relation type and two arguments, and names those two `@figure` and `@ground` in the revised movement link; the SemEval-2012 spatial-role-labeling task ran on the same asymmetry under the names *trajector* and *landmark* ([Appendix E.7](#appendix-e--related-work-and-bibliography)). Anchoring a directional relation to a frame of reference is Levinson's analysis, not a schema decision. What VSON contributes is narrower and checkable: it **fixes one of the three frames** rather than annotating which one is in use, and it makes the anchor a **structural obligation a validator enforces** — C5, `vss:DirectionalNeedsViewerShape`, a document rejected with an exit code — rather than an annotation guideline a human is asked to follow. The value of that is not novelty; it is that "which viewer?" stops being answerable by reading the annotator's mind. [Appendix E.7](#appendix-e--related-work-and-bibliography) states what each prior scheme does that this one does not.

### 3.4 Reification — the universal pattern

If you might want to negate it, modify it, quantify it, refer to it, or attach a probability — make it a node, not an edge. Six places where v1.0 reifies what v0.1 left as edges or attributes:

- Action → `Event` / `Process` / `Stative` node + thematic roles;
- Property → `Quality` node + dimension/value;
- Spatial relation → `SpatialFact` node + figure/ground/rcc/directional/viewer;
- Negation → `Negation` node;
- Belief / propositional attitude → `BeliefState` node;
- Annotation (probability, source, confidence) → `Annotation` node (RDF 1.1-portable) **or** an RDF-star quoted-triple `<<s p o>> :prob "0.9"^^xsd:decimal` (canonical when a Turtle-star parser is available).

---

## 4. Concrete syntaxes

VSON has three surface syntaxes that share one abstract graph: VSON-T (canonical, machine), VSON-P (Penman, human authoring), and VSON-X (compact sigil-based, LLM-optimized — added in v1.1). "Share one abstract graph" is not a figure of speech: **§4.6 defines when two documents denote the same scene**, and every claim of interchangeability below is a pair of equal canonical hashes in [`tests/fixtures/canonical/hashes.txt`](../tests/fixtures/canonical/hashes.txt). VSON-T and VSON-P are graph-equivalent across all 16 gallery scenes. VSON-X counterparts exist for 12 of them — scenes 01–12 — and all twelve canonicalize to the same bytes as their Penman twins (§4.3, §4.6, §9.17). Scenes 13–16 are Penman/Turtle only.

### 4.1 VSON-T (Turtle-star canonical, machine)

VSON-T is **W3C Turtle 1.2 with RDF-star quoted triples**, no syntactic deviation. Producers MUST be valid Turtle 1.2; consumers SHOULD use a standard Turtle parser (rdflib, Apache Jena, oxigraph). Canonical media type: `text/turtle`.

### 4.2 VSON-P (Penman authoring, human)

VSON-P is a Penman-style nested syntax (the same family used by AMR), tuned to the VSV vocabulary. Form:

```ebnf
document   = node ;
node       = "(" var [ "/" Concept ] role* ")" ;
role       = ":" name term ;
term       = node | var | literal ;
literal    = quoted-string | number | unit | bareword ;
var        = ID ;
Concept    = ID ;
name       = ID ;
ID         = /[A-Za-z_][\w-]*/ ;
```

Reentrancy: a `term` that is a bare `var` (no `/`) refers to a previously-declared node. Forward references are allowed; the transpiler does a pre-pass to register all declared variables before emission.

The reference transpiler is [`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py); the Rust port is [`cli/src/penman/`](../cli/src/penman/). Both consume [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json) as their single source of truth, so they cannot drift.

### 4.3 VSON-X (compact sigil-based, LLM-optimized) — v1.1

VSON-X is a bracket-free sigil syntax targeting LLM emission and human authoring. Nine sigils, bearer-class dispatch, newlines insignificant. Canonical media type: `text/vson-x` (proposed). File extension: `.x.vson` (the `.vson` suffix is preserved so the file still reads as a VSON document; the `vson` CLI selects the surface form by subcommand — `convert x2t` — not by sniffing the extension).

This section is the overview. The **normative grammar** — lexical productions, syntactic productions, the closed token vocabularies, and the complete parse-time error set — is [Appendix D](#appendix-d--vson-x-grammar-normative), reconciled line by line against the reference parser [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py). The per-key routing rationale is [`docs/vson-x-semantics.md`](./vson-x-semantics.md).

**Sigil set (closed):**

| Sigil | Kind | Example |
|---|---|---|
| `~` | Composition root | `~scene` |
| `/` | Concept marker | `/PhysicalObject`, `/CameraView` |
| `@` | Named/Skolem handle | `@alice`, `@cam` |
| `*` | Quality kv / direct property / role arg | `*color red` |
| `>` | Stative role-edge | `@bob > hold sword` |
| `>>` | Event/Process role-edge | `@bob >> strike boar *instrument sword` |
| `!` | Asymmetric SpatialFact | `crown ! EC @alice ^cam *dir above` |
| `&` | Symmetric SpatialFact (emits 2 nodes, figure/ground swapped) | `a & near & b` |
| `^` | Viewer anchor | `^cam` |

**Item boundaries.** Newlines are insignificant — no syntactic production has a NEWLINE terminal (the only line break the lexer notices is the one that ends a `#` comment). A new item begins when the parser sees a lead token at top level (`~`, `/Concept`, `^`, or a handle followed by `/`, `>`, `>>`, `!`, or `&`), so a single declaration may span several lines with arbitrary indentation, and a whole scene may equally be written on one line. Full rule and lookahead budget: [Appendix D](#appendix-d--vson-x-grammar-normative) §D.4; rationale in [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §3.7.

**Bearer-class dispatch for `*K V`** (the central rule):

| Bearer (LHS) | `*K V` is interpreted as |
|---|---|
| Composition (`~scene`) | Quality node (`vso:hasQuality`), with one exception: `*rendersAs` is a direct property |
| Frame (`/CameraView`, `/VisualStyle`, `/SceneContext`) | Direct property on the Frame |
| `/Persona` Frame | `vso:hasInvariant`-attached Quality node |
| Entity (`/PhysicalObject`, `/Aggregate`, `/Substance`) | Quality node (`vso:hasQuality`), with seven exceptions: `*class`, `*bbox2d`, `*position3d`, `*scale3d`, `*rotation`, `*visibleFraction`, `*embodies` are direct properties |
| Perdurant arglist (after `>` / `>>`) | Thematic role; the value is either a ref (entity) or a literal (e.g. `*manner swift`) |
| SpatialFact arglist (after `!`) | Direct property on the SpatialFact (`*dir above`, `*viewer @cam`) |

**Symmetric-by-construction.** The `&` form `a & near & b` MUST emit two SpatialFact nodes with figure/ground swapped (one with `figure=a, ground=b` and one with `figure=b, ground=a`), each with `vso:proximal=near`. This closes v0.1's asymmetry-by-fiat bug at the syntax level. The ontology's `vso:proximal` enum is the five-value closed list of §5.12; VSON-X's `&` form admits the three symmetric members of it (`near`, `far`, `adjacent`) — `next_to` and `facing` are proximal values but are not `&` lemmas in v1.1. Symmetric lemma with `!` (asymmetric form) is a parse error.

**Viewer anchoring.** `! ... *dir X` without a `^viewer` anchor is a parse error (matches the SHACL `vss:DirectionalNeedsViewerShape` constraint at the syntax layer).

**Lemma → kind table** (as shipped in [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py); see [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §5 for the rationale):

- Stative: `hold`, `wear`, `carry`, `own`, `sit`, `stand`, `lie`, `lean`, `look_at`, `gaze_at`, `see`, `hear`, `know`, `believe`, `intend` (signature: holder/experiencer + theme/stimulus).
- Event: `strike`, `throw`, `fall`, `give`, `send`, `arrive`, `depart`, `break`, `catch`, `drop`, `charge` (signatures: agent + theme/patient + recipient/etc.).
- Process: `run`, `walk`, `swim`, `fly`, `dance`, `burn`, `bleed`, `flow`, `pour` (signatures: agent/patient + theme).
- Symmetric proximal: `near`, `far`, `adjacent` (used only in `&` form). This list **is** closed — an unlisted `&` lemma is a parse error.

The three perdurant lists are routing tables, not a closed vocabulary: a lemma absent from all three is accepted and routed to a default signature (`>` → Stative with holder + theme; `>>` → Event with agent + patient). `>` with an Event/Process lemma OR `>>` with a Stative lemma is a parse error.

**Reference implementation:** [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py). Native Rust parser planned for v1.2; until then `vson convert x2t` shells out to Python.

**Round-trip parity.** Gallery scenes 01–12 have an [`examples/gallery-x/N.x.vson`](../examples/gallery-x/) form (12 files), and every one of them **denotes the same scene as its Penman twin under §4.6** — identical RDFC-1.0 canonical N-Quads, frozen in [`tests/fixtures/canonical/hashes.txt`](../tests/fixtures/canonical/hashes.txt) and checked by [`tests/test_canon.py`](../tests/test_canon.py) inside `make check`. `make x-check` decides the same twelve pairs the fast way, by isomorphism after the same two normalizations ([`tools/vson_x/equiv.py`](../tools/vson_x/equiv.py), which imports them from [`tools/canon.py`](../tools/canon.py)). Scenes 13–16 are Penman/Turtle only: VSON-X v1.1 has no notation for the propositional layer (§5.9) or for annotation reification (§5.11).

### 4.4 JSON-LD form

A VSON document MAY be exchanged as JSON-LD bound to context `https://w3id.org/vson/v1/context.jsonld`. Structural skeleton in [`tools/schema/vson-jsonld.schema.json`](../tools/schema/vson-jsonld.schema.json). Well-formedness is enforced by SHACL on the materialized graph, not by JSON Schema alone.

### 4.5 Image-extractor envelope (the Quick Start payload)

The wire format between an image-to-VSON extractor and its consumer is the JSON envelope in [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json). See §6.1 for the per-field reference. Every field is also annotated with its JSON Schema fragment in §6.

### 4.6 Denotation — when two documents describe the same scene

Three surfaces for one graph is the premise of this whole section, and "the same graph" is the claim it rests on. Through v1.3.0 the only thing standing behind that claim was a test helper whose own docstring called itself a test-only utility. A helper can decide a case; it cannot say what the case *is*, it cannot be cited, and it leaves a second implementer with nothing to reproduce. This section says what the case is, in terms a second implementer can check without reading any of this repository's code.

**The canonical form of a document** is computed in four steps, in order.

1. **Materialize.** Parse the document under the surface it is written in (§4.1–§4.3) into one RDF graph. Everything below is defined over that graph, so the surface cannot affect the answer — which is the property the section exists to establish. **Asserted triples only**: no entailment regime, no reasoner, no TBox, as in §5.14 and §5.15.
2. **N1 — anonymize.** Replace every IRI that begins with the **document namespace** and that the document types as one of the classes in the table below with a **fresh blank node**, one per IRI. The map is injective by construction: N1 loses names and can never merge two nodes the document kept apart.
3. **N2 — normalize the Composition edges.** Rewrite `vso:hasFact` and `vso:occurs` to `vso:depicts`. §5.2 declares the three interchangeable for the same target, and the VSON-X parser emits only the first; a scene written with `:hasFact` in one surface and `:depicts` in another is not a disagreement this specification recognizes. §5.15.1 normalizes the same three the same way for the same reason.
4. **Canonicalize.** Serialize the result under **RDFC-1.0** — *RDF Dataset Canonicalization*, W3C Recommendation 2024-05-21 ([Appendix E.6](#appendix-e--related-work-and-bibliography)) — with its default hash algorithm SHA-256, in the canonical N-Quads form of Appendix A of that Recommendation. A VSON document is one RDF graph, which is the dataset whose default graph it is and which has no named graphs, so the graph-name position is empty in every quad.

The **document namespace** is what `:` resolves to — the namespace bound to the empty prefix — falling back to the document's base IRI. A document with neither has no document namespace, and N1 rewrites nothing in it.

> Two VSON documents **denote the same scene** if and only if their canonical forms are byte-identical.

A document's **canonical hash** is the lowercase-hex SHA-256 of its canonical form. The hash is a convenience for reporting and for freezing; the definition is the bytes.

**The anonymized classes (closed list).**

| Anonymized by N1 | Why |
|---|---|
| `vso:Quality`, `vso:SpatialFact`, `vso:Event`, `vso:Process`, `vso:Stative`, `vso:Annotation`, `vso:Negation`, `vso:BeliefState`, `vso:Quantification` | The reification nodes of §3.4. No surface asks the author to name one: VSON-P's `(q1 / Quality …)` needs a variable because Penman syntax needs a variable, and the VSON-X parser mints `_q1` and emits a blank node. A name no author chose cannot be evidence that two documents disagree. |
| `vso:SceneContext`, `vso:VisualStyle` | Frames a document attaches only by `vso:framedBy`. Their scene properties carry the meaning; the IRI is a Penman authoring convention. |

Three exclusions are load-bearing. **`vso:CameraView` is not anonymized**: a camera is a referent — `vso:viewedBy` and `vso:viewer` point at it (C5, §3.3) — and every surface makes the author name it (`^cam`). **`vso:Persona` is not anonymized**: it is the cross-document identity carrier of §9.12, and erasing its name would erase what it is for. **Entities and `vso:Composition` are not anonymized**: they are what the document is about. A producer that needs a node of an anonymized class to be referenceable from *outside* the document **MUST** mint it outside the document namespace — N1 does not reach IRIs in another namespace.

**What this rule deliberately does not normalize.**

- **Names.** Two documents that name the same queen `:alice` under two different bases denote **different** scenes here, and that is the intended reading: an IRI is a name, and this is the exact test. §5.15 is the graded instrument for the question this one cannot answer — it compares document-local IRIs by local name and reports how far apart two documents are. The implication runs one way only: equal canonical forms ⇒ F1 = 1.0, and F1 = 1.0 does **not** imply equal canonical forms. [`tests/test_canon.py`](../tests/test_canon.py) pins both directions.
- **Entailment.** `owl:sameAs`, subclass closure, and everything else a reasoner could derive are out of scope, exactly as in §5.15.1.
- **Literal lexical forms.** RDF 1.1 literal term equality is lexical, so `"01"^^xsd:integer` and `"1"^^xsd:integer` are distinct terms and therefore distinct scenes. This is inherited from RDF, not chosen here, and it has an implementation consequence worth knowing: a parser that normalizes lexical forms (rdflib rewrites `"…Z"^^xsd:dateTime` to `"…+00:00"`) canonicalizes the normalized form, so two implementations agree on a document only to the extent their parsers preserve what it wrote.
- **RDF-star.** RDFC-1.0 is defined over RDF 1.1 datasets and does not cover quoted triples. A document using the Turtle 1.2 `<< s p o >>` form **MUST** be reduced to its RDF 1.1 portable form — the `vso:Annotation` reification of §5.11 — before canonicalization. No gallery scene uses quoted triples, so no hash frozen below depends on this clause.

**Which algorithm is actually running.** rdflib 7.6 ships **no** RDFC-1.0. What `rdflib.compare` implements is **RGDA1** (McCusker 2015): a different digest algorithm that decides isomorphism correctly but issues different blank-node labels and produces no canonical N-Quads document, so nothing frozen against it would be reproducible from the Recommendation. **URDNA2015**, the algorithm most JSON-LD toolchains ship, *is* RDFC-1.0 up to the canonical N-Quads escaping clarification recorded in Appendix B of the Recommendation, and agrees with it on every document that avoids the control characters where the two escaping rules differ — which is every VSON document in this repository. The reference implementation therefore carries its own RDFC-1.0, in [`tools/canon.py`](../tools/canon.py), which uses rdflib only to parse. Its RDFC-1.0 core is vocabulary-blind and is checked against the worked examples published *in* the Recommendation — the canonical labels, the first-degree hashes and the N-degree hash of §4.4.2, §4.6.2 and §4.8.2 — because a canonicalizer that agrees with itself has established nothing.

Those examples are in the checkout, so `make check` runs them. The **published test suite** is not: it is fetched, which puts it on the same terms as `make live-check` — a separate target, `make rdfc10-suite` ([`scripts/check_rdfc10_suite.py`](../scripts/check_rdfc10_suite.py)). Measured 2026-08-01 over its 65 runnable entries — the 64 eval tests, plus the poison dataset that §7.1 of the Recommendation requires an implementation to refuse: **62 match byte for byte**, including the SHA-384 entry and every named-graph case, **3 differ only in a literal rdflib rewrote on the way in** (proved rather than asserted — re-parsing the published expected output through the same parser reproduces exactly the bytes the input produced, so the canonical labelling agreed), and the suite's 21 map tests are unrunnable here because they key on input blank-node labels, which rdflib does not preserve.

**What equality establishes.** That the two documents assert the same graph after N1 and N2. Three things do not follow. It is **not conformance** — C1–C9 do not mention denotation, and two documents can denote the same scene and both fail every shape. It is **not correctness**: §2.1 governs, no image is read, and two runs of one model agreeing on the same hallucination are equal here. And it is **not a licence to discard either document** — the surfaces differ in what they are good for (§4.1–§4.3), not only in their bytes.

**Where it runs, and what is frozen.** [`tests/fixtures/canonical/hashes.txt`](../tests/fixtures/canonical/hashes.txt) carries the canonical hash of all 29 shipped documents — the 16 gallery scenes in VSON-P, the hand-authored VSON-T throne room, and the 12 VSON-X counterparts — and [`tests/test_canon.py`](../tests/test_canon.py) recomputes every one of them inside `make check`. A change to a transpiler, an emitter or a scene that alters what a document denotes turns the gate red; one that only alters how a document is written does not, which is the distinction a frozen hash exists to draw.

The cross-syntax claim is read straight off that table: **each of the twelve VSON-P scenes that has a VSON-X counterpart carries the identical hash in both surfaces** — twelve of twelve pairs, over twelve of the sixteen gallery scenes. Scenes 13–16 have no VSON-X form because VSON-X v1.1 has no notation for the propositional layer (§5.9) or for annotation reification (§5.11), so nothing is claimed for them. [`tests/fixtures/canonical/11_throne_room.nq`](../tests/fixtures/canonical/11_throne_room.nq) freezes one canonical form as bytes rather than as a hash: it is the 131-triple throne room, and the test requires *both* surfaces to produce exactly those bytes, so the cross-syntax claim is a file a reader can open. `tools/vson_x/equiv.py` — the fast isomorphism heuristic `make x-check` runs over the same pairs — applies N1 and N2 by importing them from `tools/canon.py` and is checked against this section's answer on every pair.

The gate is not vacuous in the other direction either: `examples/throne_room.ttl` and `examples/gallery/11_throne_room.vson`, the two documents in this repository that both claim to be the throne room, have **different** canonical hashes. §5.15.6 reports how different (F1 0.767) and why.

---

## 5. Spec reference

Per-field template:

> **`field_name`** *(type, required?)*
> — short description.
> **JSON Schema fragment.**
> **Validation rule.** SHACL shape or other constraint.
> *Example.*

### 5.1 Namespaces

| Prefix | IRI | Purpose |
|---|---|---|
| `vso:`   | `https://w3id.org/vson/v1/ontology#` | Core ontology and vocabulary |
| `vss:`   | `https://w3id.org/vson/v1/shapes#`   | SHACL shape names |
| `rcc:`   | `https://w3id.org/vson/v1/rcc8#`     | RCC-8 base relations |
| `allen:` | `https://w3id.org/vson/v1/allen#`   | Allen interval relations |
| `xsd:`   | `http://www.w3.org/2001/XMLSchema#` | Datatypes |
| `rdf:`   | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` | RDF |
| `rdfs:`  | `http://www.w3.org/2000/01/rdf-schema#` | RDFS |
| `sh:`    | `http://www.w3.org/ns/shacl#`   | SHACL |
| `:`      | `https://example.org/scenes/anonymous#` (default; consumers MAY override) | Document-local |

**Preferred prefix — `vson:`, while every document keeps writing `vso:`.** The table above is the binding this specification and every document in this repository use, and it does not change. What changed on 2026-07-31 is the *published* hint: `ontology/vso.ttl` declares `vann:preferredNamespacePrefix "vson"` — the prefix a vocabulary registry, a term browser or a generated SPARQL header should bind. It reads `vson` because `vso` is not free. `vso:` is Martin Hepp's Vehicle Sales Ontology, `http://purl.org/vso/ns#`, listed in [LOV](https://lov.linkeddata.es/dataset/lov/vocabs/vso) with versions back to 2010-10-02 (verified 2026-07-31). Publishing `vso` would have asked every consumer to rebind a prefix a decade-old vocabulary already holds, and a graph mixing the two could not bind both.

Both facts hold at once because **a prefix binding is syntax, not meaning**: a prefixed name is an abbreviation, expanded to a full IRI before any graph exists. So nothing migrates — no namespace, no term IRI, no shipped document, no fixture, no baked envelope — and a document binding `vso:`, `vson:` or `v:` to `https://w3id.org/vson/v1/ontology#` denotes the identical graph. That is checked rather than claimed: [`tests/test_prefix_binding.py`](../tests/test_prefix_binding.py) re-serializes every corpus document — the three ontologies, both shape profiles, and all 17 scene documents through the Penman transpiler — under both bindings and requires the round-tripped graphs to be isomorphic to each other and to the source, with an identical SHACL verdict.

The companion documents keep `rcc:`, `allen:` and `vss:`: they were not part of this collision, and their prefixes have **not** been checked against a registry — a submission for any of them needs that check first. No registration has been filed for `vson` either. [`publish/registry/prefix-cc.json`](../publish/registry/prefix-cc.json) holds the drafted prefix.cc values marked DRAFT, with the evidence and its dates, including one check that did not complete: on 2026-07-31 prefix.cc could not be reached to re-confirm that `vson` is unbound, because its TLS certificate had expired. The prefix choice does not depend on that check; filing the registration does.

**Namespace host — resolved in v1.2.** Through v1.1 every canonical IRI above was minted under `https://vson.dev/`, a hostname this project never registered: squattable by anyone, permanently non-dereferenceable, and dependent on one maintainer paying one registrar forever. v1.2 remints all five namespaces under `https://w3id.org/vson/` — the W3C Permanent Identifier Community Group's redirect service, which is free, community-maintained, and designed to keep resolving after any single maintainer stops paying attention. That permanence is the property a namespace host has to have and a private domain cannot promise.

The old names are **withdrawn, not aliased.** There is no `owl:sameAs` bridge, no redirect, and no shape that targets them: a document minted under `https://vson.dev/` selects zero focus nodes against the v1.2 shapes and does not validate. Withdrawal is the honest option here precisely because the legacy names had **zero external consumers** — they never dereferenced, no third party could have resolved or cached them, and every producer and consumer of them lives in this repository. Aliasing would have preserved a name that was never real.

These IRIs are stable names, and they dereference. The documents behind them — three ontologies, both shape profiles, the JSON-LD context, and both JSON Schemas — are served at `https://vson.pages.dev/v1/`, a static site assembled from this repository by [`scripts/build_site.py`](../scripts/build_site.py); and since 2026-07-31, when the [w3id redirect](https://github.com/perma-id/w3id.org/pull/6471) merged, each canonical name resolves to its document. `https://w3id.org/vson/v1/ontology` answers `303 See Other` to `https://vson.pages.dev/v1/ontology.ttl`, as do the other four namespace documents; the context IRI and both schema `$id`s answer `302 Found` to theirs. Cite the `w3id.org` names, not the Pages paths: the names are the identifiers, the host is only where the bytes currently sit. [`scripts/check_live_claims.py`](../scripts/check_live_claims.py) (`make live-check`) re-checks all eight of those redirects against the live services and fails when a response contradicts this paragraph — deliberately outside `make check`, which stays answerable from the checkout alone. See §8 for the immutability rule and its one historical exception.

#### 5.1.1 The imports closure — what the ontology name resolves *to*

A name that dereferences and a name that resolves to a usable vocabulary are two different achievements, and until 2026-08-01 this project had only the first. `vso:rcc` takes the eight RCC-8 relation individuals (§5.7) and the temporal edges of §5.9 **are** the thirteen Allen properties — but neither namespace appeared anywhere in the core document. Measured with rdflib 7.x: a parse of `ontology/vso.ttl` alone yields **0** IRIs in `…/rcc8#` and **0** in `…/allen#`, in any triple position. A consumer that followed the canonical name got a TBox whose value spaces were undefined names.

The core document now declares what it needs:

```turtle
<https://w3id.org/vson/v1/ontology>
    owl:imports <https://w3id.org/vson/v1/rcc8> ,
                <https://w3id.org/vson/v1/allen> .
```

So **the vocabulary is three documents, and the closure of the core name is all three.** Both imported names dereference on the same terms as the importer (the paragraph above), which is what makes the import followable rather than decorative. Two consequences worth stating explicitly:

- **Nothing in this repository's verification follows them, and none of it goes to the network.** rdflib does not resolve `owl:imports` at all; pyshacl does so only under `do_owl_imports=True`, which nothing here sets — [`tools/shacl_helper.py`](../tools/shacl_helper.py) passes the three files from local disk as `ont_graph` (the checkout, or the copies an installed distribution carries); owlrl does not resolve them either. The same holds inside the studio, whose Pyodide worker mounts the same three files into the browser filesystem. `make check` stays answerable from the tree alone, exactly as before, and an offline consumer that already has the three documents loses nothing.
- **It is an annotation, not a version event.** `owl:imports` declares no term and moves no IRI, so `owl:versionInfo` stays at `1.2` (§8.1). The same is true of everything in §5.1.2.

**One fetch: `vson-full.ttl`.** For a consumer that cannot follow an import — a script with a plain parse, a paste into a validator, a `curl` into an editor — the same closure is assembled as a single document, `v1/vson-full.ttl`: the three ontology documents concatenated, each keeping its own header, prologue and comments. `make site` writes it on every run; it reaches `https://vson.pages.dev/v1/vson-full.ttl` with the next deploy, which in this project is a manual step rather than a CI job. It is a **distribution, not a name.** No IRI is minted for it, none is promised to resolve to it, and the w3id rule routes only the five namespace documents (§8.1) — so the three canonical names above remain the things to cite, and are what every term in the file carries an `rdfs:isDefinedBy` back to.

It is derived at build time by [`scripts/build_site.py`](../scripts/build_site.py) from the same tracked sources, never committed: a tracked copy of three tracked files is a drift surface. Turtle concatenation is legal but fails quietly — a re-declared prefix rebinds from that point on, a truncated source swallows the file after it, and both still parse — so `make site` checks the result against arithmetic rather than assuming it: the merged graph must state exactly the sum of the three sources parsed apart (1322 = 1103 + 85 + 134 at v1.3), and declare the same `owl:versionInfo`. Being outside the canonical-name set, it is not part of `make live-check`'s claim table, which covers the eight names above.

**The one published document that is deliberately outside this closure** is [`ontology/alignments.ttl`](../ontology/alignments.ttl), the external-alignment and SKOS layer of §5.17. It is published at `/v1/alignments.ttl`, it is imported by nothing, and it is loaded by no gate — which is the point of it, not an oversight: what it states is how VSON's terms relate to vocabularies VSON does not depend on, and a consumer that follows the canonical name should not acquire those statements by accident. "The vocabulary is three documents" stays true after it ships.

#### 5.1.2 What each term carries

Three annotations were added to all three documents on 2026-08-01, each at zero coverage before it (183 terms, 186 labels, 186 comments — the three document IRIs are labelled but are not terms):

| Annotation | On | Why a merged graph needs it |
|---|---|---|
| `rdfs:isDefinedBy` | every term | Names the document that declares it. Once the closure is merged — by an import-following tool or by fetching `vson-full.ttl` — nothing else in the graph says which of the three a term came from. The IRI encodes it by convention (`<document>#<name>`); a convention is something a consumer must already know, and a triple is something it can follow. |
| `@en` | every `rdfs:label`, every `rdfs:comment` | An untagged literal is not English, it is *unspecified*. A term browser cannot tell a label to show an English reader from one not to, and cannot add a second language without guessing what the first was. |
| `vs:term_status "stable"` | every term | [`sw-vocab-status`](http://www.w3.org/2003/06/sw-vocab-status/ns#)'s four values are `stable`, `testing`, `unstable`, `archaic`. Every term here ships in a released vocabulary version whose IRIs §8.1 declares immutable within v1.x, which is what `stable` says. A provisional term would need its own value, deliberately. |

The layer is generated, not hand-maintained, by [`scripts/annotate_ontology.py`](../scripts/annotate_ontology.py) — a hand-maintained annotation layer rots one forgotten term at a time. It tags literals in place and appends one generated block per file, never reserializing, because a parse-and-serialize would discard every prose comment in files that are written to be read. [`tests/test_ontology_docs.py`](../tests/test_ontology_docs.py) runs it in check mode inside `make check`, so a term added without the layer fails the build rather than shipping.

Each document header also carries `dc:created`, `dc:issued`, `dc:publisher` and `dc:bibliographicCitation`. The citation restates [`CITATION.cff`](../CITATION.cff) and is compared against it on every run — it cites the **software release** (1.3.0), not the vocabulary version (1.2); §8.1 is why those are different numbers. There is no DOI: nothing has been deposited anywhere, and citing an identifier that does not exist would be worse than citing none.

### 5.2 `vso:Composition`

The mereological root of a scene. Every conformant document **MUST** declare at least one Composition.

**Required edges**

#### `vso:depicts` *(IRI ref → Entity, required, 1..n)*
Lists the entities the composition depicts. **MUST NOT** target a `vso:Frame`.
```json
{ "type": "array", "minItems": 1, "items": { "type": "string" } }
```
**SHACL.** `vss:CompositionShape` requires `sh:minCount 1` on `vso:depicts`. `vss:FrameNotDepictedShape` forbids Frame targets.
*Example.* `:scene vso:depicts :alice .`

#### `vso:viewedBy` *(IRI ref → CameraView, exactly 1 when present)*
The composition's primary viewer. It **SHOULD** always be present, and it **MUST** be present whenever the document asserts any directional `SpatialFact` — that case is what C5 enforces, via `vss:DirectionalNeedsViewerShape` on the fact itself.

**SHACL.** `vss:CompositionShape` caps `vso:viewedBy` at one (v1.3, §8.2 — "exactly 1 when present" is what the cap enforces). The *presence* half is unshaped: a composition with zero directional facts and no `vso:viewedBy` passes SHACL, because no numbered clause requires the edge and this section states it as SHOULD. The reference VSON-X parser does not close that gap either — it rejects `! ... *dir X` with no `^viewer` anchor, but accepts a composition with no top-level `^` anchor. `docs/vson-x-semantics.md` §4.10.1 specifies a stricter parser rule that is **not yet implemented**.
```json
{ "type": "string" }
```
*Example.* `:scene vso:viewedBy :cam .`

**Optional edges**

#### `vso:framedBy` *(IRI ref → Frame, optional, 0..n)*
Attaches scene-context, style, and additional camera frames.
*Example.* `:scene vso:framedBy :ctx, :style, :cam .`

#### `vso:rendersAs` *(IRI ref → VisualStyle, optional, 0..1)*
Designates which framedBy VisualStyle is the dominant aesthetic. **SHACL.** `vss:CompositionShape` caps it at one (v1.3).

#### `vso:hasQuality` *(IRI ref → Quality, optional, 0..n)*
Composition-level qualities (e.g. `Layout=triangular`, `Focal=center`).

#### `vso:hasFact` *(IRI ref → SpatialFact, optional, 0..n)*
Spatial facts that hold within this composition.

#### `vso:occurs` *(IRI ref → Perdurant, optional, 0..n)*
Events / Processes / Statives observed within this composition. Producers MAY also use `vso:depicts` for perdurants; both are conformant.

### 5.3 Frame subtypes

#### 5.3.1 `vso:SceneContext`

| Field | Type | Required | Description | Validation |
|---|---|---|---|---|
| `vso:venue` | `xsd:string` (snake_case noun) | no | `throne_room`, `marketplace`, `forest_path`, `Unknown` | none |
| `vso:atmosphere` | `xsd:string` enum | no | `tense, calm, joyful, somber, mysterious, festive, ominous, neutral, romantic, energetic, Unknown` | enum check |
| `vso:timeOfDay` | `xsd:string` enum | no | `dawn, morning, noon, afternoon, dusk, night, Unknown` | enum check |
| `vso:weather` | `xsd:string` enum | no | `clear, cloudy, overcast, rain, snow, fog, storm, indoor, Unknown` | enum check |

```json
{
  "type": "object",
  "properties": {
    "@type":      { "const": "SceneContext" },
    "venue":      { "type": "string" },
    "atmosphere": { "enum": ["tense","calm","joyful","somber","mysterious","festive","ominous","neutral","romantic","energetic","Unknown"] },
    "timeOfDay":  { "enum": ["dawn","morning","noon","afternoon","dusk","night","Unknown"] },
    "weather":    { "enum": ["clear","cloudy","overcast","rain","snow","fog","storm","indoor","Unknown"] }
  }
}
```

#### 5.3.2 `vso:VisualStyle`

| Field | Type | Required | Description |
|---|---|---|---|
| `vso:aesthetic` | `xsd:string` | no | `photographic, oil_painting, watercolor, pencil_sketch, ink_drawing, 3d_render, pixel_art, vector_illustration, anime, comic_book, concept_art, studio_ghibli, disney_classic, cyberpunk, steampunk, noir, vaporwave, ai_diffusion, ai_realistic, ai_anime, Unknown` |
| `vso:palette` | `xsd:string` | no | `warm, cool, neutral, monochrome, high_contrast, pastel, muted, saturated, earth_tones, neon, Unknown` |
| `vso:medium` | `xsd:string` | no | `photograph, canvas, paper, digital, screen, fresco, mural, screenshot, scan, Unknown` |

#### 5.3.3 `vso:CameraView`

| Field | Type | Required | Description |
|---|---|---|---|
| `vso:angle` | `xsd:string` | no | `eye_level, low, high, dutch, top_down, worms_eye` |
| `vso:focalLength` | `xsd:string` | no | `"24mm"`, `"35mm"`, `"50mm"`, `"85mm"` (lensequivalent), or numeric mm |
| `vso:framing` | `xsd:string` | no | `extreme_close_up, close_up, medium_shot, wide_shot, extreme_wide_shot` |
| `vso:cameraPosition` | `xsd:string` | no | Free-form positional cue (`"front_left_dolly"`, `"overhead"`). |

#### 5.3.4 `vso:Persona` (v1.1)

A Persona is a Frame that carries the cross-document invariants of a recurring character (an actor, a fictional protagonist, a brand mascot). It is **disjoint from `Entity`** — a Persona is never depicted directly; instead, an Entity in a scene declares `vso:embodies` pointing at a Persona, and that Entity inherits the Persona's invariants for cross-scene consistency checks.

| Field | Type | Required | Description |
|---|---|---|---|
| `vso:hasInvariant` | `vso:Quality` | yes (≥1) | Each Persona MUST carry at least one Quality (e.g. `Hair=auburn`). |

```turtle
:alice_id a vso:Persona ;
  vso:hasInvariant [ a vso:Quality ; vso:dimension vso:Hair ; vso:value "auburn" ] ,
                   [ a vso:Quality ; vso:dimension vso:Eye  ; vso:value "green"  ] .

:alice a vso:PhysicalObject ;
  vso:individuation vso:Named ; vso:animacy vso:Agentive ;
  vso:class :Knight ;
  vso:embodies :alice_id .
```

`vss:EmbodimentConsistencyShape` (Warning severity) flags scenes where an Entity's Quality contradicts its Persona's invariant for the same dimension. SHACL violation here is a *suggestion*, not a hard failure — scene-level Quality always wins (a character can be wounded, costumed, transformed); the shape exists to catch authoring mistakes, not to enforce immutability.

### 5.4 `vso:PhysicalObject` (and `vso:Aggregate`, `vso:Substance`)

Concrete entities in the scene. Subtypes share trait axes; differ only in countability defaults and inferred class.

**Required traits (every Entity)**

**Enforcement.** These four are required by this specification, but the shapes constrain them only *where the property appears*: `vss:IndividuationShape`, `vss:AnimacyShape`, `vss:CountabilityShape` and — since v1.3 — `vss:EntityClassShape` each use `sh:targetSubjectsOf` on their own property, and each caps its value at one. No shape and no clause in §2 requires an Entity to *carry* any of them, so an Entity that omits all four still passes SHACL. Completeness here is a producer obligation, and it stays one inside v1.x: §8.2 forbids a check that fires on a document this specification permits, and four shipped documents — `examples/throne_room.ttl`, `examples/throne_room.vson`, and the `kitchen` and `lamp` studio envelopes — omit a trait across 30 entity/trait pairs, counted over instances of `vso:PhysicalObject`, `vso:Substance` and `vso:Aggregate`. It was 51 across five documents until 2026-08-04, when a demo envelope carrying 21 of them was withdrawn ([`spec/CHANGELOG.md`](../spec/CHANGELOG.md)).

#### `vso:individuation` *(IRI, required, exactly 1)*
One of `vso:Generic`, `vso:Named`, `vso:Kind`, `vso:Skolem`.
```json
{ "enum": ["Generic", "Named", "Kind", "Skolem"] }
```
**SHACL.** `vss:IndividuationShape` pins `sh:in (vso:Generic vso:Named vso:Kind vso:Skolem)` with `sh:maxCount 1`. (`vss:AnimacyShape` and `vss:CountabilityShape` do the same for their axes.)

#### `vso:animacy` *(IRI, required, exactly 1)*
One of `vso:Agentive`, `vso:Inert`. Agents — humans, animals, animated mechanisms — get `Agentive`. Inanimate matter — furniture, vegetation, weapons-at-rest — gets `Inert`.

#### `vso:countability` *(IRI, required, exactly 1)*
One of `vso:Count`, `vso:Mass`, `vso:Collective`. Substances are Mass; Aggregates are Collective; otherwise Count.

#### `vso:class` *(string bareword or IRI, required, exactly 1)*
Domain class — see the example profile in Appendix C. Use `Unknown` rather than guessing.

**Optional traits/edges**

#### `vso:affordance` *(IRI, optional, 0..n)*
Subset of `{Holdable, Wearable, Mountable, Container, Edible}` — a closed list (§5.12): `vss:AffordanceShape` rejects any other value, and unlike its three sibling axes it carries no `sh:maxCount`, so an Entity MAY offer several. Reasoner-friendly; consumers MAY use it to filter.

#### `vso:hasQuality` *(IRI ref → Quality, 0..n)*
Per-entity qualities.

#### `vso:bbox2d` *(string, optional, 0..1)*
Normalized 2D bounding box in `"x,y,w,h"` form, all components in `[0, 1]`.
```json
{ "type": "string", "pattern": "^(0|0\\.\\d+|1|1\\.0+),(0|0\\.\\d+|1|1\\.0+),(0|0\\.\\d+|1|1\\.0+),(0|0\\.\\d+|1|1\\.0+)$" }
```
**SHACL.** `vss:GeometryShape` (v1.3) enforces this pattern, `sh:datatype xsd:string`, and the `0..1` cap. The shape's `sh:pattern` is byte-identical to the pattern above; [`tests/test_documented_constraints.py`](../tests/test_documented_constraints.py) fails if the two copies drift. Negative fixtures: [`bad_bbox2d_value.ttl`](../tests/fixtures/bad_bbox2d_value.ttl) (`"banana"` — conformant through v1.2) and [`bad_bbox2d_pixels.ttl`](../tests/fixtures/bad_bbox2d_pixels.ttl).

### 5.5 `vso:Quality`

Reified property. Always a node, never an inline literal on the bearer.

| Field | Type | Required | Description | Validation |
|---|---|---|---|---|
| `vso:dimension` | IRI | yes (1) | A registered VSO dimension (table below), or an IRI in the document's own namespace | `vss:QualityShape` requires exactly 1 |
| `vso:value` | bareword/string/integer | yes (1) | Per dimension's enum or free-form | exactly 1 |

```json
{
  "type": "object",
  "required": ["@type", "dimension", "value"],
  "properties": {
    "@type":     { "const": "Quality" },
    "dimension": { "type": "string" },
    "value":     { "type": ["string", "number"] }
  }
}
```

**SHACL.** `vss:QualityShape` enforces `sh:property [ sh:path vso:dimension; sh:minCount 1; sh:maxCount 1 ]` and the same for `vso:value`.

#### 5.5.1 Dimension registry (closed under the VSO namespace)

**The registry is closed.** The VSO namespace carries exactly the twenty-one dimensions below — no others. A `vso:dimension` whose value is any other IRI under `https://w3id.org/vson/v1/ontology#` is an orphan VSO term and the document is **non-conformant** by clause C2 (§2). Producers **MUST NOT** mint new `vso:` dimensions.

**Extension stays open.** A dimension the registry does not carry is minted under the producer's *own* namespace, never under `vso:` — `[ a vso:Quality ; vso:dimension :Reflectance ; vso:value "matte" ]` with `:` bound to the document namespace is conformant, and is profile-specific rather than portable (§8). This is the only sanctioned way to extend the axis set inside v1.x.

| Dimension | Bearer | Reading |
|---|---|---|
| `vso:Color` | Entity | Perceived colour |
| `vso:Weight` | Entity | Heaviness as read off the scene, not measured |
| `vso:Material` | Entity | What it is made of (stone, silk, iron) |
| `vso:Affect` | Entity | Mood or emotional state |
| `vso:Age` | Entity | Years, or an age band |
| `vso:Role` | Entity | Social or narrative role (queen, knight) |
| `vso:Size` | Entity | Relative size |
| `vso:Enchantment` | Entity | Magical or supernatural property |
| `vso:ActionState` | Entity | Transient action phase (drawn, raised, running) |
| `vso:Layout` | Composition | How the scene is arranged |
| `vso:Focal` | Composition | What the scene draws attention to |
| `vso:Amount` | Entity | Quantity, for Substances and Aggregates read by amount not count |
| `vso:Hair` | Entity / Persona | Hair colour or length (auburn, black_short) |
| `vso:Hairstyle` | Entity / Persona | Cut or styling (bob, braided, ponytail) |
| `vso:Skin` | Entity / Persona | Skin tone or complexion |
| `vso:Eye` | Entity / Persona | Eye colour |
| `vso:Eyewear` | Entity | Eyewear worn (sunglasses, round_frames) |
| `vso:Headwear` | Entity | Headwear worn (beanie, wide_brim_hat) |
| `vso:Outfit` | Entity | Garment or ensemble read as a whole |
| `vso:Fit` | Entity | How a garment sits (oversized, tailored, cropped) |
| `vso:Pose` | Entity / Persona | Bodily posture |

The **Bearer** column is guidance for producers, not a constraint: no shape ties a dimension to a bearer class, so `vso:Layout` on an Entity parses and validates. The compositional pair (`Layout`, `Focal`) attaches to the `vso:Composition` root; the rest attach to an Entity, and the appearance axes double as `vso:Persona` invariants (§5.3.4).

**Reaching them from the other syntaxes.** VSON-P names the dimension directly (`:dimension Layout`). VSON-X derives it from the `*key` by PascalCasing (`*action_state` → `ActionState`), and that derivation is mechanical — a key outside this table produces a `vso:` IRI outside the registry, which is the C2 failure above, not a warning. [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §3.2.1 and [`skills/vson-extractor-x/SKILL.md`](../skills/vson-extractor-x/SKILL.md) restate the same twenty-one keys for the VSON-X surface; they are copies of this table, not second registries.

**Where this list is enforced, and where it is copied.** `ontology/vso.ttl` is the single source: it declares all twenty-one as `vso:Dimension` individuals and names all twenty-one in one `owl:AllDifferent` — necessary because `vso:dimension` is an `owl:FunctionalProperty`, so a Quality asserting two dimensions collapses them to `owl:sameAs` under `prp-fp`, and only pairwise distinctness turns that collapse into a reported clash (§5.9). A member missing from the `owl:AllDifferent` list is a member that can silently collapse. Membership itself is checked by the C2 gate, not by SHACL: `vss:QualityShape` deliberately carries no `sh:in` on `vso:dimension`, because such an enum would reject the document-namespace dimensions that §8 keeps conformant. `shapes/vson-shapes.ttl` records that reasoning beside the shape. Since v1.3 the guard is at validate time — [`tools/c2_check.py`](../tools/c2_check.py) sweeps object positions as well as predicates, so `vso:dimension vso:Ambience` is reported as the C2 violation it is, while `vso:dimension :Ambience` in the document's own namespace stays conformant. Negative fixture: [`bad_orphan_term.ttl`](../tests/fixtures/bad_orphan_term.ttl), which satisfies every shape and fails C2 alone.

The registry is written out five times — the individuals, the `owl:AllDifferent` list, the table above, `docs/vson-x-semantics.md` §3.2.1, and the VSON-X skill — and copies drift: through v1.3.0 the two VSON-X copies carried one name fewer than the ontology, omitting `vso:Eye` — the second Persona invariant of §5.3.4's own worked example. [`scripts/check_registry_drift.py`](../scripts/check_registry_drift.py) now compares all five in `make check`, including the spelled count in this paragraph. A new dimension is added to `ontology/vso.ttl` first; the copies follow.

### 5.6 `vso:Event` / `vso:Process` / `vso:Stative`

Reified perdurants. Differ in aspectual character:

| Class | Aspect | Examples |
|---|---|---|
| `vso:Event` | punctual / completable | `strike, throw, fall, give, arrive` |
| `vso:Process` | durative, atelic | `run, dance, burn, bleed, pour` |
| `vso:Stative` | continuous state | `hold, wear, look_at, sit, believe` |

#### `vso:lemma` *(xsd:string, required, exactly 1)*
Snake_case verb naming the perdurant.
```json
{ "type": "string", "pattern": "^[a-z][a-z0-9_]*$" }
```
**SHACL.** `vss:EventShape`, `vss:ProcessShape` and `vss:StativeShape` each require `sh:datatype xsd:string; sh:minCount 1; sh:maxCount 1` on `vso:lemma`, so C6's "exactly one" is shape-enforced on all three. Through v1.2 only `vss:EventShape` carried the cap and a second lemma on a Process or Stative was a clause violation `vson validate` did not report; v1.3 closed that under §8.2 — negative fixture [`bad_two_lemmas.ttl`](../tests/fixtures/bad_two_lemmas.ttl). The pattern above is enforced by `vss:LemmaShape` (v1.3), which targets every subject of `vso:lemma` rather than the three classes, so a lemma on an untyped node is checked too — negative fixture [`bad_lemma_pattern.ttl`](../tests/fixtures/bad_lemma_pattern.ttl).

**Thematic roles (zero or more, depending on class)**

The role inventory below is closed and deliberately coarse — VerbNet-style thematic roles (Kipper Schuler 2005) rather than predicate-specific argument slots. PropBank (Palmer, Gildea & Kingsbury 2005) numbers arguments per verb sense (`ARG0` of *give* is not `ARG0` of *melt*), and FrameNet (Baker, Fillmore & Lowe 1998) names them per semantic frame (`Donor`, `Recipient`, `Theme`); both give a finer analysis than a vision-language model can reliably produce from a still image, and both require a per-predicate lexicon that VSON does not ship. VSON therefore takes the third option: one small, frame-independent role set a producer can memorize. It is closed by C2 (§2) — an invented `vso:` role is an orphan VSO term — and not by any SHACL shape; since v1.3 `vson validate`'s third gate reports it anyway, because C2 closure is what that gate decides. The VSON-X parser still emits an unlisted role verbatim without complaint, which Appendix D §D.8 note 6 records. Citations in [Appendix E](#appendix-e--related-work-and-bibliography); the AMR exporter mapping in §7 is where PropBank's per-sense numbering resurfaces.

| Predicate | Used on | Description |
|---|---|---|
| `vso:agent` | Event, Process | Volitional doer |
| `vso:patient` | Event | Affected entity |
| `vso:theme` | Event, Process, Stative | Entity in a relation/state |
| `vso:instrument` | Event | Means / tool |
| `vso:recipient` | Event | Goal-receiver in transfers |
| `vso:source` | Event | Origin in transfers |
| `vso:goal` | Event, Process | Target / destination |
| `vso:beneficiary` | Event | For-whose-benefit |
| `vso:experiencer` | Stative | Sentient in cognitive/perceptual state |
| `vso:stimulus` | Stative | What the experiencer is oriented toward |
| `vso:holder` | Stative | Possessor in `hold/wear/own` |
| `vso:manner` | any | Bareword adverbial (`swift, careful, forceful`) |
| `vso:cause` / `vso:result` | Event | Causal / resultative linkage |
| `vso:location` / `vso:time` | any | Spatial / temporal grounding |

```json
{
  "type": "object",
  "required": ["@type", "lemma"],
  "properties": {
    "@type":      { "enum": ["Event", "Process", "Stative"] },
    "lemma":      { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" },
    "agent":      { "type": "string" },
    "patient":    { "type": "string" },
    "theme":      { "type": "string" },
    "instrument": { "type": "string" },
    "recipient":  { "type": "string" },
    "experiencer":{ "type": "string" },
    "stimulus":   { "type": "string" },
    "holder":     { "type": "string" },
    "manner":     { "type": "string" }
  }
}
```

### 5.7 `vso:SpatialFact`

Reified spatial relation. Carries figure, ground, optional viewer, and one or more of `rcc/directional/proximal`.

`vso:rcc` takes the eight RCC-8 base relation names of Randell, Cui & Cohn 1992 ([Appendix E](#appendix-e--related-work-and-bibliography)). VSON ships them as a **closed value vocabulary, not as the calculus**: [`ontology/rcc8.ttl`](../ontology/rcc8.ttl) declares the eight as individuals of `rcc:Relation` and asserts only that they denote distinct values. Jointly-exhaustive-pairwise-disjoint holds in the intended interpretation, not as an axiom, and no composition table ships — given `NTPP(a,b)` and `NTPP(b,c)`, VSON derives nothing about `a` and `c`. Each of the eight carries a `skos:closeMatch` to its OGC GeoSPARQL counterpart (`geo:rcc8dc` …); see the design note in §5.9 for why the GeoSPARQL IRIs are not used directly.

| Field | Type | Required | Description | Validation |
|---|---|---|---|---|
| `vso:figure` | IRI ref → Entity | yes (1) | The thing being located | `vss:SpatialFactShape` |
| `vso:ground` | IRI ref → Entity | yes (1) | The reference frame | `vss:SpatialFactShape` |
| `vso:rcc` | IRI in `rcc:` | no (0..1) | One of `DC, EC, PO, EQ, TPP, NTPP, TPPi, NTPPi` | `vss:RccValueShape` |
| `vso:directional` | IRI in VSO | no (0..1) | `above, below, left_of, right_of, in_front_of, behind` | requires viewer |
| `vso:proximal` | IRI in VSO | no (0..1) | `near, far, adjacent, next_to, facing` | `vss:ProximalValueShape` |
| `vso:viewer` | IRI ref → CameraView | conditional | **MUST** be present when `vso:directional` is present (C5) | `vss:DirectionalNeedsViewerShape` |

```json
{
  "type": "object",
  "required": ["@type", "figure", "ground"],
  "properties": {
    "@type":       { "const": "SpatialFact" },
    "figure":      { "type": "string" },
    "ground":      { "type": "string" },
    "rcc":         { "enum": ["DC","EC","PO","EQ","TPP","NTPP","TPPi","NTPPi"] },
    "directional": { "enum": ["above","below","left_of","right_of","in_front_of","behind"] },
    "proximal":    { "enum": ["near","far","adjacent","next_to","facing"] },
    "viewer":      { "type": "string" }
  },
  "if":   { "required": ["directional"] },
  "then": { "required": ["viewer"] }
}
```

**SHACL.** `vss:DirectionalNeedsViewerShape` raises a violation when `vso:directional` is present without `vso:viewer`. Negative fixture: [`tests/fixtures/bad_no_viewer.ttl`](../tests/fixtures/bad_no_viewer.ttl). The shape checks presence (`sh:minCount 1`), that the viewer is a `vso:CameraView`, and — since v1.3 — that there is exactly one of them (`sh:maxCount 1`), which is what C5 says: two cameras is two construals of one direction, the ambiguity viewer anchoring exists to remove. Negative fixture: [`tests/fixtures/bad_two_viewers.ttl`](../tests/fixtures/bad_two_viewers.ttl). A viewer on a purely topological fact is permitted — the implication runs directional ⇒ viewer, not the converse. `vss:SpatialFactShape` caps each of `vso:rcc`, `vso:directional` and `vso:proximal` at one, matching the `0..1` this table has always stated (v1.3, fixture [`tests/fixtures/bad_two_rcc.ttl`](../tests/fixtures/bad_two_rcc.ttl)); the `sh:or` requiring at least one of the three is unchanged.

### 5.8 Mereology

| Predicate | Description | OWL characteristics |
|---|---|---|
| `vso:partOf` | x is part of y | `owl:TransitiveProperty`; inverse of `hasPart` |
| `vso:hasPart` | y has part x | `owl:TransitiveProperty`; inverse of `partOf` |
| `vso:properPartOf` | x is a proper part of y | sub-property of `partOf`, irreflexive |
| `vso:overlaps` | x and y share a part | symmetric |
| `vso:disjoint` | x and y share no part | symmetric |

Every characteristic in the third column is an axiom [`ontology/vso.ttl`](../ontology/vso.ttl) asserts, and [`tests/test_documented_constraints.py`](../tests/test_documented_constraints.py) reads this table out of this document and fails if one of them is missing. The irreflexivity of `vso:properPartOf` was published in this table from v1.1, the first release that carried this document, and asserted in the TBox from v1.3 — `owl:IrreflexiveProperty`, which is OWL 2 RL-legal (rule `prp-irp`). `owlrl` materializes nothing from it (the rule's head is a contradiction, which has nowhere to go in an RDF closure), so [`tools/owlrl_check.py`](../tools/owlrl_check.py) checks it directly, against the closure rather than the asserted triples: a two-step `properPartOf` cycle only becomes reflexive once transitivity is materialized, and it is reported.

### 5.9 Causal and Allen interval

#### Causal

`vso:causes`, `vso:enables`, `vso:prevents`, `vso:triggers` between Perdurants. Causal claims **SHOULD** be rare and high-confidence; producers SHOULD attach an `vso:Annotation` with confidence < 1.0 by default.

#### Allen interval (Perdurant ↔ Perdurant)

`allen:before`, `allen:after`, `allen:meets`, `allen:metBy`, `allen:overlaps`, `allen:overlappedBy`, `allen:starts`, `allen:startedBy`, `allen:during`, `allen:contains`, `allen:finishes`, `allen:finishedBy`, `allen:equals` — the thirteen base relations of Allen 1983 ([Appendix E](#appendix-e--related-work-and-bibliography)). Inverses are declared in [`ontology/allen.ttl`](../ontology/allen.ttl); `owl:TransitiveProperty` is asserted on exactly the members that compose with themselves (`before/after`, `during/contains`, `starts/startedBy`, `finishes/finishedBy`, `equals`), so `meets` and `overlaps` carry no transitivity axiom. As with RCC-8, the composition table itself is out of scope. Each of the thirteen carries a `skos:closeMatch` to its W3C OWL-Time counterpart (`time:intervalBefore` …).

#### Design note — why not reuse the `time:` and `geo:` IRIs directly

VSON declares its own `rcc:` and `allen:` terms instead of asserting OWL-Time and GeoSPARQL properties, for two different reasons:

- **RCC-8 (`geo:`).** GeoSPARQL models its RCC-8 terms as **binary object properties between features** (`:a geo:rcc8ntpp :b`). VSON models them as **enumerated values on a reified `vso:SpatialFact`** (`:sf vso:rcc rcc:NTPP`), because the fact node is what carries the viewer, the figure/ground asymmetry, and any `vso:Annotation` (§5.11). Dropping `geo:rcc8ntpp` in as a predicate would mean abandoning the reification pattern — and with it the C5 viewer guarantee and per-fact confidence.
- **Allen (`time:`).** These *are* object properties in VSON, so the shape matches; the typing does not. OWL-Time types its interval relations on `time:ProperInterval`, whereas VSON types them on `vso:Perdurant` — a node that carries a lemma and thematic roles and need not be given any interval extent at all. Asserting `time:intervalBefore` between two Perdurants would entail that both are proper intervals — a commitment VSON does not make and its documents do not warrant.

So the bridge is advisory rather than substitutive: each VSON relation individual (RCC-8) and each VSON relation property (Allen) carries a `skos:closeMatch` to its GeoSPARQL / OWL-Time counterpart. `skos:closeMatch` records the shared reading and imports **no** OWL entailment — a consumer that wants GeoSPARQL or OWL-Time triples must rewrite them itself, and no VSON gate checks that rewrite. Both alignment sets live in [`ontology/rcc8.ttl`](../ontology/rcc8.ttl) and [`ontology/allen.ttl`](../ontology/allen.ttl).

#### What the OWL 2 RL layer actually infers

"OWL 2 RL" in this stack is a small, concrete set of entailments, not a general reasoning claim. `vson validate` and `make check` materialize the OWL 2 RL closure of (ontology + document) with `owlrl` and inspect it — [`tools/owlrl_check.py`](../tools/owlrl_check.py). What that buys, in practice:

- **Mereological transitivity.** `vso:partOf` and `vso:hasPart` are transitive and mutually inverse, and `vso:properPartOf` is a sub-property of `partOf`; so `hilt partOf sword`, `sword partOf knight` entails `hilt partOf knight`, and every assertion has its inverse materialized.
- **Temporal inverses and transitivity.** `allen:after owl:inverseOf allen:before` (and the other five inverse pairs), plus transitivity on the self-composing members listed above.
- **Symmetry.** `vso:overlaps`, `vso:disjoint`, and `allen:equals` are `owl:SymmetricProperty`, so one asserted direction yields both. The proximal values are *not* covered: `near`/`adjacent`/`next_to` are individuals valued on a fact, not properties, and their symmetry is produced at emission time by the VSON-X `&` form (two facts with figure and ground swapped) — no axiom does it.
- **Disjointness clashes.** `vso:Frame owl:disjointWith vso:Entity`, the `Endurant/Perdurant/Quality/Region` disjointness set, and the pairwise-disjoint Frame and Perdurant subtypes. A node dragged into two disjoint classes — typically by a property's `rdfs:domain` or `rdfs:range` — is reported as a clash.
- **Functional-property clashes.** `vso:individuation`, `vso:animacy`, `vso:countability`, `vso:dimension`, `vso:figure`, and `vso:ground` are `owl:FunctionalProperty`, so two values on one node collapse to `owl:sameAs` under OWL 2 RL's `prp-fp` rule. For the four trait/dimension properties that collapse is *detectable*, because their value sets are declared `owl:AllDifferent` — an entity with two `vso:individuation` values is reported. `owlrl_check.py` raises that contradiction itself, since `owlrl` 7.1.4 (the pinned floor) does not expand `owl:AllDifferent` into `owl:differentFrom`. `vso:figure` and `vso:ground` have no such distinctness declaration to violate, so two figures on one fact are quietly equated rather than reported.

What it does **not** buy: no spatial or temporal composition tables, no cardinality reasoning beyond the functional properties above, and nothing at all from the SHACL gate — that runs with `inference="rdfs"`, which never processes `owl:disjointWith`. The SHACL and OWL gates are complementary, which is why `vson validate` runs both (and, since v1.3, the C2 gate beside them — §2). Eight bridge properties are also left as untyped `rdf:Property` to admit mixed literal / IRI / quoted-triple objects, which places the full graph outside OWL 2 DL; the RL rule set still applies, since OWL 2 RL is specified as rules over arbitrary RDF graphs.

### 5.10 Geometry

| Predicate | Type | Description | Validation |
|---|---|---|---|
| `vso:bbox2d` | `xsd:string` `"x,y,w,h"`, normalized [0,1] | 2D bounding box | `vss:GeometryShape` — pattern of §5.4, `0..1` |
| `vso:position3d` | `xsd:string` `"x,y,z"` | 3D position (if known) | `vss:GeometryShape` — three decimal numbers |
| `vso:scale3d` | `xsd:string` `"sx,sy,sz"` | 3D scale | `vss:GeometryShape` — three decimal numbers |
| `vso:rotation` | `xsd:string` quaternion or Euler | 3D orientation | `vss:GeometryShape` — four numbers, or three |
| `vso:occludes` | IRI ref → Entity | Foreground occluder | `rdfs:range vso:PhysicalObject` only |
| `vso:visibleFraction` | `xsd:decimal` in `[0,1]` | Visible fraction post-occlusion | `vss:ConfidenceRangeShape` — `[0,1]` |

**Normalized, not pixels.** Every component of `vso:bbox2d` is a fraction of the image's width or height. `ontology/vso.ttl`'s comment also offered a pixel reading until v1.3, which §2 resolves in favour of this document; the ontology comment now says normalized, `vss:GeometryShape` rejects the pixel form ([`bad_bbox2d_pixels.ttl`](../tests/fixtures/bad_bbox2d_pixels.ttl)), and every `vso:bbox2d` in the shipped corpus was already normalized.

**What the geometry shapes do not check.** They read the value space, not the picture, and not the scene's agreement with itself: nothing here checks that `x + w ≤ 1`, that an occluder's `vso:visibleFraction` is consistent with the two boxes' overlap, or that a `vso:rcc` value agrees with the rectangles it is asserted over. The last of those is decided since v1.3, outside SHACL and outside conformance, by §5.13's check — which also states why the `vso:visibleFraction` one is not merely unimplemented but unavailable: no bound on a region's visible area follows from a rectangle that over-approximates it.

The three 3D grammars admit exponent notation (`1.5,-2,3e-4`) and no whitespace, and bound no component: world coordinates are unbounded, unlike a normalized box. Negative fixture: [`bad_geometry_grammar.ttl`](../tests/fixtures/bad_geometry_grammar.ttl).

### 5.11 Annotation reification

Used for probability, source, confidence, or any meta-claim about a triple.

```turtle
:ann1 a vso:Annotation ;
    vso:annotatedSubject :sf1 ;
    vso:annotatedPredicate vso:directional ;
    vso:annotatedObject vso:above ;
    vso:probability "0.85"^^xsd:decimal ;
    vso:source "extractor:claude-opus-4-7" .
```

The RDF-star canonical form `<<:sf1 vso:directional vso:above>> vso:probability "0.85"` is equivalent and **SHOULD** be used when a Turtle-star parser is available. Both forms are conformant per §2.

| Predicate | Type | Description | Validation |
|---|---|---|---|
| `vso:probability` | number in `[0,1]` | Probability that the annotated triple holds | `vss:ConfidenceRangeShape` |
| `vso:confidence` | number in `[0,1]` | Producer's confidence in the annotated triple | `vss:ConfidenceRangeShape` |

The `[0,1]` bound is what [`ontology/vso.ttl`](../ontology/vso.ttl) has declared in both terms' `rdfs:comment` since v1.1.1; stating it here adds no restriction and closes the gap that let `vso:confidence "7.3"` pass through v1.2 ([`bad_confidence_range.ttl`](../tests/fixtures/bad_confidence_range.ttl)). The shape bounds the **value** and does not pin a datatype: `"0.95"^^xsd:decimal`, `"1"^^xsd:integer` and `"0.5"^^xsd:double` are all in range, which matters because the reference transpilers type a Penman number by its lexical form. A non-numeric literal cannot be compared with the bound and is a violation, so `vso:confidence "banana"` fails here too.

### 5.12 Reserved + closed enumerations (full list)

Producers **MUST NOT** invent values for closed enumerations. Open dimensions (`venue`, `class`, free-form quality values) MAY take novel values; if uncertain, use `Unknown`.

| Enum | Closed values |
|---|---|
| `vso:individuation` | `Generic, Named, Kind, Skolem` |
| `vso:animacy` | `Agentive, Inert` |
| `vso:countability` | `Count, Mass, Collective` |
| `vso:affordance` | `Holdable, Wearable, Mountable, Container, Edible` (`vss:AffordanceShape`; multi-valued, so no `sh:maxCount`) |
| `vso:rcc` | `rcc:DC, rcc:EC, rcc:PO, rcc:EQ, rcc:TPP, rcc:NTPP, rcc:TPPi, rcc:NTPPi` |
| `vso:directional` | `above, below, left_of, right_of, in_front_of, behind` |
| `vso:proximal` | `near, far, adjacent, next_to, facing` (five values — `vss:ProximalValueShape`; VSON-X's `&` form admits only the first three) |
| `vso:dimension` | The twenty-one registered dimensions of §5.5.1 — closed *within the VSO namespace* only. Unlike the rows above, no shape enumerates them: a document-namespace dimension IRI stays conformant, and a `vso:`-namespace one outside the registry fails C2 rather than C3 — reported by `vson validate`'s third gate since v1.3, not by SHACL. |

### 5.13 Geometry consistency (`vson verify --geometry`)

A document that carries both a relation and the geometry of §5.10 has said two things that can disagree. `:sf vso:figure :mug ; vso:ground :shelf ; vso:rcc rcc:NTPP` says the mug is inside the shelf; `:mug vso:bbox2d "0.40,0.70,0.15,0.20"` and `:shelf vso:bbox2d "0.10,0.20,0.80,0.30"` put the mug's rectangle entirely below the shelf's. Both statements are structurally well-formed, both are in their value spaces, and they cannot both describe one picture. This section defines the decision procedure that says so, and — as precisely — what it does not establish.

**What it checks, and against what.** Three constructs were named in §2.1: syntax (the parser), structure (SHACL), internal consistency (the OWL 2 RL closure). This is a **fourth**, in the same position as the third — worth running, required by no clause:

| Construct | Mechanism | What a pass means |
|---|---|---|
| **Geometry consistency** | the decision procedures below, over the document's `vso:bbox2d` rectangles ([`tools/geometry_check.py`](../tools/geometry_check.py)) | no relation the document asserts is refuted by the geometry the document asserts |

It compares **claims against claims**. It reads no image, and it is not a step toward reading one: a document whose boxes and relations agree can still describe a photograph containing neither object, and §2.1's prohibition on calling such a document accurate or verified is untouched by a green run. What it removes is one specific way of being wrong — the way that needs no picture to detect, because the document refutes itself.

**Not a conformance clause.** C1–C9 do not mention geometry consistency, and §8.2 forbids making them mention it inside v1.x: nothing in this specification, before this section, required a `vso:rcc` value to agree with a `vso:bbox2d`, so a check that rejected such a document would be rejecting a document the specification permits. A geometry-inconsistent document is a **conformant VSON document**. `vson validate` therefore does not run this check and its three gates are unchanged; `vson verify --geometry` runs it, and reports it as what it is.

#### 5.13.1 The image frame

`vso:bbox2d` is `"x,y,w,h"` as fractions of the image (§5.4). This section fixes the two things that reading leaves open, because a decision procedure cannot be stated without them:

- **Origin and axes.** The origin is the **top-left** of the frame, `x` increases to the right, and `y` increases **downward** — the convention of the layout consumers §5.4's example names, and the one every `vso:bbox2d` in this repository's corpus was written in. A rectangle is therefore the closed set `[x, x+w] × [y, y+h]`.
- **Whose image.** The rectangles are fractions of one image: the image of the `vso:CameraView` the composition is `vso:viewedBy` (§5.2). A `vso:directional` value is anchored to its own `vso:viewer` (C5, §3.3), so the rectangles may be read as *that viewer's* left and right only when the two cameras are the same node. When they are not, or when the document declares no single viewed camera, nothing directional is decided — see the taxonomy in §5.13.5. This is what the mandatory viewer buys: without C5 there would be no anchor to compare a rectangle against.

Neither point restricts what a document may say, and neither changes any clause. A document that meant `y` upward was already stating something this specification never defined.

#### 5.13.2 The engine: a bounding box refutes, it does not confirm

`vso:bbox2d` is a *bounding* box — the tightest axis-aligned rectangle containing the entity's projection. Write `bbox(X)` for it. Two properties hold, and they are the whole of what follows:

```text
X ⊆ bbox(X)                     (extensive)
X ⊆ Y  ⟹  bbox(X) ⊆ bbox(Y)     (monotone)
```

A relation asserted between two *regions* entails something about their rectangles; when the rectangles falsify that entailment, the assertion is refuted. **The converse never holds.** A cat sitting on a mat stands in `rcc:EC` — the regions touch and their interiors do not meet — while the cat's rectangle and the mat's overlap with positive area, so the *rectangles* stand in PO. The difference is not academic: of the 10 `vso:rcc` facts the 22 baked studio envelopes state over two rectangles, a check that computed the rectangles' own RCC-8 relation and demanded a match would reject **6**; the refutation table below rejects 1 (§5.13.7). One of the seven is the cat itself: the demo strip's `cat.json` asserts `rcc:EC` for a cat on a rug whose rectangles overlap with area. An implementation of this check therefore **MUST NOT** report an inconsistency except where an entailment in §5.13.3 or a rule in §5.13.4 licenses it.

#### 5.13.3 RCC-8, decided on rectangles

A rectangle is the product of two intervals, `X = [x₁,x₂] × [y₁,y₂]`, so every test below is a conjunction of the same test on the two axis projections. With `A` the figure's rectangle and `B` the ground's:

```text
meet(A,B)     ≡  A.x₁ ≤ B.x₂ ∧ B.x₁ ≤ A.x₂ ∧ A.y₁ ≤ B.y₂ ∧ B.y₁ ≤ A.y₂
inside(A,B)   ≡  B.x₁ ≤ A.x₁ ∧ A.x₂ ≤ B.x₂ ∧ B.y₁ ≤ A.y₁ ∧ A.y₂ ≤ B.y₂
strict(A,B)   ≡  B.x₁ < A.x₁ ∧ A.x₂ < B.x₂ ∧ B.y₁ < A.y₁ ∧ A.y₂ < B.y₂
```

| Asserted | Entails, of the regions | Refuted exactly when |
|---|---|---|
| `rcc:DC` | the regions share no point | **never** — disjoint regions may have any two boxes at all, up to identical ones (two interleaved combs) |
| `rcc:EC` | the regions share a boundary point | `¬meet(A,B)` |
| `rcc:PO` | the interiors share a point | `¬meet(A,B)` |
| `rcc:EQ` | one region | `A ≠ B` |
| `rcc:TPP` | figure ⊆ ground | `¬inside(A,B)` |
| `rcc:NTPP` | figure ⊆ interior(ground) | `¬strict(A,B)` |
| `rcc:TPPi` | ground ⊆ figure | `¬inside(B,A)` |
| `rcc:NTPPi` | ground ⊆ interior(figure) | `¬strict(B,A)` |

The two strict rows are the only ones that need an argument. If `X ⊆ interior(Y)`, then the point of `X` attaining its greatest `x` lies in an open subset of `Y`, so `Y` contains a point of strictly greater `x`; hence `bbox(Y)` extends strictly beyond `bbox(X)` on that side, and the same on the other three. `TPP` and `NTPP` differ only in that strictness, which is why a figure flush against one edge of its ground is `TPP`-compatible and `NTPP`-refuted.

`DC`'s row is not a gap to be closed later. It is the shape of the whole method: bounding boxes over-approximate, so they refute claims of *containment and contact* and can never refute a claim of *separation*.

Arithmetic is exact. Comparisons run on decimal values, never binary floats, and the four boundary cuts above (`EC` vs `DC`, `EQ`, the `TPP`/`NTPP` line) turn on equality of coordinates, which a float would decide by rounding error.

#### 5.13.4 Direction, decided on centroids

Unlike §5.13.3, this is a **stipulation, not an entailment**: nothing about two regions forces an ordering of their bounding boxes' centres. For the purpose of this check, and with `x̄`/`ȳ` the centroid of a rectangle read in the frame of §5.13.1:

| Asserted | Holds exactly when | Refuted otherwise |
|---|---|---|
| `vso:above` | `ȳ(figure) < ȳ(ground)` | including equality — two centroids at one height stand in no vertical order |
| `vso:below` | `ȳ(figure) > ȳ(ground)` | " |
| `vso:left_of` | `x̄(figure) < x̄(ground)` | " |
| `vso:right_of` | `x̄(figure) > x̄(ground)` | " |
| `vso:in_front_of`, `vso:behind` | — | **out of scope**: depth is not a function of the image plane, and no pair of rectangles decides it |

The decision needs the fact's `vso:viewer` and the composition's `vso:viewedBy` to be the same camera (§5.13.1). A centroid needs no interior, so a degenerate rectangle blocks §5.13.3 and not this table.

#### 5.13.5 `vso:occludes`, and what rectangles cannot reach

**`vso:occludes`.** An occluder hides part of what it occludes, so the two projections share image points and `¬meet(A,B)` refutes the claim. Only the closed test is used: §5.10 does not say an occluder hides positive *area*, and demanding overlapping interiors would refute a document this specification permits.

**`vso:visibleFraction` is out of scope, and stays so.** §5.10 lists "an occluder's `vso:visibleFraction` consistent with the two boxes' overlap" among the things nothing checks; this section does not close that one, because no bound follows. The visible fraction is a ratio of *region* areas, a rectangle over-approximates a region's area by an unbounded factor, and VSON makes no closed-world commitment about `vso:occludes` — so a value below 1 is always explicable by an occluder the document does not declare, or by the frame edge. There is no sound lower bound and no sound upper bound to compute, and this check reports the value as undecidable rather than inventing one.

**`vso:proximal` is out of scope.** VSON fixes no distance threshold for `near` / `far` / `adjacent` / `next_to`, and no orientation for `facing`. A threshold invented by a checker would be a requirement this document never stated.

#### 5.13.6 Verdicts

Every asserted relation gets exactly one of three verdicts, and an implementation **MUST NOT** report a fourth or silently omit a relation:

| Verdict | Meaning |
|---|---|
| `consistent` | decided, and the geometry does not refute the assertion — **not** evidence that the assertion is true |
| `inconsistent` | decided, and the geometry refutes the assertion |
| `undecidable` | not decided, with a reason from the list below |

| Reason | When |
|---|---|
| `no-geometry` | an endpoint carries no `vso:bbox2d` |
| `malformed-geometry` | a `vso:bbox2d` outside the §5.4 value space — a SHACL violation, reported by `vss:GeometryShape`, and decided from here not at all |
| `ambiguous-geometry` | an endpoint carries more than one `vso:bbox2d` (also a SHACL violation) |
| `ambiguous-endpoints` | the fact does not carry exactly one `vso:figure` and one `vso:ground` |
| `degenerate-geometry` | a zero-area rectangle bounds a region with no interior, and RCC-8 is defined over regions that have one |
| `viewer-not-image-frame` | a directional fact whose `vso:viewer` is not the camera the rectangles are normalized against (§5.13.1) |
| `relation-out-of-scope` | `vso:proximal`, `in_front_of` / `behind`, `vso:visibleFraction` (§5.13.5) |
| `unrecognized-value` | a value outside C8 or the §5.12 enumeration — SHACL's report, not this one's |

The list is exhaustive by construction: a relation that is not decided is reported with the reason it was not, and "not applicable" is never a silent skip.

#### 5.13.7 Where it runs, and what it found

The reference implementation is [`tools/geometry_check.py`](../tools/geometry_check.py), run by `vson verify --geometry <files>` (exit 0 clean, 1 an inconsistency, 2 no verdict) and by `make geometry-check` over the gallery, the throne room and [`tests/fixtures/geometry_consistent.ttl`](../tests/fixtures/geometry_consistent.ttl). The two negative fixtures are the claim of this section made executable — [`geometry_inconsistent_rcc.ttl`](../tests/fixtures/geometry_inconsistent_rcc.ttl) and [`geometry_inconsistent_directional.ttl`](../tests/fixtures/geometry_inconsistent_directional.ttl) are conformant VSON that `vson validate` reports `OK` on all three gates, and `vson verify --geometry` refuses.

**Measured on the shipped corpus, 2026-08-01.** The 16-scene gallery and `examples/throne_room.ttl` are clean, though only just: no gallery scene carries both a rectangle and a spatial fact, so the gallery decides nothing and the positive fixture is what gives the target teeth. The 20 baked studio envelopes are not clean. Four asserted `rcc:TPP` facts across two of them are refuted by the boxes asserted beside them — `kitchen.json` `sf4`, and `lamp.json` `sf2`, `sf3` and `sf4`, of which `sf2` says the grass is a tangential proper part of the person standing on it. Both envelopes pass SHACL, OWL 2 RL and C2 today and stay conformant, and they are byte-frozen extractor output that is not rewritten to suit a check that arrived after them. They are recorded here as the measurement that says this check is not vacuous on real model output: the corpus that clears every conformance gate contains claims that refute themselves. The corpus held 21 envelopes on the measurement date; one demo image was withdrawn on 2026-08-04 ([`spec/CHANGELOG.md`](../spec/CHANGELOG.md)) and its envelope went with it. That envelope asserted no `vso:rcc` fact at all, so the numbers above — 13 relations over two rectangles, 11 a match-demanding gate would reject, 4 this one does — were what the remaining 20 still gave.

**Re-measured 2026-08-05, after the demo set changed shape.** Three demos left (two landscapes and the figure scene, withdrawn as editorially weak — with them went `lamp.json` and three of the four refuted facts) and five session-baked scenes arrived, so the corpus is 22 envelopes. The current numbers: **10** `vso:rcc` facts over two rectangles, of which a match-demanding gate would reject **6** and the refutation table rejects **1** — `kitchen.json` `sf4`, the surviving server-era self-contradiction, byte-frozen as before. The six-to-one gap is the section's argument in the corpus's own bytes, and one of the six is literal: `cat.json` asserts `rcc:EC` for a cat on a rug whose rectangles overlap with area — the example §5.13.2 argues from, shipped as frozen extractor output.

**Groundedness is still absent.** §2.1 named two things that establishing it would take, and this section supplies the first: geometry consistency is now decided. The second — ground truth for what geometry cannot decide, meaning class, dimension values, lemmas, thematic roles and frame attributions, against human annotation over a fixed image set with a published protocol and an inter-annotator agreement figure — does not exist in this repository. **Verified** in VSON still means *verified against the schema*, now with one more thing checked beside it and nothing checked against the picture.

### 5.14 Competency questions (`queries/`)

A competency question is the question a vocabulary must be able to answer (Grüninger & Fox 1995; the artefact the NeOn methodology carries through ontology design — [Appendix E](#appendix-e--related-work-and-bibliography)). Written down, it is a design record. Written down *as a query, against a corpus, beside its frozen answer*, it is a test, and the difference is why [`queries/`](../queries/) exists: every expressiveness claim §3–§5 makes is either reachable by one of these queries or it is not made good on.

**Twenty-nine questions**, `queries/CQ-01-*.rq` … `CQ-29-*.rq`. Each `.rq` carries a header stating the natural-language question, the persona who asks it (P1–P3 as defined in [`docs/strategy/productization.md`](./strategy/productization.md) §1), the section of this document that authorizes it, and its form. **Twenty-eight are executed** on every `make check` by [`tools/cq_check.py`](../tools/cq_check.py) (`make cq-check`) and compared byte-for-byte against a frozen answer in `queries/expected/`. One is not — see the capability matrix below.

**The corpus.** Seventeen documents: the sixteen gallery scenes of §9, compiled from VSON-P by the reference transpiler, plus [`examples/throne_room.ttl`](../examples/throne_room.ttl). Each is loaded into its own named graph, and each document's namespace is rewritten in memory from the transpiler's shared `https://example.org/scenes/anonymous#` to a per-document one. Without that rewrite all sixteen gallery scenes would share a namespace and `:scene`, `:cam` and `:alice` would be one node in every scene — the corpus would answer questions about a document that does not exist, and `?doc` would bind nothing real. No file under `examples/` is modified.

**Asserted triples only.** The pack is SPARQL 1.1 over the documents as written: no TBox in the corpus, no entailment regime, no reasoner. Where a question needs a class hierarchy the query names the asserted classes with `VALUES` rather than relying on `rdfs:subClassOf` entailment the corpus does not carry. That is a deliberate cost: it makes every answer reproducible by anyone with a SPARQL 1.1 engine and this checkout, which is the property a competency-question suite exists to have.

#### 5.14.1 What the questions cover

The table is the adequacy argument: the left column is a claim this document or the README makes, the right column is what makes it checkable.

| Claim | Stated in | Questions |
|---|---|---|
| Reified Frame taxonomy — context, style, camera, composition, persona | §5.2, §5.3 | CQ-01, CQ-02, CQ-03, CQ-04 |
| A Frame is never part of the depicted world | §2 (C9), §3.1 | CQ-05 |
| A composition depicts something | §2 (C4), §5.2 | CQ-06 |
| **Directional facts are viewer-anchored** | §2 (C5), §3.3, §5.7 | **CQ-07**, CQ-08, CQ-12 |
| RCC-8 as a closed value vocabulary, not a calculus | §5.7, §5.12 | CQ-09, CQ-10, CQ-11 |
| Trait-bundle entity model — animacy × countability × individuation × affordance | §3.2, §5.4 | CQ-13, CQ-14, CQ-15, CQ-16 |
| Quality reification over a closed dimension registry | §5.5, §5.5.1 | CQ-17, CQ-18 |
| Reified perdurants — a role structure an edge cannot carry | §3.4, §5.6 | CQ-19, CQ-20, CQ-21, CQ-22 |
| Causation and temporal order as separate vocabularies | §5.9 | CQ-23 |
| Annotation reification, and its RDF-star equivalent | §3.4, §5.11 | CQ-24, CQ-25, CQ-29 |
| Persona as a cross-document identity carrier | §5.3.4 | CQ-26 |
| Propositional layer — negation, belief, quantification | §3.4, §9.13–§9.15 | CQ-27 |
| Geometry the fourth gate can reach | §5.10, §5.13 | CQ-28 |

Two questions are there to find what no gate can see. CQ-11 asks whether one document asserts two different RCC-8 relations of the same ordered figure/ground pair, and CQ-12 asks the same of opposite directional values under one viewer. Both are contradictions in the intended interpretation and neither is visible to SHACL — each fact is its own node carrying its own single value, so every shape passes — nor to the OWL 2 RL gate, since `ontology/rcc8.ttl` ships the eight relations as a closed value vocabulary and asserts no composition table (§5.7). A query is the mechanism that reaches them. Both answer `false` on this corpus.

**Three answers are findings, not decoration.** CQ-15 reports two entities in the hand-authored canonical scene that omit `vso:countability` — conformant documents, since §2.1 lists Entity trait completeness among the things no shape examines, and §8.2 is why that stays true inside v1.x. CQ-10 reports that the corpus writes two of RCC-8's eight relations. CQ-28 reports that no spatial fact in the corpus has both endpoints carrying a `vso:bbox2d`, which is §5.13.7's measurement made re-derivable by anyone with a SPARQL engine rather than asserted in prose. A frozen answer that records a gap is worth more than one that records a success.

#### 5.14.2 SPARQL 1.1 and what the pack defers

| Feature | Used by | Status |
|---|---|---|
| Basic graph patterns, `GRAPH`, `OPTIONAL`, `UNION`, `FILTER`, `VALUES`, `FILTER NOT EXISTS`, aggregates with `GROUP BY` / `HAVING`, property alternative paths, `ORDER BY` | every executed question | SPARQL 1.1 — W3C Recommendation, 21 March 2013. Supported by the pinned engine. |
| Quoted-triple patterns — `<< ?s ?p ?o >>` (SPARQL-star) and the RDF 1.2 triple-term form `<<( ?s ?p ?o )>>` | CQ-29 only | Not in SPARQL 1.1. On the Recommendation track, and not depended on here. **Verified 2026-08-01: rdflib 7.6.0 parses neither form, in Turtle or in SPARQL, and registers no Turtle-star parser.** |

CQ-29 is the §5.11 confidence question written once across *both* spellings that section declares equivalent — the RDF-star quoted triple and the RDF 1.1 `vso:Annotation` node — which is what a consumer honouring §2's consumer-conformance rule has to do. It ships **unrun and with no frozen answer**, marked `Status: documented-future` in its header. Nothing in the corpus is lost by that: no shipped document uses the quoted-triple form, so the star branch would match nothing today and the reified branch is CQ-24, which does run. What is deferred is the proof that one query reaches both.

The skip is not taken on trust. `tools/cq_check.py` asserts that the engine *rejects* CQ-29 and fails when it accepts, so the day the pinned engine gains SPARQL-star this gate goes red and says to promote the query and freeze its answer. A skip nobody re-checks is a skip that outlives its reason.

#### 5.14.3 What a frozen answer establishes

Exactly what it says: that this query, over these seventeen documents, returns these rows. It is not a conformance clause — C1–C9 do not mention it, no producer or consumer obligation follows from it, and a document that would change one of these answers is not thereby non-conformant. It is not a reading of the picture either; §2.1 governs, and a competency question is a question about the *graph*.

What it does establish is the thing an expressiveness claim otherwise cannot have: a stranger can run `make cq-check` and watch the claim resolve, or read `queries/expected/` and see the answer without running anything. [`tests/test_competency_questions.py`](../tests/test_competency_questions.py) pins the rest — that every header is complete, that every § a header cites is a heading this document carries, that all three personas are exercised, that the coverage table above names every query in the directory and no query it does not, and that the counts spelled in this section are the directory's.

### 5.15 Graph agreement (`vson diff`)

Two extractions of one image produce two documents. Nothing so far in this specification says how far apart they are, and no string comparison can say it either: one run writes `:cat` where the other writes `_:e3`, one bases its IRIs on `.../anonymous#` and the other on `.../scene-42#`, and both may be describing the same animal. The node names are arbitrary. What is not arbitrary is the structure they carry, and this section defines the measurement over it — precision, recall and F1 over triples, under the variable alignment that maximizes matches.

That is **Smatch** (Cai & Knight 2013, for AMR — [Appendix E](#appendix-e--related-work-and-bibliography)), which is the point: VSON-P borrows AMR's Penman surface (§4.2), so it inherits AMR's evaluation problem — variables whose names carry no information — and there is an answer already in the literature for it. This section states what the metric is over *VSON's* graph, adds the per-layer sub-scores a layered scheme owes its readers, and pins the determinism that lets two people compare two numbers.

**It is not a fifth construct.** §2.1's table and §5.13's fourth row are properties of *one* document — is it well-formed, does it agree with itself. Agreement is a relation between **two**, and no verdict about either one follows from it. F1 = 1.0 says the two documents assert the same graph up to variable renaming; it does not say either describes the picture. Two runs of one model agreeing on the same hallucination score 1.0, and a run that scores 0.4 against a hand-annotated reference may be the one that is right. No image is read here either, and §2.1's prohibition stands unchanged over every number this section produces. Nor is it §4.6's denotation test: equal canonical forms imply F1 = 1.0 and F1 = 1.0 does not imply equal canonical forms, because this section compares document-local IRIs by local name and §4.6 compares them as written.

Reference implementation: [`tools/metrics/smatch.py`](../tools/metrics/smatch.py), run by `vson diff <a> <b>` (`--format json`; exit 0 identical, 1 differing, 2 no verdict) and importable as `compare_paths(a, b)` for an evaluation loop. Inputs may be `.ttl` (VSON-T), `.vson` (VSON-P) or `.x.vson` (VSON-X), in any combination: the metric is defined over the **materialized VSON-T graph**, so the surface an input was written in cannot move the score.

#### 5.15.1 Variables and constants

Every term of a document is exactly one of two things:

| Kind | Which terms | Matched by |
|---|---|---|
| **variable** | a blank node; or an IRI outside the VSON and W3C vocabulary namespaces that the document asserts at least one triple **about** (it appears in subject position) | the alignment — nothing else |
| **constant** | a literal; a vocabulary IRI (`vso:`, `rcc:`, `allen:`, `rdf:`, `rdfs:`, `owl:`, `xsd:`, `sh:`, `skos:`); or a document-local IRI that appears only in object position | a literal by lexical form **and** datatype/language; a vocabulary IRI by its full IRI; a document-local IRI by its **local name** — the substring after the last `#` or `/` |

The subject-position rule is the load-bearing one. `:alice a :Human` names a class the document says nothing else about, so `:Human` is a **constant** and its local name is all the identity it has: two runs that write `:Human` and `:Person` must not be credited with agreeing merely because an alignment could pair them. A node the document *describes* is an entity whose name is a naming choice, and comparing those names across runs would measure nothing. The local-name rule for constants is what makes the score independent of the document base, which every run picks for itself.

A node one document describes and the other only names is a variable on one side and a constant on the other. The triples reaching it then cannot match, and that is the intended reading: the two documents disagree about whether it is an entity.

Predicates are always compared as constants. A document-local predicate would violate C2, and `vson validate` is where that is reported.

**One normalization, before anything else.** §5.2 declares `vso:depicts`, `vso:hasFact` and `vso:occurs` interchangeable for the same target, and the VSON-X parser emits only the first. All three are rewritten to `vso:depicts` before scoring, so a scene written with `:hasFact` in one syntax and `:depicts` in another is not reported as a disagreement this specification says does not exist. Nothing else is normalized: RDF-star quoted triples, `owl:sameAs`, and every other equivalence a reasoner could derive are out of scope, and the metric runs on **asserted triples only**, like the query pack of §5.14.

#### 5.15.2 The alignment, and the score

An **alignment** `M` is a partial injection from the variables of document A to the variables of document B. A triple `(s, p, o)` of A **matches** a triple of B under `M` when the predicates are equal and, in each of the two endpoint positions, either both sides are the same constant, or both sides are variables and `M` maps A's to B's. A variable never matches a constant, and an unmapped variable matches nothing.

Write `m(M)` for the number of matched triples. The reported score uses `M* = argmax m(M)`:

```text
precision = m / |A|          recall = m / |B|          F1 = 2·m / (|A| + |B|)
```

Matching is a bijection between the two matched subsets, so `m` counts the same pairs from either side and **F1 is symmetric**: `diff a b` and `diff b a` report the same F1 with precision and recall exchanged. Two conventions close the degenerate cases: two documents that assert nothing are identical (F1 = 1.0), and a layer with no triples on either side reports no number at all rather than a zero — there was no agreement to reach.

**Finding `M*` is NP-hard** (Cai & Knight prove it by reduction from a maximum-matching problem), so this is a search and not a computation. The reference implementation is the standard one: steepest-ascent hill climbing over two move kinds — re-point one variable, or swap two variables' targets — from several initializations, keeping the best result. A reported number is therefore a **lower bound** on the true maximum, and §5.15.4 is what makes it a repeatable one. An implementation **MUST** report the restart count and seed it used, and **SHOULD** report `m`, `|A|` and `|B|` as integers beside the ratios: the counts are exact, and the ratios are derived.

#### 5.15.3 The layers

A scheme whose thesis is that scene structure comes in layers has to report per layer. One F1 says how far apart two runs are; it never says *which* layer moved, and "the objects agree and the spatial relations do not" is the finding worth having.

Every triple lands in exactly one layer, by these rules **in order**. `family(n)` is the layer of the first VSO class the document asserts as `n`'s type, by the class table below; the tables are closed lists, and anything unlisted falls through to `other`, so the partition is total by construction.

| # | Rule | Layer |
|---|---|---|
| 1 | `p` is `rdf:type` and the object is a VSO class | the class table's row |
| 1a | `p` is `rdf:type` and the object is another vocabulary IRI | `other` |
| 1b | `p` is `rdf:type` and the object is a document-local class (`:alice a :Human`) | `family(s)`, else `objects` |
| 2 | `family(s)` is `other` — the subject is an `Annotation`, `Negation`, `BeliefState` or `Quantification` | `other` |
| 3 | `p` is the normalized Composition edge `vso:depicts` | `family(o)`, else `objects` |
| 4 | `p` ∈ frame properties | `frames` |
| 5 | `p` ∈ spatial properties | `spatial` |
| 6 | `p` ∈ event properties, or `p` is in the `allen:` namespace | `events` |
| 7 | `p` ∈ attribute properties | `attributes` |
| 8 | anything else | `other` |

| Layer | Classes (rule 1) | Properties (rules 4–7) |
|---|---|---|
| `objects` | `Entity`, `Endurant`, `PhysicalObject`, `Aggregate`, `Substance`, `Region` | — (reached through rules 1b and 3) |
| `attributes` | `Quality` | `individuation`, `animacy`, `countability`, `affordance`, `class`, `hasQuality`, `dimension`, `value`, `modifier`, `bbox2d`, `position3d`, `scale3d`, `rotation` |
| `spatial` | `SpatialFact` | `figure`, `ground`, `rcc`, `directional`, `proximal`, `viewer`, `occludes`, `visibleFraction` |
| `frames` | `Frame`, `SceneContext`, `VisualStyle`, `CameraView`, `Composition`, `Persona` | `framedBy`, `viewedBy`, `rendersAs`, `angle`, `focalLength`, `framing`, `lookAt`, `cameraPosition`, `aesthetic`, `palette`, `medium`, `venue`, `atmosphere`, `timeOfDay`, `weather`, `embodies`, `hasInvariant` |
| `events` | `Perdurant`, `Event`, `Process`, `Stative` | `lemma`, the thematic roles of §5.6, `causes`, `enables`, `prevents`, `triggers`, `holds`, `wears`, `owns`, `carries`, and every `allen:` relation |
| `other` | `Annotation`, `Negation`, `BeliefState`, `Quantification` | mereology (§5.8), the propositional layer (§5.9), annotation reification (§5.11), and anything unlisted |

Two rules earn their place. **Rule 3** files a Composition membership edge under the layer of *what it points at* — a `vso:depicts` reaching a `vso:SpatialFact` is a spatial disagreement, not a frame one — which also makes the layer independent of which of the three interchangeable edges the author wrote. **Rule 2** routes by subject rather than by predicate because `vso:source` is a thematic role on a Perdurant and a provenance string on an `vso:Annotation`; the subject decides which.

**Sub-scores are computed under the single global alignment**, never by re-optimizing per layer. A per-layer optimum would report a number no single reading of the two documents achieves, and the rows would no longer sum to the whole. Precision counts matched triples on A's side of a layer and recall on B's, which lets the two differ inside a layer when a matched pair falls in different layers on the two sides — one document types a node and the other does not. F1 is then the harmonic mean of the two, and reduces to `2m/(|A|+|B|)` whenever they agree.

**`spatial` is reported twice.** The second reading, `viewer-blind`, is the same layer with `vso:viewer` triples dropped from both sides. Directional facts are viewer-anchored by C5 (§3.3), so two runs can agree completely about *what is where* and disagree about which camera anchors it — a disagreement worth seeing separately from a disagreement about the relation. The alignment is unchanged; only the counted set is.

#### 5.15.4 Determinism, and the seed policy

A metric whose number moves between runs is not a metric. Three commitments pin this one, and an implementation that wants comparable numbers **MUST** state its position on all three:

1. **The restarts are enumerated, not sampled.** Restart 0 is the **colour-refinement alignment**: a 1-WL refinement of both graphs — a variable's initial colour is the multiset of its constant-anchored edges, and each round folds in its variable neighbours' colours — with variables ordered by colour and paired at equal rank. Restart 1 is the **greedy constant-anchored alignment**: the pair sharing the most constant-anchored triples first, then the next, skipping any variable or target already taken. Restarts 2…R−1 are pseudo-random. The default R is **5**.
2. **The pseudo-random source is specified, not imported.** A language's standard shuffle is not reproducible across versions and is reproducible across languages by accident at best. The generator is a 64-bit LCG, seeded `seed + restart_index`, driving a Fisher-Yates shuffle:

   ```text
   state ← (state · 6364136223846793005 + 1442695040888963407) mod 2⁶⁴
   output ← (state >> 32) mod 2³²
   ```

   The default seed is **0**, and CI runs the default. A published VSON agreement number **MUST** state its seed and restart count, exactly as an AMR Smatch number states its restart count.
3. **No ordering decision consults a name.** Variables are ordered by refinement colour, and ties — variables the refinement cannot tell apart — by first appearance. Blank-node labels are minted per parse and differ between runs of one file, so an implementation that sorted on them would make its score depend on its parser.

Together these make `vson diff a b` byte-identical on repeated runs, which [`tests/test_smatch.py`](../tests/test_smatch.py) checks on a blank-node-heavy pair rather than assuming.

#### 5.15.5 What a score establishes

Exactly this: that under the best alignment this search found, these two documents share this many triples. Four things follow, and no others.

- **It is not conformance.** C1–C9 do not mention agreement, no producer or consumer obligation follows from a score, and a document that scores 0.0 against another may be perfectly conformant. `vson validate` and `vson diff` answer different questions.
- **It is not correctness.** Neither document is a reference unless something outside this specification made it one. Calling the left-hand document "gold" is a decision about provenance, not a property the metric can see.
- **It is not a reading of the picture.** §2.1 governs: no image is read, and a tool reporting a score **MUST NOT** present it as evidence that either document is accurate, faithful, or verified against the image.
- **It is a lower bound.** The search is hill climbing over an NP-hard objective; a different restart budget may find a better alignment, and it will never find a worse score than the one reported, because the reported score is achieved by an alignment the implementation holds.

What it is *for* is the two things a scheme cannot otherwise have: a regression signal (this pipeline change moved the spatial layer by 0.1) and, given a corpus and a protocol this repository does not have, the statistic an inter-annotator agreement study would report. AMR states its annotator agreement as a Smatch figure, which is the comparison a future VSON number would be read against; no such VSON figure exists, and §2.1's second missing ingredient — the corpus, the protocol, the annotators — is unchanged by this section. What v1.3 adds is the instrument, not the measurement.

#### 5.15.6 Where it runs, and what it found

`vson diff` is not a `make check` gate: there is no corpus of run pairs to freeze a score over, and a gate over an empty set asserts nothing. What CI runs is [`tests/test_smatch.py`](../tests/test_smatch.py), which pins the metric's properties — identity, symmetry, determinism, invariance to renaming and to surface syntax — and the exact counts on the known-delta pair, and [`cli/tests/diff_gate.rs`](../cli/tests/diff_gate.rs), which pins the same table through the binary.

**Measured on the shipped corpus, 2026-08-01.**

- Every gallery scene and `examples/throne_room.ttl` score **1.0** against themselves, in every populated layer. That is the floor, and it is worth stating that it is reached with blank nodes on both sides.
- Each of the **twelve** `examples/gallery-x/*.x.vson` scenes scores exactly **1.0** against its VSON-P twin — including the 131-triple throne room, where one side names its Quality and SpatialFact nodes and the other leaves them blank. Surface syntax does not move the score, and this is what makes that claim checkable rather than asserted.
- `examples/throne_room.ttl` against `examples/gallery/11_throne_room.vson` — the hand-authored canonical scene against the gallery's Penman rendering of "the same" scene — scores **F1 0.767** (107 matched, of 148 and 131). The layers say where: `frames` 1.0, `spatial` 0.857, `events` 0.844, `objects` 0.800, `attributes` 0.733, `other` 0.0. The canonical file carries fourteen triples the gallery has no counterpart for at all — a `vso:Annotation` node with its three `annotated*` edges, its confidence and its source, and four local `rdfs:Class` declarations with their `rdfs:subClassOf` — and it spells the domain class as `rdf:type :Human` where the gallery writes `vso:class`. Both are conformant, both are shipped, and neither is wrong. The number is what "the same scene, written twice" actually costs, and it is a better calibration for a reader than any pair constructed to agree.

---

### 5.16 Machine-readable validation reports (`vson validate --format`)

§2 says what a verifier decides. This says how it tells a reader that is a **program**, because the two things a verifier has said until now are an exit code — one bit, about a whole run, with no location in it — and a human report beside it. Neither can put a mark on the line that caused the failure, and a build that can only say "something in here is wrong" is a build people learn to ignore.

**Four shapes, one verdict.**

| `--format` | What lands on stdout | For |
|---|---|---|
| `text` (default) | `OK` / `FAIL <file> (<gate>)`; each checker's own report goes to stderr | a person at a terminal |
| `json` | one document carrying the records of §5.16.1 | a script, a dashboard, a repair loop |
| `sarif` | a SARIF 2.1.0 log (OASIS, March 2020 — [Appendix E.6](#appendix-e--related-work-and-bibliography)) | code scanners: GitHub, GitLab, and everything that reads them |
| `compact` | one line per finding — §5.16.8 — then the `text` verdict line | a build log, a `grep`, a person reading either |

The verdict does not move with the format. An implementation **MUST** reach the same conformance decision and return the same exit code whichever format it was asked for: the formats differ in what a run *says*, never in what it decides. A structured run **MAY** report more violations than the text run prints — the reference text gate passes `--abort` to `pyshacl` and stops at the first, while a report of the first violation is not a report — and the set of documents each calls conformant is nonetheless identical.

**A clean run still produces a report.** A conformant input **MUST** produce a report whose finding set is empty, not an empty file and not no file at all. A caller that cannot tell "nothing was wrong" from "the tool never ran" has learned nothing from a green build.

#### 5.16.1 The record

One record per violation, with the parts of it that a program would otherwise have to recover from prose kept as fields.

| Field | Type | What it carries |
|---|---|---|
| `gate` | `"shacl"` \| `"owl-consistency"` \| `"c2"` | which of §2's three gates reported it |
| `rule` | string | a stable identifier to group and suppress by: `vson/shacl/<shape local name>`, `vson/owl-consistency/<clash kind>`, `vson/c2/orphan-term` |
| `severity` | `"violation"` \| `"warning"` \| `"info"` | the local name of `sh:resultSeverity`, lower-cased. The two gates that are not SHACL emit `violation`: neither computes a severity, and inventing one would be a claim |
| `message` | string | `sh:resultMessage`, or the gate's own wording |
| `shape` | IRI \| null | the **named** shape the violation belongs to — see below |
| `constraint` | IRI \| null | `sh:sourceConstraintComponent`, or the OWL construct that clashed |
| `focus_node` | IRI \| null | `sh:focusNode`. Null where the finding is about a *term* rather than a node: a C2 orphan is a name the document uses, and no node in the graph is at fault for it |
| `result_path` | IRI \| null | `sh:resultPath` |
| `value` | string \| null | `sh:value`, the second term of an OWL clash, or the orphan term itself |
| `location` | object \| null | §5.16.3 |

**`shape` names a shape a reader can look up.** A SHACL violation reports its source shape, and in these shapes that is almost always a blank node nested inside a named node shape (`vss:DirectionalNeedsViewerShape sh:property [ sh:path vso:viewer ; … ]`). A blank node identifies nothing across runs, so an implementation **SHOULD** report the nearest named ancestor in the shapes graph and **MUST NOT** report a blank node identifier as if it were a name. Where no named ancestor can be established, `shape` is null and `rule` falls back to the constraint component — the honest form of "this fired, and I cannot tell you what to call it".

**Order is part of the format.** A SHACL validation report is a graph, and a graph has no order; two runs over one document would otherwise emit the same findings in different sequences, and no output could be frozen or diffed. Findings **MUST** be emitted in an order that is a function of their content alone. The reference implementation sorts by `focus_node`, then `result_path`, then `constraint`, then `message`.

**At most one gate speaks.** The three gates run in §2's order — SHACL, then OWL 2 RL, then C2 — and stop at the first that fails, so every finding in a report comes from the same gate, and the report's `gate` field names it. A document that would fail two gates is reported against the first; that is what `vson validate` has always done, and the structured formats do not change it.

#### 5.16.2 Exit codes

| Code | Meaning |
|---|---|
| 0 | every input cleared all three gates |
| 1 | an input genuinely failed one |
| 2 | no verdict was reached: a missing dependency, an unparseable input, an unknown flag |

The 1-versus-2 distinction is the load-bearing one, and it is not free: the checkers behind the gates exit 1 both for "the document is bad" and for "I crashed", so a missing library and a malformed document arrive on the same code. A verifier **MUST NOT** report a broken toolchain as a failing document. The reference implementation separates the two by what the checker *produced* — a summary line for the text gates, a parseable report document for the structured ones — and treats anything else at exit 1 as exit 2 with the child's stderr attached.

#### 5.16.3 Source positions, and where there are none

`location` carries `line` and `column` (both 1-based, the column counted in Unicode scalar values), the `anchor` text that was matched, and `resolved_from` — the strategy that found it. It is present only when the position was **established**:

| `resolved_from` | How | Exact? |
|---|---|---|
| `penman-variable` | the focus node's local name is the Penman variable that declares the node (§4.2 mints the IRI from it); the position is the declaring token's, from the lexer | yes |
| `turtle-subject` | the first line whose leading term denotes the focus node | no — a textual scan |
| `mention` | the first place the term appears at all, for a finding with no focus node | no — a textual scan |

An implementation **MUST NOT** report a position it did not establish. Where the mapping fails — a Turtle subject written on a continuation line, a blank node with no name to look for, a prefixed name the scan cannot resolve — `location` is null and the finding names its file alone. A guessed line is worse than no line: it sends a reader to a place where nothing is wrong, and it does so with the same confidence as a correct one.

This is the one part of a report that is about the **surface** rather than the graph, and it is exact for exactly one surface. VSON-T (§4.1) is read by an RDF parser that reports no positions, and VSON-X (§4.3) is not an input to `vson validate` at all.

#### 5.16.4 The SARIF mapping

SARIF is what a scanner already reads, which is the whole reason to emit it. Each record becomes one `result`:

| Record | SARIF |
|---|---|
| `rule` | `result.ruleId`, and a `reportingDescriptor` in `tool.driver.rules` at `result.ruleIndex` |
| `severity` | `result.level` — `violation` → `error`, `warning` → `warning`, `info` → `note` |
| `message` | `result.message.text` |
| the input's path | `result.locations[0].physicalLocation.artifactLocation.uri`, as given, so a run from the repository root yields repository-relative URIs |
| `location` | `…physicalLocation.region.startLine` / `.startColumn`, omitted entirely when null |
| everything else | `result.properties` — `focusNode`, `resultPath`, `shape`, `constraint`, `value`, `gate`, `resolvedFrom` |

The log declares `runs[0].columnKind` as `unicodeCodePoints`. SARIF's default is UTF-16 code units, and leaving it unstated would put every column past a multi-byte character silently out by a few. A `reportingDescriptor` carries `helpUri` only where there is a real one to carry — a `vss:` shape IRI dereferences (§5.1) — and none is invented for the gates that have none. No `$schema` is emitted: it is optional, nothing consumes it here, and the only thing it would add to every report is a third-party URL this project has not checked resolves.

Emitting SARIF is not uploading it. Code scanning ingestion is a platform feature with its own preconditions, and a tool that quietly assumed them would report success for an upload that did nothing; the reference composite action therefore writes the log and annotates through ordinary workflow commands, leaving the upload to a caller who knows their platform admits it.

#### 5.16.5 Standard input

An input named `-` is read from standard input. It **MUST** be named at most once — there is one stream, and a second `-` would validate an empty document and call it conformant.

A stream has no extension to read a syntax off, so the syntax is decided by the first token that is neither whitespace nor a comment: `(` is VSON-P (§4.2), anything else is VSON-T (§4.1). Empty input is VSON-T, which parses to a graph of no triples rather than to a parse error nobody asked for.

#### 5.16.6 Versioning, profiles, and what is frozen

The JSON document names its own format in a `report` field, `vson-validate/1`; the record stream between the reference implementation's two halves names itself `vson-validate-records/1`, and a reader that finds a version it does not know **MUST** say so rather than interpret the records anyway. A SARIF log identifies itself the way SARIF does, with `version`, and carries no VSON version of its own. Adding a field is **not** a breaking change and does not bump the number; removing one, or changing what one means, does. A consumer **MUST** ignore fields it does not know.

The JSON document also names the `profile` that produced it. Only `strict` decides C3 and therefore conformance (§6.1); `relaxed` names a shapes file that ships and that no shipped command selects, and a verifier asked for it **MUST** either validate against that file or refuse — never validate against the strict shapes and label the result relaxed.

The reference output is frozen, byte for byte, at [`tests/fixtures/validate_report/`](../tests/fixtures/validate_report/): the JSON and SARIF reports for [`tests/fixtures/bad_no_viewer.vson`](../tests/fixtures/bad_no_viewer.vson), compared against the binary's output by [`cli/tests/report_format.rs`](../cli/tests/report_format.rs) and checked for still being *valid* SARIF — not merely stable — by [`tests/test_validate_report.py`](../tests/test_validate_report.py). They are referenced here rather than reproduced here for the reason §6.1's fragments exist to guard: a quoted copy of a shipped artifact is a copy that drifts, and this document outranks the artifact it would be misquoting.

`compact` carries **no version of its own** and is deliberately not a document format. It is a rendering of the same records for a reader, and the only parts of it a consumer may rely on are the ones §5.16.8 states: the leading position, the two-space field separation, one line per finding, and the verdict line it shares with `text`. A program that needs a field is asking for `json`, which is where the compatibility promise above lives.

#### 5.16.7 What a report establishes

Exactly what §2 and §2.1 say a verdict establishes, and nothing further. A report is the same verdict with its parts named: a finding is a place where the document breaks a shape, a clause or the vocabulary, and an empty report is a document that breaks none of them. No image is read at any point, so a producer, a consumer or a build **MUST NOT** present a green report as evidence that the document describes the picture — and a passing SARIF log, which a scanner will render beside findings from tools that do read the artifact they check, is the easiest place in this specification to forget that.

#### 5.16.8 The compact rendering

The two structured formats above are read by programs that were written for them. `compact` is for the two readers nobody writes a parser for — a person scrolling a failed build, and a `grep` — and it is one line per finding:

```text
<path>:<line>:<column>  <rule>  <message>
```

— two spaces between the fields, as in this run of the reference implementation over the negative fixture the goldens of §5.16.6 are frozen from:

```text
tests/fixtures/bad_no_viewer.vson:26:14  vson/shacl/DirectionalNeedsViewerShape  Directional spatial facts require exactly one vso:viewer for construal disambiguation (C5), and that viewer must be a CameraView, never an Entity.
FAIL tests/fixtures/bad_no_viewer.vson (shacl)
```

Each input's findings are followed by that input's `text` verdict line — `OK  <file>` or `FAIL <file> (<gate>)`, character for character, so that a reader who has seen one format has seen the other's answer. Four things are required of the finding lines, and each one is what makes them usable rather than merely short:

* **One finding is one line.** Every run of whitespace in the message — a `sh:message` may be written across several lines — is collapsed to a single space. A format that sometimes wraps cannot be counted with `grep -c` or filtered with `grep -v`.
* **The position leads**, in the `path:line:col` form a person recognises and an editor's error parser already reads. Where §5.16.3 established no position, the path stands alone: a finding that prints `:1:1` because it had nothing better sends a reader somewhere nothing is wrong.
* **Fields are separated by two spaces**, and no field but the message may contain a run of two. A split on the separator therefore yields the position, the rule and the message, in that order, whether or not the position resolved.
* **The `rule` stands in for the shape.** It is the shape's name in the form §5.16.1 defines — `vson/shacl/<local name>` — because the `shape` field is a full IRI on a SHACL finding and null on the two gates that have no shapes to report.

Everything else a record carries is dropped, not summarised: the focus node, the result path, the constraint component, the severity and the syntax appear in `json` and in `sarif`, and a reader who needs one is asking a different question than the one this format answers. Consequently a `compact` run is **not** a report a repair loop should parse; §5.16.6 says which format carries the promise.

### 5.17 External alignment ([`ontology/alignments.ttl`](../ontology/alignments.ttl))

A vocabulary that points at nothing outside itself is a vocabulary a stranger has to take on trust. Through v1.3 this one pointed outside twice — the eight `rcc:` individuals at OGC GeoSPARQL and the thirteen `allen:` properties at W3C OWL-Time (§5.9) — and the 186-term core pointed nowhere at all. This section is the layer that changes that, and the precise statement of how little it claims.

#### 5.17.1 What ships, and what loads it

[`ontology/alignments.ttl`](../ontology/alignments.ttl) is an **additive layer**. It is not in the `owl:imports` closure of the canonical name (§5.1.1), not in [`tools/shacl_helper.py`](../tools/shacl_helper.py)'s ontology list, and not loaded by any gate: `vson validate`'s three gates, `make check`'s SHACL and OWL 2 RL steps, the conformance suite of §2.2 and the studio's in-browser worker all see the same graph after this file exists that they saw before it. A conformant document is conformant whether or not a consumer ever fetches it, and nothing in this section changes a C-clause, a shape or a value space.

That inertness is the design, not an omission. Every triple in the file is a statement about how a VSON term relates to a vocabulary VSON does not depend on. A consumer that wants those statements fetches them; a consumer that does not should not receive them by parsing the canonical name.

The file is published at `/v1/alignments.ttl` on the namespace host and is **not** one of the names §5.1 promises to dereference: the `w3id.org` rule routes the five v1 namespace documents explicitly, `https://w3id.org/vson/v1/alignments` is not among them, and [`scripts/check_live_claims.py`](../scripts/check_live_claims.py) carries no claim for it. The name is declared in the document header because an `owl:Ontology` needs one; no dereference is promised, for the same reason §8.1 makes no promise for `owl:versionIRI`.

#### 5.17.2 The two predicates, and the entailment neither imports

Exactly two predicates appear, and an implementation reading the file **MUST NOT** find a third:

| Predicate | What it records |
|---|---|
| `skos:closeMatch` | The two terms have the same reading and could be interchanged in most applications. |
| `skos:relatedMatch` | The two terms are associated, and one is **not** a substitute for the other. |

Neither imports an OWL entailment. `owl:sameAs`, `owl:equivalentClass`, `owl:equivalentProperty`, `rdfs:subClassOf`, `rdfs:subPropertyOf` and `skos:exactMatch` are absent, and [`tests/test_alignments.py`](../tests/test_alignments.py) fails the build if one appears. A consumer that wants the aligned vocabulary's triples **MUST** rewrite them itself, and no VSON gate checks that rewrite — the advisory posture of the §5.9 design note, applied to the whole core.

The alignments themselves, and what each one does *not* claim:

| VSON term | Predicate | Target | The claim, and its limit |
|---|---|---|---|
| `vso:Endurant`, `vso:Perdurant`, `vso:PhysicalObject`, `vso:Substance`, `vso:Aggregate`, `vso:Quality` | `closeMatch` | `gufo:Endurant`, `gufo:Event`, `gufo:Object`, `gufo:Quantity`, `gufo:Collection`, `gufo:Quality` | §3.1's top is DOLCE-*inspired*, and gUFO ([E.3](#appendix-e--related-work-and-bibliography)) is the nearest published vocabulary whose terms are IRIs. The matches hold **term by term and do not compose**: `gufo:Quantity` and `gufo:Collection` are subclasses of `gufo:Object`, while `vso:Substance` and `vso:Aggregate` are siblings of `vso:PhysicalObject`. That is exactly the difference between `skos:closeMatch` and `rdfs:subClassOf`, and the reason only the first is asserted. |
| `vso:Region` | `relatedMatch` | `gufo:QualityValue` | A region is the space a value is drawn from; a quality value is the value. Neighbours, not substitutes. |
| `vso:properPartOf` | `closeMatch` | `gufo:isProperPartOf` | Transitive proper parthood, same direction. `vso:partOf` and `vso:hasPart` have no counterpart at that level and are left unaligned. |
| `vso:Annotation`, `vso:annotatedSubject`, `vso:annotatedPredicate`, `vso:annotatedObject` | `closeMatch` | `rdf:Statement`, `rdf:subject`, `rdf:predicate`, `rdf:object` | §5.11's reified form **is** RDF reification spelled in this namespace. VSON declares its own because the node also carries the payload (`vso:probability`, `vso:confidence`) and because it is a member of the disjointness set that separates the reification kinds from the Frame layer — a membership `rdf:Statement` could not be given without constraining RDF's own vocabulary. |
| `vso:Annotation` | `relatedMatch` | `oa:Annotation` | The body/target separation is the same shape ([E.6](#appendix-e--related-work-and-bibliography)); the targets are not. An `oa:Annotation` targets a resource or a media fragment, a `vso:Annotation` targets a **triple**, and the Web Annotation model defines no target for a statement. |
| `vso:depicts` | `relatedMatch` | `foaf:depicts` | `foaf:depicts` runs from an image; `vso:depicts` runs from a `vso:Composition`, which is the mereological root of a scene and not a depiction of one. A rewrite has to decide which image the Composition belongs to, and this vocabulary does not say. |

#### 5.17.3 The four gaps, and why each is a sentence rather than a triple

An alignment whose target has no IRI cannot be a triple. Recording it as prose is the honest form; recording it as nothing is what makes a related-work section look complete when it is not. Each of the four below is also an `rdfs:comment` on the alignment document, so a consumer holding only that graph gets the reason too.

- **ISO 24617-7:2020.** Its link structures carry a relation type and two required arguments, and the revised movement link names those two `@figure` and `@ground` — the same asymmetry `vso:figure` / `vso:ground` carries, standardized before this project existed. No triple is minted because the standard is specified as an abstract syntax with XML concrete syntaxes and publishes no RDF namespace: there is no IRI for `@figure` to close-match. [Appendix E.7](#appendix-e--related-work-and-bibliography) states the correspondence, and §3.3 states what it costs the novelty claim.
- **The vision datasets' label vocabularies.** `vso:class` is an open dimension (§5.12) and the obvious place to meet Visual Genome, GQA, PSG and Open Images V7. None is minted: PSG's object and predicate classes and GQA's cleaned vocabulary ship as label lists rather than IRIs, and Open Images V7 identifies classes by Freebase / Google Knowledge Graph MIDs (`/m/01g317`), which are identifiers rather than names that resolve today. A per-dataset mapping table is **data**, belongs with an importer, and is not an alignment — which is exactly where the three that ship live: [`tools/importers/mappings/`](../tools/importers/mappings), one JSON file per dataset, keyed on the source label (§7.1).
- **PROV-O.** VSON records producer provenance only as envelope JSON (§6.1) and as a free-text value, so there is no TBox term for `prov:wasGeneratedBy` or `prov:wasAttributedTo` to match. The one property whose name invites the mapping, `vso:source`, is already the *source* thematic role of a motion (§5.6); aligning it to provenance would make one IRI carry two unrelated readings.
- **`schema:ImageObject`.** VSON models the scene, not the file: no term denotes the image, its bytes, its dimensions or its URL. That absence is why the depiction alignment above sits on `vso:depicts` and is `relatedMatch`.

#### 5.17.4 The SKOS view of the closed value vocabularies

Six value spaces are closed to producer invention (§5.12) and their members are IRIs: `vso:individuation`, `vso:animacy`, `vso:countability`, `vso:affordance`, `vso:directional`, `vso:proximal`. That is the shape of a controlled vocabulary, and the interchange form for a controlled vocabulary is SKOS — the form a term browser, a thesaurus tool and a vocabulary registry ask for and that the VSON namespace could not give them.

The second half of the alignment file is that view: one `skos:ConceptScheme` per value class, one `skos:Concept` per value, `skos:inScheme` and `skos:topConceptOf` on every member because these vocabularies are flat. It is **generated** from [`ontology/vso.ttl`](../ontology/vso.ttl) by [`scripts/build_alignments.py`](../scripts/build_alignments.py): every `skos:prefLabel` is that value's own `rdfs:label` and every `skos:definition` its own `rdfs:comment`, copied rather than re-worded, so the view cannot say something the vocabulary does not. [`tests/test_alignments.py`](../tests/test_alignments.py) checks it twice — against a SKOS integrity shapes graph with `pyshacl`, and term-by-term against the source vocabulary, which SHACL cannot do because the source is not in the file under test.

Typing a value `skos:Concept` does not remove it from its VSO class, does not make it an `owl:Class`, and asserts no hierarchy. The eight `rcc:` relations are not viewed here — they are individuals in their own document, which already carries their GeoSPARQL alignment — and the thirteen `allen:` relations are not either, because they are *properties*, and a concept scheme whose members are properties is a category error. `vso:dimension` is closed only within the VSO namespace (§5.12) and takes document-namespace IRIs as conformant values, so it is not a controlled vocabulary in this sense.

### 5.18 Agent tool surface (`vson mcp`)

The loop this whole specification is built around — a model emits a scene, a validator rejects it with the message that fired, the model rewrites it — has always needed someone to write the plumbing: read the document out of the reply, shell out to a verifier, parse a report, build a repair prompt. §5.16 gave that plumbing a machine-readable report to read and [`vson/`](../vson) gave it a library call. This section is the surface where the plumbing is already there, because an agent's tool call *is* the plumbing.

`vson mcp` serves the reference implementations as Model Context Protocol tools, speaking JSON-RPC 2.0 over newline-delimited JSON on standard input and output. [`vson/mcp.py`](../vson/mcp.py) is the server and `python3 -m vson.mcp` runs it directly; the subcommand starts that same module with three streams inherited.

**This section is informative, and the one thing it constrains is honesty.** MCP is a third-party protocol with its own revisions, and this specification neither profiles it nor requires anyone to implement it: a verifier that serves no tools is exactly as conformant as one that serves all four. What is normative is that a tool named after a VSON operation performs that operation — a server that answers `vson_validate` **MUST** reach the same verdict `vson validate` reaches on the same document and profile, because a second answer under the same name is the drift §2 exists to forbid.

#### 5.18.1 The four tools

| Tool | Arguments | Returns |
|---|---|---|
| `vson_validate` | `document` or `path`, optional `syntax`, optional `profile` | the §5.16.6 `vson-validate-records/1` document with a `profile` field added — `conforms`, the `gate` that fired, and one finding per violation carrying the `sh:message` text a repair is written from |
| `vson_convert` | `direction` (`p2t` \| `x2t`), `document` or `path` | the VSON-T text (§4.1). There is no reverse direction, here or in the CLI: §6.1 defers back-conversion to an authoring surface |
| `vson_export` | `format` (`caption` \| `fol` \| `cypher`), `document` or `path`, optional `syntax` | the rendering, as text (§7) |
| `vson_skill_prompt` | optional `notation` (`p` \| `x`) | [`skills/vson-extractor/SKILL.md`](../skills/vson-extractor/SKILL.md) or [`skills/vson-extractor-x/SKILL.md`](../skills/vson-extractor-x/SKILL.md), verbatim |

The fourth is the one that is not a wrapper around an existing command, and it is the point of the set. Every other tool here tells an agent it was wrong; this one tells it what is right *before* it writes — the closed value vocabularies of §5.12, the trait bundles of §5.4, and the clauses of §2 that a document is about to be judged against. A server's `initialize` result **SHOULD** say so in its `instructions`, because a repair round avoided costs nothing and a repair round is the expensive half of the loop.

**A rejected document is a result, not a failure.** MCP distinguishes a protocol error, which the model never sees, from a tool result flagged as an error, which it reads. A document that breaks a shape is neither: it **MUST** come back as an ordinary successful result whose `conforms` is `false`, for the same reason `validate()` returns a `Verdict` rather than raising ([`vson/errors.py`](../vson/errors.py)). An error result is for a call that could not be made — a path that does not exist, a document that will not parse, a rendering that is not reachable.

**Which argument was given is the answer to what the input is.** `document` carries the text and `path` names a file; a call gives exactly one, and nothing downstream re-decides which it was. A `document` whose text happens to name a file **MUST** be read as that text — `{"document": "scene.vson"}` is ten characters, not a scene — and a `path` **MUST** be read as a file. This adds nothing to the requirement above; it is that requirement at the one place a server can quietly break it, because the tempting shortcut — `os.path.isfile`, or any other question put to the filesystem — answers about the directory the server was started in, which is a directory the caller never named. A server that asks it reaches the verdict `vson validate` reaches on a *different* document, under the name of the one it was sent, on the machines where the two collide.

#### 5.18.2 What is not served

No resources, no prompts, no sampling, no roots, no completion and no logging: the reference server declares the `tools` capability and nothing else, and a client needing more needs a different server. Two further gaps are properties of this repository rather than of the protocol:

* **Cypher has no Python implementation.** The mapping exists once, in [`cli/src/commands/export_cypher.rs`](../cli/src/commands/export_cypher.rs), over the Penman AST — so the server shells back out to a `vson` binary for it rather than keeping a second copy, and reads VSON-P input only. Two error results follow from that, and the order between them is fixed: the input is settled first, so an input that does not present as VSON-P — by the `syntax` argument, by the extension of a `path` (one naming no VSON syntax is refused, not guessed at), or by the first token of a `document` — is refused as such whether or not a binary is reachable, and only an input that does present as VSON-P reaches the error result naming the missing binary. Settling a syntax is not parsing it: a document that presents as Penman and is not one is the renderer's own parse error, wherever there is a renderer to reach. `caption` and `fol` are Python and need none of this. The `vson mcp` subcommand hands its own path down, so under that entry point all three formats are always available.
* **No image is read, and no network is opened.** Every tool here is `vson/api.py` behind a JSON envelope, and §2.1 governs what its answer establishes without weakening: `conforms: true` says the document is well-formed under the shapes, the ontology and the closed vocabulary. It is not evidence about a picture, and a verdict delivered through a tool call — beside tools that *do* read the artifacts they check — is the easiest place in this specification to forget that.

A `path` argument is read with the privileges of the server process. This is a local stdio server started by its own user, the same trust boundary [`vson validate`](#516-machine-readable-validation-reports-vson-validate---format) has always had; nothing here is written for input from anyone else.

#### 5.18.3 Revisions, and what is frozen

The reference server implements the handshake and the tools surface of MCP revisions `2024-11-05`, `2025-03-26` and `2025-06-18`, echoing a requested revision it knows and answering with its newest otherwise. Nothing in this specification pins that list: MCP versions itself, and a server following it will outgrow any list frozen here. What is frozen is the *content* — the four tool names above, and the report format `vson_validate` returns, which is §5.16.6's and is versioned there. Adding a tool is not a breaking change; changing what one of these four returns is.

Two behaviours differ across those three revisions and are handled by being lenient in the one direction that cannot break a client. JSON-RPC **batches** exist in `2025-03-26` and not in `2025-06-18`, so an array of messages is accepted on all three: refusing one a client is entitled to send is an incompatibility, accepting one it will never send is not. **`structuredContent`** is a later addition, so `vson_validate` returns its record *both* as a text block of JSON and in that field — the backwards-compatible pairing the newer revisions ask for, ignored by a client that predates it. No `outputSchema` is declared, because declaring one is a promise to match it on every revision the same server also answers.

**Why the protocol is hand-rolled.** The reference server implements JSON-RPC over stdio in the Python standard library rather than through the official MCP SDK, and the reason is a rule about this repository rather than a claim about that package: [`pyproject.toml`](../pyproject.toml) carries four runtime dependencies, each pinned to a range and each justified by a gate that needs it, on a `>=3.9` floor every line of `tools/`, `scripts/`, `tests/` and `vson/` is written to. What an SDK would supply here is a handshake, two methods and five error codes. If a future revision adds framing, negotiation or authorization that a hand-rolled server cannot follow, the SDK is the answer and [`vson/mcp.py`](../vson/mcp.py) is the thing to delete — the decision is recorded so it can be revisited, not so it can be defended.

---

## 6. JSON Schema and validation rules

VSON has **two layers of validation**:

| Layer | Tool | Scope | Failure mode |
|---|---|---|---|
| Structural (envelope shape) | JSON Schema | Wire payload only | rejects malformed envelopes |
| Semantic (graph well-formedness) | SHACL | Materialized RDF graph | rejects scenes that violate VSO constraints |

A document MUST pass both. JSON Schema alone is insufficient — it cannot express "directional needs viewer" or "Composition needs at least one depicts." SHACL is the load-bearing validator; JSON Schema is a fast structural pre-check.

### 6.1 The extractor envelope schema

**File:** [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json). Reproduced inline for §5-style cross-reference. The envelope is closed (`additionalProperties: false`): `scene_id`, `version`, `vson_p`, `vson_t`, and `conformance` are required keys, and any top-level key not listed below is a validation error.

A reproduction is a copy, and §2 ranks this document *above* the schemas — so a fragment that has fallen behind is not a formatting lag, it is the highest-precedence artifact stating something false. Every fenced fragment in §5–§6 is therefore compared against the file it quotes by [`scripts/check_spec_fragments.py`](../scripts/check_spec_fragments.py) in `make check`: enums must match exactly, `required` sets must be subsets, patterns must be byte-identical, and the worked example of §6.2 must validate. A fragment abbreviates by omission only.

#### `scene_id` *(string, required)*
Stable, URL-safe scene identifier. ≤64 chars, `[A-Za-z0-9_-]`.
```json
{ "type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$" }
```

#### `version` *(string, required)*
Which **spec document** the producer emitted under — not which vocabulary it used, and not which build produced it; §8.1 separates the three axes. `"1.0"` (strict), `"1.0.5"` (v1.0 + caption renderer + Phase 0 ontology additions), `"1.1"` (adds the VSON-X surface form and the partial validation profile), `"1.2"` (re-mints all five namespaces under `https://w3id.org/vson/`; envelope structure unchanged from 1.1), `"1.3"` (this document; envelope structure, every IRI, and the vocabulary unchanged from 1.2). Backwards-compatible — every v1.0 envelope remains valid under newer spec versions, so the enum only ever grows and a consumer **MUST** accept every value in it.
```json
{ "enum": ["1.0", "1.0.5", "1.1", "1.2", "1.3"] }
```

#### `source` *(object, optional)*
Provenance of the scene. Producers **SHOULD** populate it for any non-hand-authored scene. The schema does not enforce this — `source` is optional unconditionally, and only `source.kind` is required once the object is present.
```json
{
  "type": "object",
  "required": ["kind"],
  "properties": {
    "kind":   { "enum": ["image","video_frame","synthetic","hand_authored"] },
    "uri":    { "type": "string", "format": "uri" },
    "sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
    "width_px":   { "type": "integer", "minimum": 1 },
    "height_px":  { "type": "integer", "minimum": 1 },
    "captured_at":{ "type": "string", "format": "date-time" }
  }
}
```

#### `vson_p` *(string, required as a key; conditionally non-empty)*
The Penman authoring text. The key is always required, but its minimum length is version-conditional:

- `version` ∈ {`"1.0"`, `"1.0.5"`} — `minLength: 3`. Penman is the source of truth.
- `version` ∈ {`"1.1"`, `"1.2"`, `"1.3"`} — `vson_p` MAY be the empty string `""` when the authoring surface was VSON-X (back-conversion to Penman still waits on `t2p`). An `anyOf` then requires that **at least one** of `vson_p` / `vson_x` be non-empty.

Every version the enum above admits that allows an empty `vson_p` **MUST** be named in the second clause. A value added to the enum and not to the clause is a version for which the one-surface rule silently stops applying — which is why the two lists are checked against each other, and against this fragment, by [`scripts/check_spec_fragments.py`](../scripts/check_spec_fragments.py). Each `anyOf` branch carries its own `required`: a bare `properties` is vacuously satisfied by an absent key, so a branch written without it accepts the very document it exists to reject.

```json
{ "type": "string" }
```
```json
{ "allOf": [
  { "if":   { "properties": { "version": { "enum": ["1.0", "1.0.5"] } } },
    "then": { "properties": { "vson_p": { "minLength": 3 } } } },
  { "if":   { "properties": { "version": { "enum": ["1.1", "1.2", "1.3"] } } },
    "then": { "anyOf": [ { "required": ["vson_p"], "properties": { "vson_p": { "minLength": 3 } } },
                         { "required": ["vson_x"], "properties": { "vson_x": { "minLength": 3 } } } ] } }
] }
```

#### `vson_x` *(string, optional — v1.1+)*
The VSON-X (compact sigil-based) form. Populated when the authoring or extraction surface was VSON-X. Surface semantics: [`docs/vson-x-semantics.md`](./vson-x-semantics.md).
```json
{ "type": "string" }
```

#### `vson_t` *(string, required)*
Turtle 1.2 / Turtle-star derived from `vson_p` or `vson_x` via the reference transpiler. Always non-empty — this is the field a consumer parses when it wants triples.
```json
{ "type": "string", "minLength": 3 }
```
**Validation rule.** Compiling whichever authoring surface is populated MUST equal `vson_t` modulo blank-node renaming and triple ordering.

#### `graph` *(object, optional)*
UI-friendly projection: `{nodes: [...], edges: [...]}`. Lossy w.r.t. RDF-star annotations; consumers needing full fidelity MUST use `vson_t`.

#### `graph.nodes[*]` *(GraphNode array)*
```json
{
  "type": "object",
  "required": ["id", "kind"],
  "properties": {
    "id":   { "type": "string", "pattern": "^[A-Za-z_][\\w-]*$" },
    "kind": { "enum": ["Composition","SceneContext","VisualStyle","CameraView","PhysicalObject","Aggregate","Substance","Event","Process","Stative","Quality","SpatialFact","Annotation"] },
    "class":{ "type": "string" },
    "traits":{
      "type": "object",
      "properties": {
        "individuation":{ "enum": ["Generic","Named","Kind","Skolem"] },
        "animacy":      { "enum": ["Agentive","Inert"] },
        "countability": { "enum": ["Count","Mass","Collective"] },
        "affordance":   { "type": "array", "items": { "type": "string" } }
      }
    },
    "properties": { "type": "object" },
    "bbox2d":     { "type": "string" }
  }
}
```

#### `graph.edges[*]` *(GraphEdge array)*
```json
{
  "type": "object",
  "required": ["from", "to", "label"],
  "properties": {
    "from":  { "type": "string" },
    "to":    { "type": "string" },
    "label": { "type": "string" },
    "qualifiers": { "type": "object" }
  }
}
```

#### `conformance` *(object, required)*
SHACL report. `conforms` is always relative to the profile named in `profile`.

#### `conformance.profile` *(string enum, optional — v1.1+, default `"strict"`)*
Which shapes file produced the report: `"strict"` uses [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) (v1.0 byte-identical behaviour); `"relaxed"` uses [`shapes/vson-shapes-relaxed.ttl`](../shapes/vson-shapes-relaxed.ttl), which demotes the dimension-completeness constraints — viewer anchoring, the Event/Process/Stative lemma, Quality dimension+value, Quality modifier — to `sh:Warning` for authoring-time documents. Structural-integrity constraints stay `sh:Violation` in both profiles. As of v1.1 no shipped command selects the relaxed file (neither the Rust CLI nor the Python reference exposes a `--partial` flag); it is exercised by the shapes-gate test in `tests/`, and the field exists so that a producer which validates against it can say so.

**Consumer contract.** Consumers **MUST** inspect both `conforms` and `profile` to determine document status: `conforms=true` under the relaxed profile is **NOT** v1.0 conformance.
```json
{
  "type": "object",
  "required": ["conforms"],
  "properties": {
    "conforms": { "type": "boolean" },
    "profile":  { "enum": ["strict", "relaxed"], "default": "strict" },
    "violations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["message", "shape"],
        "properties": {
          "message":     { "type": "string" },
          "shape":       { "type": "string" },
          "focus_node":  { "type": "string" },
          "result_path": { "type": "string" },
          "severity":    { "enum": ["Violation","Warning","Info"] }
        }
      }
    }
  }
}
```

#### `extraction` *(object, optional)*
Producer-side metadata — model, prompt version, retry count, latency, token counts, overall confidence. Useful for telemetry; not normative.

### 6.2 Worked envelope example (image upload response)

```json
{
  "scene_id": "throne_room_01",
  "version": "1.0",
  "source": {
    "kind": "image",
    "uri": "https://example.org/uploads/throne_room.jpg",
    "sha256": "276f043f7971a3b965ee59811dc4663a4fc52f32f7173fcdffebcbc1a244ae71",
    "width_px": 1024,
    "height_px": 768,
    "captured_at": "2026-05-02T11:14:00Z"
  },
  "vson_p": "(scene / Composition :viewedBy (cam / CameraView :angle low :focalLength 35mm :framing medium_shot) :depicts (alice / PhysicalObject :individuation Named :animacy Agentive :countability Count :class Human))",
  "vson_t": "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n:scene a vso:Composition .\n:scene vso:viewedBy :cam .\n...",
  "graph": {
    "nodes": [
      { "id": "scene", "kind": "Composition" },
      { "id": "cam",   "kind": "CameraView", "properties": { "angle": "low", "focalLength": "35mm", "framing": "medium_shot" } },
      { "id": "alice", "kind": "PhysicalObject", "class": "Human",
        "traits": { "individuation": "Named", "animacy": "Agentive", "countability": "Count" } }
    ],
    "edges": [
      { "from": "scene", "to": "cam",   "label": "viewedBy" },
      { "from": "scene", "to": "alice", "label": "depicts"  }
    ]
  },
  "conformance": { "conforms": true },
  "extraction": {
    "model": "claude-opus-4-7",
    "prompt_version": "orchestrator-system@1.0",
    "shacl_retries": 0,
    "latency_ms": 4800,
    "input_tokens": 7421,
    "output_tokens": 1083,
    "confidence_overall": 0.91
  }
}
```

### 6.3 SHACL constraints — reference table

The SHACL shapes file is [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) — that file is what executes; this table is an informative index of its most load-bearing rows, not a complete listing. A disagreement between the two is resolved by the precedence order in §2, which ranks this document above the shapes: fix whichever side is wrong.

| Shape | Targets | Constraint | Negative fixture |
|---|---|---|---|
| `vss:CompositionShape` | `vso:Composition` | `sh:minCount 1` on `vso:depicts`; at most one `vso:viewedBy`, at most one `vso:rendersAs` (§5.2) | [`bad_two_viewed_by.ttl`](../tests/fixtures/bad_two_viewed_by.ttl) |
| `vss:DirectionalNeedsViewerShape` | `vso:SpatialFact` with `vso:directional` | requires exactly one `vso:viewer` | [`bad_no_viewer.ttl`](../tests/fixtures/bad_no_viewer.ttl), [`bad_two_viewers.ttl`](../tests/fixtures/bad_two_viewers.ttl) |
| `vss:RccValueShape` | `vso:SpatialFact / vso:rcc` | `sh:in (rcc:DC rcc:EC ...)` — eight values | none |
| `vss:DirectionalValueShape` | `vso:SpatialFact / vso:directional` | `sh:in (vso:above ...)` — six values | none |
| `vss:ProximalValueShape` | `vso:SpatialFact / vso:proximal` | `sh:in (vso:near vso:far vso:adjacent vso:next_to vso:facing)` — five values | none |
| `vss:EventShape` | `vso:Event`, `vso:Process`, `vso:Stative` | exactly one `vso:lemma` (`xsd:string`) | [`bad_event_no_lemma.ttl`](../tests/fixtures/bad_event_no_lemma.ttl), [`bad_two_lemmas.ttl`](../tests/fixtures/bad_two_lemmas.ttl) |
| `vss:QualityShape` | `vso:Quality` | exactly one `vso:dimension` and one `vso:value` | none |
| `vss:FrameNotDepictedShape` | `vso:depicts` | object MUST NOT be `vso:Frame` | [`bad_frame_depicted.ttl`](../tests/fixtures/bad_frame_depicted.ttl) |
| `vss:SpatialFactShape` | `vso:SpatialFact` | requires `vso:figure` and `vso:ground`; caps `rcc` / `directional` / `proximal` at one | [`bad_two_rcc.ttl`](../tests/fixtures/bad_two_rcc.ttl) |
| `vss:GeometryShape` | subjects of `vso:bbox2d`, `vso:position3d`, `vso:scale3d`, `vso:rotation` | the value grammars of §5.4 and §5.10 | [`bad_bbox2d_value.ttl`](../tests/fixtures/bad_bbox2d_value.ttl), [`bad_bbox2d_pixels.ttl`](../tests/fixtures/bad_bbox2d_pixels.ttl), [`bad_geometry_grammar.ttl`](../tests/fixtures/bad_geometry_grammar.ttl) |
| `vss:ConfidenceRangeShape` | subjects of `vso:probability`, `vso:confidence`, `vso:visibleFraction` | value in `[0,1]` (§5.10, §5.11) | [`bad_confidence_range.ttl`](../tests/fixtures/bad_confidence_range.ttl), [`bad_visible_fraction.ttl`](../tests/fixtures/bad_visible_fraction.ttl) |
| `vss:LemmaShape` | subjects of `vso:lemma` | `sh:pattern ^[a-z][a-z0-9_]*$` (§5.6) | [`bad_lemma_pattern.ttl`](../tests/fixtures/bad_lemma_pattern.ttl) |
| `vss:EntityClassShape` | subjects of `vso:class` | at most one `vso:class` (§5.4) | [`bad_two_class.ttl`](../tests/fixtures/bad_two_class.ttl) |

The last four shapes, and the caps on the four rows above them, were added in v1.3 under §8.2 — every negative fixture named in this table for one of them conformed under the v1.2 shapes.

**Not in this table, and not a shape.** Clause C2's vocabulary closure is checked by [`tools/c2_check.py`](../tools/c2_check.py), the third gate `vson validate` runs (§2, §2.1). It belongs to no shapes file because no shape can decide it, and it is listed here so a reader working from this table does not conclude that SHACL is the whole of validation. Negative fixture: [`bad_orphan_term.ttl`](../tests/fixtures/bad_orphan_term.ttl) — the one `bad_*.ttl` in the repository that satisfies every shape.

---

## 7. Exporters

| Target | Mapping | Status |
|---|---|---|
| Cypher / Neo4j | `:s :p :o` → `(s)-[r:p]->(o)`; `<<:s :p :o>> :q :v` → `r.q = v` | **shipped** in `vson export cypher` |
| Caption (English) | deterministic graph → English, template-driven, no LLM | **shipped** in `vson export caption` and the web studio (in-browser, same renderer) |
| FOL | reified nodes → Prolog-style first-order-logic facts | **shipped** in `vson export fol` and the web studio (in-browser, same renderer) |
| DOT / GraphML / Mermaid | nodes/edges → graph-viz formats | shipped in the web studio |
| AMR | `Event` → AMR predicate; `agent`/`patient`/`instrument` → `:ARG0`/`:ARG1`/`:instrument` | spec only |
| Visual Genome | `(s, p, o)` → VG relation row; `bbox2d` → VG bbox | spec only |
| Pixar USD | `CameraView` → `UsdGeomCamera`; `Composition` → USD Stage | spec only |
| JSON-LD | `@context` mapping VSO namespace | shipped (see [`tools/schema/vson-jsonld.schema.json`](../tools/schema/vson-jsonld.schema.json)) |
| SPARQL-star | direct (no mapping needed) | shipped |

### 7.1 The other direction

Every row above writes VSON *out*. Reading annotations *in* is a different
problem with a different failure mode, and three importers now ship for it —
[`tools/importers/`](../tools/importers), documented in
[`docs/importers.md`](./importers.md): **GQA**, **Visual Genome** and **PSG**,
each with its per-predicate and per-attribute mapping table checked in as data
and a lossiness report that counts every source construct exactly once, as
`exact`, `approximate` or `dropped`-with-a-reason.

The Visual Genome row above stays **spec only**, because it is the *export*
mapping and no exporter implements it. What is no longer spec only is the claim
this section could previously make in neither direction: how much of a real
annotation vocabulary VSON can carry. That is measured in
[`docs/eval/coverage.md`](./eval/coverage.md) against vocabularies counted from
the published dumps — 310 GQA relation types over 4,330,796 occurrences, 36,383
Visual Genome predicate types over 2,316,104, PSG's published 56 — and
regenerated by `make importer-check` so the numbers cannot drift from the
tables that produce them.

Two findings from it bear on this document rather than on the importers.
**C5's cost is now a number**: 90.94% of GQA's relation occurrences map to a
`vso:directional` value, and not one of the three datasets carries a viewer, so
every one of them needs the camera an importer mints and declares. And the
attribute drops cluster on four axes the §5.5.1 registry does not carry —
geometric shape, surface pattern, physical condition, surface texture — with
per-axis type and token counts, which is evidence for a v2 conversation and not
a change inside v1.x (§8.2).

---

## 8. Versioning and extension

- **IRI immutability.** All IRIs under `https://w3id.org/vson/v1/` are immutable. v2.0 will use `https://w3id.org/vson/v2/`. Concurrent versions can coexist. The rule binds from v1.2 forward, under the w3id host. It did not survive the host itself: the pre-v1.2 `https://vson.dev/v1/` names this clause used to cover were withdrawn, not aliased — see §5.1 for why that was the honest resolution and not a silent breach.
- **One historical exception.** `ontology/vso.ttl` keeps its `owl:priorVersion` under the legacy `vson.dev` host and carries a `LEGACY IRI` comment saying so. That string is the `owl:versionIRI` the prior release actually declared; rewriting it would assert a name that release never carried, which falsifies a record rather than migrating one. It is a record, not a resolvable name, and nothing dereferences it. [`scripts/check_legacy_iri.py`](../scripts/check_legacy_iri.py) pins it as the only legacy-host IRI in the repository outside prose that documents the migration or preserves a historical record; every other occurrence fails the build.
- **Backwards compatibility within v1.x.** v1.x MAY add classes, properties, and shapes. v1.x **MUST NOT** remove or rename existing terms, change cardinalities to be more restrictive, or change SHACL shapes in a way that invalidates previously-conformant documents.
- **Private extensions.** Authors MAY define private predicates under their own namespace. Private predicates SHOULD NOT shadow VSV terms. Documents using private predicates are **profile-specific**, not portable.
- **Closed vocabularies.** §5.12 lists closed enumerations. Producers **MUST NOT** invent values; consumers **MAY** treat unknown values as `Unknown`.

### 8.1 Version model

Three numbers in this project look like one number and are not. They move independently, and each one claims something different. A reader who conflates them reads "VSON 1.3" as a vocabulary change, which it is not.

| Axis | Where it is declared | What it names | What it claims |
|---|---|---|---|
| **Spec document version** | the title and `Status` line of this document; the `version` field of the envelope (§6.1) | this text together with the artifacts §2 ranks, as published | that a producer emitted under these clauses and these reference tables |
| **Vocabulary version** | `owl:versionInfo` in each of [`ontology/vso.ttl`](../ontology/vso.ttl), [`ontology/rcc8.ttl`](../ontology/rcc8.ttl), [`ontology/allen.ttl`](../ontology/allen.ttl), and both shape files | the terms in the namespace | that these classes, properties, characteristics, and registry members are what the namespace declares |
| **Software release tag** | the git tag; `CITATION.cff`, `pyproject.toml`, the Rust crate, the web package | a build of the reference implementations | that this build exists and passed its gates — nothing about the document or the namespace |

The three currently read **v1.3**, **1.2**, and **1.3.0**. That is not drift; it is the model working. v1.3 moved where verification runs (into the visitor's browser), what this document says, and — under §8.2 — how much of what it says the shapes and gates execute. It moved no term, no IRI, no clause, and no shape severity, so `owl:versionInfo` stays at `1.2`. The `sh:maxCount` caps v1.3 added are the one place a reader might expect otherwise: a cap is a cardinality this document already stated (§5.2, §5.4, §5.7, C5, C6) and the shapes had failed to transcribe, so it changes what the validator executes and not what the namespace declares — which is the axis `owl:versionInfo` names. `make site` fails if the published landing page and `owl:versionInfo` ever disagree.

**What an implementer claims.**

- *"Implements VSON v1.3"* — accepts and emits documents per C1–C9 as written **in this document**. It says nothing about which vocabulary version is loaded, because C1–C9 did not change between v1.2 and v1.3.
- *"Uses VSO 1.2"* — resolves the terms of the namespace whose `owl:versionInfo` is `1.2`. Since all v1.x IRIs are immutable (above), this is a statement about *which terms exist*, never about which IRIs to fetch.
- *"vson 1.3.0"* — a build. A user reporting a bug **SHOULD** give this number; a document **MUST NOT** be described as conforming to it.
- A producer **MUST NOT** write a `version` the envelope schema's enum does not carry, and a consumer **MUST** accept every value the enum carries (§6.1). The enum grows and never shrinks — that is what backwards compatibility within v1.x means on the wire.

**`owl:versionIRI` names a version; it is not promised to dereference.** [`ontology/vso.ttl`](../ontology/vso.ttl) declares `owl:versionIRI <https://w3id.org/vson/v1.2/ontology>`. That IRI identifies the 1.2 state of the vocabulary. It is **not** one of the dereferenceable names of §5.1: verified 2026-07-31, a GET returns `302` to the landing page, because the w3id rule for `/vson/` routes the five v1 namespace documents explicitly and sends every other path there. Only `https://w3id.org/vson/v1/…` carries a dereference promise, and `make live-check` is what verifies it.

Making the versionIRI resolve to a frozen snapshot would take two changes, and neither is worth its cost yet: a new rewrite rule in a repository this project does not own, and a second, byte-frozen copy of the ontology published at `v1.2/ontology.ttl` — a copy that no canonical name reaches today and one more surface to drift, which is precisely what §5.5.1's single-source rule exists to avoid. Recorded here rather than papered over: a name that identifies is doing its job even when nothing serves it, and claiming otherwise would be the kind of untrue sentence §2.1 is about.

### 8.2 Tightening enforcement within v1.x

The backwards-compatibility bullet above forbids changing a shape "in a way that invalidates previously-conformant documents". That is a rule about **documents**, not about shapes, and the two come apart wherever this document states a requirement that nothing checks — which, until v1.3, was most of the value spaces in §5 and one whole numbered clause (C2). Enforcement can be incomplete in two directions. Stricter than its clause is a bug, and §2's precedence order resolves it. **Looser** than its clause is the case this section governs: the requirement is stated here, nothing enforces it, and a document that breaks it passes `vson validate`. §2.1 already gives the reading — *where a clause is stated more tightly than the shape that enforces it, the clause is the requirement and the shape is incomplete*. Completing the enforcement does not invalidate a conformant document, because the documents it starts rejecting were never conformant. They were unchecked.

This section says **check**, not **shape**, throughout. A shape is the usual instrument and not the only one: C2 is a statement about which names belong to the vocabulary, which no SHACL shape can decide (§2.1), and v1.3 closed it with a third `vson validate` gate instead. The test below is about what a check rejects, so it applies wherever the check lives.

**The rule.**

- Within v1.x, a check MAY be added, and an existing check MAY be tightened, **only if** every document the tightened check newly rejects was **already non-conformant** under this specification as published — because it violates a numbered clause C1–C9 (§2), or because it violates a value space this document defines in §5 or §6. A document that satisfies both and was merely unchecked is a document this specification **permits**.
- A tightening **MUST NOT** reject a document this specification permits. If a shipped document, or any other clause-permitted document, fails a new check, **the check is wrong**: narrow the check. Do not edit the document to fit the check, and do not narrow the clause to justify the check.
- The same test applies at `sh:Warning`. An advisory that fires on a permitted document is the shapes contradicting this document one severity more quietly, and a reader cannot tell the two apart from a validation report. A constraint this document states but does not close — §5.12 is the **complete** list of closed enumerations, and §5.4's Enforcement note is explicit that no clause requires an Entity to carry its traits — therefore does not become a check inside v1.x **at any severity**. Narrowing it is a v2.0 change, where a new namespace makes the break visible.
- Every tightening **MUST** land with three things: a negative fixture under `tests/fixtures/` that the new check rejects and the previous enforcement accepted; an entry in [`spec/CHANGELOG.md`](../spec/CHANGELOG.md) naming what was closed; and the authorizing clause cited where a reader of a failure report will see it — the shape's `sh:message`, or the comment beside it, or the gate's own module docstring. [`tests/test_documented_constraints.py`](../tests/test_documented_constraints.py) holds the inventory of the shaped constraints and fails when a citation goes missing.
- **Loosening** — removing a check, or widening a value space or an enumeration — can never invalidate a conformant document, so it is permitted within v1.x without this test. It still changes what a producer may rely on the validator to catch, so it is recorded in the CHANGELOG on the same terms.

**What this section does not license.** It is not a route to changing what a clause requires. C1–C9 and the §5 value spaces are the contract; this section only governs how much of that contract the tooling executes. A tightening that needs a clause reworded first is a v2.0 change wearing a shape's clothing.

**A check outside conformance is not a tightening.** §5.13's geometry consistency check is the case, and it is worth stating because it looks like one: it landed in v1.3, it rejects documents, and four of them are shipped envelopes. It is not governed by this section, because it does not decide conformance — no clause requires geometry consistency, `vson validate` does not run it, and a document it refuses is a conformant VSON document that `vson validate` reports `OK`. Applying this section's rule to it would be the mistake: the rule would forbid the check, since the documents it rejects *are* documents this specification permits. That is exactly why it is not a `validate` gate. The line to hold is the one the third bullet draws — a check may not make a permitted document non-conformant — and a check reported under its own name, outside the conformance verdict, does not.

**Applied in v1.3.** Constraints this document already stated, made executable — the `vso:bbox2d` grammar (§5.4, §5.10), the three 3D geometry grammars and the `[0,1]` bounds on `vso:visibleFraction` (§5.10), the `[0,1]` bounds on `vso:probability` and `vso:confidence` (§5.11), the snake_case `vso:lemma` pattern (§5.6), the `vso:class`, `vso:viewedBy` and `vso:rendersAs` caps (§5.2, §5.4), the `0..1` caps on the three `SpatialFact` relation slots (§5.7), and the two clause gaps §2.1 named: C5's *exactly one* `vso:viewer` and C6's *exactly one* `vso:lemma` on `vso:Process` and `vso:Stative`. Off the shapes, one whole clause: **C2**, which `vson validate` had never checked, is now its third gate (§2, [`tools/c2_check.py`](../tools/c2_check.py)) — the most tightly authorized tightening this section can license, since the documents it rejects are the ones C2 itself names. Each landed with a `tests/fixtures/bad_*.ttl` that the v1.2 tooling accepted. Two candidates were declined under the third bullet and the measurements are recorded beside the shapes: the §5.3.1 / §5.3.3 value lists (three shipped envelopes carry `timeOfDay "day"`, `atmosphere "cold"`, `atmosphere "clear"`), and Entity trait completeness (30 entity/trait pairs across 4 shipped documents, 51 across 5 before a demo envelope was withdrawn on 2026-08-04).

---

## 9. Examples gallery

Sixteen scenes, ascending in complexity. Every example SHACL-conforms (verified by `make check` and `make cli-check`). Each file is a standalone VSON-P document.

### 9.1 Minimal — single Entity

**File:** [`examples/gallery/01_minimal.vson`](../examples/gallery/01_minimal.vson)
**Demonstrates:** smallest SHACL-conformant document — Composition + Frame + one Entity.

```vson
(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing close_up)
   :viewedBy cam
   :depicts (apple / PhysicalObject
               :individuation Generic :animacy Inert :countability Count
               :class Apple))
```

### 9.2 + Quality (color)

**File:** [`examples/gallery/02_quality.vson`](../examples/gallery/02_quality.vson)
**Demonstrates:** `Quality` reification with `dimension`/`value`.

### 9.3 Spatial topology — RCC-8 only

**File:** [`examples/gallery/03_spatial_topology.vson`](../examples/gallery/03_spatial_topology.vson)
**Demonstrates:** `SpatialFact` with `rcc:EC` only — no viewer required because RCC-8 is symmetric.

### 9.4 Directional fact with mandatory viewer

**File:** [`examples/gallery/04_directional_with_viewer.vson`](../examples/gallery/04_directional_with_viewer.vson)
**Demonstrates:** viewer anchoring — `vso:directional` requires `vso:viewer` at the schema level.

### 9.5 Possession — Stative

**File:** [`examples/gallery/05_possession_stative.vson`](../examples/gallery/05_possession_stative.vson)
**Demonstrates:** `Stative` with `holder` and `theme` (durative state, not punctual event).

### 9.6 Event with three roles (agent + patient + instrument)

**File:** [`examples/gallery/06_event_with_instrument.vson`](../examples/gallery/06_event_with_instrument.vson)
**Demonstrates:** triadic action — the v0.1 dyadic-edge defect resolved by reification.

### 9.7 Ditransitive — give

**File:** [`examples/gallery/07_ditransitive.vson`](../examples/gallery/07_ditransitive.vson)
**Demonstrates:** `agent + theme + recipient`, aligning with AMR `:ARG0/:ARG1/:ARG2`.

### 9.8 Collective countability — crowd

**File:** [`examples/gallery/08_collective.vson`](../examples/gallery/08_collective.vson)
**Demonstrates:** `Aggregate` class, `countability=Collective`, single node for many individuals.

### 9.9 Mass / Substance — water pouring

**File:** [`examples/gallery/09_mass_substance.vson`](../examples/gallery/09_mass_substance.vson)
**Demonstrates:** `Substance` class, `countability=Mass`, durative `Process`.

### 9.10 Geometry — bbox2d

**File:** [`examples/gallery/10_geometry_bbox.vson`](../examples/gallery/10_geometry_bbox.vson)
**Demonstrates:** normalized 2D bounding boxes for layout-to-image consumers.

### 9.11 Canonical full scene — throne room

**File:** [`examples/gallery/11_throne_room.vson`](../examples/gallery/11_throne_room.vson) (mirrors [`examples/throne_room.vson`](../examples/throne_room.vson))
**Demonstrates:** every feature in this spec — Frames, Entities with full traits, Qualities, Events, Statives, SpatialFacts with viewers, named entities, the works.

### 9.12 Persona — cross-document identity (v1.1)

**File:** [`examples/gallery/12_persona.vson`](../examples/gallery/12_persona.vson)
**Demonstrates:** `vso:Persona` Frame with `vso:hasInvariant` Qualities; an Entity declares `vso:embodies` to inherit stable invariants across scenes while per-scene `vso:hasQuality` stays contingent.

### 9.13 Negation — reified Negation node

**File:** [`examples/gallery/13_negation.vson`](../examples/gallery/13_negation.vson)
**Demonstrates:** `vso:Negation` node over a reified `Annotation` statement (RDF 1.1-portable equivalent of the canonical `<<s p o>>` form).

### 9.14 Belief state — propositional attitude

**File:** [`examples/gallery/14_belief_state.vson`](../examples/gallery/14_belief_state.vson)
**Demonstrates:** `vso:BeliefState` with an `experiencer` and a reified proposition (`vss:BeliefStateShape` + `vss:AnnotationShape`).

### 9.15 Quantification — "every horse is brown"

**File:** [`examples/gallery/15_quantification.vson`](../examples/gallery/15_quantification.vson)
**Demonstrates:** `vso:Quantification` node with `quantifier` (closed list), `variable`, `qDomain`, and `scope` over reified Annotation nodes.

### 9.16 Annotation — confidence on thematic-role edges

**File:** [`examples/gallery/16_annotation.vson`](../examples/gallery/16_annotation.vson)
**Demonstrates:** `vso:Annotation` reification (RDF 1.1-portable) carrying `vso:confidence` on each annotated triple; equivalent to the RDF-star `<<s p o>> vso:confidence "0.95"` form.

### 9.17 VSON-X compact-syntax mirror — v1.1

Gallery scenes 01–12 have a VSON-X form under [`examples/gallery-x/`](../examples/gallery-x/) (12 files), and each denotes the same scene as its Penman twin under §4.6. For example, `examples/gallery-x/11_throne_room.x.vson` and `examples/gallery/11_throne_room.vson` canonicalize to the same 131 quads — the bytes are [`tests/fixtures/canonical/11_throne_room.nq`](../tests/fixtures/canonical/11_throne_room.nq), and both surfaces are required to produce exactly them. `make x-check` runs the isomorphism round-trip over the same twelve pairs. Scenes 13–16 are Penman/Turtle only: VSON-X v1.1 has no notation for the propositional layer (§5.9) or for annotation reification (§5.11).

---

## 10. Reference implementations

| Implementation | Location | Scope | Tests |
|---|---|---|---|
| Python Penman transpiler | [`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py) | Penman → Turtle | 18 round-trip tests (18/18 ✓) |
| Python VSON-X parser (v1.1) | [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py) | VSON-X → Turtle, nine sigils, bearer-class dispatch | 16 lexer/parser/emitter + 11 gallery round-trip (27/27 ✓) |
| Caption renderer (v1.0.5) | [`tools/render/caption.py`](../tools/render/caption.py) | graph → English (deterministic, no LLM) | 11 fixture + determinism (11/11 ✓) |
| Rust CLI (`vson`) | [`cli/`](../cli) | `validate` (`--format text/json/sarif/compact`, `-` for stdin — §5.16), `verify --geometry`, `diff`, `convert p2t/x2t`, `export cypher/caption/fol`, `mcp` (§5.18) | 117 tests (53 lib unit + 6 error-contract + 9 golden throne room + 5 golden validate + 9 geometry gate + 9 diff gate + 15 report format + 11 standalone binary, the last of which drives an MCP session against a copy of the binary in an empty directory ✓) |
| Graph agreement metric (v1.3) | [`tools/metrics/smatch.py`](../tools/metrics/smatch.py) | two documents → triple-level precision/recall/F1 with per-layer sub-scores (§5.15); reads `.ttl`, `.vson` and `.x.vson` | 31 property + fixture tests (31/31 ✓) |
| Canonical form (v1.3) | [`tools/canon.py`](../tools/canon.py) | RDFC-1.0 canonical N-Quads + the §4.6 denotation test; reads `.ttl`, `.vson` and `.x.vson`; `--freeze` rewrites the frozen table | 34 tests — the Recommendation's own vectors, the two normalizations, the 29 frozen hashes, the 12 cross-syntax pairs (34/34 ✓) |
| SHACL validator | `pyshacl` (shelled out by `vson validate`) | semantic well-formedness, strict profile (the relaxed profile ships as a shapes file; no command selects it yet) | 5 SHACL tests + 16 gallery passes |
| Bare-VLM extractor | [`tools/extractor/baseline/extract.py`](../tools/extractor/baseline/extract.py) | image → VSON-P | offline cassette test |
| Browser studio (v1.3) | [`web/`](../web) | runs the Python references above in a Pyodide worker, in the visitor's browser: transpile, two-gate validation (the CLI's SHACL and OWL gates; not its C2 gate), caption/FOL — no backend | offline worker-parity vitest byte-pins p2t, both gate verdicts, and caption/FOL against the CLI fixtures |
| Routing tables (single source of truth) | [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json) | shared by Python + Rust — inside the crate so `include_str!` stays within the crate root and `cargo package` can verify-build it | Rust embeds it at compile time, the Python reference reads the same file at import time; `make cli-check` proves the two agree |
| Python client library (v1.3) | [`vson/`](../vson) | `import vson` — a facade over the Python references in this table, adding no behaviour: `validate()` runs the same three gates in the same order as `vson validate` and returns them structured (§5.16.1, minus `location` — §5.16.3 permits a position only where it was established, and this library establishes none), plus `to_turtle`/`from_x`, `caption`/`fol`, `diff`, canonical form, a typed `Envelope` over [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json), and `validate_and_repair(chat_fn, image)` — the emit → validate → repair loop `extraction.shacl_retries` records, taking any callable and importing no vendor SDK | 64 tests — the public surface, verdicts on good and bad from all three input forms, the input convention overruled in both directions, the loop at 0/1/2 rounds and at its bound, the studio-bound drift gate, 20 baked envelopes round-tripped read-only, and the two install layouts one resolver serves (64/64 ✓) |
| MCP server (v1.3) | [`vson/mcp.py`](../vson/mcp.py) | `vson mcp` / `python3 -m vson.mcp` — the four tools of §5.18 over JSON-RPC 2.0 on stdio, as a protocol adapter over the row above and nothing else. The transport is standard library, adds no dependency, and implements the handshake plus `tools/list` and `tools/call` and no other MCP capability | 56 tests — one scripted stdio session against a real child process (initialize, the initialized notification, `tools/list`, a call to each of the four tools, and a deliberately bad document), plus every dispatcher branch a working session never reaches, §5.18.1's rule that `document` is the text driven from a working directory holding a conformant file under the name the document carries, and the `export cypher` order of §5.18.2 with the binary lookup stubbed to *no binary anywhere*, which is the only way to reach that branch on a machine that has built the CLI (56/56 ✓), and one more in [`cli/tests/standalone_home.rs`](../cli/tests/standalone_home.rs) driving a session against a copy of the binary in an empty directory |
| Vision-dataset importers | [`tools/importers/`](../tools/importers) | `python3 -m tools.importers gqa\|vg\|psg <file>` — published scene-graph annotations → VSON-P, under a per-dataset mapping table checked in as data, with a lossiness report counting every source construct once as `exact` / `approximate` / `dropped`-with-a-reason (§7.1). Not a `vson` subcommand: the binary embeds spec artifacts, and a dataset vocabulary is not one — [`docs/importers.md`](./importers.md) §1 | 17 tests — the goldens for nine converted scenes and three reports, the three gates plus the geometry check on each, C5 checked on the graph, and every VSO term in the three tables read back out of the ontology; `make importer-check`, inside `make check`, which also re-derives [`docs/eval/coverage.md`](./eval/coverage.md) |
| Conformance suite runner (v1.3) | [`tools/conformance_runner.py`](../tools/conformance_runner.py) | executes [`tests/conformance/manifest.ttl`](../tests/conformance/manifest.ttl) — the definition of conformance (§2.2) — behind an `--engine` seam; generates §2.2's coverage table | `make conformance`, inside `make check`: 218 entries at suite v1.0.0, plus `tests/test_conformance_suite.py` on the runner itself |

**These are implementations, not the definition.** Through v1.3.0 this section closed by defining a consumer as "VSON v1.3 reference-conformant" iff it accepted every document the Python references plus `pyshacl` accepted and rejected every document they rejected. That sentence is withdrawn. It made this table normative — every bug and every undocumented tolerance in the rows above became part of the contract — and it gave a second implementer no target except imitating code. Conformance is defined in §2.2 and is claimed by passing [the conformance test suite](../tests/conformance/manifest.ttl), which the implementations above are run against like any other candidate.

---

## 11. Migration from v0.1

| v0.1 construct | v1.0 form |
|---|---|
| `{id:class}` Object | `Entity` with `individuation=Generic` |
| `@id:class` Unique Object | `Entity` with `individuation=Named` |
| `[id:type]` Item | `PhysicalObject` with `affordance ⊇ {Holdable}` |
| `<id:k=v>` Attribute | `Quality` node (`dimension k`, `value v`); link via `vso:hasQuality` |
| `~id:scene{...}` | `SceneContext` Frame with typed properties |
| `%id:style{...}` | `VisualStyle` Frame |
| `$id:camera{...}` | `CameraView` Frame |
| `#id:composition{...}` | `Composition` (mereological root) |
| `[A:verb instrument=x]` edge | `Event` node + `vso:agent`/`vso:patient`/`vso:instrument` edges |
| `[P:on]` edge | `SpatialFact` with `vso:rcc` and/or `vso:directional` (+ `vso:viewer` if directional) |
| `[P:has]` edge to attribute | `vso:hasQuality` to `Quality` node |
| `[P:scopes]` from supplementary | `vso:framedBy` from Composition to Frame |
| `[P:contains]` | `vso:depicts` (Composition → Entity) or `vso:partOf` (mereology) |

There is no migrator tool. v0.1 documents must be migrated by hand using the table above.

---

## 12. Changelog

See [`spec/CHANGELOG.md`](../spec/CHANGELOG.md). Highlights since v0.1:

- Replaced ad-hoc notation with **layered RDF-star + OWL 2 RL + SHACL** stack (`VSO/VSV/VSON-T/VSON-S/VSON-P/VSON-X`).
- Reified Events / Processes / Statives as nodes; added a closed inventory of coarse VerbNet-style thematic roles (see PropBank/FrameNet for the finer-grained alternatives VSON deliberately avoids).
- Added `SpatialFact` with the **mandatory viewer for directional facts**: directional facts are viewer-anchored by schema — VSON commits to the relative frame of reference (Levinson 2003) and makes the anchor explicit and machine-checkable; intrinsic and absolute frames are out of scope for v1.x. Figure/ground asymmetry follows Talmy.
- Replaced four-fold sigil entity taxonomy with **trait-bundle model**: `individuation × animacy × countability × affordance`.
- Added `Annotation` reification class for RDF 1.1-portable probability/source/confidence.
- Published JSON-LD context, JSON Schemas, and the extractor envelope format (this document, §6).
- Shipped Rust CLI v0.1 (`vson validate`, `convert p2t`, `export cypher`) graph-isomorphic to the Python reference.

---

## 13. Teaching an AI image generator

VSON is one notation; the producers are vision-language models. To make a model speak VSON, give it the [`vson-extractor` skill](../skills/vson-extractor/SKILL.md) — a portable ~4 KB Markdown system prompt that distills the closed vocabulary, the five hard rules, and one worked example into a self-contained brief.

### 13.1 Layout

```
skills/vson-extractor/
├── SKILL.md          # the prompt body (paste into system / systemInstruction)
├── conformance.json  # 5-image acceptance fixture for certifying a model
└── README.md         # provider-specific snippets (Claude / GPT / Gemini / OpenRouter)
```

### 13.2 Provider snippets

Each major provider takes the skill body in a slightly different field; see the [skill README](../skills/vson-extractor/README.md) for working snippets against Anthropic, OpenAI, Gemini, OpenRouter, and the Anthropic Skills API. The studio at [`web/`](../web/) extracts with `SKILL.md` (the VSON-X skill when X notation is selected); the longer 18 KB orchestrator prompt is published on the studio's `/prompts` page for pipelines that want maximum first-try conformance on hard scenes.

### 13.3 Conformance test

A model claims VSON-extractor support if it conforms on first try (no SHACL repair) for at least 4 of the 5 fixtures listed in [`skills/vson-extractor/conformance.json`](../skills/vson-extractor/conformance.json). The studio's repair loop (max 2 retries) is for graceful degradation, not for the certification path.

### 13.4 Why the skill, not the orchestrator prompt?

The orchestrator prompt at [`tools/extractor/prompts/orchestrator-system.md`](../tools/extractor/prompts/orchestrator-system.md) is 18 KB. It includes upstream-tool routing, decision policies P1–P13, and a long worked example with bbox detections. That prompt is right when an extractor pipeline is feeding the model upstream tool outputs and you need maximum first-try conformance.

The skill is right when a third-party caller wants to read VSON directly from an image with no pipeline — the model has nothing but the picture and the skill body. It is one-sixth the token cost, targets ≥ 80% first-try conformance — the certification threshold in [`skills/vson-extractor/conformance.json`](../skills/vson-extractor/conformance.json); measured results are pending (see [`tools/extractor/baseline/results.md`](../tools/extractor/baseline/results.md)) — and is small enough that prompt-cache hit rates are irrelevant: at this size, every provider's input charge is a rounding error.

### 13.5 Public surface

The studio's "what is this" page is [`web/src/routes/about/+page.svelte`](../web/src/routes/about/+page.svelte), served at `/about` by any running studio. It is the canonical public-facing explanation; the spec (this document) is the canonical machine-readable contract. They should not drift.

---

## Appendix A — Consolidated JSON Schemas

### A.1 Extractor response envelope

The full schema lives at [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) and is normative. Its `$id` is `https://w3id.org/vson/v1/schema/vson-output.schema.json`.

The schema body is reproduced below. Producers MUST validate every emitted envelope against this schema; consumers MAY trust an envelope that already passed validation upstream.

> See [`tools/schema/vson-output.schema.json`](../tools/schema/vson-output.schema.json) for the full text. Inlining it here would duplicate ~120 lines of JSON; the file is canonical.

### A.2 JSON-LD scene structural schema

Lives at [`tools/schema/vson-jsonld.schema.json`](../tools/schema/vson-jsonld.schema.json). Structural only; well-formedness is enforced by SHACL on the materialized graph, not by JSON Schema.

### A.3 SHACL shapes

Lives at [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl). Normative.

---

## Appendix B — Penman EBNF

The notation is the one [§D.1](#appendix-d--vson-x-grammar-normative) defines, and the two blocks below are the ones `make grammar-check` extracts, translates and runs against the corpus (§D.10). The reference implementation is [`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py).

The lexer is a single scan over the source text. **Whitespace, including newlines, only separates tokens** — it carries no syntax. Comments are discarded with it. At each position the scanner tries the alternatives below in order; that ordering is what makes `35mm` one `UNIT` rather than a `NUM` followed by an `ID`.

| # | Token | Value carried | Note |
|---|---|---|---|
| 1 | `COMMENT` | — | `#` to end of line; discarded, never reaches the parser |
| 2 | `(` `)` `/` | — | single-character sigils |
| 3 | `STRING` | the text between the quotes | the lexer decodes the Turtle `ECHAR` escapes; the emitter re-encodes them |
| 4 | `ROLE` | the name after the `:` | the `:` and the name are **one** token: `:agent` is a `ROLE`, `: agent` is a lexical error |
| 5 | `UNIT` | the whole token | tried before `NUM`; always emitted as a plain string literal (`35mm` → `"35mm"`) |
| 6 | `NUM` | the whole token | one token kind for both shapes below |
| 7 | `ID` | the whole token | |
| 8 | any other non-whitespace character | — | lexical error |

```ebnf
(* Lexical grammar. *)

COMMENT   = "#" { CHAR - NEWLINE } ;
STRING    = '"' { ( CHAR - ( '"' | "\" ) ) | ( "\" ( CHAR - NEWLINE ) ) } '"' ;
ROLE      = ":" ID ;
UNIT      = NUM ALPHA_ { ALPHA_ | DIGIT | "-" } ;   (* "35mm", "1.5x" *)
NUM       = FLOAT | INT ;
INT       = [ "-" ] DIGIT { DIGIT } ;
FLOAT     = INT "." DIGIT { DIGIT } ;
ID        = ALPHA_ { ALPHA_ | DIGIT | "-" } ;
ALPHA_    = "A".."Z" | "a".."z" | "_" ;
DIGIT     = "0".."9" ;
CHAR      = ? any Unicode code point ? ;
NEWLINE   = ? U+000A ? ;
```

```ebnf
(* Syntactic grammar. *)

document  = node ;
node      = "(" ID [ "/" ID ] { role } ")" ;
role      = ROLE term ;
term      = node | ID | STRING | NUM | UNIT ;
```

Reading the productions:

1. A `node`'s first `ID` is its variable; the `ID` after `/` is its concept. Both are the same terminal, so the grammar does not tell a variable from a concept name — the position does.
2. An `ID` in `term` position is either a reentrant reference to a declared variable or a bareword literal, and **the grammar does not decide which**. The routing tables do, by role name, exactly as §D.6 describes for VSON-X: [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json). This is why `term` names one `ID` alternative and not the two — `var` and `bareword` — an earlier draft of this appendix listed.
3. Forward references are allowed; the emitter does a pre-pass to register declared variables.
4. Exactly one `node` may appear at top level; a trailing token is a parse error.

**Annotation (v1.3).** This appendix previously wrote the same grammar in an ad-hoc notation and left to the prose three things the productions now carry: that a `ROLE` is one token (`: agent`, with a space, has never parsed), that a `UNIT`'s suffix admits digits and hyphens after its first letter (`1.5x2` is one token, not `1.5x` followed by `2`), and that a backslash escape inside a `STRING` cannot span a line. All three restate what [`tools/penman/vson_penman.py`](../tools/penman/vson_penman.py) has accepted since v1.0; none of them changes the language of any document this repository ships. §D.10 records how the block is checked, and how the three were found.

---

## Appendix C — Example class profile

**This is an example profile, not a registry** — the word *registry* was this appendix's title through v1.3, and it invited exactly the reading the paragraph beneath it denied. `vso:class` is an **open** dimension (§5.12): any bareword is conformant, and `Unknown` is the always-safe fallback. What follows is one worked profile for the fantasy-scene domain the gallery depicts — a starting vocabulary sized for those scenes, chosen to make the examples readable, and neither a controlled vocabulary nor a canonical set. Nothing registers a term here, nothing reviews an addition, and no validator checks membership: a document using none of these names is exactly as conformant as one using all of them. Extend or replace it per domain, under your own namespace where you need term identity (§8). §5.17.3 records why no alignment is minted from this list to any vision dataset's labels.

**People / agents.** `Human, Knight, Queen, King, Soldier, Woman, Man, Child, Merchant, Monk, Servant, Civilian, Peasant`

**Animals.** `Animal, Boar, Dog, Horse, Cat, Bird, Fish, Wolf, Deer`

**Wearables / regalia / weapons / tools.** `Crown, Hat, Helmet, Sword, Spear, Bow, Shield, Scroll, Torch, Cup, Bowl, Plate, Throne, Chair, Bed, Vessel, Weapon, Regalia, Tool`

**Architecture / nature.** `Tree, Rock, Pillar, Building, Castle, House, Furniture, Lamp, Door, Window`

**Sky / atmosphere.** `Cloud, Sun, Moon, Sky, Star`

**Substances.** `Water, Smoke, Fire, Blood, Stone`

**Aggregates / collectives.** `Group, Crowd, Flock, Herd`

**Special.** `Apple` (Quick Start canonical), `Unknown` (always conformant fallback).

---

## Appendix D — VSON-X grammar (normative)

This appendix is the single normative grammar for VSON-X. §4.3 is the overview; the per-key routing rationale — which bearer turns `*K V` into a Quality node and which into a direct property — is [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §3.

The grammar is reconciled against the reference parser [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py). That reconciliation used to be a reading; since v1.3 it is a gate — `make grammar-check` extracts the productions below, generates a parser from them, and runs the generated parser and the reference parser over the same corpora on every commit (§D.10). Where an earlier draft of the grammar and the shipping parser disagreed, **the parser wins**; each such case is recorded in §D.9. The Rust port planned for v1.2 (§4.3) MUST accept exactly the language below.

### D.1 Notation

`{ x }` is zero or more `x`; `[ x ]` is an optional `x`; `|` is alternation; `A - B` is set difference; `"…"` is a literal, in either quote style; `"a".."z"` is a character range; `? … ?` is a character set named in prose; `(* … *)` is a comment. UPPERCASE names are terminals produced by the lexer (§D.2–D.3); lowercase names are syntactic productions (§D.5). Appendix B states the VSON-P grammar in the same notation.

### D.2 Lexical productions

The lexer is a single scan over the source text. **Whitespace, including newlines, only separates tokens** — it carries no syntax. Comments are discarded with it. At each position the scanner tries the alternatives below in order; that ordering is what makes `35mm` one `UNIT` rather than a `NUM` followed by an `IDENT`, and `>>` one arrow rather than two.

| # | Token | Value carried | Note |
|---|---|---|---|
| 1 | `COMMENT` | — | `#` to end of line; discarded, never reaches the parser |
| 2 | `>>` | — | tried before `>` |
| 3 | `>` `~` `^` `*` `/` `@` `!` `&` | — | single-character sigils |
| 4 | `STRING` | the text between the quotes | the lexer does not decode `\` escapes; the emitter re-escapes the raw body for Turtle |
| 5 | `UNIT` | the whole token | tried before `NUM`; always emitted as a plain string literal (`50mm` → `"50mm"`) |
| 6 | `NUM` | the whole token | one token kind for both shapes below |
| 7 | `IDENT` | the whole token | |
| 8 | any other non-whitespace character | — | lexical error (§D.7) |

```ebnf
(* Lexical grammar. NEWLINE bounds a comment and a string escape; it is not a
   terminal in any syntactic production of §D.5. *)

COMMENT   = "#" { CHAR - NEWLINE } ;
STRING    = '"' { ( CHAR - ( '"' | "\" ) ) | ( "\" ( CHAR - NEWLINE ) ) } '"' ;
UNIT      = NUM ALPHA_ { ALPHA_ | DIGIT | "-" } ;   (* "35mm", "1.5x" *)
NUM       = FLOAT | INT ;
INT       = [ "-" ] DIGIT { DIGIT } ;
FLOAT     = INT "." DIGIT { DIGIT } ;
IDENT     = ALPHA_ { ALPHA_ | DIGIT | "-" } ;
MOD       = IDENT - TRAIT_KEYWORD ;
ALPHA_    = "A".."Z" | "a".."z" | "_" ;
DIGIT     = "0".."9" ;
CHAR      = ? any Unicode code point ? ;
NEWLINE   = ? U+000A ? ;
```

`INT` and `FLOAT` are the two shapes a `NUM` can take, not two token kinds: the lexer emits a single `NUM`, and the split is re-derived at emission time, where a `FLOAT` becomes `xsd:decimal` and an `INT` becomes `xsd:integer` (unless the role forces a string — §D.6).

An escape inside a `STRING` cannot span a line: the shipped lexer's `\\.` matches every code point except the newline, so `"a\` followed by a line break is an unterminated string, not an escaped newline. Earlier revisions of this block wrote `( "\" CHAR )`, which said otherwise; Appendix B carried the same over-broad production for VSON-P and is corrected with it (§D.10).

`MOD` is the token after `~` in a `*K V ~M` tail. A `~` is read as a modifier prefix only when the very next token is an `IDENT` that is not a `TRAIT_KEYWORD`; otherwise the `~` is left where it is, and anywhere but the first token of the document that is a parse error.

### D.3 Closed token vocabularies

These terminals are closed. They restate, as token sets, the VSV enumerations of §5.12.

**`TRAIT_KEYWORD`** — 14 tokens, the union of the four trait axes of §5.12. Recognized only inside `entity_tail` (§D.5); in any other position these spellings are ordinary `IDENT`s.

| Axis (§5.12) | Tokens | Emits |
|---|---|---|
| individuation | `Generic`, `Named`, `Kind`, `Skolem` | `vso:individuation` |
| animacy | `Agentive`, `Inert` | `vso:animacy` |
| countability | `Count`, `Mass`, `Collective` | `vso:countability` |
| affordance | `Holdable`, `Wearable`, `Mountable`, `Container`, `Edible` | `vso:affordance` (repeatable) |

**`CONCEPT`** — 12 tokens admissible after `/`: `PhysicalObject`, `Aggregate`, `Substance`, `CameraView`, `VisualStyle`, `SceneContext`, `Persona`, `Quality`, `Event`, `Process`, `Stative`, `SpatialFact`. Domain classes (`Knight`, `Crown`, `Sword`) never appear here — they are values of `*class` (Appendix C). `FRAME_KIND` (`CameraView`, `VisualStyle`, `SceneContext`, `Persona`) is a semantic subset, not a separate terminal: the grammar admits any `CONCEPT` after a leading `/` and only the bearer dispatch of §4.3 distinguishes them (see §D.8).

**`RCC_TOKEN`** — 8 tokens, the local names of the §5.12 `vso:rcc` enum, written without the prefix: `DC`, `EC`, `PO`, `EQ`, `TPP`, `NTPP`, `TPPi`, `NTPPi`. The emitter re-attaches `rcc:` because `rcc` is listed under `role_value_to_rcc` and these eight under `rcc_values` in [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json).

**`DIR_TOKEN`** — 9 tokens accepted, 6 conformant. The six §5.12 `vso:directional` values `above`, `below`, `left_of`, `right_of`, `in_front_of`, `behind`, plus three camelCase aliases the shipping parser also accepts: `leftOf`, `rightOf`, `inFrontOf`. The aliases are passed through verbatim and emit `vso:leftOf` / `vso:rightOf` / `vso:inFrontOf`, which are **not** in `vss:DirectionalValueShape`'s `sh:in` list — a document using one parses and then fails SHACL. Producers **MUST** use the six snake_case spellings; the aliases are recorded here because they are in the shipped token set, not because they are permitted output.

**`SYM_LEMMA`** — 3 tokens: `near`, `far`, `adjacent`, the three symmetric members of the five-value `vso:proximal` enum of §5.12. An unlisted `&` lemma is a parse error.

```ebnf
(* Closed token vocabularies. The tables and paragraphs above give each
   member's axis, the property it emits and its conformance status; this
   block is the same five sets as productions. Every member is IDENT-shaped,
   so a member only matches a whole IDENT — `Namedly` is an IDENT, not a
   TRAIT_KEYWORD followed by `ly`. *)

TRAIT_KEYWORD = "Generic" | "Named" | "Kind" | "Skolem"
              | "Agentive" | "Inert"
              | "Count" | "Mass" | "Collective"
              | "Holdable" | "Wearable" | "Mountable" | "Container" | "Edible" ;
CONCEPT       = "PhysicalObject" | "Aggregate" | "Substance"
              | "CameraView" | "VisualStyle" | "SceneContext" | "Persona"
              | "Quality" | "Event" | "Process" | "Stative" | "SpatialFact" ;
RCC_TOKEN     = "DC" | "EC" | "PO" | "EQ" | "TPP" | "NTPP" | "TPPi" | "NTPPi" ;
DIR_TOKEN     = "above" | "below" | "left_of" | "right_of" | "in_front_of" | "behind"
              | "leftOf" | "rightOf" | "inFrontOf" ;
SYM_LEMMA     = "near" | "far" | "adjacent" ;
```

`make grammar-check` fails unless these five sets, the five counts stated above them, the reference lexer's own token sets in [`tools/vson_x/vson_x.py`](../tools/vson_x/vson_x.py), and — for `RCC_TOKEN` — the `rcc_values` list in [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json) all agree (§D.10).

The perdurant lemma tables (`>` / `>>`) are routing tables, not closed vocabularies: they are listed in §4.3, with their role signatures in [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §5.

### D.4 Item boundaries and lookahead

No production in §D.5 has a `NEWLINE` terminal. A composition body is a flat sequence of items — no block nesting, no indentation rule — and an item ends exactly where the next item's lead token begins. A declaration may therefore span many lines with arbitrary indentation, and a whole scene may equally be written on one line.

| Lead pattern | Item |
|---|---|
| `~ IDENT` | composition root; the document's first two tokens |
| `/ CONCEPT` | `frame_decl` |
| `^ IDENT` | `viewer_anchor` at composition level |
| `[ "@" ] IDENT "/"` | `entity_tail` |
| `[ "@" ] IDENT ">"` | `stative` |
| `[ "@" ] IDENT ">>"` | `event` |
| `[ "@" ] IDENT "!"` | `spatial_asym` |
| `[ "@" ] IDENT "&"` | `spatial_sym` |

**Lookahead budget.** The grammar needs two tokens at exactly one place — the handle position, where an `IDENT` is resolved against the token after it to choose among `entity_tail` / `stative` / `event` / `spatial_asym` / `spatial_sym`. An `@` prefix pushes the same decision one token further, so the worst case is three tokens; everywhere else one token suffices.

**Arglist termination.** Inside a perdurant `arglist`, a bare `IDENT` is a positional ref unless the token immediately after it is `/`, `>`, `>>`, `!`, or `&` — in which case the arglist ends and that `IDENT` begins the next item. An `@ IDENT` applies the same test one token further along. Any other token kind (`~`, `^`, `/`, end of input) also ends the arglist.

**`*K V` binds to the nearest open bearer.** Composition-level `kv` must sit between `~IDENT` and the first item. Once an item has started, every following `*` is consumed by that item's `kv` loop, so a `*layout triangular` written after an entity declaration becomes a Quality of that entity, not of the composition. This is a consequence of flat items plus greedy `kv` loops, and it is the one place where the ordering of a document changes its meaning.

### D.5 Syntactic productions

```ebnf
document       = composition ;
composition    = "~" IDENT { kv } { item } ;

item           = frame_decl | viewer_anchor | handle_item ;

frame_decl     = "/" CONCEPT [ "@" IDENT ] { kv } ;
viewer_anchor  = "^" IDENT ;

handle_item    = handle ( entity_tail | stative | event
                        | spatial_asym | spatial_sym ) ;
handle         = [ "@" ] IDENT ;

entity_tail    = "/" CONCEPT { TRAIT_KEYWORD | kv } ;   (* order-independent *)

stative        = ">"  IDENT arglist ;
event          = ">>" IDENT arglist ;
arglist        = { ref | arg_kv } ;
arg_kv         = "*" IDENT value ;                      (* kv without the ~MOD tail *)

spatial_asym   = "!" REL ref [ viewer_anchor ] { kv } ;
REL            = RCC_TOKEN | DIR_TOKEN ;
spatial_sym    = "&" SYM_LEMMA "&" ref ;

kv             = "*" IDENT value [ "~" MOD ] ;
value          = STRING | UNIT | NUM | ref ;
ref            = [ "@" ] IDENT ;
```

1. **`kv` is one production; its meaning is not.** What a `*K V` emits depends entirely on the bearer it sits inside — the dispatch table in §4.3, with rationale in [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §3. Grammar and dispatch are separate layers, which is why there is one rule here and six rows there.
2. **`@` is optional and meaningless in `ref` position.** `@sword` and `sword` denote the same node. `@` is load-bearing in exactly two places: at a `handle` that heads an `entity_tail`, where it selects the default individuation when no individuation `TRAIT_KEYWORD` is given (`@` → `vso:Named`, bare → `vso:Generic`); and in `frame_decl`, where it is the only admissible handle form (`/CameraView @cam` is well-formed, `/CameraView cam` is not).
3. **`/CameraView @cam` and `@cam /CameraView` are different items.** The first is a `frame_decl` and attaches via `vso:framedBy`. The second is a `handle_item` whose `entity_tail` happens to name a Frame concept: it attaches via `vso:depicts` and acquires a default `vso:individuation`. Only the first form is correct for a Frame.
4. **In `spatial_asym` the viewer anchor MUST precede the `{ kv }` tail.** `a ! EC b ^cam *dir above` is well-formed; `a ! EC b *dir above ^cam` is not — the `^cam` falls outside the item and becomes a composition-level `vso:viewedBy`, leaving the directional fact with no viewer, which is the parse error of §D.7. Only a `^` anchor satisfies that requirement; a literal `*viewer @cam` emits the triple but does not satisfy it.
5. **The only nesting is composition → items.** Quality, Stative, Event, Process and SpatialFact nodes are synthesised by the parser; they are never written with brackets, and their identity is a blank node (see [`tools/vson_x/equiv.py`](../tools/vson_x/equiv.py) for how round-trip equivalence treats them).
6. **A thematic-role `*K V` takes no modifier.** `arg_kv` is `kv` without its `[ "~" MOD ]` tail. v1.1 has no encoding for a modifier on a thematic role and the reference parser rejects one whatever the key is, so the restriction belongs in the production rather than only in the error table — writing it here is what lets the grammar alone decide §D.7 E10 (§D.10).

### D.6 Bare identifiers — literal or IRI

VSON-X carries no literal/IRI distinction on its surface: `value`'s `ref` alternative covers both `@sword` and `sword`, and `*manner gently` and `*instrument @sword` are the same shape. The distinction is made at emission time, by **role name**, against [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json) — the same table VSON-P consumes, so the two surfaces route identically and cannot drift.

| Order | Test (routing-tables.json key) | Result | Example |
|---|---|---|---|
| 1 | role ∈ `role_value_as_string` | Turtle string literal | `*manner gently` → `vso:manner "gently"` |
| 2 | name was declared as a node var | reentrant IRI ref | `*instrument @sword` → `vso:instrument :sword` |
| 3 | role ∈ `role_value_to_rcc` and name ∈ `rcc_values` | `rcc:` IRI | `! EC` → `vso:rcc rcc:EC` |
| 4 | role ∈ `role_value_to_vso` | `vso:` IRI | `*dir above` → `vso:directional vso:above` |
| 5 | otherwise | document-local IRI | `*class Knight` → `vso:class :Knight` |

`STRING` and `UNIT` always render as string literals. A `NUM` renders as `xsd:decimal` or `xsd:integer` unless its role is in `role_value_as_string`. A Quality's `vso:value` is not in any of the three lists, so a bareword quality value lands in rule 5 and becomes a document-local IRI — `*color red` → `vso:value :red`, which §5.5's "bareword/string/integer" admits.

### D.7 Parse-time error set

Every condition below aborts the parse. This is the complete set raised by the reference parser; nothing else is a parse error.

| # | Error | Raised when | Decided by |
|---|---|---|---|
| E1 | `unexpected character: <c>` | lexer meets a non-whitespace character outside §D.2 | grammar |
| E2 | `expected <KIND>, got <tok>` | a required terminal is missing (e.g. `*` not followed by `IDENT`, or a `&` lemma with no closing `&`) | grammar |
| E3 | `unknown concept after /: <X>` | the token after `/` is not one of the 12 `CONCEPT`s | grammar |
| E4 | `unexpected lead token: <tok>` | a token at item position that is not `/`, `^`, `@`, or `IDENT` | grammar |
| E5 | `unexpected EOF after handle '<h>'` | input ends immediately after a handle | grammar |
| E6 | `after handle '<h>': expected '/', '>', '>>', '!', or '&', got <tok>` | a handle is followed by anything else | grammar |
| E7 | `modifier ~<M> not valid on direct property *<K>` | `~MOD` on the Composition's `*rendersAs` | parser |
| E8 | `modifier ~<M> not valid on Frame direct property *<K>` | `~MOD` on a metadata-Frame `kv` (Persona `kv` does admit one) | parser |
| E9 | `modifier ~<M> not valid on Entity direct property *<K>` | `~MOD` on one of the seven Entity direct keys | parser |
| E10 | `modifier ~<M> not valid on thematic role *<K>` | `~MOD` on a perdurant arglist `kv` — v1.1 has no encoding for it | grammar |
| E11 | `lemma '<L>' is Event/Process; use '>>' instead of '>'` | `>` with a lemma in the Event or Process table | parser |
| E12 | `lemma '<L>' is Stative; use '>' instead of '>>'` | `>>` with a lemma in the Stative table only | parser |
| E13 | `too many positional arguments: lemma expects <n>, got <m>` | more positional refs than the lemma's signature has slots | parser |
| E14 | `unknown spatial relation '<R>'` | the token after `!` is neither an `RCC_TOKEN` nor a `DIR_TOKEN` | grammar |
| E15 | `*dir value must be a directional bareword` / `*prox value must be a proximal bareword` | `*dir` / `*prox` given a `STRING`, `NUM` or `UNIT` value | parser |
| E16 | `directional spatial fact requires a viewer anchor (^cam)` | a `!` fact carries a direction (as `REL` or as `*dir`) with no `^` anchor. The message's "§4.10.2" is [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §4.10.2 | parser |
| E17 | `'<L>' is not a symmetric proximal lemma` | a `&` lemma outside `SYM_LEMMA` | grammar |
| E18 | `unexpected value token: <tok>` / `unexpected EOF in value` | a `kv` with no parsable value | grammar |

**Decided by** names the layer that does the rejecting. `grammar` means §D.2–§D.5 alone reject the document: any parser generated from those productions, in any host language, refuses the input before the reference parser's tables are consulted. `parser` means the productions accept it and the reference parser rejects it afterwards, from a table the grammar does not carry — the direct-property key sets of §4.3, the lemma signatures of [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §5, or the Talmy rule of §4.10.2. Ten rows are `grammar` and eight are `parser`. `make grammar-check` holds one negative fixture per row and asserts exactly that split, so the column is a checked claim rather than a reading (§D.10): a row moving from `parser` to `grammar` is a grammar that got stronger, and a row moving the other way is a regression.

Two conditions are **warnings**, not errors: a `>` lemma absent from all three tables falls back to `holder` + `theme`, and a `>>` lemma absent from all three falls back to an Event with `agent` + `patient`. Both are written to stderr and neither changes the emitted graph.

### D.8 Accepted by the grammar, checked elsewhere

The grammar is deliberately thin. These are well-formed VSON-X and are caught — if at all — by a later gate (§2 C1–C9) rather than by the parser. "A later gate" was SHACL alone through v1.2; v1.3 added the C2 vocabulary-closure gate, which is what now catches 6. Listing them is not an endorsement; a producer **MUST NOT** rely on any of them.

1. **Duplicate handle declarations.** Declaring `a /PhysicalObject` twice parses; both declarations emit onto the same IRI.
2. **Undeclared handles.** A ref to a handle that is never declared parses and emits a dangling IRI.
3. **Out-of-enum `*dir` / `*prox` values.** The parser checks only that the value is a bareword; `*dir sideways` parses and then fails `vss:DirectionalValueShape`. The same holds for the three camelCase `DIR_TOKEN` aliases of §D.3.
4. **Non-Frame concepts after a leading `/`.** `/PhysicalObject @x` parses and attaches via `vso:framedBy`, producing a `framedBy` edge to something that is not a `vso:Frame`.
5. **Viewer anchors.** Nothing checks that a `^` target is a declared `CameraView`, and a composition with zero or with several top-level `^` anchors parses. [`docs/vson-x-semantics.md`](./vson-x-semantics.md) §4.10.1 specifies stricter rules and marks each as unimplemented.
6. **Arglist key names.** Any `IDENT` is accepted as a thematic-role key; `*frobnicate zzz` emits `vso:frobnicate :zzz`, an undeclared VSO term the C2 gate rejects (§5.6).
7. **`~MOD` on a SpatialFact `kv` other than `*dir` / `*prox`.** Accepted and then discarded — the modifier reaches no triple.
8. **Geometry value ranges.** `*bbox2d` is not range-checked at parse time; `vss:GeometryShape` checks it at validate time (§5.4, v1.3).

### D.9 Reconciliation notes

Six differences between the pre-implementation grammar draft and the shipped parser. In each, the parser is authoritative and this appendix follows it.

**Annotation (v1.3).** The reconciliation this table records was done once, by hand, against the shipped parser. It is now also done by machine, on every commit: §D.10 describes the gate, and records the five further mismatches it found. The six rows below are the historical record of the pre-implementation draft and are left as written.

| # | Draft said | Shipped parser does | Resolution |
|---|---|---|---|
| 1 | `composition = "~" IDENT { quality_kv } NEWLINE block` | newlines are stripped by the lexer; items are found by lead token | `NEWLINE` and `block` dropped; §D.4 is the item-boundary rule |
| 2 | `rel = RCC_TOKEN \| DIR_TOKEN` — suspected over-broad | `! above b ^cam` is accepted, emitting `vso:directional vso:above` and **no** `vso:rcc` | `DIR_TOKEN` kept in `REL`; the emitted triple is documented in §D.3 |
| 3 | `value = IDENT \| INT \| FLOAT \| UNIT \| STRING \| ref` | `IDENT` in value position *is* the `ref` alternative; `INT`/`FLOAT` are one `NUM` token | collapsed to `value = STRING \| UNIT \| NUM \| ref`; §D.6 covers what a bareword becomes |
| 4 | `item = … \| comment` | comments never reach the parser | `COMMENT` moved to §D.2, removed from `item` |
| 5 | `trait = TRAIT_KEYWORD (* §5.x; order-independent *)` | traits are recognized inline in the entity declaration loop | inlined into `entity_tail`; the dangling `§5.x` is now §5.12, enumerated in §D.3 |
| 6 | Frames accept `@id` or bare `id` | `frame_decl` accepts an `@` handle only | `frame_decl = "/" CONCEPT [ "@" IDENT ] { kv }`; see §D.5 note 2 |

### D.10 Executable grammar and constrained decoding

Appendix B and this appendix are the normative grammars for the two syntaxes a person writes by hand. Through v1.2 nothing executed them, so the only way to know whether a production described the shipped parser was to read both and believe the answer — which is what §D.9 records having done once. Since v1.3 `make grammar-check` runs them, on every commit.

**The spec is the source.** [`tools/grammar/extract_grammar.py`](../tools/grammar/extract_grammar.py) reads the `ebnf` blocks of Appendix B and of §D.2, §D.3 and §D.5 out of this document by heading, together with the scanner-order tables, §D.4's lead-pattern table, §D.3's spelled counts and §D.7's rows. Nothing under [`tools/grammar/`](../tools/grammar/) carries a transcription of a production, a terminal or a token vocabulary: a grammar that changes here changes there in the same commit, or the gate goes red. [`tests/test_grammar_gate.py`](../tests/test_grammar_gate.py) establishes that by doctoring this file and watching the generated parser change with it.

**The translation is mechanical, and its rules are written down.** [`tools/grammar/ebnf.py`](../tools/grammar/ebnf.py) parses §D.1's notation; [`tools/grammar/lark_backend.py`](../tools/grammar/lark_backend.py) rewrites it into an LALR(1) grammar with a contextual lexer under twelve numbered rules (T1–T12) stated in its module docstring, and refuses — loudly — to translate a construct it has no rule for. Two of those rules exist because EBNF cannot say what this appendix says in prose: T11 realises §D.4's item-boundary rule, which needs a lookahead the notation has no spelling for, and T12 is what leaves a `TRAIT_KEYWORD` spelling an ordinary `IDENT` outside `entity_tail` (§D.3). The generated parser is never written to disk; it is regenerated on each run, because a generated parser in the checkout is a copy and a copy can be stale.

**What the gate asserts.** The generated parsers accept `examples/throne_room.vson`, all sixteen `examples/gallery/*.vson` and all twelve `examples/gallery-x/*.x.vson`, and so do the two reference implementations. `tests/fixtures/grammar/negative/` holds one document per §D.7 row, named for the row: the reference parser must reject all eighteen, and the generated parser must reject exactly the ten the `Decided by` column calls `grammar`. `tests/fixtures/grammar/vocabulary/` holds one out-of-vocabulary token per closed terminal of §D.3, and both parsers must reject each. The five §D.3 sets are compared against the five counts stated in the prose, against the reference lexer's own constants, and — for `RCC_TOKEN` — against `rcc_values` in [`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json).

**What it found.** Writing the grammars down in a form a program had to accept produced five mismatches between what the appendices said and what has always shipped. Each was resolved the way §D.9 resolved its six — the parser is authoritative — and each is annotated where it was fixed.

| # | Appendix said | Shipped parser does | Resolution |
|---|---|---|---|
| 1 | `role = ":" name term` — the `:` and the name are two symbols, and whitespace is insignificant | `:agent` is one token; `: agent` has never lexed | Appendix B declares `ROLE = ":" ID` and its scanner-order table says so |
| 2 | `unit = number letter+` — the suffix is letters only | `1.5x2` is one `UNIT`; the suffix admits digits and hyphens after its first letter | Appendix B declares `UNIT = NUM ALPHA_ { ALPHA_ \| DIGIT \| "-" }`, the same production §D.2 already carried |
| 3 | `term = node \| var \| literal` with `var` and `bareword` both `ID` | one `ID` branch, routed at emission time by role name | `term = node \| ID \| STRING \| NUM \| UNIT`, with the routing stated as note 2. The old form was ambiguous, so no parser generator would accept it at all |
| 4 | `( "\" CHAR )` — a string escape may span a line | the lexer's `\\.` does not match a newline, so `"a\` + newline is an unterminated string | Both Appendix B and §D.2 now write `( "\" ( CHAR - NEWLINE ) )` |
| 5 | `arglist = { ref \| kv }` — a thematic-role `kv` may carry `~MOD` | rejected unconditionally, whatever the key is | §D.5 declares `arg_kv` without the tail, which moves §D.7 E10 from `parser` to `grammar` |

**The constrained-decoding artifact.** [`tools/grammar/vson-x.gbnf`](../tools/grammar/vson-x.gbnf) is a translation of this appendix into [GBNF](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md), the grammar format llama.cpp accepts for constrained sampling. It is generated by [`tools/grammar/gbnf_backend.py`](../tools/grammar/gbnf_backend.py) under ten numbered rules (G1–G10) in its module docstring, regenerated by `make grammar-gbnf`, and compared byte for byte by `make grammar-check` — so it cannot drift from the productions above. GBNF is the target because it is an open format with a public parser, tied to no vendor and no model, usable by anyone running an open model locally with no account and no request; the other constrained-decoding grammars in circulation read the same kind of input, so this file is what they can be derived from.

**What the GBNF does not guarantee.** It constrains characters, and nothing else.

* **It is not conformance.** A document sampled under it is syntactically VSON-X; whether it is *conformant* VSON-X is decided by SHACL and the OWL RL check afterwards (§2 C1–C9). A constrained decoder can emit `*dir sideways`, a `vso:` term the vocabulary does not declare, or a scene whose asserted relations contradict its own rectangles — all three parse, and all three fail a later gate. Token-level constraint moves errors from the syntax layer to the semantic layer; it does not remove them.
* **It is wider than this appendix.** GBNF has no lookahead, so §D.4's item-boundary rule (rule G9) and the closed vocabularies' whole-identifier guard (G8) are not expressible, and `MOD = IDENT - TRAIT_KEYWORD` is emitted as `IDENT` (G10, listed in the generated file's header). Whitespace is inserted by an analysis that requires a separator only where it can prove both sides are identifier-shaped (G7), so `! ECb` — which the reference lexer reads as one unknown relation and rejects — is admitted here. Every relaxation is in the widening direction on purpose: the grammar never blocks a document the reference parser accepts.
* **It is verified in this repository, not against llama.cpp.** The gate re-reads the committed file as GBNF and checks that the language it defines still contains every shipped VSON-X scene. It does not run llama.cpp, and no sampling result is claimed here.

---

## Appendix E — Related work and bibliography

VSON is an assembly of existing ideas, not a new theory. This appendix names the sources the rest of the document leans on and states, for each, exactly what VSON takes and what it leaves behind. Nothing here is an endorsement by, or an affiliation with, the cited authors or standards bodies; entries omit page numbers and DOIs rather than risk an unverified one.

### E.1 Spatial and temporal calculi

**Randell, D. A., Cui, Z., & Cohn, A. G. (1992). A Spatial Logic Based on Regions and Connection. *Proceedings of the 3rd International Conference on Principles of Knowledge Representation and Reasoning (KR'92)*, Morgan Kaufmann.**
VSON ships the eight RCC-8 base relation names as a closed value vocabulary for `vso:rcc` (§5.7) and stops there — the composition calculus, the JEPD axioms, and constraint propagation over region networks are all out of scope.

**Allen, J. F. (1983). Maintaining Knowledge about Temporal Intervals. *Communications of the ACM*, 26(11).**
Same posture on the temporal side: VSON declares the thirteen interval relations as properties between Perdurants with their inverses and the self-composing transitivity (§5.9), and ships no composition table.

**Cox, S., & Little, C. (eds.). *Time Ontology in OWL*. W3C Recommendation, 2017. Namespace `http://www.w3.org/2006/time#`.**
Every `allen:` property carries a `skos:closeMatch` to its OWL-Time counterpart; VSON does not use the `time:` IRIs directly because OWL-Time types them on `time:ProperInterval` while VSON types them on `vso:Perdurant` (§5.9 design note).

**Perry, M., & Herring, J. (eds.). *OGC GeoSPARQL — A Geographic Query Language for RDF Data*. Open Geospatial Consortium, 2012 (v1.0; later revised as v1.1). Namespace `http://www.opengis.net/ont/geosparql#`.**
GeoSPARQL defines the `geo:rcc8*` IRIs each `rcc:` individual close-matches; VSON keeps its own terms because GeoSPARQL models the relations as binary properties between features while VSON models them as values on a reified `vso:SpatialFact` (§5.9 design note).

### E.2 Space in language

**Talmy, L. (2000). *Toward a Cognitive Semantics* (2 vols.). MIT Press.**
The figure/ground asymmetry is the reason `vso:SpatialFact` has two distinct, non-interchangeable slots (`vso:figure`, `vso:ground`) instead of an unordered pair (§3.3).

**Levinson, S. C. (2003). *Space in Language and Cognition: Explorations in Cognitive Diversity*. Cambridge University Press.**
Levinson's three frames of reference are why C5 exists: VSON commits to the **relative** frame and forces every directional fact to name its viewer, leaving intrinsic and absolute frames out of scope for v1.x (§3.3).

### E.3 Upper ontology

**Masolo, C., Borgo, S., Gangemi, A., Guarino, N., & Oltramari, A. (2003). *WonderWeb Deliverable D18: Ontology Library (final)*. ISTC-CNR.**
The definitive DOLCE description; VSON's `Endurant / Perdurant / Quality / Region` top is **DOLCE-inspired** — it borrows the category names and the endurant/perdurant cut, and imports no DOLCE IRI or axiom (§3.1).

**Almeida, J. P. A., Guizzardi, G., Sales, T. P., & Falbo, R. A. (2019). *gUFO: A Lightweight Implementation of the Unified Foundational Ontology (UFO)*. Namespace `http://purl.org/nemo/gufo#`.**
Where the borrowing above is finally recorded as triples. DOLCE's own IRIs are not used (§3.1), and gUFO is the nearest published foundational vocabulary whose terms *are* IRIs, so §5.17's `skos:closeMatch` set points at gUFO: `Endurant`, `Event`, `Object`, `Quantity`, `Collection`, `Quality`. What VSON does not take is gUFO's axiomatization or its taxonomy shape — `gufo:Quantity` and `gufo:Collection` sit under `gufo:Object` where `vso:Substance` and `vso:Aggregate` are siblings of `vso:PhysicalObject` — which is why six close-matches do not add up to a subsumption mapping.

### E.4 Predicate-argument structure

**Kipper Schuler, K. (2005). *VerbNet: A Broad-Coverage, Comprehensive Verb Lexicon*. PhD dissertation, University of Pennsylvania.**
VSON's thematic-role inventory (§5.6) is VerbNet-style: coarse, frame-independent role labels shared across predicates — though VSON uses a small fixed subset and ships no verb-class lexicon.

**Palmer, M., Gildea, D., & Kingsbury, P. (2005). The Proposition Bank: An Annotated Corpus of Semantic Roles. *Computational Linguistics*, 31(1).**
The finer-grained alternative VSON deliberately avoids: PropBank numbers arguments per verb sense, which needs a per-predicate lexicon at extraction time — the numbering only reappears in the AMR exporter mapping (§7).

**Baker, C. F., Fillmore, C. J., & Lowe, J. B. (1998). The Berkeley FrameNet Project. *Proceedings of COLING-ACL 1998*.**
The other alternative VSON avoids: FrameNet's frame-specific role names (`Donor`, `Recipient`) are more expressive than a vision-language model can reliably assign from a still image.

**Banarescu, L., Bonial, C., Cai, S., Georgescu, M., Griffitt, K., Hermjakob, U., Knight, K., Koehn, P., Palmer, M., & Schneider, N. (2013). Abstract Meaning Representation for Sembanking. *Proceedings of the 7th Linguistic Annotation Workshop and Interoperability with Discourse (LAW VII), ACL*.**
AMR is where the Penman authoring pattern of VSON-P comes from — nested `(var / Concept :role target)` with reentrancy (§4.2) — and AMR is also an export target (§7); VSON's concepts and roles are its own.

**Cai, S., & Knight, K. (2013). Smatch: an Evaluation Metric for Semantic Feature Structures. *Proceedings of the 51st Annual Meeting of the Association for Computational Linguistics (ACL), Short Papers*.**
Borrowing AMR's surface (§4.2) means inheriting its evaluation problem: variable names carry no information, so two correct annotations of one input share no node identifiers. Smatch is the published answer — search for the variable alignment maximizing matched triples, then report precision, recall and F1 over triples, with hill climbing and restarts because the maximization is NP-hard. §5.15 takes the method whole, including the restart discipline, and adds two things it does not have: a partition of the triples into VSON's own layers so a single F1 cannot hide which layer moved, and a written-down pseudo-random generator so the restarts are reproducible across implementations rather than only across runs of one. What VSON does not take is the surrounding practice — Smatch is reported in AMR as an inter-annotator agreement figure over an annotated corpus, and this repository has no annotated corpus, so it reports no such figure (§2.1, §5.15.5).

### E.5 Scene graphs in vision

**Johnson, J., Krishna, R., Stark, M., Li, L.-J., Shamma, D. A., Bernstein, M. S., & Fei-Fei, L. (2015). Image Retrieval using Scene Graphs. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*.**
The paper that established the object/attribute/relationship scene-graph formulation VSON starts from; VSON's departure is to reify relationships as nodes so they can be viewer-anchored, negated, and annotated.

**Krishna, R., Zhu, Y., Groth, O., Johnson, J., Hata, K., Kravitz, J., Chen, S., Kalantidis, Y., Li, L.-J., Shamma, D. A., Bernstein, M. S., & Fei-Fei, L. (2017). Visual Genome: Connecting Language and Vision Using Crowdsourced Dense Image Annotations. *International Journal of Computer Vision*, 123(1).**
The reference corpus for dense scene-graph annotation and a listed export target (§7); its open-string predicates are what VSON's closed relation vocabularies (§5.12) are a reaction to.

**Hudson, D. A., & Manning, C. D. (2019). GQA: A New Dataset for Real-World Visual Reasoning and Compositional Question Answering. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*.**
GQA showed what a normalized, cleaned scene-graph vocabulary buys downstream — the argument for VSON's closed enumerations and SHACL gate, rather than post-hoc cleanup.

**Lu, C., Krishna, R., Bernstein, M., & Fei-Fei, L. (2016). Visual Relationship Detection with Language Priors. *European Conference on Computer Vision (ECCV)*.**
VRD is where the ⟨subject, predicate, object⟩ triple over a **fixed** predicate list became the unit vision research is scored on — 100 object categories and 70 predicates. VSON's closed relation vocabularies (§5.12) share that instinct and apply it one layer up, in the schema rather than in a dataset split. What VSON leaves is the flat list: VRD's 70 predicates mix verbs, prepositions and comparatives in one set, so a single label carries a topological, a directional and an action reading at once. VSON splits those into `vso:rcc`, `vso:directional` (with its viewer), `vso:proximal`, thematic roles and possession, which is why no VSON slot can be ambiguous in the way a flat predicate is.

**Yang, J., Ang, Y. Z., Guo, Z., Zhou, K., Zhang, W., & Liu, Z. (2022). Panoptic Scene Graph Generation. *European Conference on Computer Vision (ECCV)*.**
The closed-predicate move, executed on a corpus, three years before this project started — the entry that most constrains what §5.12 may claim. PSG annotates 49k images overlapping COCO and Visual Genome against a **predefined predicate set of 56 relations** which its authors group into positional relations, common object–object relations, common actions, human actions, traffic-scene actions, sports-scene actions and background interactions, with objects drawn from COCO panoptic's 133 classes (80 *things* + 53 *stuff*) instead of Visual Genome's open strings. The stated reason is the one §5.12 gives: predicate definition was left unexamined in earlier datasets, and a curated set is what removes trivial and duplicated relations. **So closing a predicate vocabulary for visual scenes is not this project's idea, and this document does not claim it is.** What VSON adds is the locus of enforcement — PSG's 56 predicates are what annotators were *asked* to use, VSON's closed sets are what a document is *rejected* for leaving (C2/C3, §2) — and what VSON does not have is PSG's evidence: an annotated corpus at that scale, and models trained against it. It does now have the reading direction: [`tools/importers/psg.py`](../tools/importers/psg.py) converts PSG annotations under a checked-in mapping table, and of the 56 predicates published in that table 55 get a VSON construct and one — `about to hit` — is dropped, because asserting the perdurant would assert an event the annotation says has not happened (§7.1, [`docs/eval/coverage.md`](./eval/coverage.md)). §7's Visual Genome row is still spec-only: that is the *export* mapping, and no exporter implements it.

**Chang, X., Ren, P., Xu, P., Li, Z., Chen, X., & Hauptmann, A. (2023). A Comprehensive Survey of Scene Graphs: Generation and Application. *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 45(1).**
The field survey a reader should start from rather than from this appendix: scene-graph generation as a task, its datasets and its metrics, in one place. Cited to say where VSON is *not* — it is a notation and a validator, and takes no position on generation architectures.

**Ji, J., Krishna, R., Fei-Fei, L., & Niebles, J. C. (2020). Action Genome: Actions as Compositions of Spatio-Temporal Scene Graphs. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*.**
Scene graphs over time: an action decomposed into the per-frame graphs it passes through. VSON is a **still-image** scheme — §5.9's Allen relations hold between Perdurants inside one depicted moment, and nothing in v1.x indexes a frame or a timestamp. Action Genome is the shape a future video profile would have to take, and naming it here is the honest way to bound §5.9's temporal claim.

**Armeni, I., He, Z.-Y., Gwak, J., Zamir, A. R., Fischer, M., Malik, J., & Savarese, S. (2019). 3D Scene Graph: A Structure for Unified Semantics, 3D Space, and Camera. *IEEE/CVF International Conference on Computer Vision (ICCV)*.**
The prior art nearest to §3.3's `vso:CameraView`: a scene graph whose nodes include cameras alongside objects and rooms. Putting the camera in the graph is therefore not new here. The difference is obligation — 3D Scene Graph *can* relate a camera to what it sees; VSON *requires* one on every directional fact, and rejects the document without it.

**Anderson, P., Fernando, B., Johnson, M., & Gould, S. (2016). SPICE: Semantic Propositional Image Caption Evaluation. *European Conference on Computer Vision (ECCV)*.**
The other graph-agreement metric §5.15 could have been. SPICE scores a caption by parsing it into a scene graph and comparing that graph's tuples with the reference's — F-score over propositional content rather than over n-grams. VSON does not use it, for one structural reason: SPICE's input is text and its graph is whatever its parser produced, so the metric measures parser and caption together, while §5.15 compares two documents that are already graphs. What VSON takes from it is the argument, which is the same argument: the unit of agreement for a scene description is the tuple, not the string.

### E.6 Web standards VSON builds on or borrows patterns from

The four Recommendations below are the load-bearing ones: remove any of them and a conformance clause of §2 stops having a definition. They were left implicit through v1.3, named in the prose but absent from this bibliography, which made the list of things VSON *builds on* shorter than the list of things it *cites*.

**Knublauch, H., & Kontokostas, D. (eds.). *Shapes Constraint Language (SHACL)*. W3C Recommendation, 20 July 2017.**
C3 is a SHACL verdict and nothing else (§2). VSON defines no constraint component and no extension: [`shapes/vson-shapes.ttl`](../shapes/vson-shapes.ttl) is Core SHACL plus one `sh:sparql` constraint where Core cannot reach. What VSON does not take is SHACL-AF's rule layer — a shape here rejects, it never infers.

**Motik, B., Cuenca Grau, B., Horrocks, I., Wu, Z., Fokoue, A., & Lutz, C. (eds.). *OWL 2 Web Ontology Language Profiles (Second Edition)*. W3C Recommendation, 11 December 2012.**
The document that defines the fragment §2's second gate materializes. VSON's TBox is written to stay inside **OWL 2 RL** so that closure is a fixed-point computation rather than a tableau search; §5.9's "what the OWL 2 RL layer actually infers" is the concrete list, and the eight untyped bridge properties that put the full graph outside OWL 2 DL are recorded in the ontology header rather than hidden.

**Prud'hommeaux, E., & Carothers, G. (eds.). *RDF 1.1 Turtle: Terse RDF Triple Language*. W3C Recommendation, 25 February 2014.**
VSON-T's syntax (§4.1), with no deviation. The `<< s p o >>` quoted-triple form §5.11 admits belongs to the later RDF 1.2 / Turtle 1.2 work, which is on the Recommendation track; this document states no publication status for that suite, because the only fact that bears on a VSON implementation is the measured one in §5.14.2 — the pinned engine parses neither spelling — and §4.6 already requires the RDF 1.1-portable reduction before canonicalization.

**Harris, S., & Seaborne, A. (eds.). *SPARQL 1.1 Query Language*. W3C Recommendation, 21 March 2013.**
The language the competency-question pack of §5.14 is written in, and the reason it stops where it does: 28 of the 29 questions are SPARQL 1.1 with no extension, and the twenty-ninth needs quoted-triple patterns that this Recommendation does not define. §5.14.2 is the capability matrix.

**Miles, A., & Bechhofer, S. (eds.). *SKOS Simple Knowledge Organization System Reference*. W3C Recommendation, 18 August 2009.**
Two uses, both deliberately weak. `skos:closeMatch` and `skos:relatedMatch` carry every alignment this project asserts — in [`ontology/rcc8.ttl`](../ontology/rcc8.ttl), [`ontology/allen.ttl`](../ontology/allen.ttl) and §5.17's layer — precisely because SKOS mapping properties import no OWL entailment, which is the whole claim. And §5.17.4's generated view spells the six closed value vocabularies as concept schemes so a thesaurus tool can read them. What VSON does not use is the rest of SKOS: no `broader`/`narrower`, no collections, no `skos:exactMatch` anywhere.

**Sanderson, R., Ciccarese, P., & Young, B. (eds.). *Web Annotation Data Model*. W3C Recommendation, 2017.**
The body/target separation is the same shape as `vso:Annotation` (§5.11); VSON keeps its own minimal class rather than adopting the model, because its targets are triples rather than media fragments. §5.17 records that as a `skos:relatedMatch` — related, not interchangeable, because the model defines no target for a statement.

**Brickley, D., & Miller, L. *FOAF Vocabulary Specification*. Namespace `http://xmlns.com/foaf/0.1/`.**
Not a W3C Recommendation and named here for one term: `foaf:depicts`, the long-standing way to say an image shows a thing. §5.17 close-matches nothing to it and relates `vso:depicts` to it, because `foaf:depicts` starts at an image and `vso:depicts` starts at a `vso:Composition` — and this vocabulary has no term for the image at all.

**Lebo, T., Sahoo, S., & McGuinness, D. (eds.). *PROV-O: The PROV Ontology*. W3C Recommendation, 2013.**
The natural target for extractor provenance; VSON v1.1 records only a free-text `vso:source` on annotations and envelope-level `extraction` metadata (§6.1), so PROV-O alignment is future work, not a shipped feature.

**Longley, D., Kellogg, G., & Yamamoto, D. (eds.). *RDF Dataset Canonicalization*. W3C Recommendation, 21 May 2024. <https://www.w3.org/TR/2024/REC-rdf-canon-20240521/>** — the RDFC-1.0 algorithm.
The standard §4.6 borrows whole: label every blank node from the graph's own shape, serialize to canonical N-Quads (Appendix A of that Recommendation), and two isomorphic datasets are two identical byte strings. VSON adds only the two normalizations that come before it, and takes the hard half — the gossip-path search that separates blank nodes tied at first degree — from the Recommendation rather than inventing a hash of its own. Appendix B of the same document records that **URDNA2015** is the same algorithm up to the canonical N-Quads escaping clarification, which is why a JSON-LD toolchain's canonicalizer should agree with `tools/canon.py` on any VSON document. rdflib is not such a toolchain: its `rdflib.compare` implements **RGDA1** (McCusker, J. P. (2015). *WebSig: A Digital Signature Framework for the Web*. Rensselaer Polytechnic Institute), a correct isomorphism digest that issues different labels and emits no canonical document — the reason §4.6's reference implementation carries RDFC-1.0 itself instead of calling one.

**OASIS. *Static Analysis Results Interchange Format (SARIF) Version 2.1.0*. OASIS Standard, 27 March 2020.**
The report format §5.16.4 emits, and the reason `vson validate` emits one at all: a violation only becomes a mark on the offending line if something already reads the file, and every code scanner already reads this. VSON adds nothing to it — one `run`, one `result` per violation, the VSON-specific fields parked in `result.properties` where the format says extensions belong. No URL is cited here for the same reason the emitted log carries no `$schema`: this document does not name a location it has not checked.

### E.7 Spatial annotation standards

The section this appendix was missing, and the one that most changes what §3.3 may claim. Everything below annotates **language** rather than pictures, which is why none of it appeared here before — and every one of them had already made the two decisions §3.3 presents as VSON's design: name the two arguments of a spatial relation asymmetrically, and require both. Reading this section as a list of things VSON did first is reading it wrong. It is the record of what was already standardized, so that the narrow thing VSON does add is legible as narrow.

Two conventions apply throughout. The ISO entries are cited **by number and title only**: this project has not verified a copy of either standard's text, and paraphrasing a paywalled clause would be asserting something it cannot show. Where a fact about ISO-Space is stated below, it is stated from the open-access ISA-14 paper immediately after it, which is the source that was read. And no inter-annotator agreement number is restated from any entry here — the studies are named and their designs described, because that is what was verified; their tables were not.

**ISO 24617-7:2020. *Language resource management — Semantic annotation framework — Part 7: Spatial information*. International Organization for Standardization.**
The standard for annotating spatial and spatiotemporal information in natural-language text: locations, spatial entities, spatial relations with topological, orientational and metric values, motion events, paths and event-paths. The 2020 edition is the second, superseding ISO 24617-7:2014, whose title carried the scheme's common name, *ISOspace*. Its link structures are required to carry a relation type and two arguments — the triplet structure ISO 24617-6 mandates of a link — and in the revised movement link those two arguments are named, literally, `@figure` and `@ground`. That is established below from the open-access ISA-14 paper, not from this standard's text. **What VSON takes:** nothing it needed to be told — but the reification pattern of §3.4 and §5.7, a relation made into a structure with two distinct named arguments and a relation type, is this standard's structure, published before this project began. **What VSON leaves:** the entire text layer. ISO-Space anchors its structures to *markables* — spans of a document — and VSON has no document to point into; and its motion apparatus (motion events, paths, event-paths) has no VSON counterpart at all, since §5.9's Allen relations hold between Perdurants inside one depicted moment and nothing in v1.x describes a trajectory.

**Lee, K., Pustejovsky, J., & Bunt, H. (2018). The Revision of ISO-Space, Focused on the Movement Link. *Proceedings of the 14th Joint ACL–ISO Workshop on Interoperable Semantic Annotation (ISA-14)*.**
The open-access record of the revision that became the 2020 edition, and the source the paragraph above rests on rather than on a standard this project has not read. Its attribute-value specification for the movement link lists `figure`, `ground` and `relType` among the **required** attributes, and states that this instantiates the general triplet link structure ⟨η, E, ρ⟩ that ISO 24617-6 requires of a link — η the figure, E the ground, ρ the relation type. That triplet is, slot for slot, a `vso:SpatialFact` carrying `vso:figure`, `vso:ground` and exactly one relation value. The names are Talmy's on both sides; the requirement that both be present is standardized on the ISO side and enforced by a shape on the VSON side, and those are different things but not different ideas.

**ISO 24617-14:2023. *Language resource management — Semantic annotation framework (SemAF) — Part 14: Spatial semantics*. International Organization for Standardization.**
Part 7's companion: a formal semantics for the annotation structures Part 7 defines, translating them into semantic forms in a type-theoretic first-order logic and interpreting those against a model. Named here for what VSON does **not** have. §7's FOL exporter renders a document into first-order syntax and no clause of this specification interprets that syntax against a model; "machine-checkable" here means SHACL, an OWL 2 RL closure and a geometry procedure (§2.1, §5.13), never model-theoretic truth. A reader looking for the semantics half of a spatial annotation scheme should read this standard, not this document.

**Bateman, J. A., Hois, J., Ross, R., & Tenbrink, T. (2010). A linguistic ontology of space for natural language processing. *Artificial Intelligence*, 174(14).**
GUM-Space: the spatial extension of the Generalized Upper Model, a detailed semantics for linguistic spatial expressions built with the methods of formal ontology, covering space, action in space, and spatial relationships. It is the fully-worked version of what §5.7's six directional and five proximal values are a deliberate coarsening of, and it is cited here for the same reason §5.6 cites FrameNet: the finer analysis is the one a vision-language model cannot reliably produce from a still image, so VSON took the smaller inventory on purpose and owes the reader the name of what it gave up.

**Hois, J. (2010). Inter-Annotator Agreement on a Linguistic Ontology for Spatial Language — A Case Study for GUM-Space. *Proceedings of the 7th International Conference on Language Resources and Evaluation (LREC 2010)*.**
The published agreement study for GUM-Space, and the entry that says most about this project. Its design, from the abstract: four uninformed annotators, instructed by a manual, annotating 200 sentences of varying length and complexity, with the authors' own expert annotation of the same sentences included in the computation. **This document does not restate its figures.** The abstract reports "encouraging results" without quantifying them, this project verified the abstract and not the tables, and a number cited from something unread is exactly the failure §2.1 exists to prevent. What is verified, and what matters: a scheme that asks people to apply it publishes a study like this one, and VSON has not. §2.1 and §5.15.5 already say this repository reports no agreement figure, because it has no annotated corpus and no second annotator; this is the shape of the study that would have to exist before it could.

**Mani, I., Doran, C., Harris, D., et al. (2010). SpatialML: annotation scheme, resources, and evaluation. *Language Resources and Evaluation*, 44.** (The author list is given as the indexing record gives it; this document does not spell names it has not seen on the paper.)
The place-focused ancestor: named and nominal references to places, grounded in geo-coordinates where possible, with relations among places characterized in a region calculus — the same RCC family §5.7 draws its eight values from — plus an annotation editor and annotated corpora, and a published agreement evaluation whose figures this document likewise does not restate. **VSON takes the opposite line on grounding, deliberately.** SpatialML grounds a place in the world: coordinates, gazetteer identity, a referent that exists whether or not anyone wrote about it. VSON grounds nothing outside the picture — a `vso:PhysicalObject` carries a `vso:bbox2d` in normalized image coordinates (§5.10) and makes no claim about the Earth, and §2.1 states that a green verdict is not even a claim about the image. Two schemes with a shared calculus and opposite referential commitments.

**Kordjamshidi, P., Bethard, S., & Moens, M.-F. (2012). SemEval-2012 Task 3: Spatial Role Labeling. *\*SEM 2012: The First Joint Conference on Lexical and Computational Semantics*.**
The shared task that turned the figure/ground pair into an evaluated unit under different names: *trajector*, *landmark*, and the *spatial indicator* that triggers the relation, with a relation type assigned to each ⟨trajector, spatial indicator, landmark⟩ triple. `vso:figure` and `vso:ground` are those two roles with Talmy's names. VSON has no counterpart to the spatial indicator, and cannot: there is no text to point at, so the trigger of a `vso:SpatialFact` is a producer's decision about a picture rather than a word in a sentence. What this entry costs the project is what the ISO entries cost it — naming the two arguments and requiring both is prior art, with a shared task and a leaderboard behind it.

**What is left over.** Every scheme above annotates language; VSON annotates a picture, and the trade that comes with the move is worth stating in both directions. What VSON gives up: a text layer, a semantics (24617-14), a motion apparatus, world-grounded referents (SpatialML), and — the one that is not a design decision — an annotated corpus and a published agreement figure, which several entries here have and this project has neither of. What VSON adds is one thing: the constraints are executed by a **validator that rejects documents**, not written in a manual an annotator is asked to follow. C5 is not a stronger claim about space than ISO-Space's `@figure`/`@ground`; it is the same claim with an exit code attached. §3.3 says this, and earlier drafts of it did not.

### E.8 Ontology engineering methodology

**Grüninger, M., & Fox, M. S. (1995). Methodology for the Design and Evaluation of Ontologies. *Proceedings of the IJCAI-95 Workshop on Basic Ontological Issues in Knowledge Sharing*.**
Where competency questions come from: the requirements an ontology is evaluated against are stated as questions it must be able to answer, and the evaluation is whether it answers them. §5.14 takes the second half literally — each question ships as a query with a frozen answer, so "can answer" is a thing CI decides rather than a thing the author asserts.

**Suárez-Figueroa, M. C., Gómez-Pérez, A., & Fernández-López, M. (2012). The NeOn Methodology for Ontology Engineering. In *Ontology Engineering in a Networked World*. Springer.**
The methodology that carries competency questions through as a first-class artefact, with the natural-language question, its author or stakeholder, and its authorizing requirement recorded beside the formalization. `queries/*.rq` keeps that header — question, persona, spec section — for the same reason.

---

*This document is normative. When it disagrees with another VSON artifact, resolve the conflict by the precedence order in §2 — this document ranks first, but a mismatch is a bug either way, not a licence to ignore the lower-ranked artifact.*
