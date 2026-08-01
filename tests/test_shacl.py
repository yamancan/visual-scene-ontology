"""
SHACL conformance tests.

  - examples/throne_room.ttl  MUST conform.
  - tests/fixtures/bad_*.ttl  MUST NOT conform (each exercises one shape).

Skipped automatically if rdflib/pyshacl are not installed.
"""

from __future__ import annotations

import unittest

try:
    import pyshacl
    import rdflib

    from tools.shacl_helper import validate_path
except ImportError:
    rdflib = None
    pyshacl = None
    validate_path = None


@unittest.skipUnless(rdflib and pyshacl, "rdflib + pyshacl required")
class ConformanceTests(unittest.TestCase):
    def test_throne_room_conforms(self) -> None:
        conforms, report = validate_path("examples/throne_room.ttl")
        self.assertTrue(conforms, msg=report)

    def test_directional_without_viewer_fails(self) -> None:
        conforms, report = validate_path("tests/fixtures/bad_no_viewer.ttl")
        self.assertFalse(conforms)
        self.assertIn("viewer", report)

    def test_frame_depicted_fails(self) -> None:
        conforms, report = validate_path("tests/fixtures/bad_frame_depicted.ttl")
        self.assertFalse(conforms)

    def test_event_without_lemma_fails(self) -> None:
        conforms, report = validate_path("tests/fixtures/bad_event_no_lemma.ttl")
        self.assertFalse(conforms)
        self.assertIn("lemma", report)

    def test_frame_bears_quality_fails(self) -> None:
        # A CameraView (a Frame, neither Entity nor Composition) bearing
        # vso:hasQuality MUST fail vss:HasQualityShape. Guards against the shape
        # regressing to the vacuous `sh:class vso:QualityBearer` form, which
        # could never fire under inference="rdfs".
        conforms, report = validate_path("tests/fixtures/bad_frame_bears_quality.ttl")
        self.assertFalse(conforms)
        self.assertIn("QualityBearer", report)


@unittest.skipUnless(rdflib and pyshacl, "rdflib + pyshacl required")
class ValueSpaceTests(unittest.TestCase):
    """The value spaces docs/vson.md §5 defines, one fixture each.

    Every fixture below conformed under the v1.2 shapes and is rejected by the
    v1.3 ones — which is what docs/vson.md §8.2 requires of a tightening: the
    documents it newly rejects were already non-conformant under a clause or a
    §5 value space, and no shipped document is among them (`make envelope-check`
    and `make spec-check` are the standing proof of the second half).

    Each assertion names a distinguishing fragment of the shape's own message,
    so a failure is attributable to the constraint under test rather than to
    some other shape that happens to fire on the same document.
    """

    def _rejects(self, fixture: str, fragment: str) -> None:
        conforms, report = validate_path(f"tests/fixtures/{fixture}")
        self.assertFalse(
            conforms, msg=f"{fixture} must not conform ({fragment})"
        )
        self.assertIn(fragment, report)

    def test_bbox2d_non_numeric_fails(self) -> None:
        # `vso:bbox2d "banana"` — conformant until v1.3.
        self._rejects("bad_bbox2d_value.ttl", "vso:bbox2d must be one normalized")

    def test_bbox2d_pixels_fail(self) -> None:
        # The units decision, made executable: normalized wins over pixels.
        self._rejects("bad_bbox2d_pixels.ttl", "vso:bbox2d must be one normalized")

    def test_geometry_grammars_fail(self) -> None:
        conforms, report = validate_path("tests/fixtures/bad_geometry_grammar.ttl")
        self.assertFalse(conforms)
        for fragment in ("vso:position3d must be", "vso:scale3d must be", "vso:rotation must be"):
            self.assertIn(fragment, report)

    def test_confidence_out_of_range_fails(self) -> None:
        # `vso:confidence "7.3"` — conformant until v1.3.
        self._rejects("bad_confidence_range.ttl", "vso:confidence must be a number in [0,1]")

    def test_visible_fraction_out_of_range_fails(self) -> None:
        self._rejects("bad_visible_fraction.ttl", "vso:visibleFraction must be a number in [0,1]")

    def test_lemma_not_snake_case_fails(self) -> None:
        self._rejects("bad_lemma_pattern.ttl", "vso:lemma must be a snake_case verb")

    def test_two_lemmas_on_a_process_fail(self) -> None:
        # C6's "exactly one", enforced on Process for the first time.
        self._rejects("bad_two_lemmas.ttl", "Process must have exactly one vso:lemma (C6)")

    def test_two_viewers_on_a_directional_fact_fail(self) -> None:
        # C5's "exactly one", enforced for the first time.
        self._rejects("bad_two_viewers.ttl", "require exactly one vso:viewer")

    def test_two_rcc_relations_on_one_fact_fail(self) -> None:
        self._rejects("bad_two_rcc.ttl", "at most one vso:rcc")

    def test_two_viewed_by_on_one_composition_fail(self) -> None:
        self._rejects("bad_two_viewed_by.ttl", "at most one vso:viewedBy")

    def test_two_classes_on_one_entity_fail(self) -> None:
        self._rejects("bad_two_class.ttl", "at most one vso:class")


if __name__ == "__main__":
    unittest.main()
