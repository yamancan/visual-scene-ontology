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

# The VSO namespace is minted once, in cli/src/penman/routing-tables.json, and
# vson_penman resolves it from there at import time. Reading it from that module
# rather than restating the IRI here matters most for this file: a stale
# namespace would make every class test below fall through, so nothing would be
# anonymized, no composition edge would be normalized — and graph_equivalent
# would go on returning True for the cases it happens to agree on while
# silently no longer checking what it was written to check.
from tools.penman.vson_penman import VSO as VSO_IRI

VSO = rdflib.Namespace(VSO_IRI)

# Classes whose instances are typically reified anonymous nodes.
# CameraView is intentionally excluded — it's frequently the target of
# vso:viewedBy and vso:viewer references and so needs stable identity
# in the document namespace. SceneContext and VisualStyle are typically
# attached only via vso:framedBy and so their IRI naming is purely a
# Penman authoring convention; cross-syntax comparison should treat
# them as anonymous (their scene-property triples carry the semantic
# weight, not the IRI).
ANON_CANDIDATE_CLASSES: Set[URIRef] = {
    VSO.Quality,
    VSO.Stative,
    VSO.Event,
    VSO.Process,
    VSO.SpatialFact,
    VSO.Annotation,
    VSO.Negation,
    VSO.BeliefState,
    VSO.SceneContext,
    VSO.VisualStyle,
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


# Composition-edge predicates that are interchangeable for the same
# target type per v1.0 spec docs/vson.md §5.2:
#   - vso:depicts: any Entity OR (per spec, also valid for) Perdurant + SpatialFact
#   - vso:hasFact: SpatialFact (Composition only)
#   - vso:occurs:  Event / Process / Stative (Composition only)
# VSON-X parser collapses to vso:depicts for parser simplicity (spec
# §4.4); gallery scenes use a mix. Treat the three as equivalent when
# comparing graphs across syntaxes.
_INTERCHANGEABLE_COMPOSITION_EDGES = {
    VSO.depicts,
    VSO.hasFact,
    VSO.occurs,
}
_CANONICAL_COMPOSITION_EDGE = VSO.depicts


def _normalize_composition_edges(g: Graph) -> Graph:
    """Replace vso:hasFact and vso:occurs with vso:depicts so cross-syntax
    comparisons treat the three as equivalent (which they are per spec)."""
    out = Graph()
    for prefix, ns in g.namespaces():
        out.bind(prefix, ns)
    for s, p, o in g:
        np = _CANONICAL_COMPOSITION_EDGE if p in _INTERCHANGEABLE_COMPOSITION_EDGES else p
        out.add((s, np, o))
    return out


def graph_equivalent(g1: Graph, g2: Graph) -> bool:
    """Two VSON graphs are equivalent iff they're isomorphic after:
      - anonymizing the auto-anonymous reified nodes (Quality, Stative,
        Event, Process, SpatialFact, Annotation, ...) to blank nodes, and
      - canonicalizing the interchangeable Composition edges
        (vso:depicts / vso:hasFact / vso:occurs) to vso:depicts.
    """
    n1 = _normalize_composition_edges(anonymize(g1))
    n2 = _normalize_composition_edges(anonymize(g2))
    return isomorphic(n1, n2)


__all__ = ["anonymize", "graph_equivalent"]
