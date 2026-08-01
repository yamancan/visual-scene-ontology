"""Structured validation records (tools/validate_report.py) + the frozen goldens.

Two things are checked here, and the second is the one a Rust test cannot do.

**The records.** One per violation, from whichever of the three gates fired,
with the fields docs/vson.md §5.16 lists. The SHACL case is the interesting
one: the source shape a violation reports is usually a blank node nested inside
a named node shape, and a rule id built from a blank node identifies nothing —
so the walk up to the named ancestor is pinned directly.

**The goldens.** `cli/tests/report_format.rs` compares the binary's output to
`tests/fixtures/validate_report/*` byte for byte, which keeps the output from
drifting but says nothing about whether the frozen bytes are *valid*: refreeze
a broken SARIF log and the byte test goes green. This asserts the required
properties of SARIF 2.1.0 (OASIS, March 2020) against the frozen file, so the
two tests together mean "still valid, still stable".

Skipped automatically when rdflib/pyshacl are not installed.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import unittest

try:
    import rdflib

    from tools import validate_report as vr
except ImportError:  # pragma: no cover — dependency probe
    rdflib = None
    vr = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_DIR = os.path.join(ROOT, "tests/fixtures/validate_report")
PFX = (
    "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n"
    "@prefix : <https://example.org/scene#> .\n"
)

# A directional spatial fact with no viewer — C5, the fixture the CLI goldens
# use as well, minus the Penman surface.
NO_VIEWER = """
:c a vso:Composition ; vso:depicts :sf, :a, :b .
:a a vso:PhysicalObject .
:b a vso:PhysicalObject .
:sf a vso:SpatialFact ;
    vso:figure :a ; vso:ground :b ;
    vso:directional vso:above .
"""


def read_golden(name: str) -> dict:
    with open(os.path.join(GOLDEN_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


@unittest.skipUnless(rdflib and vr, "rdflib + pyshacl required")
class RecordTests(unittest.TestCase):
    def _graph(self, body: str) -> "rdflib.Graph":
        g = rdflib.Graph()
        g.parse(data=PFX + body, format="turtle")
        return g

    def _shacl(self, body: str):
        shapes = rdflib.Graph()
        shapes.parse(os.path.join(ROOT, vr.DEFAULT_SHAPES), format="turtle")
        return vr.shacl_findings(self._graph(body), shapes, vr.ontology())

    def test_a_shacl_violation_carries_every_documented_field(self) -> None:
        conforms, findings = self._shacl(NO_VIEWER)
        self.assertFalse(conforms)
        self.assertEqual(len(findings), 1, findings)
        found = findings[0]
        self.assertEqual(found["gate"], "shacl")
        self.assertEqual(found["severity"], "violation")
        self.assertIn("vso:viewer", found["message"])
        self.assertEqual(found["focus_node"], "https://example.org/scene#sf")
        self.assertEqual(
            found["result_path"], "https://w3id.org/vson/v1/ontology#viewer"
        )
        self.assertTrue(found["constraint"].endswith("MinCountConstraintComponent"))

    def test_the_rule_names_the_shape_not_the_blank_node_that_fired(self) -> None:
        # sh:sourceShape is `[ sh:path vso:viewer ; sh:minCount 1 ; ... ]` — a
        # blank node. A rule id built from that identifies nothing across runs;
        # the named ancestor is what a reader can look up in the shapes file.
        _conforms, findings = self._shacl(NO_VIEWER)
        self.assertEqual(
            findings[0]["shape"],
            "https://w3id.org/vson/v1/shapes#DirectionalNeedsViewerShape",
        )
        self.assertEqual(
            findings[0]["rule"], "vson/shacl/DirectionalNeedsViewerShape"
        )

    def test_findings_come_back_in_a_deterministic_order(self) -> None:
        # Three violations on one node from one shape. The report graph is a
        # set, so without the sort the goldens would flap between runs.
        body = """
:scene a vso:Composition ; vso:framedBy :cam ; vso:viewedBy :cam ;
       vso:depicts :lamp .
:cam a vso:CameraView ; vso:angle "eye_level" ; vso:framing "wide_shot" .
:lamp a vso:PhysicalObject ;
      vso:individuation vso:Generic ; vso:animacy vso:Inert ;
      vso:countability vso:Count ;
      vso:position3d "1.5,2.0" ; vso:scale3d "big" ; vso:rotation "0,0,0,0,0" .
"""
        _conforms, findings = self._shacl(body)
        self.assertEqual(len(findings), 3, findings)
        paths = [f["result_path"] for f in findings]
        self.assertEqual(paths, sorted(paths))
        for _ in range(2):
            _c, again = self._shacl(body)
            self.assertEqual(again, findings)

    def test_an_owl_clash_is_one_record_naming_both_classes(self) -> None:
        findings = vr.owl_findings(self._graph(":x a vso:Frame, vso:Entity ."))
        self.assertTrue(findings)
        found = findings[0]
        self.assertEqual(found["gate"], "owl-consistency")
        self.assertEqual(found["rule"], "vson/owl-consistency/disjoint-classes")
        self.assertEqual(found["focus_node"], "https://example.org/scene#x")
        self.assertIn("inferred into both", found["message"])

    def test_a_c2_orphan_is_a_record_about_a_term_not_a_node(self) -> None:
        findings = vr.c2_findings(
            self._graph(":q a vso:Quality ; vso:dimension vso:Ambience .")
        )
        self.assertEqual(len(findings), 1, findings)
        found = findings[0]
        self.assertEqual(found["rule"], "vson/c2/orphan-term")
        self.assertIsNone(found["focus_node"])
        self.assertEqual(found["value"], "https://w3id.org/vson/v1/ontology#Ambience")

    def test_a_conformant_document_reports_no_gate_and_no_findings(self) -> None:
        report = vr.report_for(
            os.path.join(ROOT, "examples/throne_room.ttl"),
            os.path.join(ROOT, vr.DEFAULT_SHAPES),
            "examples/throne_room.ttl",
        )
        self.assertTrue(report["conforms"])
        self.assertIsNone(report["gate"])
        self.assertEqual(report["findings"], [])


@unittest.skipUnless(rdflib and vr, "rdflib + pyshacl required")
class ExitCodeTests(unittest.TestCase):
    """0 conformant, 1 a real verdict against the document, 2 no verdict.

    The CLI reads the same three, and reads 1-vs-2 off the JSON document rather
    than off a summary line — so an exit 2 that still printed a report would be
    a misreported verdict, not a cosmetic slip.
    """

    def _run(self, rel: str) -> int:
        """The report is the module's product; here only the code is under test."""
        with contextlib.redirect_stdout(io.StringIO()):
            return vr.main([os.path.join(ROOT, rel)])

    def test_a_conformant_document_exits_0(self) -> None:
        self.assertEqual(self._run("examples/throne_room.ttl"), 0)

    def test_a_violating_document_exits_1(self) -> None:
        self.assertEqual(self._run("tests/fixtures/bad_no_viewer.ttl"), 1)

    def test_an_unreadable_input_exits_2(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self._run("no/such/scene.ttl"), 2)


class GoldenTests(unittest.TestCase):
    """The frozen reports must stay *valid*, not merely stable."""

    def test_the_json_golden_carries_the_documented_record_fields(self) -> None:
        doc = read_golden("bad_no_viewer.json")
        self.assertEqual(doc["report"], "vson-validate/1")
        self.assertEqual(doc["profile"], "strict")
        self.assertFalse(doc["conforms"])
        finding = doc["files"][0]["findings"][0]
        for field in (
            "gate",
            "rule",
            "severity",
            "message",
            "shape",
            "constraint",
            "focus_node",
            "result_path",
            "value",
            "location",
        ):
            self.assertIn(field, finding)
        self.assertEqual(finding["location"]["resolved_from"], "penman-variable")

    def test_the_sarif_golden_is_minimal_valid_2_1_0(self) -> None:
        # Required by the SARIF 2.1.0 schema on the path this tool emits:
        # sarifLog.version + .runs (§3.13), run.tool (§3.14), tool.driver
        # (§3.18), toolComponent.name (§3.19), result.message (§3.27),
        # message.text (§3.11). ruleId / level / locations are optional in the
        # schema and required in practice by every scanner, so they are checked
        # on the same footing.
        log = read_golden("bad_no_viewer.sarif")
        self.assertEqual(log["version"], "2.1.0")
        self.assertTrue(log["runs"])
        run = log["runs"][0]
        driver = run["tool"]["driver"]
        self.assertEqual(driver["name"], "vson")
        self.assertTrue(run["results"])
        for result in run["results"]:
            self.assertIsInstance(result["message"]["text"], str)
            self.assertIsInstance(result["ruleId"], str)
            self.assertIn(result["level"], ("none", "note", "warning", "error"))
            location = result["locations"][0]["physicalLocation"]
            self.assertTrue(location["artifactLocation"]["uri"])
            self.assertGreaterEqual(location["region"]["startLine"], 1)
            # Every result points at a rule the driver declares, at the index
            # it names — a scanner reads the description from there.
            self.assertEqual(
                driver["rules"][result["ruleIndex"]]["id"], result["ruleId"]
            )

    def test_the_sarif_golden_declares_how_it_counts_columns(self) -> None:
        # SARIF defaults columnKind to utf16CodeUnits; the resolver counts
        # Unicode scalar values. Left undeclared, every column past a multi-byte
        # character would be silently off.
        log = read_golden("bad_no_viewer.sarif")
        self.assertEqual(log["runs"][0]["columnKind"], "unicodeCodePoints")


if __name__ == "__main__":
    unittest.main()
