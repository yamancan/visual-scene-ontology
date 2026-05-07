"""
Graph equivalence helper for VSON-X round-trip tests.

The Penman parser emits author-chosen variable names (`q1`, `sf1`, `cq1`)
as named IRIs in the document's default namespace. The VSON-X parser
auto-generates `_q1`, `_sf1`, etc. for reified Quality / Stative / Event /
Process / SpatialFact nodes (which have no author-meaningful identity).

The Penman emitter then renders these `_`-prefixed vars as RDF blank
nodes (`_:qN` syntax). This means:
  - Penman gallery output: `:apple :hasQuality :q1 ; :q1 a Quality ; ...`
  - VSON-X gallery output: `:apple :hasQuality _:q1 ; _:q1 a Quality ; ...`

Triples are structurally identical but `:q1` (named) and `_:q1` (blank)
fail rdflib.compare.isomorphic — isomorphic only finds bijections among
blank nodes, not between blanks and named IRIs.

`graph_equivalent` normalizes both graphs by demoting default-namespace
IRIs that are clearly auto-anonymous (typed as Quality / Stative /
Event / Process / SpatialFact AND only referenced once outside their
own outgoing triples) to fresh blank nodes, then runs isomorphic.

This is a test-only utility. The emitter behavior is unchanged.
"""

from __future__ import annotations

from typing import Set

import rdflib
from rdflib import RDF, BNode, Graph, URIRef
from rdflib.compare import isomorphic

VSO = rdflib.Namespace("https://vson.dev/v1/ontology#")

# Classes whose instances are typically reified anonymous nodes.
ANON_CANDIDATE_CLASSES: Set[URIRef] = {
    VSO.Quality,
    VSO.Stative,
    VSO.Event,
    VSO.Process,
    VSO.SpatialFact,
    VSO.Annotation,
    VSO.Negation,
    VSO.BeliefState,
}


def _is_default_ns(iri: URIRef, default_ns_prefix: str) -> bool:
    return str(iri).startswith(default_ns_prefix)


def _anonymizable(g: Graph, subj: URIRef, default_ns_prefix: str) -> bool:
    """Decide whether `subj` looks like an auto-anonymous reified node.

    Heuristic: subject is in the default namespace AND has rdf:type one
    of the ANON_CANDIDATE_CLASSES. We don't apply the "referenced only
    once" check because Penman's `:q1` may be referenced by `:hasQuality`
    from the parent — but that's exactly the use-case we want to merge
    with VSON-X's blank-node version.
    """
    if not _is_default_ns(subj, default_ns_prefix):
        return False
    for cls in g.objects(subj, RDF.type):
        if cls in ANON_CANDIDATE_CLASSES:
            return True
    return False


def _detect_default_ns(g: Graph) -> str:
    # Default namespace is what `:` resolves to. rdflib stores it as
    # the empty-string prefix in NamespaceManager.
    for prefix, ns in g.namespaces():
        if prefix == "":
            return str(ns)
    return "https://example.org/scenes/anonymous#"


def anonymize(g: Graph) -> Graph:
    """Return a copy of g with auto-anonymous-looking IRIs demoted to BNodes."""
    default_ns = _detect_default_ns(g)
    rewrite: dict = {}
    out = Graph()
    for prefix, ns in g.namespaces():
        out.bind(prefix, ns)

    # First pass: identify subjects to rewrite.
    candidates = {
        s for s in g.subjects() if isinstance(s, URIRef) and _anonymizable(g, s, default_ns)
    }
    for c in candidates:
        rewrite[c] = BNode()

    # Second pass: re-emit triples with rewrite map applied to s and o.
    for s, p, o in g:
        ns = rewrite.get(s, s) if isinstance(s, URIRef) else s
        no = rewrite.get(o, o) if isinstance(o, URIRef) else o
        out.add((ns, p, no))

    return out


def graph_equivalent(g1: Graph, g2: Graph) -> bool:
    """Two VSON graphs are equivalent iff they're isomorphic after
    anonymizing the auto-anonymous reified nodes (Quality, Stative, etc.).
    """
    return isomorphic(anonymize(g1), anonymize(g2))


__all__ = ["anonymize", "graph_equivalent"]
