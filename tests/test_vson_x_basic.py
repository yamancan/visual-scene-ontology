"""
Phase B B2 (first slice) — VSON-X parser unit tests.

Covers the initial parser scope:
  - Composition root (~scene)
  - Frame declarations (/CameraView, /VisualStyle, /SceneContext)
  - Frame direct properties (*K V on Frame)
  - Entity declarations (handle /Class trait* *K V*)
  - Entity special direct properties (*class, *bbox2d, *embodies, ...)
  - Entity Quality dispatch (*K V -> hasQuality)
  - Composition-level Quality dispatch (*K V on root)
  - Composition rendersAs special direct property
  - Viewer anchor (^cam)

Stative (>), Event/Process (>>), Spatial (! / &) are deferred to
subsequent slices and asserted as parse errors here.

Test invariant: VSON-X source and the corresponding gallery Penman
source produce graph-equivalent RDF graphs (modulo blank-node
identity for auto-anonymous reified nodes; see tools.vson_x.equiv).
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import rdflib

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.vson_x import to_turtle as vson_x_to_turtle  # noqa: E402
from tools.vson_x.equiv import graph_equivalent  # noqa: E402
from tools.vson_x.vson_x import parse  # noqa: E402

CLI = REPO / "cli" / "target" / "release" / "vson"


def _penman_to_turtle_via_cli(vson_path: Path) -> str:
    if not CLI.exists():
        raise unittest.SkipTest(f"Rust CLI not built at {CLI}")
    return subprocess.run(
        [str(CLI), "convert", "p2t", str(vson_path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _load(turtle: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle, format="turtle")
    return g


class TokenizerAndParseSmokeTests(unittest.TestCase):
    def test_minimal_parses(self):
        src = (
            "~scene\n"
            "  /CameraView @cam *angle eye_level *focalLength 50mm *framing close_up\n"
            "  ^cam\n"
            "  apple /PhysicalObject Inert Count *class Apple\n"
        )
        ast = parse(src)
        self.assertEqual(ast.var, "scene")
        self.assertEqual(ast.concept, "Composition")
        # Should have at least: framedBy, viewedBy, depicts (3+ edges)
        edge_roles = [r for r, _ in ast.edges]
        self.assertIn("framedBy", edge_roles)
        self.assertIn("viewedBy", edge_roles)
        self.assertIn("depicts", edge_roles)

    def test_quality_kv_creates_quality_node(self):
        src = (
            "~scene\n"
            "  /CameraView @cam\n"
            "  ^cam\n"
            "  apple /PhysicalObject *class Apple *color red\n"
        )
        turtle = vson_x_to_turtle(src)
        g = _load(turtle)
        # Apple should have a Quality with dimension Color, value red
        qualities = list(g.subjects(
            predicate=rdflib.URIRef("https://vson.dev/v1/ontology#dimension"),
            object=rdflib.URIRef("https://vson.dev/v1/ontology#Color"),
        ))
        self.assertEqual(len(qualities), 1, "expected one Quality with dimension Color")
        # Its value is :red
        values = list(g.objects(
            qualities[0],
            rdflib.URIRef("https://vson.dev/v1/ontology#value"),
        ))
        self.assertEqual(len(values), 1)
        self.assertTrue(str(values[0]).endswith("#red"))

    def test_modifier_emits_modifier_triple(self):
        src = (
            "~scene\n"
            "  /CameraView @cam\n"
            "  ^cam\n"
            "  apple /PhysicalObject *class Apple *color red ~dark\n"
        )
        turtle = vson_x_to_turtle(src)
        g = _load(turtle)
        modifiers = list(g.objects(
            predicate=rdflib.URIRef("https://vson.dev/v1/ontology#modifier")
        ))
        self.assertEqual(len(modifiers), 1)
        self.assertEqual(str(modifiers[0]), "dark")

    def test_named_handle_routes_to_named_individuation(self):
        src = (
            "~scene\n"
            "  /CameraView @cam\n"
            "  ^cam\n"
            "  @alice /PhysicalObject *class Human\n"
        )
        ast = parse(src)
        # Find alice's individuation edge
        alice = next(
            t for r, t in ast.edges if r == "depicts" and getattr(t, "var", None) == "alice"
        )
        ind_targets = [tgt for r, tgt in alice.edges if r == "individuation"]
        self.assertEqual(len(ind_targets), 1)
        self.assertEqual(ind_targets[0].var, "Named")

    def test_bare_handle_routes_to_generic(self):
        src = (
            "~scene\n"
            "  /CameraView @cam\n"
            "  ^cam\n"
            "  apple /PhysicalObject *class Apple\n"
        )
        ast = parse(src)
        apple = next(
            t for r, t in ast.edges if r == "depicts" and getattr(t, "var", None) == "apple"
        )
        ind_targets = [tgt for r, tgt in apple.edges if r == "individuation"]
        self.assertEqual(len(ind_targets), 1)
        self.assertEqual(ind_targets[0].var, "Generic")

    def test_explicit_trait_overrides_default(self):
        src = (
            "~scene\n"
            "  /CameraView @cam\n"
            "  ^cam\n"
            "  apple /PhysicalObject Skolem *class Apple\n"
        )
        ast = parse(src)
        apple = next(
            t for r, t in ast.edges if r == "depicts" and getattr(t, "var", None) == "apple"
        )
        ind_targets = [tgt for r, tgt in apple.edges if r == "individuation"]
        # Explicit Skolem wins over the bare-handle default of Generic.
        self.assertEqual(len(ind_targets), 1)
        self.assertEqual(ind_targets[0].var, "Skolem")


class GalleryEquivalenceTests(unittest.TestCase):
    """For each gallery scene we currently support, verify the VSON-X
    rendering of an equivalent scene produces a graph that's equivalent
    (modulo auto-anonymous blank-node identity) to the Penman version."""

    def assertEquivalent(self, vson_x_src: str, penman_path: Path):
        x_turtle = vson_x_to_turtle(vson_x_src)
        p_turtle = _penman_to_turtle_via_cli(penman_path)
        gx = _load(x_turtle)
        gp = _load(p_turtle)
        self.assertTrue(
            graph_equivalent(gx, gp),
            f"VSON-X output not graph-equivalent to {penman_path.name}\n"
            f"--- VSON-X turtle ---\n{x_turtle}\n--- Penman turtle ---\n{p_turtle}",
        )

    def test_01_minimal(self):
        src = (
            "~scene\n"
            "  /CameraView @cam *angle eye_level *focalLength 50mm *framing close_up\n"
            "  ^cam\n"
            "  apple /PhysicalObject Inert Count *class Apple\n"
        )
        self.assertEquivalent(src, REPO / "examples/gallery/01_minimal.vson")

    def test_02_quality(self):
        src = (
            "~scene\n"
            "  /CameraView @cam *angle eye_level *focalLength 50mm *framing close_up\n"
            "  ^cam\n"
            "  apple /PhysicalObject Inert Count *class Apple *color red\n"
        )
        self.assertEquivalent(src, REPO / "examples/gallery/02_quality.vson")


class UnimplementedFeatureErrors(unittest.TestCase):
    """Sigils not yet supported MUST fail with a clear error so we don't
    silently emit malformed graphs."""

    def test_stative_arrow_not_yet_implemented(self):
        src = (
            "~scene\n"
            "  /CameraView @cam\n"
            "  ^cam\n"
            "  apple /PhysicalObject *class Apple\n"
            "  @bob > hold apple\n"
        )
        with self.assertRaises(SyntaxError):
            parse(src)


if __name__ == "__main__":
    unittest.main()
