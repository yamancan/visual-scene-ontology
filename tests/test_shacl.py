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
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import rdflib
    import pyshacl
    from tools.shacl_helper import validate_path
except ImportError:
    rdflib = None
    pyshacl = None
    validate_path = None


@unittest.skipUnless(rdflib and pyshacl, "rdflib + pyshacl required")
class ConformanceTests(unittest.TestCase):
    def test_throne_room_conforms(self) -> None:
        conforms, report = validate_path("examples/throne_room.ttl")
        self.assertTrue(conforms, msg=report)

    def test_directional_without_viewer_fails(self) -> None:
        conforms, report = validate_path("tests/fixtures/bad_no_viewer.ttl")
        self.assertFalse(conforms)
        self.assertIn("viewer", report)

    def test_frame_depicted_fails(self) -> None:
        conforms, report = validate_path("tests/fixtures/bad_frame_depicted.ttl")
        self.assertFalse(conforms)

    def test_event_without_lemma_fails(self) -> None:
        conforms, report = validate_path("tests/fixtures/bad_event_no_lemma.ttl")
        self.assertFalse(conforms)
        self.assertIn("lemma", report)


if __name__ == "__main__":
    unittest.main()
