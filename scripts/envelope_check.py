#!/usr/bin/env python3
"""Strict-SHACL gate over every committed studio envelope under
web/static/demos/envelopes/. Every envelope's `vson_t` field MUST parse, MUST
mint under the VSO namespace the routing tables declare, MUST carry at least
one vso:Composition subject, and MUST conform to shapes/vson-shapes.ttl with
ontology RDFS inference. Fails with non-zero exit if any envelope fails — the
gate is intended to run in pre-commit / CI so the studio corpus stays
spec-aligned by construction.

Conformance on its own is not evidence. SHACL selects focus nodes by IRI, so
an envelope minted under a namespace the shapes do not target validates
*vacuously*: zero focus nodes selected, conforms=true, gate green, corpus
unchecked. The namespace and vso:Composition assertions here turn that silent
pass into a failure.

The expected namespace is read from cli/src/penman/routing-tables.json — the
single mint site both the Rust CLI and the Python reference emitter consume —
and never hardcoded in this file, so the gate follows the namespace wherever it
moves instead of pinning the corpus to whatever host it happens to use today.

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
ROUTING_TABLES = os.path.join(REPO, "cli", "src", "penman", "routing-tables.json")

SH_TARGET_CLASS = rdflib.URIRef("http://www.w3.org/ns/shacl#targetClass")


def vso_namespace() -> str:
    """Return the VSO namespace both emitters mint under.

    A plain json.load rather than an import of tools.penman.vson_penman: this
    gate has to keep working when the transpiler is broken or absent, and it
    must not be able to agree with a bug over there. The routing tables are
    the fact; this reads the fact.
    """
    with open(ROUTING_TABLES, encoding="utf-8") as fh:
        return json.load(fh)["namespaces"]["vso"]


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

    vso = vso_namespace()
    composition = rdflib.URIRef(vso + "Composition")
    print(f"envelope-check: routing tables mint VSO under <{vso}>")

    shacl = rdflib.Graph()
    shacl.parse(os.path.join(REPO, "shapes/vson-shapes.ttl"), format="turtle")
    if (None, SH_TARGET_CLASS, composition) not in shacl:
        print(
            f"envelope-check: shapes/vson-shapes.ttl targets no <{composition}>.\n"
            "  The shapes and the routing tables disagree on the VSO namespace, so "
            "every\n  envelope below would validate against zero focus nodes and pass "
            "vacuously."
        )
        return 1

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
        if vso not in ttl:
            print(f"  FAIL {rel}: mints no IRI under <{vso}>")
            fails.append(rel)
            continue
        g = rdflib.Graph()
        try:
            g.parse(data=ttl, format="turtle")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {rel}: parse error: {e}")
            fails.append(rel)
            continue
        if (None, rdflib.RDF.type, composition) not in g:
            print(f"  FAIL {rel}: no <{composition}> subject (shapes would select nothing)")
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
    print(f"\nenvelope-check: {len(files)} envelope(s) pass strict SHACL under <{vso}>.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
