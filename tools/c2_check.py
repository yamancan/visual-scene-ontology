#!/usr/bin/env python3
"""C2 vocabulary-closure gate — no orphan VSO terms.

Clause C2 (docs/vson.md §2): every IRI a document asserts under the VSON
namespaces resolves to a class, property or individual declared in
`ontology/vso.ttl`, `ontology/rcc8.ttl` or `ontology/allen.ttl`.

Why this is a gate of its own rather than a SHACL shape. C2 is a statement about
the *ontology*, not about the document's graph: deciding it needs the ontology's
declared subjects on hand, and a shapes file that assumed they were in the data
graph would be relying on an inoculation the SHACL spec does not require and a
second engine would not supply. It is also not an OWL entailment — an undeclared
IRI is perfectly consistent, it is merely not VSON's. So the closure is computed
here, directly, the same way `tools/owlrl_check.py` hand-rolls the OWL 2 RL rules
whose heads a closure cannot hold.

Adding this check tightens what `vson validate` rejects, which docs/vson.md §8.2
permits only for documents an existing numbered clause already declared
non-conformant. C2 is that clause, verbatim, so every document this gate newly
rejects was already non-conformant when it was written. Measured before landing:
zero orphan terms across `examples/`, the 16-scene gallery, `examples/gallery-x`
and all 20 baked envelopes.

What counts as "declared" is what the ontology files state about a term — any
triple with the term as subject. That is deliberately the weakest possible
reading: `vso:above rdf:type vso:Direction` declares `vso:above`, and so would a
bare `rdfs:label`. C2 asks whether a name is part of the vocabulary, not whether
its axiomatization is complete.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.c2_check [files...]
With no args, checks examples/throne_room.ttl + every examples/gallery/*.vson.

Exit 0 — every document is C2-closed. Exit 1 — an orphan term was found.
"""

from __future__ import annotations

import glob
import os
import sys

import rdflib

from tools import resource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ONTOLOGY_FILES = ("ontology/vso.ttl", "ontology/rcc8.ttl", "ontology/allen.ttl")

# The three namespaces C2 closes. `.../v1/shapes#` is deliberately absent: the
# shapes graph is a validator artifact, not vocabulary a document asserts, and
# no ontology file declares its terms.
VSON_NAMESPACES = (
    "https://w3id.org/vson/v1/ontology#",
    "https://w3id.org/vson/v1/rcc8#",
    "https://w3id.org/vson/v1/allen#",
)

_DECLARED: frozenset | None = None


def declared_terms() -> frozenset:
    """Every VSON-namespace IRI the three ontology files say anything about."""
    global _DECLARED
    if _DECLARED is None:
        g = rdflib.Graph()
        for f in ONTOLOGY_FILES:
            g.parse(resource(f), format="turtle")
        _DECLARED = frozenset(
            str(s)
            for s in g.subjects()
            if isinstance(s, rdflib.URIRef) and str(s).startswith(VSON_NAMESPACES)
        )
    return _DECLARED


def orphans_in(doc: rdflib.Graph) -> list:
    """Sorted VSON-namespace IRIs the document asserts and no ontology declares.

    Every triple position is swept, not just predicates: `vso:dimension
    vso:Ambience` puts an undeclared term in the object slot, and docs/vson.md
    §5.5.1 names exactly that case as the C2 failure a closed registry produces.
    """
    known = declared_terms()
    used = set()
    for triple in doc:
        for term in triple:
            if isinstance(term, rdflib.URIRef) and str(term).startswith(
                VSON_NAMESPACES
            ):
                used.add(str(term))
    return sorted(t for t in used if t not in known)


def _load(path: str) -> rdflib.Graph:
    g = rdflib.Graph()
    if path.endswith(".vson"):
        # Imported lazily: Turtle-only runs should not pay for the transpiler.
        from tools.penman import vson_penman as vp

        with open(path, encoding="utf-8") as fh:
            g.parse(data=vp.to_turtle(fh.read()), format="turtle")
    else:
        g.parse(path, format="turtle")
    return g


def main(argv) -> int:
    files = argv[1:]
    if not files:
        files = [os.path.join(ROOT, "examples/throne_room.ttl")] + sorted(
            glob.glob(os.path.join(ROOT, "examples/gallery/*.vson"))
        )
    bad = False
    for f in files:
        rel = os.path.relpath(f, ROOT)
        found = orphans_in(_load(f))
        if found:
            bad = True
            print(f"  ORPHAN {rel}")
            for term in found:
                print(f"      <{term}> is asserted but declared in no ontology file")
        else:
            print(f"  OK {rel}")
    if bad:
        # The summary line is the tell cli/src/commands/validate.rs looks for to
        # tell "this document violates C2" from "this checker never ran".
        print("c2-closure: orphan VSO term detected (C2).")
        return 1
    print("c2-closure: every document uses declared VSO terms only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
