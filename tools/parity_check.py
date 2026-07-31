#!/usr/bin/env python3
"""Golden parity gate: the Rust CLI and the Python reference transpiler must
emit graph-isomorphic Turtle for every VSON-P example.

Compares with rdflib.compare.to_isomorphic, so blank-node identity is matched
structurally rather than by label string — and covers throne_room + the whole
gallery rather than a single example. (The previous gate diffed sorted triple
strings for one file, which both missed broad coverage and forced byte-identical
blank-node labels across the two implementations.)

With --bytes, additionally require the two emitters' Turtle to be
byte-identical per file. The studio's line-oriented Turtle walker
(web/src/lib/graph/walk.ts) assumes the exact one-triple-per-line shape the
Rust emitter produces, and the v1.3 browser worker runs this Python
reference emitter — byte equality is the invariant that keeps the host CLI
and the browser output interchangeable.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.parity_check [--bytes] [rust_binary] [files...]
With no files, checks examples/throne_room.vson + every examples/gallery/*.vson.
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys

import rdflib
from rdflib.compare import to_isomorphic

from tools.penman import vson_penman as vp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _files(argv):
    if argv:
        return argv
    return [os.path.join(ROOT, "examples/throne_room.vson")] + sorted(
        glob.glob(os.path.join(ROOT, "examples/gallery/*.vson"))
    )


def _first_divergence(py: str, rust: str) -> str:
    """Locate the first differing line so a byte mismatch is actionable."""
    py_lines = py.splitlines()
    rust_lines = rust.splitlines()
    for i, (a, b) in enumerate(zip(py_lines, rust_lines), start=1):
        if a != b:
            return f"line {i}: py={a[:60]!r} rust={b[:60]!r}"
    return f"line count: py={len(py_lines)} rust={len(rust_lines)}"


def main(argv) -> int:
    bytes_mode = "--bytes" in argv[1:]
    args = [a for a in argv[1:] if a != "--bytes"]
    rust = args[0] if args else "cli/target/release/vson"
    files = _files(args[1:])
    bad = 0
    for f in files:
        rel = os.path.relpath(f, ROOT)
        with open(f, encoding="utf-8") as fh:
            py = vp.to_turtle(fh.read())
        proc = subprocess.run([rust, "convert", "p2t", f], capture_output=True)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "replace").strip()[:80]
            print(f"  RUST-ERR {rel}: {err}")
            bad += 1
            continue
        rust_ttl = proc.stdout.decode("utf-8")
        gp = rdflib.Graph()
        gp.parse(data=py, format="turtle")
        gr = rdflib.Graph()
        gr.parse(data=rust_ttl, format="turtle")
        iso_ok = to_isomorphic(gp) == to_isomorphic(gr)
        byte_ok = (not bytes_mode) or proc.stdout == py.encode("utf-8")
        if iso_ok and byte_ok:
            print(f"  OK {rel}  triples={len(gp)}")
        else:
            if not iso_ok:
                print(f"  MISMATCH {rel}  py={len(gp)} rust={len(gr)}")
            if not byte_ok:
                print(f"  BYTE-MISMATCH {rel}  {_first_divergence(py, rust_ttl)}")
            bad += 1
    if bad:
        print(f"parity: {bad} file(s) diverged.")
        return 1
    kind = "byte-identical + isomorphic" if bytes_mode else "isomorphic"
    print(f"parity: {len(files)} file(s) {kind} across Rust + Python reference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
