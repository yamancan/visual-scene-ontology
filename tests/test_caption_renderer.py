"""
Caption renderer determinism tests (Phase A).

Asserts:
  1. Every gallery scene renders to a non-empty caption.
  2. Output is byte-identical to the ground-truth fixture under
     tests/fixtures/captions/{base}.txt.
  3. The renderer is deterministic — repeated invocations yield the
     same string.
  4. The renderer consumes an rdflib.Graph (syntax-independent).
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import rdflib

from tools.render.caption import render

REPO = Path(__file__).resolve().parent.parent
GALLERY = REPO / "examples" / "gallery"
FIXTURES = REPO / "tests" / "fixtures" / "captions"
CLI = REPO / "cli" / "target" / "release" / "vson"


def _vson_to_turtle(vson_path: Path) -> str:
    """Use the Rust CLI to transpile Penman -> Turtle."""
    if not CLI.exists():
        raise unittest.SkipTest(f"Rust CLI not built at {CLI}; run `cd cli && cargo build --release`")
    result = subprocess.run(
        [str(CLI), "convert", "p2t", str(vson_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _load_graph_from_vson(vson_path: Path) -> rdflib.Graph:
    turtle = _vson_to_turtle(vson_path)
    g = rdflib.Graph()
    g.parse(data=turtle, format="turtle")
    return g


class GalleryCaptionTests(unittest.TestCase):
    """One test method per gallery scene; each verifies fixture parity."""

    @classmethod
    def setUpClass(cls):
        cls.scene_files = sorted(GALLERY.glob("*.vson"))
        if not cls.scene_files:
            raise unittest.SkipTest(f"No gallery scenes found at {GALLERY}")

    def test_all_scenes_have_fixtures(self):
        """Every gallery scene MUST have a corresponding caption fixture."""
        for scene in self.scene_files:
            with self.subTest(scene=scene.name):
                fixture = FIXTURES / f"{scene.stem}.txt"
                self.assertTrue(
                    fixture.exists(),
                    f"Missing caption fixture for {scene.name}: expected {fixture}",
                )

    def test_renders_non_empty(self):
        """No gallery scene should render to an empty caption."""
        for scene in self.scene_files:
            with self.subTest(scene=scene.name):
                g = _load_graph_from_vson(scene)
                caption = render(g)
                self.assertTrue(caption, f"Empty caption for {scene.name}")
                self.assertGreater(
                    len(caption),
                    5,
                    f"Suspiciously short caption for {scene.name}: {caption!r}",
                )

    def test_byte_identical_to_fixture(self):
        """Renderer output MUST equal the ground-truth fixture byte-for-byte."""
        for scene in self.scene_files:
            with self.subTest(scene=scene.name):
                fixture = FIXTURES / f"{scene.stem}.txt"
                if not fixture.exists():
                    continue  # covered by test_all_scenes_have_fixtures
                expected = fixture.read_text(encoding="utf-8").rstrip("\n")
                g = _load_graph_from_vson(scene)
                actual = render(g).rstrip("\n")
                self.assertEqual(
                    actual,
                    expected,
                    f"Caption mismatch for {scene.name}:\n  expected: {expected!r}\n  actual:   {actual!r}",
                )

    def test_deterministic_repeat(self):
        """Calling render() twice on the same graph yields the same string."""
        for scene in self.scene_files:
            with self.subTest(scene=scene.name):
                g = _load_graph_from_vson(scene)
                first = render(g)
                second = render(g)
                self.assertEqual(
                    first, second, f"Non-deterministic render for {scene.name}"
                )

    def test_deterministic_reload(self):
        """Re-parsing the same Turtle and re-rendering yields the same string."""
        for scene in self.scene_files:
            with self.subTest(scene=scene.name):
                turtle = _vson_to_turtle(scene)
                g1 = rdflib.Graph()
                g1.parse(data=turtle, format="turtle")
                g2 = rdflib.Graph()
                g2.parse(data=turtle, format="turtle")
                self.assertEqual(
                    render(g1),
                    render(g2),
                    f"Render differs across re-parses for {scene.name}",
                )


class RenderApiTests(unittest.TestCase):
    """Smoke tests for the public render() API."""

    def test_empty_graph_returns_empty_string(self):
        g = rdflib.Graph()
        self.assertEqual(render(g), "")

    def test_graph_without_composition_returns_empty(self):
        g = rdflib.Graph()
        g.parse(
            data="""
                @prefix vso: <https://w3id.org/vson/v1/ontology#> .
                @prefix : <https://example.org/scenes/anonymous#> .
                :apple a vso:PhysicalObject .
            """,
            format="turtle",
        )
        self.assertEqual(render(g), "")


class DisambiguationTests(unittest.TestCase):
    """Generic same-class entities must get distinguishable noun phrases."""

    HEADER = """@prefix vso: <https://w3id.org/vson/v1/ontology#> .
@prefix : <https://example.org/scenes/test#> .
"""

    def _graph(self, body: str) -> rdflib.Graph:
        g = rdflib.Graph()
        g.parse(data=self.HEADER + body, format="turtle")
        return g

    def test_layout_drives_positional_labels(self):
        body = """
        :scene a vso:Composition ;
          vso:depicts :p1 , :p2 , :p3 , :sf .
        :p1 a vso:PhysicalObject ; vso:class "Person" ;
          vso:individuation "Generic" ;
          vso:hasQuality [ a vso:Quality ; vso:dimension "Layout" ; vso:value "left" ] .
        :p2 a vso:PhysicalObject ; vso:class "Person" ;
          vso:individuation "Generic" ;
          vso:hasQuality [ a vso:Quality ; vso:dimension "Layout" ; vso:value "center" ] .
        :p3 a vso:PhysicalObject ; vso:class "Person" ;
          vso:individuation "Generic" ;
          vso:hasQuality [ a vso:Quality ; vso:dimension "Layout" ; vso:value "right" ] .
        :sf a vso:SpatialFact ; vso:figure :p1 ; vso:ground :p3 ;
          vso:directional vso:left_of ; vso:viewer :cam .
        """
        out = render(self._graph(body)).lower()
        self.assertIn("the leftmost person", out)
        self.assertIn("the middle person", out)
        self.assertIn("the rightmost person", out)
        self.assertIn(
            "the leftmost person is to the left of the rightmost person.", out
        )

    def test_four_entities_get_ordinal_labels(self):
        body = """
        :scene a vso:Composition ;
          vso:depicts :a, :b, :c, :d .
        :a a vso:PhysicalObject ; vso:class "Person" ; vso:individuation "Generic" ;
          vso:bbox2d "0.00,0.0,0.2,1.0" .
        :b a vso:PhysicalObject ; vso:class "Person" ; vso:individuation "Generic" ;
          vso:bbox2d "0.25,0.0,0.2,1.0" .
        :c a vso:PhysicalObject ; vso:class "Person" ; vso:individuation "Generic" ;
          vso:bbox2d "0.50,0.0,0.2,1.0" .
        :d a vso:PhysicalObject ; vso:class "Person" ; vso:individuation "Generic" ;
          vso:bbox2d "0.75,0.0,0.2,1.0" .
        """
        out = render(self._graph(body)).lower()
        self.assertIn("the leftmost person", out)
        self.assertIn("the second person from the left", out)
        self.assertIn("the third person from the left", out)
        self.assertIn("the rightmost person", out)

    def test_repeated_predicate_collapses(self):
        body = """
        :scene a vso:Composition ;
          vso:depicts :p1, :p2, :p3, :wall, :sf1, :sf2, :sf3 .
        :p1 a vso:PhysicalObject ; vso:class "Person" ; vso:individuation "Generic" ;
          vso:hasQuality [ a vso:Quality ; vso:dimension "Layout" ; vso:value "left" ] .
        :p2 a vso:PhysicalObject ; vso:class "Person" ; vso:individuation "Generic" ;
          vso:hasQuality [ a vso:Quality ; vso:dimension "Layout" ; vso:value "center" ] .
        :p3 a vso:PhysicalObject ; vso:class "Person" ; vso:individuation "Generic" ;
          vso:hasQuality [ a vso:Quality ; vso:dimension "Layout" ; vso:value "right" ] .
        :wall a vso:PhysicalObject ; vso:class "Wall" ; vso:individuation "Generic" .
        :sf1 a vso:SpatialFact ; vso:figure :p1 ; vso:ground :wall ;
          vso:rcc "TPP" ; vso:viewer :cam .
        :sf2 a vso:SpatialFact ; vso:figure :p2 ; vso:ground :wall ;
          vso:rcc "TPP" ; vso:viewer :cam .
        :sf3 a vso:SpatialFact ; vso:figure :p3 ; vso:ground :wall ;
          vso:rcc "TPP" ; vso:viewer :cam .
        """
        out = render(self._graph(body))
        self.assertIn("are tangential parts of the wall", out)
        self.assertEqual(out.count("are tangential parts of the wall"), 1)

    def test_multi_value_color_slash_joined(self):
        body = """
        :scene a vso:Composition ;
          vso:depicts :shirt .
        :shirt a vso:PhysicalObject ; vso:class "Shirt" ; vso:individuation "Generic" ;
          vso:hasQuality [ a vso:Quality ; vso:dimension "Color" ; vso:value "white" ] ,
                         [ a vso:Quality ; vso:dimension "Color" ; vso:value "blue" ] .
        """
        out = render(self._graph(body))
        self.assertTrue(
            "blue/white" in out or "white/blue" in out,
            f"expected slash-joined colors, got {out!r}",
        )


if __name__ == "__main__":
    unittest.main()
