# `vson` — VSON v1.0 CLI

Single static Rust binary for the four most-used VSON operations.

## Install

```bash
cd cli
cargo build --release
# binary lands at target/release/vson
```

The release binary is ~1.8 MB stripped, no shared-library dependencies beyond `pyshacl` (used only by `validate`).

```bash
pip install pyshacl rdflib   # required for `vson validate`
```

## Subcommands

```bash
vson validate <files...>         # exit 0 conform, 1 violation, 2 usage error
vson convert p2t <file.vson>     # Penman -> Turtle on stdout
vson convert t2p <file.ttl>      # not implemented in v0.1 (use Python ref)
vson export cypher <file.vson>   # Cypher CREATE statements on stdout
vson --version
vson --help
```

`validate` accepts both `.ttl` and `.vson` files. For `.vson`, the binary transpiles to a temp `.ttl` and shells out to `pyshacl --abort`. Exit code maps directly to pyshacl's verdict.

## Cold-start example

```bash
$ git clone <repo> && cd visual-scene-ontology
$ pip install pyshacl rdflib
$ cd cli && cargo build --release && cd ..
$ cli/target/release/vson validate examples/throne_room.ttl
Validation Report
Conforms: True
OK  examples/throne_room.ttl

$ cli/target/release/vson export cypher examples/throne_room.vson > scene.cypher
$ wc -l scene.cypher
     108 scene.cypher
```

## VSON_HOME

`vson validate` needs to find `ontology/` and `shapes/` next to the data file. By default the CLI assumes the working directory is the repo root. To run from elsewhere:

```bash
vson validate --home /path/to/visual-scene-ontology /tmp/scene.ttl
# or
VSON_HOME=/path/to/visual-scene-ontology vson validate /tmp/scene.ttl
```

## Verification

```bash
cd cli && cargo test               # 19 Rust tests
make cli-check                     # build + test + graph-isomorphic check vs Python ref
```

`cli-check` asserts that the Rust transpiler produces graph-isomorphic Turtle to the Python reference on the canonical throne-room scene (134 triples).

## Source of truth

VSON-P role routing rules live in [`../tools/penman/routing-tables.json`](../tools/penman/routing-tables.json). Both this CLI and the Python reference at [`../tools/penman/vson_penman.py`](../tools/penman/vson_penman.py) consume it directly, so they cannot drift between releases.

## Known limitations (v0.1)

- `convert t2p` not implemented — needs a native Rust Turtle parser.
- `validate` shells out to `pyshacl`. A self-contained binary would require either vendoring `oxigraph` + a SHACL interpreter or waiting for `shacl-rs` to mature. Decision recorded for v0.2.
- `export cypher` accepts Penman input only; Turtle import follows once `t2p` ships.

Per the v0.1 sprint plan, deferred subcommands: `query`, `render`, `generate`, `serve`, `init`, `lint`, `diff`.
