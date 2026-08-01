"""Smatch graph agreement — docs/vson.md §5.15.

A metric is only worth the properties it can be shown to have. Five are pinned
here, and the file is organized around them:

  (a) **Identity.** A document scores 1.0 against itself, in every layer. That
      is the floor: a metric that cannot recognize a document as itself measures
      nothing. It is checked on the 148-triple canonical scene, which populates
      all six layers, and across the gallery.

  (b) **The known-delta pair, by hand.** `tests/fixtures/diff/run_a.ttl` and
      `run_b.ttl` differ in four places, one per layer the report separates, and
      `test_known_delta_*` pins every count in the table. The expected numbers
      are *derived* in the docstring of `KnownDelta`, triple by triple — a
      pinned number nobody can re-derive only records what the code did on the
      day it was written.

  (c) **Symmetry.** F1 is invariant under swapping the arguments, and precision
      and recall exchange places. `2m / (|A| + |B|)` makes that arithmetic, and
      the test makes it a fact about the shipped implementation.

  (d) **Determinism.** Two runs over the same inputs produce byte-identical
      JSON, and the reported score does not move with the seed on this corpus.
      Blank-node labels are minted per parse by rdflib and differ between runs,
      so this is a real property and not a tautology.

  (e) **Invariance to naming and to surface syntax.** Renaming every variable
      and changing the document base changes nothing; and each of the twelve
      VSON-X gallery scenes scores 1.0 against its Penman twin, which is the
      claim "it operates on the materialized graph, so any syntax works" made
      executable. The converse is pinned too: a *leaf* IRI is a constant, so two
      runs that write different class names must not be credited with agreeing.

Run: python3 -m unittest tests.test_smatch

Skipped automatically if rdflib is not installed.
"""

from __future__ import annotations

import glob
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

try:
    import pyshacl  # noqa: F401 — imported for the dependency probe below
    import rdflib

    from tools.c2_check import orphans_in
    from tools.metrics import smatch
    from tools.owlrl_check import clashes_for
    from tools.shacl_helper import validate_path
except ImportError:  # pragma: no cover — dependency probe for the skip guards
    pyshacl = None
    rdflib = None
    smatch = None
    orphans_in = None
    clashes_for = None
    validate_path = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HAVE_DEPS = rdflib is not None

RUN_A = "tests/fixtures/diff/run_a.ttl"
RUN_B = "tests/fixtures/diff/run_b.ttl"
THRONE = "examples/throne_room.ttl"


def _path(rel: str) -> str:
    return os.path.join(ROOT, rel)


def _doc(rel: str):
    return smatch.load_document(_path(rel))


def _run_main(argv):
    """Run the module's entry point, capturing both streams."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = smatch.main(argv)
    return code, out.getvalue(), err.getvalue()


@unittest.skipUnless(_HAVE_DEPS, "rdflib not installed")
class Identity(unittest.TestCase):
    """(a) A document against itself."""

    def test_canonical_scene_scores_one_in_every_layer(self):
        doc = _doc(THRONE)
        report = smatch.compare(doc, _doc(THRONE))
        self.assertTrue(report.identical)
        self.assertEqual(report.f1, 1.0)
        for layer in smatch.LAYERS:
            score = report.layers[layer]
            with self.subTest(layer=layer):
                # Every layer is non-empty on this scene, so 1.0 here is a
                # statement about six populated layers and not about six
                # vacancies. If a future edit empties one, this says so.
                self.assertGreater(score.total_a, 0)
                self.assertEqual(score.f1, 1.0)

    def test_every_gallery_scene_scores_one_against_itself(self):
        for path in sorted(glob.glob(os.path.join(ROOT, "examples/gallery/*.vson"))):
            with self.subTest(scene=os.path.basename(path)):
                doc = smatch.load_document(path)
                report = smatch.compare(doc, smatch.load_document(path))
                self.assertTrue(report.identical)
                self.assertEqual(report.f1, 1.0)

    def test_two_empty_documents_agree(self):
        empty = smatch.build_document(rdflib.Graph(), "<empty>")
        report = smatch.compare(empty, empty)
        self.assertTrue(report.identical)
        self.assertEqual(report.f1, 1.0)
        # A layer with nothing on either side reports no number rather than a
        # zero: there was no agreement to reach.
        self.assertIsNone(report.layers[smatch.LAYER_SPATIAL].f1)

    def test_an_empty_document_against_a_full_one_scores_zero(self):
        empty = smatch.build_document(rdflib.Graph(), "<empty>")
        report = smatch.compare(empty, _doc(RUN_A))
        self.assertFalse(report.identical)
        self.assertEqual(report.f1, 0.0)


@unittest.skipUnless(_HAVE_DEPS, "rdflib not installed")
class KnownDelta(unittest.TestCase):
    """(b) The pinned pair, derived by hand.

    `run_a.ttl` states 23 triples and `run_b.ttl` states 26. Both describe a cat
    above a mat under one camera; B renames everything, swaps the fact's figure
    and ground, calls the mat a Textile, declares a second camera, and anchors
    the direction to it.

    Two alignments are plausible and the metric must prefer the right one.
    Writing `scene→s, cam→k, cat→c, mat→m, sf1→f`:

      frames      scene rdf:type, framedBy, viewedBy, cam rdf:type,
                  cam angle                                        5 of 5 match
      objects     depicts cat, depicts mat, cat rdf:type,
                  mat rdf:type                                     4 of 4 match
      attributes  cat's four traits all match; mat's individuation,
                  animacy and countability match and its class
                  does not                                         7 of 8 match
      spatial     hasFact and sf1 rdf:type and directional match;
                  figure (cat vs the mat) and ground (mat vs the
                  cat) do not, and viewer points at the other
                  camera                                           3 of 6 match
                                                                  ---------------
                                                                  19 of 23

    The alternative alignment `cat→m, mat→c` — the one a figure/ground swap
    invites — rescues the two spatial arguments but loses both entities' animacy
    and class, and scores 18. 19 is the maximum, and the search has to find it.

    On B's side the same 19 triples match out of 26: B carries three frame
    triples A does not (the second camera's declaration, type and angle).

      precision = 19/23 = 0.826086…
      recall    = 19/26 = 0.730769…
      F1        = 2·19/(23+26) = 38/49 = 0.775510…
    """

    MATCHED = 19
    TOTAL_A = 23
    TOTAL_B = 26

    @classmethod
    def setUpClass(cls):
        if not _HAVE_DEPS:
            raise unittest.SkipTest("rdflib not installed")
        cls.report = smatch.compare(_doc(RUN_A), _doc(RUN_B))

    def test_the_two_documents_are_the_size_the_fixtures_claim(self):
        self.assertEqual(len(self.report.doc_a), self.TOTAL_A)
        self.assertEqual(len(self.report.doc_b), self.TOTAL_B)

    def test_overall_counts_and_scores(self):
        overall = self.report.overall
        self.assertEqual(overall.matched_a, self.MATCHED)
        self.assertEqual(overall.matched_b, self.MATCHED)
        self.assertAlmostEqual(overall.precision, 19 / 23, places=12)
        self.assertAlmostEqual(overall.recall, 19 / 26, places=12)
        self.assertAlmostEqual(self.report.f1, 38 / 49, places=12)
        self.assertFalse(self.report.identical)

    def test_the_search_does_not_settle_for_the_swapped_alignment(self):
        # 18 is the score of the alignment that follows the swapped figure and
        # ground. Reaching only 18 would mean the hill climb stopped at the
        # local optimum this fixture exists to have.
        self.assertEqual(self.report.overall.matched_a, 19)

    def test_per_layer_table(self):
        expected = {
            # layer: (matched_a, matched_b, total_a, total_b)
            smatch.LAYER_OBJECTS: (4, 4, 4, 4),
            smatch.LAYER_ATTRIBUTES: (7, 7, 8, 8),
            smatch.LAYER_SPATIAL: (3, 3, 6, 6),
            smatch.SPATIAL_VIEWER_BLIND: (3, 3, 5, 5),
            smatch.LAYER_FRAMES: (5, 5, 5, 8),
            smatch.LAYER_EVENTS: (0, 0, 0, 0),
            smatch.LAYER_OTHER: (0, 0, 0, 0),
        }
        for layer, counts in expected.items():
            score = self.report.layers[layer]
            with self.subTest(layer=layer):
                self.assertEqual(
                    (score.matched_a, score.matched_b, score.total_a, score.total_b),
                    counts,
                )

    def test_the_viewer_blind_row_is_the_reason_it_exists(self):
        with_viewer = self.report.layers[smatch.LAYER_SPATIAL]
        blind = self.report.layers[smatch.SPATIAL_VIEWER_BLIND]
        # Dropping the viewer removes one triple from each side and no match, so
        # the spatial score rises from 3/6 to 3/5: the disagreement about which
        # camera anchors the direction is separated from the disagreement about
        # the relation itself.
        self.assertAlmostEqual(with_viewer.f1, 0.5, places=12)
        self.assertAlmostEqual(blind.f1, 0.6, places=12)

    def test_the_layers_partition_the_document(self):
        for doc in (self.report.doc_a, self.report.doc_b):
            with self.subTest(doc=doc.path):
                self.assertEqual(len(doc.layers), len(doc.triples))
                self.assertEqual(
                    sum(
                        1
                        for layer in doc.layers
                        if layer in smatch.LAYERS
                    ),
                    len(doc),
                )
                by_layer = {
                    layer: doc.layers.count(layer) for layer in smatch.LAYERS
                }
                self.assertEqual(sum(by_layer.values()), len(doc))


@unittest.skipUnless(_HAVE_DEPS, "rdflib not installed")
class Symmetry(unittest.TestCase):
    """(c) Swapping the arguments swaps precision and recall and nothing else."""

    def test_f1_is_symmetric_on_the_known_delta_pair(self):
        forward = smatch.compare(_doc(RUN_A), _doc(RUN_B))
        backward = smatch.compare(_doc(RUN_B), _doc(RUN_A))
        self.assertAlmostEqual(forward.f1, backward.f1, places=12)
        self.assertAlmostEqual(forward.overall.precision, backward.overall.recall, 12)
        self.assertAlmostEqual(forward.overall.recall, backward.overall.precision, 12)

    def test_f1_is_symmetric_across_the_gallery(self):
        scenes = sorted(glob.glob(os.path.join(ROOT, "examples/gallery/*.vson")))
        # Every consecutive pair: unrelated scenes, which is the case a metric
        # is most likely to get subtly asymmetric.
        for left, right in zip(scenes, scenes[1:]):
            with self.subTest(pair=(os.path.basename(left), os.path.basename(right))):
                a, b = smatch.load_document(left), smatch.load_document(right)
                self.assertAlmostEqual(
                    smatch.compare(a, b).f1, smatch.compare(b, a).f1, places=12
                )

    def test_matched_counts_agree_on_both_sides(self):
        # Matching is a bijection between the two matched subsets, so the two
        # counts are equal overall however they split across layers.
        report = smatch.compare(_doc(THRONE), _doc("examples/gallery/11_throne_room.vson"))
        self.assertEqual(report.overall.matched_a, report.overall.matched_b)


@unittest.skipUnless(_HAVE_DEPS, "rdflib not installed")
class Determinism(unittest.TestCase):
    """(d) The same inputs give the same bytes."""

    def test_two_runs_are_byte_identical(self):
        first = _run_main(["--format", "json", _path(RUN_A), _path(RUN_B)])
        second = _run_main(["--format", "json", _path(RUN_A), _path(RUN_B)])
        self.assertEqual(first, second)

    def test_two_runs_over_blank_node_heavy_input_are_byte_identical(self):
        # The canonical scene writes its Quality nodes as blank nodes, whose
        # rdflib labels are minted per parse. If any ordering decision touched a
        # label, this is where it would show.
        args = ["--format", "json", _path(THRONE), _path("examples/gallery/11_throne_room.vson")]
        self.assertEqual(_run_main(args), _run_main(args))

    def test_the_score_does_not_move_with_the_seed(self):
        a, b = _doc(RUN_A), _doc(RUN_B)
        scores = {smatch.compare(a, b, seed=seed).f1 for seed in range(6)}
        self.assertEqual(len(scores), 1, "seed changed the reported score: {}".format(scores))

    def test_the_score_does_not_move_with_the_restart_count(self):
        a = _doc(THRONE)
        b = _doc("examples/gallery/11_throne_room.vson")
        scores = {smatch.compare(a, b, restarts=n).f1 for n in (1, 2, 5, 9)}
        self.assertEqual(len(scores), 1, "restart count changed the score: {}".format(scores))

    def test_the_generator_is_the_one_the_spec_writes_down(self):
        # §5.15.4 states the restart source exactly so a reimplementation can
        # match it. These are the first four outputs of the documented LCG at
        # two seeds; changing the constants without changing the spec would
        # silently fork every published number from every future one.
        self.assertEqual(
            [smatch.Lcg(0).next_u32() for _ in range(1)], [335903614]
        )
        rng = smatch.Lcg(0)
        self.assertEqual(
            [rng.next_u32() for _ in range(4)],
            [335903614, 436792849, 2599843874, 1723210473],
        )
        rng = smatch.Lcg(2)
        self.assertEqual(
            [rng.next_u32() for _ in range(4)],
            [3299435481, 3938983765, 2969520912, 1565561008],
        )
        self.assertEqual(smatch.Lcg(7).shuffled(range(6)), [5, 0, 1, 2, 3, 4])

    def test_the_incremental_search_score_is_the_direct_match_count(self):
        # The search adds and subtracts deltas; the report counts matched
        # triples directly. They are two independent computations of one number,
        # and a drift between them would be invisible in the report alone.
        a, b = _doc(RUN_A), _doc(RUN_B)
        _mapping, score = smatch.best_alignment(a, b)
        self.assertEqual(score, smatch.compare(a, b).overall.matched_a)


@unittest.skipUnless(_HAVE_DEPS, "rdflib not installed")
class InvariantToNaming(unittest.TestCase):
    """(e) Names and surface syntax carry no weight; leaf labels do."""

    def test_renaming_every_variable_changes_nothing(self):
        with open(_path(RUN_A), encoding="utf-8") as handle:
            source = handle.read()
        renamed = (
            source.replace("scenes/run_a#", "elsewhere/2026/07/31#")
            .replace(":scene", ":x0")
            .replace(":cam", ":x1")
            .replace(":cat", ":x2")
            .replace(":mat", ":x3")
            .replace(":sf1", ":x4")
        )
        graph = rdflib.Graph()
        graph.parse(data=renamed, format="turtle")
        report = smatch.compare(_doc(RUN_A), smatch.build_document(graph, "<renamed>"))
        self.assertTrue(report.identical, smatch.render_text(report))

    def test_a_leaf_iri_is_a_constant_not_a_variable(self):
        # `:Animal` is never a subject, so it is a class designation and its
        # name is all it is. Two runs that write different designations must not
        # be credited with agreeing just because an alignment could pair them.
        with open(_path(RUN_A), encoding="utf-8") as handle:
            source = handle.read()
        graph = rdflib.Graph()
        graph.parse(data=source.replace(":Animal", ":Creature"), format="turtle")
        report = smatch.compare(_doc(RUN_A), smatch.build_document(graph, "<reclassed>"))
        self.assertFalse(report.identical)
        self.assertEqual(report.overall.matched_a, len(report.doc_a) - 1)
        self.assertEqual(report.layers[smatch.LAYER_ATTRIBUTES].matched_a, 7)

    def test_the_penman_and_vson_x_galleries_agree_exactly(self):
        pairs = 0
        for x_path in sorted(glob.glob(os.path.join(ROOT, "examples/gallery-x/*.x.vson"))):
            stem = os.path.basename(x_path)[: -len(".x.vson")]
            p_path = os.path.join(ROOT, "examples/gallery", stem + ".vson")
            if not os.path.exists(p_path):
                continue
            pairs += 1
            with self.subTest(scene=stem):
                report = smatch.compare(
                    smatch.load_document(p_path), smatch.load_document(x_path)
                )
                self.assertTrue(report.identical, smatch.render_text(report))
        self.assertGreaterEqual(pairs, 12, "the VSON-X corpus shrank")

    def test_the_three_composition_edges_are_one_edge(self):
        # §5.2 declares vso:depicts / vso:hasFact / vso:occurs interchangeable
        # for the same target, and the VSON-X parser emits only the first. A
        # metric that reported that as a disagreement would report a difference
        # the specification says does not exist.
        header = (
            "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n"
            "@prefix :    <https://example.org/t#> .\n"
        )
        with_fact = rdflib.Graph()
        with_fact.parse(
            data=header + ":s a vso:Composition ; vso:hasFact :f . "
            ":f a vso:SpatialFact .",
            format="turtle",
        )
        with_depicts = rdflib.Graph()
        with_depicts.parse(
            data=header + ":s a vso:Composition ; vso:depicts :f . "
            ":f a vso:SpatialFact .",
            format="turtle",
        )
        report = smatch.compare(
            smatch.build_document(with_fact, "<hasFact>"),
            smatch.build_document(with_depicts, "<depicts>"),
        )
        self.assertTrue(report.identical)
        # And the edge is still filed under the layer of what it points at.
        self.assertEqual(report.layers[smatch.LAYER_SPATIAL].total_a, 2)


@unittest.skipUnless(_HAVE_DEPS and pyshacl is not None, "rdflib/pyshacl not installed")
class FixturesAreConformant(unittest.TestCase):
    """The pair's header claims both sides are conformant VSON. Pinned here.

    A diff fixture that could not survive `vson validate` would be testing two
    things at once: a reader who found `run_b.ttl` failing SHACL could not tell
    whether the metric or the fixture was wrong. Both sides clear all three
    gates, and the deltas between them are the only thing this pair asserts.
    """

    def test_both_sides_clear_all_three_gates(self):
        for rel in (RUN_A, RUN_B):
            with self.subTest(fixture=rel):
                conforms, report = validate_path(rel)
                self.assertTrue(conforms, report)
                graph = rdflib.Graph()
                graph.parse(_path(rel), format="turtle")
                self.assertEqual(clashes_for(graph), [])
                self.assertEqual(orphans_in(graph), [])


@unittest.skipUnless(_HAVE_DEPS, "rdflib not installed")
class CommandLine(unittest.TestCase):
    """The interface `vson diff` is a thin wrapper over."""

    def test_identical_inputs_exit_zero(self):
        code, out, _err = _run_main([_path(RUN_A), _path(RUN_A)])
        self.assertEqual(code, 0)
        self.assertIn("F1 1.0000", out)

    def test_differing_inputs_exit_one(self):
        code, out, _err = _run_main([_path(RUN_A), _path(RUN_B)])
        self.assertEqual(code, 1)
        self.assertIn(smatch.TELL, out)

    def test_an_unreadable_input_is_exit_two_not_a_verdict(self):
        code, out, err = _run_main([_path(RUN_A), _path("tests/fixtures/diff/nope.ttl")])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("nope.ttl", err)

    def test_an_unknown_syntax_is_exit_two(self):
        code, _out, err = _run_main([_path(RUN_A), _path("README.md")])
        self.assertEqual(code, 2)
        self.assertIn("unknown syntax", err)

    def test_json_stdout_is_parseable_and_the_tell_goes_to_stderr(self):
        code, out, err = _run_main(["--format", "json", _path(RUN_A), _path(RUN_B)])
        self.assertEqual(code, 1)
        payload = json.loads(out)  # nothing else may be on stdout
        self.assertEqual(payload["metric"], "vson-smatch")
        self.assertEqual(payload["overall"]["matched_a"], 19)
        self.assertEqual(payload["seed"], smatch.DEFAULT_SEED)
        self.assertEqual(payload["restarts"], smatch.DEFAULT_RESTARTS)
        self.assertFalse(payload["identical"])
        self.assertIn(smatch.SPATIAL_VIEWER_BLIND, payload["layers"])
        self.assertIn(smatch.TELL, err)

    def test_the_report_never_calls_a_document_correct(self):
        # docs/vson.md §2.1. Agreement between two documents is not evidence
        # about the image, and the report says so on every run.
        _code, out, _err = _run_main([_path(RUN_A), _path(RUN_B)])
        self.assertIn("not evidence about the image", out)
        for forbidden in ("accurate", "correct", "verified against the image"):
            self.assertNotIn(forbidden, out)

    def test_labels_rename_the_inputs_in_the_report(self):
        _code, out, _err = _run_main(
            ["--label-a", "run-1", "--label-b", "run-2", _path(RUN_A), _path(RUN_B)]
        )
        self.assertIn("run-1", out)
        self.assertNotIn(_path(RUN_A), out)


if __name__ == "__main__":
    unittest.main()
