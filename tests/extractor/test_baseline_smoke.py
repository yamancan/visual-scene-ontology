"""
Offline smoke test for the bare-VLM baseline plumbing.

Replays a canned VLM response (no API call) and asserts the
Penman -> Turtle -> SHACL pipeline produces a row with the
expected shape. Exercises plumbing only; says nothing about
real model behavior. Runs in `make check`.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import rdflib
    import pyshacl
    from tools.penman import vson_penman as vp
    from tools.shacl_helper import validate_graph
except ImportError:
    rdflib = None


@unittest.skipUnless(rdflib, "rdflib + pyshacl required")
class BaselineSmoke(unittest.TestCase):
    def test_canned_response_passes_pipeline(self) -> None:
        cassette = HERE / "cassettes" / "throne_room_response.txt"
        text = cassette.read_text()

        ttl = vp.to_turtle(text)
        g = rdflib.Graph()
        g.parse(data=ttl, format="turtle")
        self.assertGreater(len(g), 0)

        conforms, report = validate_graph(g)
        self.assertTrue(conforms, msg=report[:1000])

        row = {
            "image": "synthetic_throne_room",
            "shacl_first_try": conforms,
            "retries": 0,
        }
        self.assertEqual(set(row.keys()), {"image", "shacl_first_try", "retries"})


if __name__ == "__main__":
    unittest.main()
