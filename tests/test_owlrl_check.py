"""OWL 2 RL consistency-gate tests (tools/owlrl_check.py).

Locks in the two non-obvious guarantees the gate provides over the project's
rdfs-inference SHACL gate:

  - A Composition (a Frame, owl:disjointWith Entity) may bear vso:hasQuality via
    the QualityBearer covering class WITHOUT being inferred into vso:Entity.
    Reverting hasQuality's domain to Entity reintroduces the clash (regression
    guard for the v1.1 ontology fix).
  - Two distinct trait-kinds on one functional trait property is a *detected*
    inconsistency. owlrl 7.1.4 collapses the kinds to owl:sameAs (prp-fp) but
    does NOT expand owl:AllDifferent into owl:differentFrom, so the gate
    hand-rolls the eq-diff1 check; this test pins that behaviour.

Skipped automatically if rdflib/owlrl are not installed.
"""

from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import rdflib
    import owlrl  # noqa: F401
    from tools.owlrl_check import clashes_for
except ImportError:
    rdflib = None
    clashes_for = None

PFX = (
    "@prefix vso: <https://vson.dev/v1/ontology#> .\n"
    "@prefix : <https://example.org/scene#> .\n"
)


@unittest.skipUnless(rdflib and clashes_for, "rdflib + owlrl required")
class OwlRlConsistencyTests(unittest.TestCase):
    def _doc(self, body: str) -> "rdflib.Graph":
        g = rdflib.Graph()
        g.parse(data=PFX + body, format="turtle")
        return g

    def test_clean_entity_is_consistent(self) -> None:
        g = self._doc(":e a vso:Entity ; vso:individuation vso:Generic .")
        self.assertEqual(clashes_for(g), [])

    def test_composition_may_bear_quality(self) -> None:
        # QualityBearer covering class: a Composition (a Frame) bearing a Quality
        # must NOT be inferred into Entity (Frame owl:disjointWith Entity).
        g = self._doc(
            ":scene a vso:Composition ; vso:hasQuality :q . :q a vso:Quality ."
        )
        self.assertEqual(clashes_for(g), [])

    def test_frame_and_entity_is_inconsistent(self) -> None:
        # The canonical disjointness clash the gate exists to catch.
        g = self._doc(":x a vso:Frame, vso:Entity .")
        self.assertTrue(clashes_for(g))

    def test_two_individuation_kinds_is_inconsistent(self) -> None:
        # individuation is functional → prp-fp collapses Generic+Named to
        # owl:sameAs; AllDifferent makes that an inconsistency the gate detects.
        g = self._doc(
            ":e a vso:Entity ; vso:individuation vso:Generic, vso:Named ."
        )
        self.assertTrue(clashes_for(g))

    def test_two_animacy_kinds_is_inconsistent(self) -> None:
        g = self._doc(":e a vso:Entity ; vso:animacy vso:Agentive, vso:Inert .")
        self.assertTrue(clashes_for(g))

    def test_two_dimensions_on_quality_is_inconsistent(self) -> None:
        # dimension is functional → prp-fp collapses Color+Weight to owl:sameAs;
        # the AllDifferent over the Dimension individuals makes that a detected
        # eq-diff1 clash, parity with the individuation/animacy/countability axes.
        g = self._doc(
            ":q a vso:Quality ; vso:dimension vso:Color, vso:Weight ; vso:value \"x\" ."
        )
        self.assertTrue(clashes_for(g))


if __name__ == "__main__":
    unittest.main()
