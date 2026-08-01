"""GitHub annotations + step summary from a validate report (scripts/gha_annotate.py).

The workflow-command syntax is the whole point of this script, and it is
unforgiving: one unescaped `,` inside a property value and GitHub reads the
rest of the message as another property, so the annotation lands on nothing.
None of that is visible in a green CI run — a malformed command is *ignored*,
not reported — which is exactly why it is pinned here rather than left to be
noticed on a pull request.

The reader half matters for the same reason: `--format sarif` and
`--format json` are two shapes of one report, and a caller that asked for SARIF
must still get its annotations.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

import gha_annotate as ga  # noqa: E402 — path shim above

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_DIR = os.path.join(ROOT, "tests/fixtures/validate_report")


def finding(**overrides) -> dict:
    base = {
        "file": "scenes/a.vson",
        "line": 12,
        "column": 4,
        "command": "error",
        "rule": "vson/shacl/DirectionalNeedsViewerShape",
        "gate": "shacl",
        "message": "needs a viewer",
    }
    base.update(overrides)
    return base


class AnnotationTests(unittest.TestCase):
    def test_a_located_finding_names_the_file_line_and_column(self) -> None:
        self.assertEqual(
            ga.annotation(finding()),
            "::error file=scenes/a.vson,line=12,col=4,"
            "title=vson/shacl/DirectionalNeedsViewerShape::needs a viewer",
        )

    def test_an_unlocated_finding_annotates_the_file_and_omits_the_region(self) -> None:
        # A Turtle subject the scan could not place: the file is still worth
        # annotating, and a guessed line 1 would point at a prefix declaration.
        command = ga.annotation(finding(line=None, column=None))
        self.assertIn("file=scenes/a.vson", command)
        self.assertNotIn("line=", command)

    def test_a_column_is_dropped_when_there_is_no_line_to_hang_it_on(self) -> None:
        self.assertNotIn("col=", ga.annotation(finding(line=None, column=9)))

    def test_property_values_escape_the_delimiters_of_the_command(self) -> None:
        # `:` and `,` are what separates a property from the next one, so a rule
        # id or a path containing either would truncate the annotation.
        command = ga.annotation(finding(rule="a:b,c", file="x,y.vson"))
        self.assertIn("title=a%3Ab%2Cc", command)
        self.assertIn("file=x%2Cy.vson", command)

    def test_the_message_escapes_newlines_and_percent(self) -> None:
        command = ga.annotation(finding(message="100% over\ntwo lines"))
        self.assertTrue(command.endswith("100%25 over%0Atwo lines"))
        # A literal newline in the middle would end the workflow command.
        self.assertEqual(len(command.splitlines()), 1)

    def test_severity_decides_the_command_kind(self) -> None:
        self.assertEqual(ga.SEVERITY_TO_COMMAND["violation"], "error")
        self.assertEqual(ga.SEVERITY_TO_COMMAND["warning"], "warning")
        self.assertEqual(ga.SEVERITY_TO_COMMAND["info"], "notice")
        self.assertEqual(ga.LEVEL_TO_COMMAND["error"], "error")


class ReaderTests(unittest.TestCase):
    """Both report shapes, read from the frozen goldens the CLI produced."""

    def _golden(self, name: str) -> dict:
        with open(os.path.join(GOLDEN_DIR, name), encoding="utf-8") as fh:
            return json.load(fh)

    def test_the_two_formats_yield_the_same_annotation(self) -> None:
        from_json = ga.findings_from_json(self._golden("bad_no_viewer.json"))
        from_sarif = ga.findings_from_sarif(self._golden("bad_no_viewer.sarif"))
        self.assertEqual(len(from_json), 1)
        self.assertEqual(ga.annotation(from_json[0]), ga.annotation(from_sarif[0]))
        self.assertIn("line=26", ga.annotation(from_json[0]))

    def test_a_json_report_with_no_findings_yields_none(self) -> None:
        clean = {"files": [{"path": "a.vson", "findings": []}]}
        self.assertEqual(ga.findings_from_json(clean), [])


class SummaryTests(unittest.TestCase):
    def test_a_clean_run_says_what_a_green_result_does_not_establish(self) -> None:
        table = ga.summary_table([], files=3)
        self.assertIn("3 document(s) conform", table)
        self.assertIn("§2.1", table)
        self.assertIn("not the picture", table)

    def test_a_violation_becomes_a_row(self) -> None:
        table = ga.summary_table([finding()], files=1)
        self.assertIn("| `scenes/a.vson` | 12 | shacl |", table)

    def test_a_pipe_in_a_message_cannot_break_the_table(self) -> None:
        table = ga.summary_table([finding(message="a | b")], files=1)
        self.assertIn("a \\| b", table)


class MainTests(unittest.TestCase):
    def _run(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = ga.main(argv)
        return code, buffer.getvalue()

    def test_it_writes_annotations_the_summary_and_the_step_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = os.path.join(tmp, "summary.md")
            outputs = os.path.join(tmp, "outputs.txt")
            code, printed = self._run(
                [
                    "--report",
                    os.path.join(GOLDEN_DIR, "bad_no_viewer.json"),
                    "--format",
                    "json",
                    "--summary",
                    summary,
                    "--github-output",
                    outputs,
                ]
            )
            self.assertEqual(code, 0, "the CLI's exit code is the verdict, not this")
            self.assertTrue(printed.startswith("::error "))
            with open(summary, encoding="utf-8") as fh:
                self.assertIn("1 violation(s)", fh.read())
            with open(outputs, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "findings=1\ndocuments=1\n")

    def test_no_annotate_writes_the_summary_and_stays_silent(self) -> None:
        # The job that *expects* a failure still wants the table; what it must
        # not do is flag its own fixture as an error on the pull request.
        with tempfile.TemporaryDirectory() as tmp:
            summary = os.path.join(tmp, "summary.md")
            _code, printed = self._run(
                [
                    "--report",
                    os.path.join(GOLDEN_DIR, "bad_no_viewer.sarif"),
                    "--format",
                    "sarif",
                    "--no-annotate",
                    "--summary",
                    summary,
                ]
            )
            self.assertEqual(printed, "")
            self.assertTrue(os.path.getsize(summary) > 0)

    def test_the_caller_may_state_how_many_documents_were_checked(self) -> None:
        # A SARIF log records results, not the clean files beside them, so a
        # passing run counted from the log alone would report zero documents —
        # "0 document(s) conform" under a green check. The action passes the
        # number it globbed.
        clean_sarif = {"runs": [{"results": []}]}
        with tempfile.TemporaryDirectory() as tmp:
            report = os.path.join(tmp, "clean.sarif")
            summary = os.path.join(tmp, "summary.md")
            with open(report, "w", encoding="utf-8") as fh:
                json.dump(clean_sarif, fh)
            self.assertEqual(ga.documents_in(clean_sarif, "sarif"), 0)
            self._run(
                [
                    "--report",
                    report,
                    "--format",
                    "sarif",
                    "--documents",
                    "17",
                    "--summary",
                    summary,
                ]
            )
            with open(summary, encoding="utf-8") as fh:
                self.assertIn("17 document(s) conform", fh.read())

    def test_an_unreadable_report_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()):
            missing = os.path.join(tmp, "nope.json")
            self.assertEqual(ga.main(["--report", missing]), 2)
            broken = os.path.join(tmp, "broken.json")
            with open(broken, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            self.assertEqual(ga.main(["--report", broken]), 2)

    def test_the_annotation_flood_is_capped_and_the_cap_is_announced(self) -> None:
        # GitHub drops annotations past a limit *silently*; the summary table
        # keeps every finding, so the notice is what tells a reader the log is
        # not the whole story.
        many = {
            "files": [
                {
                    "path": "a.vson",
                    "findings": [
                        {
                            "gate": "shacl",
                            "rule": "vson/shacl/X",
                            "severity": "violation",
                            "message": "m%d" % i,
                            "location": {"line": i + 1, "column": 1},
                        }
                        for i in range(ga.MAX_ANNOTATIONS + 3)
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            report = os.path.join(tmp, "many.json")
            with open(report, "w", encoding="utf-8") as fh:
                json.dump(many, fh)
            _code, printed = self._run(["--report", report, "--format", "json"])
        lines = printed.strip().split("\n")
        self.assertEqual(len(lines), ga.MAX_ANNOTATIONS + 1)
        self.assertIn("3 further violation(s)", lines[-1])


if __name__ == "__main__":
    unittest.main()
