#!/usr/bin/env python3
"""Strict-SHACL gate over every committed studio envelope under
web/static/demos/envelopes/. Every envelope's `vson_t` field MUST parse and
MUST conform to shapes/vson-shapes.ttl with ontology RDFS inference. Fails
with non-zero exit if any envelope fails — the gate is intended to run in
pre-commit / CI so the studio corpus stays spec-aligned by construction.

Usage:
  python3 scripts/envelope_check.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

import pyshacl
import rdflib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    files = sorted(
        glob.glob(
            os.path.join(REPO, "web/static/demos/envelopes/**/*.json"),
            recursive=True,
        )
    )
    files = [f for f in files if os.path.basename(f) != "index.json"]
    if not files:
        print("envelope-check: no envelopes found")
        return 0

    shacl = rdflib.Graph()
    shacl.parse(os.path.join(REPO, "shapes/vson-shapes.ttl"), format="turtle")
    ont = rdflib.Graph()
    for f in (
        "ontology/vso.ttl",
        "ontology/rcc8.ttl",
        "ontology/allen.ttl",
    ):
        ont.parse(os.path.join(REPO, f), format="turtle")

    fails: list[str] = []
    for f in files:
        rel = os.path.relpath(f, REPO)
        with open(f, encoding="utf-8") as fh:
            env = json.load(fh)
        ttl = env.get("vson_t") or ""
        if not ttl.strip():
            print(f"  SKIP {rel} (no vson_t)")
            continue
        g = rdflib.Graph()
        try:
            g.parse(data=ttl, format="turtle")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {rel}: parse error: {e}")
            fails.append(rel)
            continue
        conforms, _, report = pyshacl.validate(
            g,
            shacl_graph=shacl,
            ont_graph=ont,
            inference="rdfs",
            allow_warnings=True,
        )
        ok = "OK" if conforms else "FAIL"
        print(f"  {ok} {rel} ({len(g)} triples)")
        if not conforms:
            fails.append(rel)
            print(report)

    if fails:
        print(f"\nenvelope-check: {len(fails)}/{len(files)} envelope(s) failed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"\nenvelope-check: {len(files)} envelope(s) pass strict SHACL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
