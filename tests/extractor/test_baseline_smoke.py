"""
Offline smoke test for the bare-VLM baseline plumbing.

Replays a canned VLM response (no API call) and asserts the
Penman -> Turtle -> SHACL pipeline produces a row with the
expected shape. Exercises plumbing only; says nothing about
real model behavior. Runs in `make check`.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    import pyshacl  # noqa: F401  — availability probe for the skip guard below
    import rdflib

    from tools.extractor.baseline.extract import ROW_FIELDS, run_one
    from tools.penman import vson_penman as vp
    from tools.shacl_helper import validate_graph
except ImportError:
    rdflib = None


class _StubBlock:
    """One content block of a replayed response."""

    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _StubUsage:
    input_tokens = 1234
    output_tokens = 567


class _StubMessage:
    def __init__(self, text: str) -> None:
        self.content = [_StubBlock(text)]
        self.usage = _StubUsage()


class _StubMessages:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    def create(self, **kwargs) -> _StubMessage:
        self.calls += 1
        return _StubMessage(self._text)


class _StubClient:
    """Stands in for anthropic.Anthropic — replays one canned response."""

    def __init__(self, text: str) -> None:
        self.messages = _StubMessages(text)


@unittest.skipUnless(rdflib, "rdflib + pyshacl required")
class BaselineSmoke(unittest.TestCase):
    def _cassette(self) -> str:
        return (HERE / "cassettes" / "throne_room_response.txt").read_text()

    def test_canned_response_passes_pipeline(self) -> None:
        ttl = vp.to_turtle(self._cassette())
        g = rdflib.Graph()
        g.parse(data=ttl, format="turtle")
        self.assertGreater(len(g), 0)

        conforms, report = validate_graph(g)
        self.assertTrue(conforms, msg=report[:1000])

    def test_run_one_row_matches_shipped_schema(self) -> None:
        """run_one's row MUST carry exactly the results.csv columns."""
        client = _StubClient(self._cassette())
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "synthetic_throne_room.jpg"
            # Never decoded — run_one only base64-encodes the bytes.
            image.write_bytes(b"\xff\xd8\xff\xd9")
            row = run_one(client, image, "system prompt")

        self.assertEqual(tuple(row), ROW_FIELDS)
        self.assertEqual(row["image"], "synthetic_throne_room.jpg")
        self.assertTrue(row["shacl_first_try"])
        self.assertTrue(row["shacl_after_retries"])
        self.assertEqual(row["retries"], 0)
        self.assertEqual(client.messages.calls, 1, "conforming reply needs no repair call")


if __name__ == "__main__":
    unittest.main()
