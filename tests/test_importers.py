"""The vision-dataset importers, pinned against golden output.

Three things are checked here, and they are different in kind.

1. **The output is VSON.** Every golden document goes through the three gates
   `vson validate` runs — SHACL, OWL 2 RL, C2 vocabulary closure — and through
   the geometry check of §5.13. An importer that emits something conformant by
   accident is an importer whose next change breaks silently.
2. **The output does not move.** The emitted text and the lossiness report are
   frozen byte-for-byte, so a mapping-table edit that changes a corpus shows up
   as a diff in this repository rather than in someone's converted graph.
3. **The tables name only real terms.** Every VSO term the three mapping tables
   mention is read back out of `ontology/vso.ttl` and `ontology/rcc8.ttl`. A
   table is data, and data with a typo in it produces documents that fail C2 —
   so the typo is caught here, not at conversion time.

Regenerate the goldens with ``VSON_FREEZE_IMPORTERS=1 python3 -m unittest
tests.test_importers``. That is an authoring step: establish what moved first.
"""

import json
import os
import re
import unittest

from rdflib import Graph, Namespace

import vson
from tools import geometry_check
from tools.importers import read
from tools.importers.mapping import (
    AFFORDANCES, ANIMACY, COUNTABILITY, DIRECTIONAL_VALUES, EDGE_PREDICATES,
    INDIVIDUATION, LEMMA_RE, PROXIMAL_VALUES, RCC_VALUES, ROLES, load_table,
)
from tools.importers.model import normalize_bbox
from tools.penman import vson_penman

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "tests", "fixtures", "importers")
FREEZE = os.environ.get("VSON_FREEZE_IMPORTERS") == "1"

VSO = Namespace("https://w3id.org/vson/v1/ontology#")

#: dataset -> (input fixture, extra reader options)
CASES = {
    "gqa": ("sample_sceneGraphs.json", {}),
    "vg": ("sample_scene_graphs.json", {"image_data": "sample_image_data.json"}),
    "psg": ("sample_psg.json", {}),
}

#: The §5.4 value grammar, byte-identical to the copy in docs/vson.md and in
#: vss:GeometryShape.
BBOX_RE = re.compile(
    r"^(0|0\.\d+|1|1\.0+),(0|0\.\d+|1|1\.0+),(0|0\.\d+|1|1\.0+),"
    r"(0|0\.\d+|1|1\.0+)$"
)


def run(dataset, **overrides):
    """Convert one fixture and return ``(scenes, report dict)``."""
    source, options = CASES[dataset]
    options = dict(options)
    options.update(overrides)
    if "image_data" in options and options["image_data"]:
        options["image_data"] = os.path.join(FIXTURES, dataset,
                                             options["image_data"])
    path = os.path.join(FIXTURES, dataset, source)
    scenes, report = read(dataset, path, **options)
    payload = report.to_dict()
    # The fixture path is absolute so the test does not depend on a working
    # directory; the frozen report names it the way the repository does.
    payload["source"] = os.path.relpath(payload["source"], REPO).replace(
        os.sep, "/"
    )
    if payload["policy"].get("image_data", "(none)") != "(none)":
        payload["policy"]["image_data"] = os.path.relpath(
            payload["policy"]["image_data"], REPO
        ).replace(os.sep, "/")
    return scenes, payload


def golden_dir(dataset):
    return os.path.join(FIXTURES, dataset, "golden")


class GoldenOutput(unittest.TestCase):
    """The emitted VSON-P and the lossiness report are frozen."""

    def test_goldens(self):
        for dataset in sorted(CASES):
            with self.subTest(dataset=dataset):
                scenes, report = run(dataset)
                self.assertTrue(scenes, "%s produced no scene" % dataset)
                directory = golden_dir(dataset)
                if FREEZE:
                    os.makedirs(directory, exist_ok=True)
                for scene in scenes:
                    path = os.path.join(directory, "%s.vson" % scene.doc_id)
                    text = scene.to_vson_p()
                    if FREEZE:
                        with open(path, "w", encoding="utf-8") as handle:
                            handle.write(text)
                    with open(path, encoding="utf-8") as handle:
                        self.assertEqual(handle.read(), text, path)
                path = os.path.join(directory, "report.json")
                text = json.dumps(report, indent=2, sort_keys=True) + "\n"
                if FREEZE:
                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write(text)
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(json.load(handle), report, path)

    def test_no_golden_is_orphaned(self):
        """Every frozen .vson is one this run still produces."""
        for dataset in sorted(CASES):
            with self.subTest(dataset=dataset):
                scenes, _ = run(dataset)
                produced = {"%s.vson" % scene.doc_id for scene in scenes}
                frozen = {
                    name for name in os.listdir(golden_dir(dataset))
                    if name.endswith(".vson")
                }
                self.assertEqual(frozen, produced)


class GoldensAreVson(unittest.TestCase):
    """Every golden passes the gates a VSON document has to pass."""

    def goldens(self):
        for dataset in sorted(CASES):
            directory = golden_dir(dataset)
            for name in sorted(os.listdir(directory)):
                if name.endswith(".vson"):
                    yield dataset, os.path.join(directory, name)

    def test_three_gates(self):
        for dataset, path in self.goldens():
            with self.subTest(path=os.path.basename(path)):
                verdict = vson.validate(path)
                self.assertTrue(
                    verdict.conforms,
                    "%s failed the %s gate:\n%s"
                    % (path, verdict.gate, verdict.report),
                )

    def test_geometry_consistency(self):
        """§5.13: no imported document may contradict its own rectangles.

        Not a conformance clause — a geometry-inconsistent document is still
        VSON. It is pinned because the fixtures were written to be decidable
        and clean, so a mapping change that turns 'on' into a containment
        claim shows up here.
        """
        for dataset, path in self.goldens():
            with self.subTest(path=os.path.basename(path)):
                graph = Graph()
                with open(path, encoding="utf-8") as handle:
                    graph.parse(
                        data=vson_penman.to_turtle(handle.read()),
                        format="turtle",
                    )
                inconsistent = [
                    finding for finding in geometry_check.findings_for(graph)
                    if finding.verdict == "inconsistent"
                ]
                self.assertEqual([], inconsistent, path)

    def test_every_directional_carries_a_viewer(self):
        """C5, checked on the graph rather than trusted from the code.

        This is the clause none of the three source datasets can satisfy on
        its own — none of them has a viewer — so it is the one an importer is
        most likely to break.
        """
        for dataset, path in self.goldens():
            with self.subTest(path=os.path.basename(path)):
                graph = Graph()
                with open(path, encoding="utf-8") as handle:
                    graph.parse(
                        data=vson_penman.to_turtle(handle.read()),
                        format="turtle",
                    )
                for fact in set(graph.subjects(VSO.directional, None)):
                    viewers = list(graph.objects(fact, VSO.viewer))
                    self.assertEqual(
                        1, len(viewers),
                        "%s: %s has %d viewers" % (path, fact, len(viewers)),
                    )
                    self.assertIn(
                        VSO.CameraView, list(graph.objects(viewers[0], None)),
                    )


class Policies(unittest.TestCase):
    """The two decisions the importers make for VSON rather than for a
    dataset."""

    def test_skip_policy_emits_no_directional(self):
        for dataset in sorted(CASES):
            with self.subTest(dataset=dataset):
                scenes, report = run(dataset, directional_policy="skip")
                for scene in scenes:
                    for fact in scene.facts:
                        self.assertIsNone(fact.directional)
                self.assertEqual(
                    report["directionals"].get("viewer_inferred", 0), 0
                )

    def test_camera_policy_counts_every_inferred_viewer(self):
        """Under the default, the count of inferred viewers equals the count
        of emitted directional facts — the number is not decorative."""
        for dataset in sorted(CASES):
            with self.subTest(dataset=dataset):
                scenes, report = run(dataset)
                emitted = sum(
                    1 for scene in scenes for fact in scene.facts
                    if fact.directional
                )
                self.assertEqual(
                    emitted, report["directionals"].get("viewer_inferred", 0)
                )

    def test_skip_and_camera_agree_on_the_total(self):
        """Every source predicate is counted exactly once under either
        policy: what 'camera' emits, 'skip' drops."""
        for dataset in sorted(CASES):
            with self.subTest(dataset=dataset):
                _, camera = run(dataset)
                _, skip = run(dataset, directional_policy="skip")
                self.assertEqual(
                    camera["predicates"]["read"], skip["predicates"]["read"]
                )
                self.assertEqual(
                    camera["directionals"].get("viewer_inferred", 0),
                    skip["directionals"].get("skipped", 0),
                )

    def test_vg_without_image_data_writes_no_geometry(self):
        """VG's scene graphs carry pixels and no image size, so §5.4
        normalization is impossible without the sidecar."""
        scenes, report = run("vg", image_data=None)
        for scene in scenes:
            for entity in scene.entities:
                self.assertIsNone(entity.bbox2d)
        self.assertGreater(
            report["geometry"].get("dropped: image size unknown", 0), 0
        )


class Tables(unittest.TestCase):
    """The mapping tables are data, and every VSO term in them is real."""

    def setUp(self):
        self.ontology = Graph()
        for name in ("vso.ttl", "rcc8.ttl"):
            self.ontology.parse(
                os.path.join(REPO, "ontology", name), format="turtle"
            )
        self.tables = {name: load_table(name) for name in CASES}

    def term(self, local):
        return (VSO[local], None, None) in self.ontology

    def test_closed_value_sets_match_the_ontology(self):
        """The copies in tools/importers/mapping.py are not a second
        registry: every value is declared in ontology/vso.ttl."""
        for local in (list(DIRECTIONAL_VALUES) + list(PROXIMAL_VALUES)
                      + list(EDGE_PREDICATES) + list(ROLES)
                      + list(AFFORDANCES) + list(ANIMACY)
                      + list(COUNTABILITY) + list(INDIVIDUATION)):
            with self.subTest(term=local):
                self.assertTrue(self.term(local), "vso:%s is not declared" % local)
        rcc = Namespace("https://w3id.org/vson/v1/rcc8#")
        for local in RCC_VALUES:
            with self.subTest(term=local):
                self.assertIn(
                    (rcc[local], None, None), self.ontology,
                    "rcc:%s is not declared" % local,
                )

    def test_every_dimension_is_in_the_registry(self):
        """§5.5.1: a vso: dimension outside the twenty-one fails C2. A
        mapping table is exactly where that typo would live."""
        registry = {
            str(subject).rsplit("#", 1)[1]
            for subject in self.ontology.subjects(None, VSO.Dimension)
        }
        self.assertEqual(21, len(registry), sorted(registry))
        for dataset, table in sorted(self.tables.items()):
            for name, entry in sorted(table.attributes.items()):
                if entry["kind"] != "quality":
                    continue
                with self.subTest(dataset=dataset, attribute=name):
                    self.assertIn(entry["dimension"], registry)

    def test_every_lemma_is_well_formed(self):
        for dataset, table in sorted(self.tables.items()):
            for name, entry in sorted(table.predicates.items()):
                if entry["kind"] != "perdurant":
                    continue
                with self.subTest(dataset=dataset, predicate=name):
                    self.assertRegex(entry["lemma"], LEMMA_RE)

    def test_every_drop_states_a_reason_and_every_approximation_a_note(self):
        for dataset, table in sorted(self.tables.items()):
            entries = sorted(table.predicates.items()) + sorted(
                table.attributes.items()
            )
            for name, entry in entries:
                with self.subTest(dataset=dataset, source=name):
                    if entry["kind"] == "drop":
                        self.assertTrue(entry.get("reason"))
                    elif entry["fidelity"] == "approximate":
                        self.assertTrue(entry.get("note"))

    def test_psg_carries_the_published_fifty_six(self):
        """The PSG table is the one closed vocabulary here, so its size is
        pinned: 56 predicates plus the parenthesised alternates the source
        table gives for four of them."""
        table = self.tables["psg"]
        canonical = [
            name for name, entry in table.predicates.items()
            if "variant_of" not in entry
        ]
        self.assertEqual(56, len(canonical), sorted(canonical))


class Geometry(unittest.TestCase):
    """Pixel boxes become §5.4 values, or nothing at all."""

    def test_normalization_matches_the_value_grammar(self):
        cases = [
            (0, 0, 640, 480, 640, 480, "0,0,1,1"),
            (220, 310, 50, 80, 640, 480, "0.3438,0.6458,0.0781,0.1667"),
            (-5, 0, 320, 90, 300, 200, "0,0,1,0.45"),
            (100, 100, 0, 0, 200, 200, "0.5,0.5,0,0"),
        ]
        for x, y, w, h, width, height, expected in cases:
            with self.subTest(box=(x, y, w, h)):
                text, _ = normalize_bbox(x, y, w, h, width, height)
                self.assertEqual(expected, text)
                self.assertRegex(text, BBOX_RE)

    def test_a_box_outside_the_frame_is_reported_as_clamped(self):
        _, clamped = normalize_bbox(-5, 0, 320, 90, 300, 200)
        self.assertTrue(clamped)
        _, clamped = normalize_bbox(0, 0, 300, 200, 300, 200)
        self.assertFalse(clamped)

    def test_no_image_size_is_no_geometry(self):
        self.assertEqual((None, False), normalize_bbox(1, 2, 3, 4, None, None))
        self.assertEqual((None, False), normalize_bbox(1, 2, 3, 4, 0, 100))


if __name__ == "__main__":
    unittest.main()
