#!/usr/bin/env python3
"""OWL 2 RL consistency gate.

Materializes the OWL-RL deductive closure of (ontology + each document) and
asserts that no individual is inferred into two classes that are declared
owl:disjointWith (or jointly via owl:AllDisjointClasses).

This catches clashes the project's SHACL gate cannot see: that gate runs with
inference="rdfs", which does NOT process owl:disjointWith, so a Composition
(a Frame) inferred into vso:Entity via a property domain would slip through
SHACL while being a genuine OWL 2 RL inconsistency.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.owlrl_check [files...]
With no args, checks examples/throne_room.ttl + every examples/gallery/*.vson.
"""

from __future__ import annotations

import glob
import os
import sys

import rdflib
from rdflib import RDF, OWL
from rdflib.collection import Collection
from owlrl import DeductiveClosure, OWLRL_Semantics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ONTOLOGY_FILES = ("ontology/vso.ttl", "ontology/rcc8.ttl", "ontology/allen.ttl")


def _ontology() -> rdflib.Graph:
    g = rdflib.Graph()
    for f in ONTOLOGY_FILES:
        g.parse(os.path.join(ROOT, f), format="turtle")
    return g


_ONTOLOGY_CLOSED: rdflib.Graph | None = None


def _ontology_closed() -> rdflib.Graph:
    """The ontology with its OWL-RL closure materialized once, then cached.

    OWL-RL closure is a monotone fixpoint, so expanding (closed_ontology + doc)
    reaches the same result as expanding (ontology + doc). Caching lets the
    ontology's own entailments (subclass/subproperty/disjointness scaffolding) be
    computed a single time instead of re-parsing three TTL files and re-running
    the full closure once per checked document.
    """
    global _ONTOLOGY_CLOSED
    if _ONTOLOGY_CLOSED is None:
        g = _ontology()
        DeductiveClosure(OWLRL_Semantics).expand(g)
        _ONTOLOGY_CLOSED = g
    return _ONTOLOGY_CLOSED


def _disjoint_pairs(g: rdflib.Graph):
    """All unordered class pairs declared disjoint, via owl:disjointWith and
    owl:AllDisjointClasses/owl:members."""
    pairs = set()
    for a, _, b in g.triples((None, OWL.disjointWith, None)):
        pairs.add(frozenset((a, b)))
    for adc in g.subjects(RDF.type, OWL.AllDisjointClasses):
        members = None
        for lst in g.objects(adc, OWL.members):
            members = list(Collection(g, lst))
        if not members:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                pairs.add(frozenset((members[i], members[j])))
    return [tuple(p) for p in pairs if len(p) == 2]


def _distinct_sets(g: rdflib.Graph):
    """Groups of individuals asserted pairwise-distinct: owl:AllDifferent
    (owl:distinctMembers or owl:members) plus explicit owl:differentFrom pairs.

    owlrl 7.1.4 does NOT expand owl:AllDifferent into owl:differentFrom, so the
    OWL 2 RL eq-diff1 contradiction (x sameAs y while x differentFrom y) is never
    raised by the closure. We collect the distinctness assertions here and check
    them against the materialized owl:sameAs edges in clashes_for() ourselves —
    otherwise two trait-kinds on one functional trait property (which prp-fp
    collapses to owl:sameAs) would slip through the OWL gate."""
    sets = []
    for ad in g.subjects(RDF.type, OWL.AllDifferent):
        members = None
        for lst in g.objects(ad, OWL.distinctMembers):
            members = list(Collection(g, lst))
        if members is None:
            for lst in g.objects(ad, OWL.members):
                members = list(Collection(g, lst))
        if members:
            sets.append(members)
    for a, _, b in g.triples((None, OWL.differentFrom, None)):
        sets.append([a, b])
    return sets


def clashes_for(doc: rdflib.Graph):
    """Return a list of (individual, classA, classB) disjointness violations."""
    g = _ontology_closed() + doc
    DeductiveClosure(OWLRL_Semantics).expand(g)
    found = []
    for a, b in _disjoint_pairs(g):
        common = set(g.subjects(RDF.type, a)) & set(g.subjects(RDF.type, b))
        for x in common:
            found.append((x, a, b))
    # owl:Nothing membership is an explicit inconsistency marker.
    for x in g.subjects(RDF.type, OWL.Nothing):
        found.append((x, OWL.Nothing, OWL.Nothing))
    # Distinctness violations (eq-diff1, hand-rolled — see _distinct_sets): any
    # two members of a distinct set inferred owl:sameAs is an inconsistency.
    for members in _distinct_sets(g):
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                m1, m2 = members[i], members[j]
                if m1 != m2 and (
                    (m1, OWL.sameAs, m2) in g or (m2, OWL.sameAs, m1) in g
                ):
                    found.append((m1, OWL.sameAs, m2))
    return found


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
        found = clashes_for(_load(f))
        if found:
            bad = True
            print(f"  CLASH {rel}")
            for x, a, b in found:
                if a == OWL.sameAs:
                    print(
                        f"      <{x}> and <{b}> are asserted distinct yet inferred owl:sameAs"
                    )
                else:
                    print(f"      <{x}> is inferred into both <{a}> and <{b}>")
        else:
            print(f"  OK {rel}")
    if bad:
        print("owl-consistency: OWL 2 RL disjointness clash detected.")
        return 1
    print("owl-consistency: all documents are OWL 2 RL consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
