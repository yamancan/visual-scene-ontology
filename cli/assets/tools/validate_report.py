#!/usr/bin/env python3
"""Structured records for the three `vson validate` gates — one per violation.

`vson validate` prints `OK` / `FAIL` lines and forwards each checker's own
human-readable report. That is what a person reads. A build cannot read it: to
fail a pull request on the offending line, a caller needs the violation broken
into fields — which shape fired, on which node, under which path, at which
severity — and this module is where that shape lives (docs/vson.md §5.16).

It runs the same three gates, in the same order, short-circuiting the same way:

  1. SHACL over `shapes/vson-shapes.ttl` plus the three ontology files, at
     `inference="rdfs"` (C3-C9);
  2. OWL 2 RL disjointness, via `tools.owlrl_check.clashes_for` — the same
     function `vson validate`'s second gate runs, not a re-implementation;
  3. C2 vocabulary closure, via `tools.c2_check.orphans_in` — likewise.

Two settings differ from the CLI's own SHACL gate, and only two. `--abort` is
not passed, because a report of the first violation is not a report; and the
report *graph* is kept rather than the text rendering, because the fields are
in the graph. The conformance verdict is unaffected: `abort_on_first` decides
how many results are collected, never whether the document conforms. Warnings
are not allowed to pass (no `allow_warnings`), which is the CLI gate's
behaviour and not `tools/shacl_helper.py`'s — the helper is deliberately not
reused here for that reason, and because it returns text.

**No line numbers are resolved here.** A `.vson` input reaches this module as
transpiled Turtle in a temp file; the Penman source and its variable positions
are known only to the caller, which is why `cli/src/commands/sourcemap.rs` adds
the `location` field and this module never emits one.

Output — one JSON document on stdout, for one input:

    {"report": "vson-validate-records/1", "path": "<label>",
     "conforms": false, "gate": "shacl", "findings": [ {...}, ... ]}

`gate` names the first gate that failed, or null. Findings are sorted by
(focus_node, result_path, constraint, message) so two runs over one document
are byte-identical — the goldens under `tests/fixtures/validate_report/`
depend on it.

Exit codes
----------
  0  a report was produced and the document conforms.
  1  a report was produced and the document does not.
  2  no report: the input would not parse, a dependency is missing, usage.

The 1-vs-2 split is what `cli/src/commands/validate.rs` reads, and here it
needs no summary-line tell: exit 1 with a parseable JSON document on stdout is
a verdict, and anything else is not.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.validate_report --shapes shapes/vson-shapes.ttl scene.ttl
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

import pyshacl
import rdflib
from rdflib import RDF
from rdflib.namespace import Namespace

from tools import resource
from tools.c2_check import orphans_in
from tools.owlrl_check import clashes_for

ONTOLOGY_FILES = ("ontology/vso.ttl", "ontology/rcc8.ttl", "ontology/allen.ttl")
DEFAULT_SHAPES = "shapes/vson-shapes.ttl"

SH = Namespace("http://www.w3.org/ns/shacl#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")

# The record format this module emits. Bumped only when a field is removed or
# its meaning changes; adding a field is not a break (docs/vson.md §5.16).
RECORDS = "vson-validate-records/1"


def _local(iri: str) -> str:
    """The local name of an IRI — everything after the last `#` or `/`."""
    for sep in ("#", "/"):
        if sep in iri:
            tail = iri.rpartition(sep)[2]
            if tail:
                return tail
    return iri


def _load_graph(path: str) -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(path, format="turtle")
    return g


def ontology() -> rdflib.Graph:
    g = rdflib.Graph()
    for f in ONTOLOGY_FILES:
        g.parse(resource(f), format="turtle")
    return g


def named_shape(shapes: rdflib.Graph, node: Any) -> Optional[str]:
    """The nearest named shape at or above `node` in the shapes graph.

    A property shape is usually a blank node nested inside a named node shape
    (`vss:DirectionalNeedsViewerShape sh:property [ sh:path vso:viewer ... ]`),
    and a violation reports the *inner* node — which names nothing a reader can
    look up. pyshacl hands back the very blank node from the shapes graph we
    passed it, so walking up `?parent ?p <node>` finds the named ancestor.

    That identity is an implementation detail of the engine, not a guarantee of
    the SHACL specification, so a miss is expected and handled: the caller falls
    back to the constraint component, and no rule id is ever invented.
    """
    if isinstance(node, rdflib.URIRef):
        return str(node)
    seen = set()
    current = node
    # Bounded: a shapes graph is a DAG in practice, and the guard is against a
    # cyclic one rather than against depth.
    while isinstance(current, rdflib.BNode) and current not in seen:
        seen.add(current)
        parents = list(shapes.subjects(None, current))
        named = [p for p in parents if isinstance(p, rdflib.URIRef)]
        if named:
            return str(sorted(str(p) for p in named)[0])
        anonymous = [p for p in parents if isinstance(p, rdflib.BNode)]
        if not anonymous:
            return None
        current = sorted(anonymous, key=str)[0]
    return None


def _finding(
    gate: str,
    rule: str,
    severity: str,
    message: str,
    shape: Optional[str] = None,
    constraint: Optional[str] = None,
    focus_node: Optional[str] = None,
    result_path: Optional[str] = None,
    value: Optional[str] = None,
) -> Dict[str, Any]:
    """One record. Key order is the order `--format json` prints them in."""
    return {
        "gate": gate,
        "rule": rule,
        "severity": severity,
        "message": message,
        "shape": shape,
        "constraint": constraint,
        "focus_node": focus_node,
        "result_path": result_path,
        "value": value,
    }


def _sort_key(f: Dict[str, Any]) -> tuple:
    return (
        f["focus_node"] or "",
        f["result_path"] or "",
        f["constraint"] or "",
        f["message"],
    )


def shacl_findings(
    data: rdflib.Graph, shapes: rdflib.Graph, ont: rdflib.Graph
) -> "tuple[bool, List[Dict[str, Any]]]":
    """Gate 1. Returns (conforms, findings)."""
    conforms, report, _text = pyshacl.validate(
        data,
        shacl_graph=shapes,
        ont_graph=ont,
        inference="rdfs",
        abort_on_first=False,
    )
    findings = []
    for result in report.subjects(RDF.type, SH.ValidationResult):
        messages = sorted(str(m) for m in report.objects(result, SH.resultMessage))
        severity = next(report.objects(result, SH.resultSeverity), None)
        constraint = next(report.objects(result, SH.sourceConstraintComponent), None)
        focus = next(report.objects(result, SH.focusNode), None)
        path = next(report.objects(result, SH.resultPath), None)
        value = next(report.objects(result, SH.value), None)
        source = next(report.objects(result, SH.sourceShape), None)
        shape = named_shape(shapes, source) if source is not None else None
        # The rule id a caller groups by. The named shape is the useful name;
        # the constraint component is the honest fallback when the shape is
        # anonymous and cannot be resolved.
        anchor = _local(shape) if shape else _local(str(constraint or "Constraint"))
        findings.append(
            _finding(
                gate="shacl",
                rule="vson/shacl/" + anchor,
                severity=_local(str(severity)).lower() if severity else "violation",
                message=" ".join(messages) if messages else "SHACL constraint violated",
                shape=shape,
                constraint=str(constraint) if constraint else None,
                focus_node=str(focus) if focus is not None else None,
                result_path=str(path) if path is not None else None,
                value=str(value) if value is not None else None,
            )
        )
    return bool(conforms), sorted(findings, key=_sort_key)


def owl_findings(data: rdflib.Graph) -> List[Dict[str, Any]]:
    """Gate 2. The wording mirrors `tools/owlrl_check.py`'s own report lines."""
    findings = []
    for x, a, b in clashes_for(data):
        if a == OWL.sameAs:
            rule, message = (
                "vson/owl-consistency/distinct-yet-same",
                "<{}> and <{}> are asserted distinct yet inferred owl:sameAs".format(
                    x, b
                ),
            )
        elif x == b:
            rule, message = (
                "vson/owl-consistency/irreflexive",
                "<{}> stands in irreflexive <{}> to itself".format(x, a),
            )
        else:
            rule, message = (
                "vson/owl-consistency/disjoint-classes",
                "<{}> is inferred into both <{}> and <{}>".format(x, a, b),
            )
        findings.append(
            _finding(
                gate="owl-consistency",
                rule=rule,
                severity="violation",
                message=message,
                constraint=str(a),
                focus_node=str(x),
                value=str(b),
            )
        )
    return sorted(findings, key=_sort_key)


def c2_findings(data: rdflib.Graph) -> List[Dict[str, Any]]:
    """Gate 3. An orphan term has no focus node: the term itself is the finding."""
    return [
        _finding(
            gate="c2",
            rule="vson/c2/orphan-term",
            severity="violation",
            message=(
                "<{}> is asserted but declared in no ontology file "
                "(clause C2, docs/vson.md §2)".format(term)
            ),
            value=term,
        )
        for term in orphans_in(data)
    ]


def report_for(path: str, shapes_path: str, label: str) -> Dict[str, Any]:
    """Every finding for one Turtle document, gates short-circuited in order."""
    data = _load_graph(path)
    shapes = _load_graph(shapes_path)
    conforms, findings = shacl_findings(data, shapes, ontology())
    gate = None
    if not conforms or findings:
        gate = "shacl"
    else:
        findings = owl_findings(data)
        if findings:
            gate = "owl-consistency"
        else:
            findings = c2_findings(data)
            if findings:
                gate = "c2"
    return {
        "report": RECORDS,
        "path": label,
        "conforms": gate is None,
        "gate": gate,
        "findings": findings,
    }


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.validate_report",
        description=(
            "Structured records for the three `vson validate` gates "
            "(docs/vson.md §5.16). Reads no image."
        ),
    )
    ap.add_argument("file", help="the Turtle document to check")
    ap.add_argument(
        "--shapes",
        default=resource(DEFAULT_SHAPES),
        help="shapes file (default: the strict profile, {})".format(DEFAULT_SHAPES),
    )
    ap.add_argument(
        "--label",
        help="report the input under this name (for a caller that transpiled it)",
    )
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = report_for(args.file, args.shapes, args.label or args.file)
    except Exception as exc:  # noqa: BLE001 — every failure here is "no verdict"
        print(
            "validate-report: could not check {}: {}: {}".format(
                args.file, type(exc).__name__, exc
            ),
            file=sys.stderr,
        )
        return 2
    sys.stdout.write(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    )
    return 0 if report["conforms"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
