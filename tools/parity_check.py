#!/usr/bin/env python3
"""Golden parity gate: the Rust CLI and the Python reference transpiler must
emit graph-isomorphic Turtle for every VSON-P example.

Compares with rdflib.compare.to_isomorphic, so blank-node identity is matched
structurally rather than by label string — and covers throne_room + the whole
gallery rather than a single example. (The previous gate diffed sorted triple
strings for one file, which both missed broad coverage and forced byte-identical
blank-node labels across the two implementations.)

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.parity_check [rust_binary] [files...]
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


def main(argv) -> int:
    rust = argv[1] if len(argv) > 1 else "cli/target/release/vson"
    files = _files(argv[2:])
    bad = 0
    for f in files:
        rel = os.path.relpath(f, ROOT)
        with open(f, encoding="utf-8") as fh:
            py = vp.to_turtle(fh.read())
        proc = subprocess.run(
            [rust, "convert", "p2t", f], capture_output=True, text=True
        )
        if proc.returncode != 0:
            print(f"  RUST-ERR {rel}: {proc.stderr.strip()[:80]}")
            bad += 1
            continue
        gp = rdflib.Graph()
        gp.parse(data=py, format="turtle")
        gr = rdflib.Graph()
        gr.parse(data=proc.stdout, format="turtle")
        if to_isomorphic(gp) == to_isomorphic(gr):
            print(f"  OK {rel}  triples={len(gp)}")
        else:
            print(f"  MISMATCH {rel}  py={len(gp)} rust={len(gr)}")
            bad += 1
    if bad:
        print(f"parity: {bad} file(s) diverged.")
        return 1
    print(f"parity: {len(files)} file(s) isomorphic across Rust + Python reference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
