"""
The fast graph-equivalence heuristic for the VSON-X round-trip tests.

**The rule this file applies is not defined here.** It is `docs/vson.md` §4.6,
and the executable statement of it is `tools/canon.py`: two documents denote
the same scene iff, after N1 (anonymization of the reified nodes and the
attached-only frames) and N2 (the interchangeable Composition edges), their
RDFC-1.0 canonical N-Quads are byte-identical. Both normalizations are
imported from that module rather than restated, so the heuristic and the
oracle cannot drift apart: there is one rule, spelled once, and this file is
one way of deciding it.

What this file adds is speed. `graph_equivalent` runs
`rdflib.compare.isomorphic` over the normalized graphs instead of
canonicalizing them, which is what `make x-check` wants on every gallery pair.
It answers *whether* two documents agree; it produces no canonical form, so
nothing can be frozen against it and no second implementer can reproduce it.
That is the oracle's job, and `tests/test_canon.py` checks the two against
each other on every pair in the corpus — positives and a known-different pair
— so a heuristic that started answering differently would be caught by the
section it stands in for.

The case it exists for
----------------------
The Penman parser emits author-chosen variable names (`q1`, `sf1`, `cq1`) as
named IRIs in the document's default namespace. The VSON-X parser
auto-generates `_q1`, `_sf1`, … for reified Quality / Stative / Event /
Process / SpatialFact nodes, which have no author-meaningful identity, and the
emitter renders those as RDF blank nodes:

  - Penman gallery output: `:apple :hasQuality :q1 ; :q1 a Quality ; ...`
  - VSON-X gallery output: `:apple :hasQuality _:q1 ; _:q1 a Quality ; ...`

The triples are structurally identical, but `rdflib.compare.isomorphic` finds
bijections among blank nodes only, never between a blank node and an IRI, so
it reports two different graphs. N1 is what closes that gap.
"""

from __future__ import annotations

from rdflib import Graph
from rdflib.compare import isomorphic

from tools.canon import canonical_graph

__all__ = ["graph_equivalent"]


def graph_equivalent(g1: Graph, g2: Graph) -> bool:
    """The §4.6 question, answered by isomorphism instead of by bytes.

    True iff the two graphs are isomorphic after the §4.6 normalizations.
    `tools.canon.denotes_same` is the normative answer to the same question;
    this is the fast one.
    """
    return isomorphic(canonical_graph(g1), canonical_graph(g2))
