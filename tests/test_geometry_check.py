"""The geometry consistency gate — docs/vson.md §5.13.

Four things are pinned here, in rising order of how much they would cost to get
wrong:

  (a) **The decision procedures are the ones §5.13 defines.** The RCC-8 table is
      exercised as a table (every relation, both verdicts, the TPP/NTPP boundary
      cut), and two theorems §5.13 states are checked over a grid of rectangle
      pairs rather than on hand-picked examples: `rcc:DC` is never refutable,
      and the relation the two *rectangles* themselves stand in is never refuted
      when asserted.

  (b) **It refutes and does not confirm.** The single most likely way for this
      gate to become harmful is for someone to "improve" it into computing the
      rectangles' own RCC-8 relation and demanding a match. A bounding box
      contains the region and is not the region, so that gate would reject
      correct documents — `EC` between a cat and the table it sits on, with
      overlapping boxes, is the standing example, and it is in the positive
      fixture. Several tests here fail loudly if that change is ever made.

  (c) **It never guesses.** Every undecidable tag in §5.13's taxonomy is
      reachable and reached, and no input in this file produces `consistent` or
      `inconsistent` from geometry the document did not supply.

  (d) **The three-layer contract holds on the negative fixtures.** They are
      conformant VSON: SHACL green, OWL 2 RL green, C2 green, geometry red.
      That combination is the whole claim of §5.13, and if a future shape ever
      starts rejecting them, this file says so before the claim goes stale.

Run: python3 -m unittest tests.test_geometry_check

Skipped automatically if rdflib / pyshacl are not installed.
"""

from __future__ import annotations

import glob
import io
import json
import os
import re
import unittest
from contextlib import redirect_stdout
from decimal import Decimal

try:
    import pyshacl  # noqa: F401 — imported for the dependency probe below
    import rdflib

    from tools import geometry_check as gc
    from tools.c2_check import orphans_in
    from tools.owlrl_check import clashes_for
    from tools.penman import vson_penman as vp
    from tools.shacl_helper import validate_path
except ImportError:  # pragma: no cover — dependency probe for the skip guards
    pyshacl = None
    rdflib = None
    gc = None
    orphans_in = None
    clashes_for = None
    vp = None
    validate_path = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HAVE_DEPS = rdflib is not None and pyshacl is not None

CONSISTENT_FIXTURE = "tests/fixtures/geometry_consistent.ttl"
BAD_RCC_FIXTURE = "tests/fixtures/geometry_inconsistent_rcc.ttl"
BAD_DIR_FIXTURE = "tests/fixtures/geometry_inconsistent_directional.ttl"

SHAPES = "shapes/vson-shapes.ttl"
SH_PATTERN = rdflib.URIRef("http://www.w3.org/ns/shacl#pattern") if rdflib else None
VSO_NS = "https://w3id.org/vson/v1/ontology#"


def _rect(x1: str, y1: str, x2: str, y2: str) -> "gc.Rect":
    """A rectangle from its corners, so the tests read as x1,y1,x2,y2."""
    return gc.Rect(Decimal(x1), Decimal(y1), Decimal(x2), Decimal(y2))


def _graph(path: str) -> "rdflib.Graph":
    g = rdflib.Graph()
    g.parse(os.path.join(ROOT, path), format="turtle")
    return g


def _findings(path: str):
    return gc.findings_for(_graph(path))


def _verdicts(findings, verdict):
    return [f for f in findings if f.verdict == verdict]


def _from_turtle(body: str) -> "rdflib.Graph":
    """A tiny in-memory document, for the cases no fixture should exist for."""
    g = rdflib.Graph()
    g.parse(
        data="@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n"
        "@prefix rcc: <https://w3id.org/vson/v1/rcc8#> .\n"
        "@prefix :    <https://example.org/t#> .\n" + body,
        format="turtle",
    )
    return g


# A grid of rectangles covering every qualitative arrangement of two axis-
# aligned boxes: disjoint, edge-sharing, overlapping, nested with and without a
# shared edge, and identical.
GRID = [
    ("0.0", "0.0", "0.4", "0.4"),
    ("0.4", "0.0", "0.8", "0.4"),
    ("0.5", "0.5", "0.9", "0.9"),
    ("0.0", "0.0", "1.0", "1.0"),
    ("0.1", "0.1", "0.5", "0.5"),
    ("0.0", "0.0", "0.5", "0.5"),
    ("0.2", "0.2", "0.3", "0.3"),
    ("0.2", "0.0", "0.6", "0.6"),
]


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class RectangleAlgebraTests(unittest.TestCase):
    """The exact 2D decision procedures, as procedures."""

    def test_rect_rcc8_is_jointly_exhaustive_on_the_grid(self) -> None:
        for a in GRID:
            for b in GRID:
                with self.subTest(a=a, b=b):
                    self.assertIn(gc.rect_rcc8(_rect(*a), _rect(*b)), gc.RCC8)

    def test_rect_rcc8_names_the_eight_arrangements(self) -> None:
        unit = _rect("0.0", "0.0", "1.0", "1.0")
        cases = {
            "DC": _rect("2.0", "2.0", "3.0", "3.0"),
            "EC": _rect("1.0", "0.0", "2.0", "1.0"),
            "PO": _rect("0.5", "0.5", "1.5", "1.5"),
            "EQ": unit,
            "NTPPi": _rect("0.2", "0.2", "0.8", "0.8"),
            "TPPi": _rect("0.0", "0.2", "0.8", "0.8"),
        }
        for expected, other in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(gc.rect_rcc8(unit, other), expected)
        # The inverses, read from the other side.
        self.assertEqual(gc.rect_rcc8(_rect("0.2", "0.2", "0.8", "0.8"), unit), "NTPP")
        self.assertEqual(gc.rect_rcc8(_rect("0.0", "0.2", "0.8", "0.8"), unit), "TPP")

    def test_dc_is_never_refutable(self) -> None:
        # §5.13: two disjoint regions may have any pair of bounding boxes at all
        # — two interleaved combs share one. Nothing the rectangles say refutes
        # rcc:DC, so a gate that ever reports one has stopped being sound.
        for a in GRID:
            for b in GRID:
                with self.subTest(a=a, b=b):
                    self.assertEqual(gc.rcc_refutation("DC", _rect(*a), _rect(*b)), "")

    def test_the_rectangles_own_relation_is_never_refuted(self) -> None:
        # The soundness direction that matters in practice: whatever relation
        # the two boxes themselves stand in is a relation the boxes cannot
        # refute. A refutation table that failed this would reject documents
        # whose geometry agrees with them exactly.
        for a in GRID:
            for b in GRID:
                ra, rb = _rect(*a), _rect(*b)
                own = gc.rect_rcc8(ra, rb)
                with self.subTest(a=a, b=b, own=own):
                    self.assertEqual(gc.rcc_refutation(own, ra, rb), "")

    def test_boxes_in_po_do_not_refute_ec_or_tpp(self) -> None:
        # The (b) property, stated as its two most tempting counter-examples. A
        # cat sitting on a table is rcc:EC with an overlapping box; a handle is
        # rcc:TPP of a mug with a box that can sit anywhere inside the mug's.
        cat, table = _rect("0.05", "0.45", "0.30", "0.75"), _rect("0.0", "0.6", "1.0", "1.0")
        self.assertEqual(gc.rect_rcc8(cat, table), "PO")
        self.assertEqual(gc.rcc_refutation("EC", cat, table), "")
        self.assertEqual(gc.rcc_refutation("DC", cat, table), "")

    def test_tpp_ntpp_boundary_cut(self) -> None:
        outer = _rect("0.0", "0.0", "1.0", "1.0")
        flush = _rect("0.0", "0.1", "0.5", "0.5")  # shares the left edge
        strict = _rect("0.1", "0.1", "0.5", "0.5")
        self.assertEqual(gc.rcc_refutation("TPP", flush, outer), "")
        self.assertNotEqual(gc.rcc_refutation("NTPP", flush, outer), "")
        self.assertEqual(gc.rcc_refutation("NTPP", strict, outer), "")
        self.assertEqual(gc.rcc_refutation("TPP", strict, outer), "")

    def test_inverses_swap_the_roles(self) -> None:
        outer = _rect("0.0", "0.0", "1.0", "1.0")
        inner = _rect("0.2", "0.2", "0.4", "0.4")
        self.assertEqual(gc.rcc_refutation("NTPPi", outer, inner), "")
        self.assertNotEqual(gc.rcc_refutation("NTPPi", inner, outer), "")
        self.assertEqual(gc.rcc_refutation("TPPi", outer, inner), "")

    def test_eq_needs_identical_rectangles(self) -> None:
        a = _rect("0.1", "0.1", "0.2", "0.2")
        self.assertEqual(gc.rcc_refutation("EQ", a, a), "")
        self.assertNotEqual(gc.rcc_refutation("EQ", a, _rect("0.1", "0.1", "0.2", "0.3")), "")

    def test_ec_and_po_need_the_boxes_to_meet(self) -> None:
        a, far = _rect("0.0", "0.0", "0.1", "0.1"), _rect("0.5", "0.5", "0.6", "0.6")
        touching = _rect("0.1", "0.0", "0.2", "0.1")
        for name in ("EC", "PO"):
            with self.subTest(name=name):
                self.assertNotEqual(gc.rcc_refutation(name, a, far), "")
                self.assertEqual(gc.rcc_refutation(name, a, touching), "")


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class DirectionalRuleTests(unittest.TestCase):
    """§5.13's centroid rule — a stipulation, applied exactly."""

    def test_the_four_values_read_the_image_frame(self) -> None:
        left, right = _rect("0.0", "0.4", "0.2", "0.6"), _rect("0.8", "0.4", "1.0", "0.6")
        top, bottom = _rect("0.4", "0.0", "0.6", "0.2"), _rect("0.4", "0.8", "0.6", "1.0")
        self.assertEqual(gc.directional_refutation("left_of", left, right), "")
        self.assertNotEqual(gc.directional_refutation("left_of", right, left), "")
        self.assertEqual(gc.directional_refutation("right_of", right, left), "")
        # y grows downward in image coordinates, so `above` is the smaller y.
        self.assertEqual(gc.directional_refutation("above", top, bottom), "")
        self.assertNotEqual(gc.directional_refutation("above", bottom, top), "")
        self.assertEqual(gc.directional_refutation("below", bottom, top), "")

    def test_equal_centroids_refute_every_direction(self) -> None:
        # The rule is a strict ordering: two entities whose centroids coincide
        # on the axis in question stand in no direction along it.
        a = _rect("0.0", "0.0", "1.0", "1.0")
        b = _rect("0.25", "0.25", "0.75", "0.75")
        for name in gc.DIRECTIONAL_RULE:
            with self.subTest(name=name):
                self.assertNotEqual(gc.directional_refutation(name, a, b), "")

    def test_comparisons_are_exact_beyond_float_precision(self) -> None:
        # No binary floats and no rounding step. These two rectangles differ in
        # the 30th decimal place — past IEEE-754 double precision *and* past
        # `decimal`'s 28-digit default context, which is why the module widens
        # the context for its two additions. §5.4 bounds a component's value,
        # not its length, so a document may state this and the gate must not
        # decide it by the rounding.
        nudge = "0" * 29 + "1"
        a = _rect("0.1", "0.1", "0.2", "0.2")
        b = _rect(f"0.1{nudge}", "0.1", f"0.2{nudge}", "0.2")
        self.assertEqual(gc.directional_refutation("left_of", a, b), "")
        self.assertNotEqual(gc.directional_refutation("left_of", b, a), "")
        self.assertNotEqual(a.cx2, b.cx2)

    def test_the_corner_is_computed_exactly_from_x_plus_w(self) -> None:
        long_w = "0.1" + "0" * 27 + "1"
        rect = gc.parse_bbox2d(f"0.1,0.1,{long_w},0.1")
        self.assertEqual(rect.x2, Decimal("0.2" + "0" * 27 + "1"))

    def test_depth_is_not_in_the_table(self) -> None:
        # in_front_of / behind are §5.12 values with no image-plane reading.
        self.assertNotIn("in_front_of", gc.DIRECTIONAL_RULE)
        self.assertNotIn("behind", gc.DIRECTIONAL_RULE)


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class ValueSpaceTests(unittest.TestCase):
    """The gate's bbox2d reader accepts exactly what `vss:GeometryShape` does."""

    def test_bbox2d_grammar_matches_the_shape(self) -> None:
        # The module's own regex is written component-wise rather than copied,
        # so this is the gate that keeps the two from drifting: a document the
        # checker calls malformed must be a document SHACL rejects, and vice
        # versa. docs/vson.md §5.4 quotes the same pattern a third time and
        # tests/test_documented_constraints.py pins that copy.
        shapes = _graph(SHAPES)
        patterns = [
            str(o)
            for s, _, o in shapes.triples((None, SH_PATTERN, None))
            if (s, rdflib.URIRef("http://www.w3.org/ns/shacl#path"),
                rdflib.URIRef(VSO_NS + "bbox2d")) in shapes
        ]
        self.assertEqual(len(patterns), 1, msg=f"expected one bbox2d pattern, got {patterns}")
        shape_re = re.compile(patterns[0])
        corpus = [
            "0.42,0.55,0.12,0.14", "0,0,1,1", "1.0,1.0,1.0,1.0", "0.0,0.0,0.0,0.0",
            "0.5,0.5,0.5,0.5", "banana", "12,40,200,300", "0.1,0.2,0.3",
            "0.1,0.2,0.3,0.4,0.5", "1.5,0,0,0", "-0.1,0,0,0", "0.1, 0.2,0.3,0.4",
            "2,0,0,0", "01.0,0,0,0", ".5,0,0,0",
        ]
        for value in corpus:
            with self.subTest(value=value):
                self.assertEqual(
                    bool(gc.BBOX2D_RE.match(value)),
                    bool(shape_re.match(value)),
                    msg=f"the gate and vss:GeometryShape disagree about {value!r}",
                )

    def test_parse_bbox2d_reads_xywh_not_corners(self) -> None:
        self.assertEqual(gc.parse_bbox2d("0.1,0.2,0.3,0.4"), _rect("0.1", "0.2", "0.4", "0.6"))
        self.assertIsNone(gc.parse_bbox2d("banana"))


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class UndecidableTaxonomyTests(unittest.TestCase):
    """Every reason §5.13 lists is reachable, and reached instead of guessed."""

    def _only(self, body: str) -> "gc.Finding":
        findings = gc.findings_for(_from_turtle(body))
        self.assertEqual(len(findings), 1, msg=f"expected one finding, got {findings}")
        return findings[0]

    def test_no_geometry(self) -> None:
        f = self._only(
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:rcc rcc:NTPP ."
        )
        self.assertEqual(f.verdict, gc.UNDECIDABLE)
        self.assertEqual(f.tag, gc.NO_GEOMETRY)

    def test_one_endpoint_without_geometry(self) -> None:
        f = self._only(
            ':a vso:bbox2d "0.1,0.1,0.2,0.2" .\n'
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:rcc rcc:NTPP ."
        )
        self.assertEqual(f.tag, gc.NO_GEOMETRY)
        self.assertIn("ground", f.detail)

    def test_malformed_geometry(self) -> None:
        f = self._only(
            ':a vso:bbox2d "banana" . :b vso:bbox2d "0.1,0.1,0.2,0.2" .\n'
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:rcc rcc:NTPP ."
        )
        self.assertEqual(f.tag, gc.MALFORMED)

    def test_ambiguous_geometry(self) -> None:
        f = self._only(
            ':a vso:bbox2d "0.1,0.1,0.2,0.2" , "0.3,0.3,0.2,0.2" .\n'
            ':b vso:bbox2d "0.0,0.0,1.0,1.0" .\n'
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:rcc rcc:NTPP ."
        )
        self.assertEqual(f.tag, gc.AMBIGUOUS)

    def test_ambiguous_endpoints(self) -> None:
        f = self._only(
            ':a vso:bbox2d "0.1,0.1,0.2,0.2" . :b vso:bbox2d "0.0,0.0,1.0,1.0" .\n'
            ":sf a vso:SpatialFact ; vso:figure :a , :b ; vso:ground :b ; vso:rcc rcc:NTPP ."
        )
        self.assertEqual(f.tag, gc.AMBIGUOUS_ENDPOINTS)

    def test_degenerate_geometry(self) -> None:
        f = self._only(
            ':a vso:bbox2d "0.1,0.1,0.0,0.2" . :b vso:bbox2d "0.0,0.0,1.0,1.0" .\n'
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:rcc rcc:NTPP ."
        )
        self.assertEqual(f.tag, gc.DEGENERATE)

    def test_directional_without_a_shared_image_frame(self) -> None:
        # Two cameras are two construals of "left". C5 anchors the fact; the
        # rectangles are normalized against the image of the composition's
        # vso:viewedBy camera. When those differ, nothing is decided.
        f = self._only(
            ':a vso:bbox2d "0.8,0.4,0.1,0.1" . :b vso:bbox2d "0.1,0.4,0.1,0.1" .\n'
            ":cam a vso:CameraView . :other a vso:CameraView .\n"
            ":scene a vso:Composition ; vso:viewedBy :cam .\n"
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:viewer :other ;"
            " vso:directional vso:left_of ."
        )
        self.assertEqual(f.tag, gc.NO_IMAGE_FRAME)

    def test_relation_out_of_scope(self) -> None:
        for slot, value in (
            ("vso:proximal", "vso:near"),
            ("vso:directional", "vso:behind"),
        ):
            with self.subTest(slot=slot):
                f = self._only(
                    ':a vso:bbox2d "0.1,0.1,0.2,0.2" . :b vso:bbox2d "0.0,0.0,1.0,1.0" .\n'
                    ":cam a vso:CameraView .\n"
                    ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; "
                    f"vso:viewer :cam ; {slot} {value} ."
                )
                self.assertEqual(f.verdict, gc.UNDECIDABLE)
                self.assertEqual(f.tag, gc.OUT_OF_SCOPE)

    def test_unrecognized_value(self) -> None:
        # SHACL rejects these (C8, §5.12). The gate reports them and decides
        # nothing from them, rather than falling through to a default.
        f = self._only(
            ':a vso:bbox2d "0.1,0.1,0.2,0.2" . :b vso:bbox2d "0.0,0.0,1.0,1.0" .\n'
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:rcc rcc:Banana ."
        )
        self.assertEqual(f.tag, gc.UNRECOGNIZED)

    def test_visible_fraction_is_always_out_of_scope(self) -> None:
        # Not an oversight: a rectangle over-approximates area, and vso:occludes
        # carries no closed-world reading, so no bound on the visible fraction
        # follows from any pair of boxes (§5.13).
        f = self._only(':a vso:visibleFraction "0.5" .')
        self.assertEqual(f.slot, "vso:visibleFraction")
        self.assertEqual(f.tag, gc.OUT_OF_SCOPE)

    def test_nothing_is_decided_without_both_rectangles(self) -> None:
        # The blanket form of the rule: across every document in this file that
        # withholds geometry, no finding is ever consistent or inconsistent.
        bodies = [
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:rcc rcc:EQ .",
            ':a vso:bbox2d "banana" .\n'
            ":sf a vso:SpatialFact ; vso:figure :a ; vso:ground :b ; vso:rcc rcc:EQ .",
        ]
        for body in bodies:
            with self.subTest(body=body):
                for f in gc.findings_for(_from_turtle(body)):
                    self.assertEqual(f.verdict, gc.UNDECIDABLE)


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class OcclusionTests(unittest.TestCase):
    def test_disjoint_boxes_refute_occlusion(self) -> None:
        findings = gc.findings_for(
            _from_turtle(
                ':a vso:bbox2d "0.0,0.0,0.1,0.1" . :b vso:bbox2d "0.5,0.5,0.1,0.1" .\n'
                ":a vso:occludes :b ."
            )
        )
        self.assertEqual([f.verdict for f in findings], [gc.INCONSISTENT])

    def test_meeting_boxes_are_all_occlusion_requires(self) -> None:
        # Deliberately the *closed* test: §5.10 does not say an occluder hides
        # positive area, so touching rectangles are not refuted.
        findings = gc.findings_for(
            _from_turtle(
                ':a vso:bbox2d "0.0,0.0,0.1,0.1" . :b vso:bbox2d "0.1,0.0,0.1,0.1" .\n'
                ":a vso:occludes :b ."
            )
        )
        self.assertEqual([f.verdict for f in findings], [gc.CONSISTENT])


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class FixtureTests(unittest.TestCase):
    """The three fixtures, and the corpus `make geometry-check` runs."""

    def test_positive_fixture_has_no_inconsistency(self) -> None:
        findings = _findings(CONSISTENT_FIXTURE)
        self.assertEqual(_verdicts(findings, gc.INCONSISTENT), [])
        decided = _verdicts(findings, gc.CONSISTENT)
        self.assertGreaterEqual(len(decided), 8, msg="the fixture must decide, not skip")

    def test_positive_fixture_keeps_the_ec_with_overlapping_boxes(self) -> None:
        # The load-bearing row. `:sf_cat_table` is rcc:EC between a cat and the
        # table it sits on, whose rectangles stand in PO. Turn the gate into a
        # match-the-relation gate and this is the assertion that fails.
        by_subject = {(f.subject, f.slot): f for f in _findings(CONSISTENT_FIXTURE)}
        fact = by_subject[("sf_cat_table", "vso:rcc")]
        self.assertEqual(fact.verdict, gc.CONSISTENT)
        cat = gc.parse_bbox2d("0.05,0.45,0.25,0.30")
        table = gc.parse_bbox2d("0.00,0.60,1.00,0.40")
        self.assertEqual(gc.rect_rcc8(cat, table), "PO")

    def test_rcc_fixture_is_inconsistent_on_exactly_one_fact(self) -> None:
        findings = _findings(BAD_RCC_FIXTURE)
        bad = _verdicts(findings, gc.INCONSISTENT)
        self.assertEqual([f.subject for f in bad], ["sf_mug_shelf"])
        self.assertIn("NTPP entails", bad[0].detail)
        # The control in the same file stays consistent.
        self.assertEqual([f.subject for f in _verdicts(findings, gc.CONSISTENT)], ["sf_pot_shelf"])

    def test_directional_fixture_is_inconsistent_on_exactly_one_fact(self) -> None:
        findings = _findings(BAD_DIR_FIXTURE)
        bad = _verdicts(findings, gc.INCONSISTENT)
        self.assertEqual([f.subject for f in bad], ["sf_sign_door"])
        self.assertIn("left_of", bad[0].detail)
        self.assertEqual([f.subject for f in _verdicts(findings, gc.CONSISTENT)], ["sf_lamp_door"])

    def test_the_shipped_corpus_is_geometry_consistent(self) -> None:
        # The acceptance half: every gallery scene and the throne room pass.
        paths = [os.path.join(ROOT, "examples/throne_room.ttl")] + sorted(
            glob.glob(os.path.join(ROOT, "examples/gallery/*.vson"))
        )
        for path in paths:
            with self.subTest(path=os.path.relpath(path, ROOT)):
                g = rdflib.Graph()
                if path.endswith(".vson"):
                    with open(path, encoding="utf-8") as fh:
                        g.parse(data=vp.to_turtle(fh.read()), format="turtle")
                else:
                    g.parse(path, format="turtle")
                self.assertEqual(_verdicts(gc.findings_for(g), gc.INCONSISTENT), [])

    def test_exit_codes(self) -> None:
        # Quiet: the gate's report is stdout, and the suite's own output is not
        # the place for it. HonestNamingTests is where that text is read.
        for fixture, code in (
            (CONSISTENT_FIXTURE, 0),
            (BAD_RCC_FIXTURE, 1),
            (BAD_DIR_FIXTURE, 1),
        ):
            with self.subTest(fixture=fixture), redirect_stdout(io.StringIO()):
                self.assertEqual(gc.main([fixture]), code)


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class ThreeLayerContractTests(unittest.TestCase):
    """SHACL green, OWL 2 RL green, C2 green, geometry red (§5.13, §2.1).

    Without this, the negative fixtures would prove nothing: a document that
    failed SHACL too would be evidence of nothing but a broken document. The
    claim is that geometry inconsistency is *invisible* to the conformance
    surface, and this is where that is measured rather than asserted.
    """

    def test_the_negative_fixtures_are_conformant_vson(self) -> None:
        for fixture in (BAD_RCC_FIXTURE, BAD_DIR_FIXTURE, CONSISTENT_FIXTURE):
            with self.subTest(fixture=fixture):
                conforms, report = validate_path(fixture)
                self.assertTrue(conforms, msg=f"{fixture} must pass SHACL:\n{report}")
                g = _graph(fixture)
                self.assertEqual(clashes_for(g), [], msg=f"{fixture} must be OWL 2 RL consistent")
                self.assertEqual(orphans_in(g), [], msg=f"{fixture} must be C2-closed")

    def test_geometry_is_the_only_gate_the_bad_fixtures_fail(self) -> None:
        for fixture in (BAD_RCC_FIXTURE, BAD_DIR_FIXTURE):
            with self.subTest(fixture=fixture):
                self.assertTrue(_verdicts(_findings(fixture), gc.INCONSISTENT))


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class ShippedEnvelopeTests(unittest.TestCase):
    """What the gate finds in the 20 baked studio envelopes.

    Measured, not assumed: the demo corpus is model output frozen at bake time,
    it passes `make envelope-check` (SHACL) today, and four of its asserted
    `rcc:TPP` facts are contradicted by the boxes asserted beside them — a
    figure whose rectangle lies partly or wholly outside the ground's cannot be
    a part of it. `lamp.json` says the grass is a tangential proper part of the
    person standing on it.

    Those envelopes stay byte-frozen and stay conformant: geometry consistency
    is not a numbered clause and §8.2 forbids making it one inside v1.x, so
    nothing here un-conforms a shipped document. What it does establish is that
    the gate is not vacuous on real extractor output — the corpus that passes
    the three conformance gates contains claims that refute themselves.

    The expected set is pinned rather than counted. If a re-bake ever changes
    it, this test is the notice, and the fix is to re-measure and re-record —
    here and in docs/vson.md §5.13 — not to relax the assertion.

    The corpus size moved once without a re-bake: a demo image was withdrawn on
    2026-08-04 (spec/CHANGELOG.md) and its envelope went with it. It stated no
    `vso:rcc` fact at all, so every number this class and §5.13 report — 13
    relations over two rectangles, 11 a match-demanding gate would reject, 4
    this one does — is what the remaining 20 still measure.
    """

    EXPECTED = {
        ("kitchen.json", "sf4"),
        ("lamp.json", "sf2"),
        ("lamp.json", "sf3"),
        ("lamp.json", "sf4"),
    }

    def _corpus(self):
        return sorted(
            p
            for p in glob.glob(
                os.path.join(ROOT, "web/static/demos/envelopes/**/*.json"), recursive=True
            )
            if os.path.basename(p) != "index.json"
        )

    def test_the_known_contradictions_are_still_the_only_ones(self) -> None:
        paths = self._corpus()
        if not paths:  # pragma: no cover — the studio corpus is committed
            self.skipTest("no baked envelopes in this checkout")
        self.assertEqual(len(paths), 20, msg="the corpus size the docstring reports")
        found = set()
        for path in paths:
            with open(path, encoding="utf-8") as fh:
                envelope = json.load(fh)
            graph = rdflib.Graph()
            graph.parse(data=envelope["vson_t"], format="turtle")
            for f in _verdicts(gc.findings_for(graph), gc.INCONSISTENT):
                found.add((os.path.basename(path), f.subject))
        self.assertEqual(
            found,
            self.EXPECTED,
            msg=(
                "the geometry gate's verdicts on the frozen studio corpus moved. "
                "Re-measure and re-record; do not relax this assertion."
            ),
        )


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class HonestNamingTests(unittest.TestCase):
    """§2.1: a tool MUST NOT present a pass as evidence about the image."""

    def test_the_summary_line_names_the_construct_and_disclaims_the_image(self) -> None:
        for fixture, code in ((CONSISTENT_FIXTURE, 0), (BAD_RCC_FIXTURE, 1)):
            with self.subTest(fixture=fixture):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    self.assertEqual(gc.main([fixture]), code)
                out = buffer.getvalue()
                self.assertIn("geometry-consistency:", out)
                self.assertIn("No image was read.", out)
                for forbidden in ("accurate", "correct", "faithful", "verified against"):
                    self.assertNotIn(forbidden, out)


if __name__ == "__main__":
    unittest.main()
