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
  - A clash is reported in an order that is a function of its content. The two
    classes come out of a set of frozensets, which iterates in the order
    Python's per-process string hashing decides, so one unchanged document used
    to report (Endurant, Perdurant) in one run and (Perdurant, Endurant) in the
    next — through `tools/validate_report.py` into the `constraint` and `value`
    fields of a record docs/vson.md §5.16 promises a caller can freeze.

Skipped automatically if rdflib/owlrl are not installed.
"""

from __future__ import annotations

import unittest

try:
    import owlrl  # noqa: F401  — availability probe for the skip guard below
    import rdflib

    from tools.owlrl_check import clashes_for
except ImportError:
    rdflib = None
    clashes_for = None

PFX = (
    "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n"
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

    def test_a_clash_is_reported_in_a_stable_order(self) -> None:
        """The pair, not just the set — see the module docstring.

        Asserting sortedness rather than a literal pair is deliberate: the
        property the report needs is that the order is a function of the
        content, and `sorted` is what makes it one. A subprocess per hash seed
        would test the same thing more slowly and would still only sample.
        """
        g = self._doc(":x a vso:Frame, vso:Entity .")
        clashes = clashes_for(g)
        self.assertTrue(clashes)
        for _individual, first, second in clashes:
            self.assertLessEqual(
                str(first), str(second), msg="the reported pair is not ordered"
            )
        self.assertEqual(clashes, clashes_for(self._doc(":x a vso:Frame, vso:Entity .")))


if __name__ == "__main__":
    unittest.main()
