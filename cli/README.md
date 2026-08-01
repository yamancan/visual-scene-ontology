# `vson` — VSON v1.1 CLI

Single static Rust binary for the most-used VSON operations.

## Install

```bash
cd cli
cargo build --release
# binary lands at target/release/vson
```

The release binary links nothing beyond libc, and it carries the repository files its subcommands read — the ontology, the shapes and the Python reference implementations — so it runs from any directory, with no checkout and no `VSON_HOME`. What it does **not** carry is a Python runtime: `validate`, `verify`, `diff` and the three Python-backed convert/export subcommands spawn `pyshacl` and `python3`.

```bash
pip install pyshacl rdflib owlrl   # required for `vson validate` (or: make deps)
```

See [What the binary carries](#what-the-binary-carries) for the exact list, and for what remains a host dependency.

## Subcommands

```bash
vson validate <files...>         # exit 0 pass, 1 gate failure, 2 could not run
vson verify --geometry <files...># non-conformance checks; same three exit codes
vson diff <a> <b>                # graph agreement: 0 identical, 1 differing, 2 no verdict
vson convert p2t <file.vson>     # Penman -> Turtle on stdout
vson convert t2p <file.ttl>      # not implemented (stub; use Python ref)
vson convert x2t <file.x.vson>   # VSON-X -> Turtle on stdout
vson export cypher <file.vson>   # one Cypher CREATE statement on stdout
vson export caption <file.vson>  # deterministic English caption on stdout
vson export fol <file.vson>      # Prolog-style first-order-logic facts on stdout
vson --version
vson --help
```

## `validate`

`validate` accepts both `.ttl` and `.vson` files. For `.vson`, the binary transpiles to a temp `.ttl` first; all three gates then read that temp file, which is deleted on every exit path.

It runs **three gates** against every file you name, in order, stopping at the
first one that fails:

1. **SHACL** — `pyshacl --abort` over `shapes/vson-shapes.ttl` plus the three ontology files, with `rdfs` inference.
2. **OWL 2 RL consistency** — `python3 -m tools.owlrl_check <file>`, run from the resolved `VSON_HOME`. This catches `owl:disjointWith` / `owl:AllDifferent` clashes that gate 1 is structurally blind to, because `rdfs` inference never processes disjointness.
3. **C2 vocabulary closure** — `python3 -m tools.c2_check <file>`, same home. Clause C2 of [`../docs/vson.md`](../docs/vson.md) §2: every VSON-namespace IRI the document asserts is declared in `ontology/vso.ttl`, `rcc8.ttl` or `allen.ttl`. Neither gate above can decide it — a shape would have to assume the ontology sits in the data graph, and an undeclared IRI entails no OWL clash — so through v1.2 `vson validate` did not establish C2 and §2 said so. Added in v1.3.

A file is reported `OK` only once it clears all three. Each gate costs a Python
process spawn, so validating the whole gallery in one invocation is noticeably
slower than validating one scene.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | every input cleared all three gates |
| 1 | an input genuinely failed a gate — `FAIL <file> (shacl)`, `FAIL <file> (owl-consistency)`, or `FAIL <file> (c2)` |
| 2 | a gate never reached a verdict: missing `pyshacl`/`python3`/`owlrl`, an unparseable input, a wrong `--home` |

The 1-vs-2 split takes more than the child's exit status. `pyshacl` and both
Python gates exit 1 for "did not conform" *and* for "crashed with an uncaught
exception" — an unparseable `.ttl` and a missing `owlrl` module both land on
the same code. The CLI therefore captures each child's stdout and looks for the
report that tool writes only when it truly ran; anything else at exit 1 is
reported as a broken toolchain (exit 2) with the child's stderr attached, not as
a failed document.

### Output discipline

The `OK` / `FAIL` lines are the only thing on **stdout**, so `vson validate` is
scriptable. Every human-readable report — the pyshacl violation report, the
OWL clash listing, error messages — goes to **stderr**.

`convert x2t`, `export caption`, and `export fol` shell out to the Python references (`tools/vson_x/`, `tools/render/`), so they require `python3` on `PATH`. No native Rust VSON-X parser or caption/FOL renderer ships: the Python modules are the single source of truth for the fixtures CI checks, and the Rust side is one shared bridge (`src/commands/python_bridge.rs`) that resolves a home and runs `python3 -m <module>` from it. When there is no checkout to be a home, the binary writes its own from the copy it carries.

Files are read from disk by path; stdin (`-`) input is not yet supported.

## Cold-start example

```bash
$ git clone <repo> && cd visual-scene-ontology
$ make deps
$ cd cli && cargo build --release && cd ..
$ cli/target/release/vson validate examples/throne_room.ttl
OK  examples/throne_room.ttl
$ echo $?
0

$ cli/target/release/vson export cypher examples/throne_room.vson > scene.cypher
$ wc -l scene.cypher
      78 scene.cypher
```

A failing document prints one `FAIL` line on stdout and the report on stderr:

```bash
$ cli/target/release/vson validate tests/fixtures/bad_no_viewer.ttl 2>/dev/null
FAIL tests/fixtures/bad_no_viewer.ttl (shacl)
$ echo $?
1
```

The same binary, away from the checkout entirely — no `VSON_HOME`, nothing on
disk but the binary and one scene:

```bash
$ mkdir /tmp/elsewhere && cd /tmp/elsewhere
$ cp ~/visual-scene-ontology/cli/target/release/vson .
$ cat > scene.vson <<'EOF'
(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :framing close_up)
   :viewedBy cam
   :depicts (apple / PhysicalObject :individuation Generic :animacy Inert
                                    :countability Count :class Apple))
EOF
$ ./vson validate scene.vson
OK  scene.vson
$ ./vson export caption scene.vson
Eye level close up. An apple.
```

The ontology, the shapes and the Python modules those two commands ran came out
of the binary; `python3`, `rdflib`, `pyshacl` and `owlrl` came from the host.
[What the binary carries](#what-the-binary-carries) draws that line exactly.

## `verify`

`validate` answers one question: is this a conformant VSON document? `verify` is
where the checks that are **not** conformance live — properties worth checking
that no numbered clause requires, and that a document may fail while staying
fully conformant. Today there is one:

```bash
vson verify --geometry [--verbose] <files...>
```

`--geometry` checks the spatial relations a document asserts against the
`vso:bbox2d` rectangles it asserts beside them ([`../docs/vson.md`](../docs/vson.md)
§5.13, via `python3 -m tools.geometry_check`). When a `vso:SpatialFact`'s figure
and ground both carry a box, the two statements can disagree — `rcc:NTPP`
between rectangles that do not overlap, `vso:left_of` between centroids ordered
the other way — and this reports the disagreements.

It **reads no image**. A clean run says the document does not contradict itself,
not that it describes the picture; §2.1 of the spec is unchanged and the report
says so on every run. The check refutes rather than confirms: a bounding box
contains the region and is not the region, so `rcc:DC` is never refutable and a
cat that is `rcc:EC` with the table it sits on keeps its overlapping box.
Anything the rectangles cannot decide — `vso:proximal`, `in_front_of` /
`behind`, `vso:visibleFraction`, a missing box — is reported `undecidable` with
a reason, never guessed at. `--verbose` prints every relation's verdict instead
of only the contradicted ones.

Naming a check is required: `vson verify` with no flag is a usage error (exit
2), so that a second check landing later cannot change what an existing command
line means.

```bash
$ vson validate tests/fixtures/geometry_inconsistent_rcc.ttl
OK  tests/fixtures/geometry_inconsistent_rcc.ttl
$ vson verify --geometry tests/fixtures/geometry_inconsistent_rcc.ttl
FAIL tests/fixtures/geometry_inconsistent_rcc.ttl (geometry)
$ echo $?
1
```

That pair is the point: three conformance gates green, geometry red, on one
file. Exit codes match `validate` — 0 clean, 1 a document that contradicts its
own geometry, 2 no verdict — and stdout carries only the `OK` / `FAIL` lines,
with the report on stderr.

## `diff`

`validate` and `verify` each ask about one document. `diff` asks about two: how
much of the graph they share, once the arbitrary names each one gave its nodes
are aligned away.

```bash
vson diff [--format text|json] <a> <b>
```

Two extraction runs over one image name their nodes independently — `:cat` in
one, `_:e3` in the other — so no string comparison can tell whether they agree.
This searches for the variable alignment that maximizes matched triples and
reports precision, recall and F1 over triples under it, overall and per layer:
objects, attributes, spatial (a second time viewer-blind), frames, events,
other. That is Smatch, the metric AMR uses, defined over VSON's graph;
[`../docs/vson.md`](../docs/vson.md) §5.15 is the full definition, down to the
seed policy, and `python3 -m tools.metrics.smatch` is the implementation.

Inputs may be `.ttl`, `.vson` or `.x.vson`, **in any combination**: the metric
runs on the materialized graph, so the surface an input was written in cannot
move the score.

```bash
$ vson diff examples/gallery/04_directional_with_viewer.vson \
            examples/gallery-x/04_directional_with_viewer.x.vson
...
  overall               26     26     26     1.0000   1.0000   1.0000
smatch: the two documents assert the same graph up to variable renaming (F1 1.0000). No image was read.
$ echo $?
0
```

Exit 0 means the two documents are identical at triple level, 1 that they
differ, 2 that no verdict was reached (unreadable input, unknown syntax, no
`python3`). **Agreement is not correctness**: F1 = 1.0 says the two documents
assert the same graph, not that either describes the picture — two runs
agreeing on the same hallucination score 1.0. No image is read.

Output discipline differs from `validate` here, because the report *is* the
product rather than a diagnostic: the table goes to **stdout**. Under
`--format json` stdout is a single parseable document — counts as integers,
ratios rounded — and the summary line moves to stderr so `| jq` keeps working.

## `export cypher`

The exporter emits **one** Cypher statement for the whole scene — every node
pattern first, then every relationship pattern reusing the variables those node
patterns bound:

```cypher
CREATE
  (scene:Composition {id: 'scene'}),
  (ctx:SceneContext {id: 'ctx', venue: 'throne_room', atmosphere: 'tense', timeOfDay: 'dusk'}),
  (scene)-[:framedBy]->(ctx);
```

One statement is load-bearing, not cosmetic: Cypher scopes a variable to its
statement, so a file of one-`CREATE`-per-line would leave every relationship's
endpoints unbound and quietly create empty nodes instead of edges.

Mapping rules:

- a Penman node `(v / Concept ...)` becomes `(v:Concept {id: 'v', ...})`;
- a role whose target is a literal, or a bare name that is not a declared
  variable, folds into that node's property map;
- a role whose target is a declared variable becomes a relationship;
- `-` is folded to `_` in variables, labels, relationship types and property
  keys, because the VSON-P lexer admits it and Cypher does not. Two roles that
  collide after that fold (`:focal-length` and `:focal_length`) resolve
  last-write-wins, since a Cypher map may not repeat a key.

Load it into an **empty** database:

```bash
cypher-shell -u neo4j -p <password> < scene.cypher
```

The export is **not idempotent**: it is `CREATE`, not `MERGE`, so re-running it
against a populated database duplicates every node and relationship. Wipe the
database (or import into a fresh one) between loads.

`cargo test` checks the output structurally — exactly one statement terminator,
no `SET` clause, and every relationship endpoint bound by a node pattern in the
same `CREATE`. It is not checked against a live Neo4j server.

## What the binary carries

Six of the nine subcommands read files that used to exist only inside a
checkout — everything except `convert p2t`, `convert t2p` (a stub) and `export
cypher` — and a binary copied anywhere else exited 2 on all six. The crate now
embeds those files with `include_str!` and writes them to a per-version cache
directory the first time one is needed, so a downloaded binary works in a
directory that has never seen this repository.

**Carried** — 21 files, ~292 KiB of source, listed in
[`src/commands/embed.rs`](src/commands/embed.rs):

| Group | Files | Needed by |
| --- | --- | --- |
| Ontology | `ontology/vso.ttl`, `ontology/rcc8.ttl`, `ontology/allen.ttl` | `validate` gates 1 and 3 |
| Shapes | `shapes/vson-shapes.ttl`, `shapes/vson-shapes-relaxed.ttl` | `validate` gate 1 (the relaxed profile ships in the binary, though no flag selects it yet) |
| Gates | `tools/owlrl_check.py`, `tools/c2_check.py`, `tools/geometry_check.py` | `validate` gates 2 and 3, `verify --geometry` |
| Metric | `tools/metrics/smatch.py` | `diff` |
| Transpilers | `tools/penman/vson_penman.py`, `tools/vson_x/vson_x.py`, `tools/vson_ast.py`, `src/penman/routing-tables.json` | `convert x2t`, `diff`, both renderers |
| Renderers | `tools/render/caption.py`, `tools/render/fol.py`, `tools/render/verbs.json` | `export caption`, `export fol` |

plus the five `__init__.py` files that make `tools/`, `tools/penman/`,
`tools/render/`, `tools/vson_x/` and `tools/metrics/` importable packages —
without them Python resolves each directory as a namespace package and the
relative imports inside fail. `routing-tables.json` is written back to
`cli/src/penman/routing-tables.json` inside the materialized tree, because that
is the path `tools/penman/vson_penman.py` computes from its own location.

**Not carried, and still required of the host:**

- **`python3` on `PATH`.** Every gate, the metric, both renderers and `convert x2t` run as `python3 -m <module>`.
- **`rdflib`, `pyshacl` and `owlrl`** importable by that interpreter — `pip install pyshacl rdflib owlrl`. `validate`'s first gate spawns the `pyshacl` **console script**, so that has to be on `PATH` as well, not merely importable.

So the claim is exactly this and no more: **self-contained with respect to
repository files, not with respect to the Python runtime.** On a machine with
no Python, `convert p2t` and `export cypher` work and nothing else does.

### Where the copy is written

`<cache>/vson/<version>/`, with `<cache>` resolved in this order:

| Step | Location |
| --- | --- |
| 1 | `$VSON_CACHE_DIR` (verbatim — the escape hatch for a read-only or absent home directory) |
| 2 | `$XDG_CACHE_HOME/vson` |
| 3 | `%LOCALAPPDATA%\vson` |
| 4 | `~/Library/Caches/vson` on macOS, `~/.cache/vson` elsewhere |
| 5 | the system temp directory — always writable, and the least durable of the five |

Nothing is written while a checkout is in play: materialization happens only on
the last leg of home resolution, so a contributor's runs touch no cache at all.

The tree is keyed by the crate version **and** by a fingerprint of the payload,
recorded in a `.vson-embedded` stamp written last of all. Two consequences worth
knowing: a run killed halfway leaves no stamp and is rewritten rather than
half-trusted, and a development build whose shapes changed without a version
bump refreshes instead of validating against last week's copy. Deleting the
directory costs one rewrite.

### VSON_HOME

A *home* is a directory laid out like this repository. Four kinds of thing can
be one — a path you name, a checkout above the input file, a checkout above the
working directory, or the copy inside the binary — tried in this order:

| Step | `validate`, `verify`, `diff` | `convert x2t`, `export caption`, `export fol` |
| --- | --- | --- |
| 1 | `--home <dir>` | — (no flag) |
| 2 | `$VSON_HOME` | `$VSON_HOME` |
| 3 | — (several inputs, so no single directory to walk up from) | the input file's directory, then each parent, up to `/` |
| 4 | the working directory, then each parent | the working directory, then each parent |
| 5 | the copy embedded in the binary | the copy embedded in the binary |

**An explicit home wins and never falls back.** If `--home` or `$VSON_HOME` is
set and does not hold the file a subcommand needs, that is an error (exit 2)
naming the file, the directory, and the way out — not a silent switch to the
copy compiled in a month ago. The point is the contributor editing
`shapes/vson-shapes.ttl` who has to find out that their path is wrong.

```bash
vson validate --home /path/to/visual-scene-ontology /tmp/scene.ttl
# or
VSON_HOME=/path/to/visual-scene-ontology vson validate /tmp/scene.ttl
VSON_HOME=/path/to/visual-scene-ontology vson export fol /tmp/scene.vson
```

Steps 3–5 live in one place — [`src/commands/home.rs`](src/commands/home.rs) —
so every subcommand resolves alike and every failure names both the file it
looked for and which of the five steps produced the directory it looked in.

### Keeping the embedded copy honest

The payload is a byte-identical mirror under `cli/assets/`, not a second
source. It has to be a copy rather than a path out of the checkout because
`include_str!` may not reach outside the crate root (see [Source of
truth](#source-of-truth)), and `scripts/check_embedded_assets.py` — run by `make
cli-check` — is what keeps the copy a copy. It fails the build on four things:
a mirrored file that differs from the repository original by one byte; a
`tools.…` import that escapes the embedded closure (one new `from tools.canon
import …` inside `smatch.py` would break `vson diff` for everyone outside a
checkout, and no test that runs from the checkout could see it); a repository
path named anywhere in `cli/src/` that is not embedded, which is what makes a
*new* Python-backed subcommand fail in CI instead of in a user's terminal; and
an orphan file under `cli/assets/` that nothing lists.

```bash
python3 scripts/check_embedded_assets.py          # the gate
python3 scripts/check_embedded_assets.py --sync   # refresh the mirror after editing an original
```

Edit the original, run `--sync`, commit both.

## Verification

```bash
cd cli && cargo test               # 84 tests: 36 unit, 48 integration
make cli-check                     # fmt + clippy + build + test + embedded-payload gate + standalone-binary test + graph-isomorphic check vs Python ref
```

The 48 integration tests split six ways: 9 golden-fixture tests
(`tests/golden_throne_room.rs`), 5 validate-fixture tests
(`tests/golden_validate.rs`), 9 geometry-gate tests
(`tests/geometry_gate.rs`), 9 diff tests (`tests/diff_gate.rs`), 6
error-contract tests (`tests/error_contract.rs`) pinning the exit-2 "never
reached a verdict" half of the interface, and 10 standalone tests
(`tests/standalone_home.rs`) that copy the binary **alone** into an empty
directory outside any checkout, write their fixture there, unset `VSON_HOME`,
and assert exit 0 — the proof that a downloaded binary works. `make cli-check`
runs that file a second time against the **release** binary, which is the
artifact a user would actually copy.

Everything else needs `python3`/`pyshacl`. The six error-contract tests, and the
three standalone cases covering the pure-Rust subcommands and a wrong
`$VSON_HOME`, fail in Rust before anything is spawned and pass on a machine with
no Python at all.

`cli-check` asserts that the Rust transpiler produces graph-isomorphic Turtle to the Python reference on the canonical throne-room scene (134 triples).

## Source of truth

VSON-P role routing rules live in [`src/penman/routing-tables.json`](src/penman/routing-tables.json), inside this crate. `src/penman/routing.rs` embeds that file with `include_str!` at compile time; the Python reference at [`../tools/penman/vson_penman.py`](../tools/penman/vson_penman.py) reads the same file out of the checkout at import time. One file, two consumers, so they cannot drift — `make cli-check` is what proves it, comparing both emitters' graphs with `rdflib.to_isomorphic`.

The table sits in the crate rather than next to the Python reference because `include_str!` may not reach outside the crate root. A path that escapes it with `../../../` compiles fine inside a checkout but fails the isolated verify build that `cargo package` runs, which would make the crate impossible to publish or `cargo install`. `cd cli && cargo package` is the standing check; the crate is self-contained today, though it is not published to crates.io yet.

That same constraint is why the ontology, the shapes and the Python package the binary carries live under [`assets/`](assets/) as a byte-identical mirror rather than as `../ontology/...` paths — see [Keeping the embedded copy honest](#keeping-the-embedded-copy-honest) for the gate that keeps a mirror a mirror.

## Known limitations

- `convert t2p` not implemented — needs a native Rust Turtle parser.
- There is no `--partial` flag, in this CLI or in the Python reference: no argument parser defines it and no code branches on it. The relaxed profile it would select does ship, as [`../shapes/vson-shapes-relaxed.ttl`](../shapes/vson-shapes-relaxed.ttl) and inside the binary, and is exercised by the test suite (`tests/test_shapes_gate.py`) — but no command-line entry point selects it yet.
- The binary carries every repository **file** it reads, but not the Python **runtime** that reads them: `validate` shells out to `pyshacl`, `python3 -m tools.owlrl_check` and `python3 -m tools.c2_check`, so all three gates still need `python3` with `rdflib`, `pyshacl` and `owlrl` (`make deps`). Removing that dependency is a different piece of work — vendoring `oxigraph` plus a SHACL interpreter, or waiting for `shacl-rs` to mature — and is recorded for a later release. See [What the binary carries](#what-the-binary-carries) for the exact boundary.
- The CLI's SHACL gate does not pass pyshacl's `allow_warnings`, while `make check`'s `shacl` target and `tools/shacl_helper.py` do. Nothing in the shipped corpus is affected — all 17 gallery + canonical documents pass either way — but a document that trips only an `sh:Warning` shape would be rejected here and accepted there. No CLI flag exposes the choice yet.
- `export cypher` accepts Penman input only; Turtle import follows once `t2p` ships.
- Input is read from a file path; stdin (`-`) is not supported.

Deferred subcommands (planned, not yet shipped): `query`, `render`, `generate`, `serve`, `init`, `lint`.
