"""
Phase B B3a — VSON-X gallery round-trip parity.

For each (Penman, VSON-X) pair under examples/gallery and
examples/gallery-x, we assert:

    graph_equivalent(emit(parse_x(N.x.vson)), emit(parse_p(N.vson)))

The two syntaxes must produce identical RDF graphs (modulo blank-node
identity for auto-anonymous reified nodes; see tools.vson_x.equiv).

Twelve of the sixteen gallery scenes have a VSON-X counterpart, and this
asserts every one of them denotes the same scene as its Penman twin. The
question it answers is docs/vson.md §4.6's; the answer it computes is the
fast one. tests/test_canon.py answers the same twelve through the
normative route — RDFC-1.0 canonical N-Quads, compared byte for byte and
frozen — and checks the two routes against each other.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import rdflib

from tools.vson_x import to_turtle as vson_x_to_turtle
from tools.vson_x.equiv import graph_equivalent

REPO = Path(__file__).resolve().parent.parent

CLI = REPO / "cli" / "target" / "release" / "vson"
GALLERY_P = REPO / "examples" / "gallery"
GALLERY_X = REPO / "examples" / "gallery-x"

PAIRS = [
    "01_minimal",
    "02_quality",
    "03_spatial_topology",
    "04_directional_with_viewer",
    "05_possession_stative",
    "06_event_with_instrument",
    "07_ditransitive",
    "08_collective",
    "09_mass_substance",
    "10_geometry_bbox",
    "11_throne_room",
    "12_persona",
]


def _penman_turtle(stem: str) -> str:
    if not CLI.exists():
        raise unittest.SkipTest(f"Rust CLI not built at {CLI}")
    return subprocess.run(
        [str(CLI), "convert", "p2t", str(GALLERY_P / f"{stem}.vson")],
        check=True, capture_output=True, text=True,
    ).stdout


def _x_turtle(stem: str) -> str:
    return vson_x_to_turtle((GALLERY_X / f"{stem}.x.vson").read_text())


def _load(turtle: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=turtle, format="turtle")
    return g


class GalleryRoundTripTests(unittest.TestCase):
    """Generated dynamically below — one method per gallery pair."""


def _make_test(stem: str):
    def test(self):
        gx = _load(_x_turtle(stem))
        gp = _load(_penman_turtle(stem))
        self.assertTrue(
            graph_equivalent(gx, gp),
            f"VSON-X output not graph-equivalent to Penman for {stem}\n"
            f"  |VSON-X|={len(gx)}  |Penman|={len(gp)}",
        )
    test.__name__ = f"test_{stem}"
    return test


for stem in PAIRS:
    setattr(GalleryRoundTripTests, f"test_{stem}", _make_test(stem))


if __name__ == "__main__":
    unittest.main()
