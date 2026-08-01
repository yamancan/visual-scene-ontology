# `vson` — VSON v1.1 CLI

Single static Rust binary for the most-used VSON operations.

## Install

```bash
cd cli
cargo build --release
# binary lands at target/release/vson
```

The release binary is ~1.8 MB stripped and links nothing beyond libc. `validate` and the three Python-backed subcommands are the only parts that need an external toolchain: they spawn `pyshacl` and `python3`.

```bash
pip install pyshacl rdflib owlrl   # required for `vson validate` (or: make deps)
```

## Subcommands

```bash
vson validate <files...>         # exit 0 pass, 1 gate failure, 2 could not run
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

`convert x2t`, `export caption`, and `export fol` shell out to the Python references (`tools/vson_x/`, `tools/render/`), so they require `python3` on `PATH`. No native Rust VSON-X parser or caption/FOL renderer ships: the Python modules are the single source of truth for the fixtures CI checks, and the Rust side is one shared bridge (`src/commands/python_bridge.rs`) that locates a checkout and runs `python3 -m <module>` from it.

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

## VSON_HOME

Two families of subcommand need to find a VSON checkout — the repo root, not
the data file's directory:

- `validate` reads `ontology/vso.ttl`, `ontology/rcc8.ttl`, `ontology/allen.ttl`, `shapes/vson-shapes.ttl`, `tools/owlrl_check.py` and `tools/c2_check.py` from it;
- `convert x2t`, `export caption` and `export fol` run their Python module from it (`tools/vson_x/vson_x.py`, `tools/render/caption.py`, `tools/render/fol.py` respectively) — `python3 -m` puts the child's working directory on `sys.path`, so the root *is* the import path.

They resolve it differently, because only `validate` has a flag:

| Step | `validate` | `convert x2t`, `export caption`, `export fol` |
| --- | --- | --- |
| 1 | `--home <dir>` | — (no flag) |
| 2 | `$VSON_HOME` | `$VSON_HOME`, if it holds the module |
| 3 | — (no walk-up) | the input file's directory, then each parent, up to `/` |
| 4 | the working directory | the working directory, if it holds the module |

`validate` takes the first of its steps that is set and then reports whichever
file is missing under it. The three Python-backed commands take the first step
that actually holds the module they are about to run, so passing a stale
`VSON_HOME` is not fatal as long as the input sits inside a checkout. Their
resolution lives in exactly one place — [`src/commands/python_bridge.rs`](src/commands/python_bridge.rs) —
so all three fail identically, naming the module file they looked for.

```bash
vson validate --home /path/to/visual-scene-ontology /tmp/scene.ttl
# or
VSON_HOME=/path/to/visual-scene-ontology vson validate /tmp/scene.ttl
VSON_HOME=/path/to/visual-scene-ontology vson export fol /tmp/scene.vson
```

## Verification

```bash
cd cli && cargo test               # 43 tests: 25 unit, 18 integration
make cli-check                     # fmt + clippy + build + test + graph-isomorphic check vs Python ref
```

The 18 integration tests split three ways: 9 golden-fixture tests
(`tests/golden_throne_room.rs`), 3 negative SHACL fixtures
(`tests/golden_validate.rs`), and 6 error-contract tests
(`tests/error_contract.rs`) pinning the exit-2 "never reached a verdict" half
of the interface. Only the first two groups need `python3`/`pyshacl`; the
error-contract tests fail in Rust before anything is spawned and pass on a
machine with no Python at all.

`cli-check` asserts that the Rust transpiler produces graph-isomorphic Turtle to the Python reference on the canonical throne-room scene (134 triples).

## Source of truth

VSON-P role routing rules live in [`src/penman/routing-tables.json`](src/penman/routing-tables.json), inside this crate. `src/penman/routing.rs` embeds that file with `include_str!` at compile time; the Python reference at [`../tools/penman/vson_penman.py`](../tools/penman/vson_penman.py) reads the same file out of the checkout at import time. One file, two consumers, so they cannot drift — `make cli-check` is what proves it, comparing both emitters' graphs with `rdflib.to_isomorphic`.

The table sits in the crate rather than next to the Python reference because `include_str!` may not reach outside the crate root. A path that escapes it with `../../../` compiles fine inside a checkout but fails the isolated verify build that `cargo package` runs, which would make the crate impossible to publish or `cargo install`. `cd cli && cargo package` is the standing check; the crate is self-contained today, though it is not published to crates.io yet.

## Known limitations

- `convert t2p` not implemented — needs a native Rust Turtle parser.
- There is no `--partial` flag, in this CLI or in the Python reference: no argument parser defines it and no code branches on it. The relaxed profile it would select does ship, as [`../shapes/vson-shapes-relaxed.ttl`](../shapes/vson-shapes-relaxed.ttl), and is exercised by the test suite (`tests/test_shapes_gate.py`) — but no command-line entry point selects it yet.
- `validate` shells out to `pyshacl`, `python3 -m tools.owlrl_check` and `python3 -m tools.c2_check`, so all three gates need the Python toolchain (`make deps`) even though the binary itself is static. A self-contained binary would require either vendoring `oxigraph` + a SHACL interpreter or waiting for `shacl-rs` to mature. Decision recorded for a later release.
- The CLI's SHACL gate does not pass pyshacl's `allow_warnings`, while `make check`'s `shacl` target and `tools/shacl_helper.py` do. Nothing in the shipped corpus is affected — all 17 gallery + canonical documents pass either way — but a document that trips only an `sh:Warning` shape would be rejected here and accepted there. No CLI flag exposes the choice yet.
- `export cypher` accepts Penman input only; Turtle import follows once `t2p` ships.
- Input is read from a file path; stdin (`-`) is not supported.

Deferred subcommands (planned, not yet shipped): `query`, `render`, `generate`, `serve`, `init`, `lint`, `diff`.
