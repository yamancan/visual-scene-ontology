"""
SHACL conformance tests.

  - examples/throne_room.ttl  MUST conform.
  - tests/fixtures/bad_*.ttl  MUST NOT conform (each exercises one shape).

Skipped automatically if rdflib/pyshacl are not installed.
"""

from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

try:
    import rdflib
    import pyshacl
except ImportError:
    rdflib = None
    pyshacl = None


def _validate(data_path: str):
    data = rdflib.Graph()
    data.parse(os.path.join(ROOT, data_path), format="turtle")

    shapes = rdflib.Graph()
    shapes.parse(os.path.join(ROOT, "shapes/vson-shapes.ttl"), format="turtle")

    ontology = rdflib.Graph()
    for f in ("ontology/vso.ttl", "ontology/rcc8.ttl", "ontology/allen.ttl"):
        ontology.parse(os.path.join(ROOT, f), format="turtle")

    conforms, _, report_text = pyshacl.validate(
        data,
        shacl_graph=shapes,
        ont_graph=ontology,
        inference="rdfs",
        abort_on_first=False,
        allow_warnings=True,
    )
    return conforms, report_text


@unittest.skipUnless(rdflib and pyshacl, "rdflib + pyshacl required")
class ConformanceTests(unittest.TestCase):
    def test_throne_room_conforms(self) -> None:
        conforms, report = _validate("examples/throne_room.ttl")
        self.assertTrue(conforms, msg=report)

    def test_directional_without_viewer_fails(self) -> None:
        conforms, report = _validate("tests/fixtures/bad_no_viewer.ttl")
        self.assertFalse(conforms)
        self.assertIn("viewer", report)

    def test_frame_depicted_fails(self) -> None:
        conforms, report = _validate("tests/fixtures/bad_frame_depicted.ttl")
        self.assertFalse(conforms)

    def test_event_without_lemma_fails(self) -> None:
        conforms, report = _validate("tests/fixtures/bad_event_no_lemma.ttl")
        self.assertFalse(conforms)
        self.assertIn("lemma", report)


if __name__ == "__main__":
    unittest.main()
