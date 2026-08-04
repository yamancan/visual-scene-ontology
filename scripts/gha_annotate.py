#!/usr/bin/env python3
"""Turn a `vson validate` report into GitHub annotations and a step summary.

`.github/actions/validate` runs the CLI and then runs this. Two outputs, both
of them things a workflow command can produce on any repository — no GitHub
Advanced Security, no code-scanning upload, nothing whose delivery depends on
the repository's visibility or on the plan it is billed under:

  * **annotations** — one `::error file=…,line=…,col=…::message` per finding.
    GitHub renders those inline on the diff of the offending line, which is the
    whole point of resolving a position in the first place.
  * **a step summary** — a markdown table appended to `$GITHUB_STEP_SUMMARY`,
    so the run page says what failed without anybody opening the log.

Reads either report format. `sarif` is read through its own shape (results,
locations, ruleId) rather than being converted first, because a caller that
asked for SARIF wants the SARIF file to be the artifact.

Exit codes
----------
  0  the report was read (whatever it said — the CLI's own exit code is the
     build's verdict, and this must not overwrite it).
  2  the report is missing or unreadable.

Usage:
  python3 scripts/gha_annotate.py --report vson.json --format json
  python3 scripts/gha_annotate.py --report vson.sarif --format sarif --no-annotate
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

# How many annotations to emit. GitHub renders at most 10 error annotations per
# step on the diff view and drops the rest silently; the summary table carries
# every finding, so the cap is on the noisy channel only.
MAX_ANNOTATIONS = 50

LEVEL_TO_COMMAND = {
    "error": "error",
    "warning": "warning",
    "note": "notice",
}
SEVERITY_TO_COMMAND = {
    "violation": "error",
    "warning": "warning",
    "info": "notice",
}


def escape_data(text: str) -> str:
    """A workflow command's message body (GitHub's documented escapes)."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text: str) -> str:
    """A workflow command's property value — `:` and `,` end it otherwise."""
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def findings_from_json(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for entry in doc.get("files", []):
        for finding in entry.get("findings", []):
            location = finding.get("location") or {}
            out.append(
                {
                    "file": entry.get("path", ""),
                    "line": location.get("line"),
                    "column": location.get("column"),
                    "command": SEVERITY_TO_COMMAND.get(
                        finding.get("severity", ""), "error"
                    ),
                    "rule": finding.get("rule", ""),
                    "gate": finding.get("gate", ""),
                    "message": finding.get("message", ""),
                }
            )
    return out


def findings_from_sarif(log: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for run in log.get("runs", []):
        for result in run.get("results", []):
            physical = {}
            for location in result.get("locations", []):
                physical = location.get("physicalLocation", {})
                break
            region = physical.get("region", {})
            out.append(
                {
                    "file": physical.get("artifactLocation", {}).get("uri", ""),
                    "line": region.get("startLine"),
                    "column": region.get("startColumn"),
                    "command": LEVEL_TO_COMMAND.get(result.get("level", ""), "error"),
                    "rule": result.get("ruleId", ""),
                    "gate": result.get("properties", {}).get("gate", ""),
                    "message": result.get("message", {}).get("text", ""),
                }
            )
    return out


def annotation(finding: Dict[str, Any]) -> str:
    """One workflow command. A finding with no position annotates the file."""
    properties = ["file=" + escape_property(finding["file"])]
    if finding.get("line"):
        properties.append("line=%d" % finding["line"])
        if finding.get("column"):
            properties.append("col=%d" % finding["column"])
    if finding.get("rule"):
        properties.append("title=" + escape_property(finding["rule"]))
    return "::{} {}::{}".format(
        finding["command"], ",".join(properties), escape_data(finding["message"])
    )


def summary_table(findings: List[Dict[str, Any]], files: int) -> str:
    """The markdown a reader sees on the run page."""
    if not findings:
        return (
            "### VSON validate\n\n"
            "**{} document(s) conform.** SHACL, OWL 2 RL and C2 vocabulary "
            "closure all passed.\n\n"
            "This checks the graph, not the picture — a conformant document "
            "may still describe an image incorrectly "
            "(docs/vson.md §2.1).\n".format(files)
        )
    rows = [
        "### VSON validate",
        "",
        "**{} violation(s) across {} document(s).**".format(len(findings), files),
        "",
        "| File | Line | Gate | Rule | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for finding in findings:
        rows.append(
            "| `{}` | {} | {} | `{}` | {} |".format(
                finding["file"],
                finding.get("line") or "—",
                finding.get("gate") or "—",
                finding.get("rule") or "—",
                finding["message"].replace("|", "\\|"),
            )
        )
    rows.append("")
    return "\n".join(rows)


def documents_in(doc: Dict[str, Any], fmt: str) -> int:
    if fmt == "json":
        return len(doc.get("files", []))
    # A SARIF log records results, not the clean documents beside them, so the
    # count it can honestly report is the number of files with a finding.
    return len({f["file"] for f in findings_from_sarif(doc)})


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 scripts/gha_annotate.py",
        description="GitHub annotations + step summary from a vson validate report.",
    )
    ap.add_argument("--report", required=True, help="the report file the CLI wrote")
    ap.add_argument("--format", choices=("json", "sarif"), default="json")
    ap.add_argument(
        "--no-annotate",
        action="store_true",
        help="write the summary only — for a job that expects the failure",
    )
    ap.add_argument(
        "--summary",
        default=os.environ.get("GITHUB_STEP_SUMMARY", ""),
        help="file to append the markdown table to (default: $GITHUB_STEP_SUMMARY)",
    )
    ap.add_argument(
        "--github-output",
        default="",
        help="file to append `findings=` and `documents=` to (the step's outputs)",
    )
    ap.add_argument(
        "--documents",
        type=int,
        default=None,
        help=(
            "how many documents were checked. The caller knows; a SARIF log "
            "does not (it records results, not the clean files beside them), "
            "so without this a clean SARIF run could only say zero"
        ),
    )
    args = ap.parse_args(argv)

    try:
        with open(args.report, encoding="utf-8") as fh:
            document = json.load(fh)
    except (OSError, ValueError) as exc:
        print(
            "gha-annotate: could not read {}: {}".format(args.report, exc),
            file=sys.stderr,
        )
        return 2

    findings = (
        findings_from_json(document)
        if args.format == "json"
        else findings_from_sarif(document)
    )
    if not args.no_annotate:
        for finding in findings[:MAX_ANNOTATIONS]:
            print(annotation(finding))
        if len(findings) > MAX_ANNOTATIONS:
            print(
                "::notice::{} further violation(s) are in the report and the summary "
                "table; only the first {} are annotated.".format(
                    len(findings) - MAX_ANNOTATIONS, MAX_ANNOTATIONS
                )
            )
    documents = (
        args.documents
        if args.documents is not None
        else documents_in(document, args.format)
    )
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(summary_table(findings, documents))
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write("findings={}\ndocuments={}\n".format(len(findings), documents))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
