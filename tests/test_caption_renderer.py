"""
Caption renderer determinism tests (Phase A).

Asserts:
  1. Every gallery scene renders to a non-empty caption.
  2. Output is byte-identical to the ground-truth fixture under
     tests/fixtures/captions/{base}.txt.
  3. The renderer is deterministic — repeated invocations yield the
     same string.
  4. The renderer consumes an rdflib.Graph (syntax-independent).

Generation faithfulness (CLIP/blind A/B against image-gen output) is
evaluated separately by tests/eval_caption.py and is NOT a CI gate.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import rdflib

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.render.caption import render  # noqa: E402

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
            fixture = FIXTURES / f"{scene.stem}.txt"
            self.assertTrue(
                fixture.exists(),
                f"Missing caption fixture for {scene.name}: expected {fixture}",
            )

    def test_renders_non_empty(self):
        """No gallery scene should render to an empty caption."""
        for scene in self.scene_files:
            g = _load_graph_from_vson(scene)
            caption = render(g)
            self.assertTrue(caption, f"Empty caption for {scene.name}")
            self.assertGreater(len(caption), 5, f"Suspiciously short caption for {scene.name}: {caption!r}")

    def test_byte_identical_to_fixture(self):
        """Renderer output MUST equal the ground-truth fixture byte-for-byte."""
        for scene in self.scene_files:
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
            g = _load_graph_from_vson(scene)
            first = render(g)
            second = render(g)
            self.assertEqual(first, second, f"Non-deterministic render for {scene.name}")

    def test_deterministic_reload(self):
        """Re-parsing the same Turtle and re-rendering yields the same string."""
        for scene in self.scene_files:
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
                @prefix vso: <https://vson.dev/v1/ontology#> .
                @prefix : <https://example.org/scenes/anonymous#> .
                :apple a vso:PhysicalObject .
            """,
            format="turtle",
        )
        self.assertEqual(render(g), "")


if __name__ == "__main__":
    unittest.main()
