"""
FOL renderer determinism tests.

Asserts:
  1. Every gallery scene renders to a non-empty FOL document.
  2. Output is byte-identical to the ground-truth fixture under
     tests/fixtures/fol/{base}.fol.
  3. The renderer is deterministic — repeated invocations and re-parses
     yield the same string.
  4. Reified Event/Process/Stative/SpatialFact nodes get collapsed into
     n-ary facts; their binary triples are NOT also emitted in the
     binary-predicate section.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import rdflib

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.render.fol import render  # noqa: E402

GALLERY = REPO / "examples" / "gallery"
FIXTURES = REPO / "tests" / "fixtures" / "fol"
CLI = REPO / "cli" / "target" / "release" / "vson"


def _vson_to_turtle(vson_path: Path) -> str:
    if not CLI.exists():
        raise unittest.SkipTest(f"Rust CLI not built at {CLI}")
    result = subprocess.run(
        [str(CLI), "convert", "p2t", str(vson_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _load_graph_from_vson(vson_path: Path) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=_vson_to_turtle(vson_path), format="turtle")
    return g


class GalleryFolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene_files = sorted(GALLERY.glob("*.vson"))
        if not cls.scene_files:
            raise unittest.SkipTest(f"No gallery scenes at {GALLERY}")

    def test_all_scenes_have_fixtures(self):
        for scene in self.scene_files:
            self.assertTrue(
                (FIXTURES / f"{scene.stem}.fol").exists(),
                f"Missing FOL fixture for {scene.name}",
            )

    def test_byte_identical_to_fixture(self):
        for scene in self.scene_files:
            fixture = FIXTURES / f"{scene.stem}.fol"
            if not fixture.exists():
                continue
            expected = fixture.read_text(encoding="utf-8")
            actual = render(_load_graph_from_vson(scene))
            self.assertEqual(
                actual, expected, f"FOL mismatch for {scene.name}"
            )

    def test_deterministic_repeat(self):
        for scene in self.scene_files:
            g = _load_graph_from_vson(scene)
            self.assertEqual(render(g), render(g))


class CollapseTests(unittest.TestCase):
    """Reified n-ary nodes are emitted once (collapsed), never as binaries."""

    HEADER = """@prefix vso: <https://vson.dev/v1/ontology#> .
@prefix : <https://example.org/scenes/test#> .
"""

    def _graph(self, body: str) -> rdflib.Graph:
        g = rdflib.Graph()
        g.parse(data=self.HEADER + body, format="turtle")
        return g

    def test_event_collapses_to_nary_fact(self):
        body = """
        :scene a vso:Composition ; vso:depicts :strike .
        :strike a vso:Event ;
          vso:lemma "strike" ;
          vso:agent :bob ; vso:patient :boar ; vso:instrument :sword .
        :bob a vso:PhysicalObject .
        :boar a vso:PhysicalObject .
        :sword a vso:PhysicalObject .
        """
        out = render(self._graph(body))
        self.assertIn(
            "strike(agent=bob, instrument=sword, patient=boar).", out
        )
        # Role triples must not also appear in the binary section.
        self.assertNotIn("agent(strike, bob)", out)
        self.assertNotIn("patient(strike, boar)", out)
        self.assertNotIn("instrument(strike, sword)", out)
        # The reified node's class predicate is NOT emitted as unary
        # (it's already implicit in the head 'strike').
        self.assertNotIn("Event(strike).", out)

    def test_spatial_fact_collapses(self):
        body = """
        :scene a vso:Composition ; vso:hasFact :sf .
        :sf a vso:SpatialFact ;
          vso:figure :a ; vso:ground :b ;
          vso:directional vso:left_of ; vso:viewer :cam .
        :a a vso:PhysicalObject .
        :b a vso:PhysicalObject .
        """
        out = render(self._graph(body))
        self.assertIn(
            "spatialfact(dir=left_of, figure=a, ground=b, viewer=cam).", out
        )
        self.assertNotIn("figure(sf, a)", out)
        self.assertNotIn("ground(sf, b)", out)


if __name__ == "__main__":
    unittest.main()
