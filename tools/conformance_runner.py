#!/usr/bin/env python3
"""`make conformance` — run the VSON v1 conformance suite. docs/vson.md §2.2.

The suite is `tests/conformance/manifest.ttl`: an RDF manifest in the shape of
the W3C SHACL test suite, where every entry names an input document and the
verdict that document MUST get. This module is what executes it, and — with
`--coverage-table` — what generates the coverage table §2.2 publishes.

What it establishes, in order:

  1. **The manifest is well formed.** It parses, its `mf:entries` list has the
     length it declares, and every `vsont:` term it uses is declared in
     `tests/conformance/vocabulary.ttl`. That last check is clause C2 asked of
     the suite's own manifest: a term nobody declared is a typo, not a feature.
  2. **Every entry gets its pinned verdict.** Parse tests are run through the
     reference transpiler for their surface; a §D.7 row identifier is checked
     against the message column the *specification* carries, extracted at run
     time, so a manifest cannot claim a row the spec does not define.
     Validation tests are run through the three gates of §2.1 and compared
     against the pinned report — exhaustively, so an over-firing shape fails
     here rather than passing unnoticed. Equivalence tests re-derive the
     RDFC-1.0 hash of §4.6. Export tests compare bytes.
  3. **The coverage claim is true.** Every named shape in
     `shapes/vson-shapes.ttl` is exercised by a negative entry or is listed in
     the manifest's exemptions with a reason; every §D.7 row has a negative
     entry; every closed enumeration of §5.12 has a positive and a negative;
     and the coverage table in docs/vson.md §2.2 is byte-identical to the one
     this suite generates. A new shape with no negative entry fails here,
     which is the whole point of generating the table rather than writing it.

Engines
-------
The SHACL gate runs behind a plugin seam. `--engine pyshacl` is the only
adapter this repository ships and it is the default; `--list-engines` prints
what is registered. A second engine is the cross-validation this suite was
asked for and does not have: Apache Jena's SHACL CLI needs a JVM and a
downloaded distribution, which is not something `make check` may assume on a
contributor's machine or pay for on every CI run, and no pure-Python second
implementation exists. The seam is real and the slot is open — `--engine
<name>` for an unregistered name exits 2 with that message rather than
quietly running pyshacl and calling the result cross-validated. Registering
one is `register(Engine())`; the protocol is four methods and is documented on
the `Engine` base class.

Exit codes
----------
  0  every entry got its pinned verdict and the coverage claim holds.
  1  at least one did not — the failing entries are named.
  2  no verdict: the manifest would not parse, a dependency is missing, or the
     requested engine has no adapter. A run that could not happen is not a
     pass.

Usage
-----
  python3 -m tools.conformance_runner
  python3 -m tools.conformance_runner --filter validate-neg --verbose
  python3 -m tools.conformance_runner --coverage-table      # §2.2's table
  python3 -m tools.conformance_runner --coverage-map        # clause -> entry ids
  python3 -m tools.conformance_runner --list-engines
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Dict, List, Optional, Sequence, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE = os.path.join(REPO, "tests", "conformance")
MANIFEST = os.path.join(SUITE, "manifest.ttl")
VOCABULARY = os.path.join(SUITE, "vocabulary.ttl")
SPEC = os.path.join(REPO, "docs", "vson.md")

MF = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#"
SHT = "http://www.w3.org/ns/shacl-test#"
SH = "http://www.w3.org/ns/shacl#"
VSONT = "https://w3id.org/vson/v1/conformance#"
TESTS = "https://w3id.org/vson/v1/conformance/tests#"


class Unavailable(Exception):
    """Exit 2 — the run could not happen, which is not a verdict."""


class Failure(Exception):
    """Exit 1 — the run happened and contradicted the manifest."""


# ---------------------------------------------------------------------------
# The engine seam
# ---------------------------------------------------------------------------


class Engine:
    """A SHACL implementation the suite can run its validation entries against.

    Four methods, and the reason each exists:

      * `name` — what `--engine` selects and what the report prints. A run
        that does not say which engine produced it is not evidence about any
        engine.
      * `unavailable()` — returns None when the engine can run here, or a
        sentence saying why it cannot. Never raises: "not installed" is an
        answer the runner reports as exit 2, not a crash.
      * `validate(data, shapes, ont)` — returns `(conforms, findings)` where a
        finding is the record shape of `tools/validate_report.py` (docs/vson.md
        §5.16), so an adapter's job is to translate its engine's report into
        that shape rather than to invent one.
      * `describe()` — a version string for the report header.

    An adapter MUST run the gate the specification defines: SHACL over the
    given shapes graph with the RDFS entailment of C3 (`inference="rdfs"`),
    warnings counted as non-conformance, and no early abort. An engine that
    computes something else may agree with pyshacl by accident and the
    agreement would establish nothing.
    """

    name = "abstract"

    def unavailable(self) -> Optional[str]:
        return "%s has no adapter in this repository" % self.name

    def describe(self) -> str:
        return self.name

    def validate(self, data, shapes, ont):  # pragma: no cover - abstract
        raise NotImplementedError


class PyshaclEngine(Engine):
    """pyshacl, through the same call `vson validate` makes."""

    name = "pyshacl"

    def unavailable(self) -> Optional[str]:
        try:
            import pyshacl  # noqa: F401
        except ImportError:
            return "pyshacl is not installed (pip install -e \".[dev]\")"
        return None

    def describe(self) -> str:
        import pyshacl

        return "pyshacl %s" % getattr(pyshacl, "__version__", "unknown")

    def validate(self, data, shapes, ont):
        from tools.validate_report import shacl_findings

        return shacl_findings(data, shapes, ont)


ENGINES: Dict[str, Engine] = {}


def register(engine: Engine) -> None:
    """Add an engine to the registry. Called by an adapter module at import."""
    ENGINES[engine.name] = engine


register(PyshaclEngine())


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _rdflib():
    try:
        import rdflib
    except ImportError as exc:  # pragma: no cover - environment
        raise Unavailable("rdflib is not installed: %s" % exc)
    return rdflib


def _path_of(term) -> str:
    """The filesystem path an mf:action IRI denotes."""
    from urllib.parse import unquote, urlparse

    parsed = urlparse(str(term))
    if parsed.scheme != "file":
        raise Failure("action IRI is not a file: IRI: %s" % term)
    return unquote(parsed.path)


def load_graph(path: str):
    rdflib = _rdflib()
    graph = rdflib.Graph()
    graph.parse(path, format="turtle")
    return graph


def document_graph(path: str):
    """The VSON-T graph of a document in any of the three surfaces.

    The transpilers are the reference implementations, called directly: a
    suite that shelled out to the Rust binary would need it built, and the two
    are byte-compared by `make cli-check` anyway.
    """
    rdflib = _rdflib()
    graph = rdflib.Graph()
    graph.parse(data=turtle_of(path), format="turtle")
    return graph


def turtle_of(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    if path.endswith(".x.vson"):
        from tools.vson_x import vson_x

        return vson_x.to_turtle(source)
    if path.endswith(".vson"):
        from tools.penman import vson_penman as vp

        return vp.to_turtle(source)
    return source


# ---------------------------------------------------------------------------
# §D.7 — the error table, read out of the specification
# ---------------------------------------------------------------------------


def error_patterns() -> Dict[str, List[str]]:
    """Row identifier -> the regexes §D.7's Error column translates into.

    The manifest names a row; this is what decides whether the parser actually
    rejected at that row. Reading the message column from docs/vson.md rather
    than copying it here is the same discipline `make grammar-check` follows:
    the spec is the grammar, and a copy of it in a tool is a copy that drifts.

    A template's `<placeholder>` becomes `.*` and the match is anchored at the
    start only — the reference parser appends detail after several of the
    messages ("expected one of [...]") and the specification quotes the stem.
    """
    from tools.grammar import extract_grammar as eg

    body = eg.section(eg.spec_text(), "D.7")
    patterns: Dict[str, List[str]] = {}
    for cells in eg.table_rows(body):
        if len(cells) < 2 or not re.fullmatch(r"E\d+", cells[0]):
            continue
        alternatives = eg._ticked(cells[1])
        if not alternatives:
            raise Failure("§D.7 row %s carries no message" % cells[0])
        patterns[cells[0]] = [
            "".join(
                re.escape(part) if index % 2 == 0 else ".*"
                for index, part in enumerate(re.split(r"(<[^>]*>)", alternative))
            )
            for alternative in alternatives
        ]
    if not patterns:
        raise Failure("§D.7 carries no error rows")
    return patterns


def row_of(message: str, patterns: Dict[str, List[str]]) -> List[str]:
    return sorted(
        row
        for row, alternatives in patterns.items()
        if any(re.match(pattern, message) for pattern in alternatives)
    )


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


class Entry:
    """One manifest entry, read into the fields the runners need."""

    def __init__(self, graph, node):
        rdflib = _rdflib()
        self.node = node
        self.id = str(node)[len(TESTS):] if str(node).startswith(TESTS) else str(node)
        self.kind = _local(str(next(graph.objects(node, rdflib.RDF.type))))
        self.name = str(next(graph.objects(node, rdflib.URIRef(MF + "name")), ""))
        self.clauses = sorted(
            str(c) for c in graph.objects(node, rdflib.URIRef(VSONT + "clause"))
        )
        self.sections = sorted(
            str(s) for s in graph.objects(node, rdflib.URIRef(VSONT + "section"))
        )
        self.shape = next(graph.objects(node, rdflib.URIRef(VSONT + "shape")), None)
        self.enums = sorted(
            _local(str(e)) for e in graph.objects(node, rdflib.URIRef(VSONT + "enum"))
        )
        self.action = next(graph.objects(node, rdflib.URIRef(MF + "action")), None)
        self.result = next(graph.objects(node, rdflib.URIRef(MF + "result")), None)
        self.graph = graph

    # -- action / result accessors -----------------------------------------

    def obj(self, subject, predicate):
        rdflib = _rdflib()
        return next(self.graph.objects(subject, rdflib.URIRef(predicate)), None)

    def negative(self) -> bool:
        """Does this entry expect a rejection or a non-conforming verdict?"""
        rdflib = _rdflib()
        if self.kind in ("ParsePTest", "ParseXTest"):
            return self.result != rdflib.URIRef(VSONT + "Accepted")
        if self.kind == "ValidationTest":
            return self.obj(self.result, SH + "conforms") == rdflib.Literal(False)
        return False


def _local(iri: str) -> str:
    for separator in ("#", "/"):
        if separator in iri:
            tail = iri.rpartition(separator)[2]
            if tail:
                return tail
    return iri


# ---------------------------------------------------------------------------
# The runners, one per test type
# ---------------------------------------------------------------------------


class Suite:
    def __init__(self, engine: Engine, manifest_path: str = MANIFEST):
        self.engine = engine
        self.manifest_path = manifest_path
        self.graph = load_graph(manifest_path)
        self.vocabulary = load_graph(VOCABULARY)
        self.patterns = error_patterns()
        self.shapes = load_graph(os.path.join(REPO, "shapes", "vson-shapes.ttl"))
        from tools.validate_report import ontology

        self.ontology = ontology()
        self.entries = self._entries()

    # -- manifest structure -------------------------------------------------

    def _entries(self) -> List[Entry]:
        rdflib = _rdflib()
        from rdflib.collection import Collection

        manifests = list(self.graph.subjects(rdflib.RDF.type, rdflib.URIRef(MF + "Manifest")))
        if len(manifests) != 1:
            raise Failure("expected exactly one mf:Manifest, found %d" % len(manifests))
        self.manifest = manifests[0]
        head = next(self.graph.objects(self.manifest, rdflib.URIRef(MF + "entries")), None)
        if head is None:
            raise Failure("the manifest declares no mf:entries")
        nodes = list(Collection(self.graph, head))
        counts = list(self.graph.objects(self.manifest, rdflib.URIRef(VSONT + "entryCount")))
        if len(counts) > 1:
            raise Failure(
                "the manifest states %d entry counts; one document, one count"
                % len(counts)
            )
        if counts and int(counts[0]) != len(nodes):
            raise Failure(
                "the manifest declares %s entries and lists %d"
                % (counts[0], len(nodes))
            )
        return [Entry(self.graph, node) for node in nodes]

    def check_vocabulary(self) -> None:
        """Clause C2, asked of the manifest: no undeclared vsont: term."""
        rdflib = _rdflib()
        used = {
            str(term)
            for triple in self.graph
            for term in triple
            if isinstance(term, rdflib.URIRef) and str(term).startswith(VSONT)
        }
        declared = {
            str(subject)
            for subject in self.vocabulary.subjects(None, None)
            if str(subject).startswith(VSONT)
        }
        orphans = sorted(term[len(VSONT):] for term in used - declared)
        if orphans:
            raise Failure(
                "manifest.ttl uses %d vsont: term(s) vocabulary.ttl does not "
                "declare: %s" % (len(orphans), ", ".join(orphans))
            )

    # -- per-type runners ---------------------------------------------------

    def run_parse(self, entry: Entry) -> None:
        rdflib = _rdflib()
        path = _path_of(entry.action)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        if entry.kind == "ParsePTest":
            from tools.penman import vson_penman as reference

        else:
            from tools.vson_x import vson_x as reference
        error = None
        try:
            reference.to_turtle(source)
        except Exception as exc:  # noqa: BLE001 - any rejection is a rejection
            error = str(exc)

        if entry.result == rdflib.URIRef(VSONT + "Accepted"):
            if error is not None:
                raise Failure("expected acceptance, parser said: %s" % error)
            return
        if error is None:
            raise Failure("expected a rejection and the parser accepted the input")

        row = entry.obj(entry.result, VSONT + "errorRow")
        if row is not None:
            matched = row_of(error, self.patterns)
            if len(matched) != 1:
                raise Failure(
                    "the message %r matches %s §D.7 rows (%s); the identifier a "
                    "manifest pins has to name exactly one"
                    % (error, len(matched), ", ".join(matched) or "no")
                )
            if matched[0] != str(row):
                raise Failure(
                    "expected §D.7 %s, the parser raised %s: %s"
                    % (row, matched[0], error)
                )
            return
        message = entry.obj(entry.result, VSONT + "errorMessage")
        if message is None:
            raise Failure("the expected rejection pins neither a row nor a message")
        if error != str(message):
            raise Failure("expected message %r, got %r" % (str(message), error))

    def run_validation(self, entry: Entry) -> None:
        rdflib = _rdflib()
        data_path = _path_of(entry.obj(entry.action, SHT + "dataGraph"))
        shapes_path = _path_of(entry.obj(entry.action, SHT + "shapesGraph"))
        shapes = (
            self.shapes
            if os.path.realpath(shapes_path)
            == os.path.realpath(os.path.join(REPO, "shapes", "vson-shapes.ttl"))
            else load_graph(shapes_path)
        )
        data = document_graph(data_path)

        conforms, findings = self.engine.validate(data, shapes, self.ontology)
        gate = "shacl" if (not conforms or findings) else None
        if gate is None:
            from tools.validate_report import c2_findings, owl_findings

            findings = owl_findings(data)
            gate = "owl-consistency" if findings else None
            if gate is None:
                findings = c2_findings(data)
                gate = "c2" if findings else None

        expected_conforms = entry.obj(entry.result, SH + "conforms")
        if expected_conforms == rdflib.Literal(True):
            if gate is not None:
                raise Failure(
                    "expected a conforming document; the %s gate reported %d "
                    "finding(s), first: %s"
                    % (gate, len(findings), findings[0]["message"])
                )
            return
        if gate is None:
            raise Failure("expected a non-conforming document and every gate passed")

        expected_gate = entry.obj(entry.result, VSONT + "gate")
        if expected_gate is not None and _local(str(expected_gate)) != gate:
            raise Failure(
                "expected the %s gate to speak first, %s did"
                % (_local(str(expected_gate)), gate)
            )
        self._compare_results(entry, findings)

    def _compare_results(self, entry: Entry, findings: List[dict]) -> None:
        """Exhaustive comparison: one pinned result per finding, and back."""
        rdflib = _rdflib()
        pinned = list(self.graph.objects(entry.result, rdflib.URIRef(SH + "result")))
        if len(pinned) != len(findings):
            raise Failure(
                "the manifest pins %d result(s) and the run produced %d: %s"
                % (
                    len(pinned),
                    len(findings),
                    "; ".join(
                        "%s/%s" % (_local(f["shape"] or f["rule"]), _local(f["constraint"] or "-"))
                        for f in findings
                    ),
                )
            )
        remaining = list(findings)
        for result in pinned:
            match = None
            for finding in remaining:
                if self._matches(result, finding):
                    match = finding
                    break
            if match is None:
                raise Failure(
                    "no finding matches the pinned result %s"
                    % self._render_expected(result)
                )
            remaining.remove(match)

    def _matches(self, result, finding: dict) -> bool:
        checks = (
            (SH + "sourceShape", "shape"),
            (SH + "sourceConstraintComponent", "constraint"),
            (SH + "resultPath", "result_path"),
            (SH + "focusNode", "focus_node"),
            (SH + "value", "value"),
        )
        for predicate, field in checks:
            expected = self.entry_obj(result, predicate)
            if expected is not None and str(expected) != (finding.get(field) or ""):
                return False
        severity = self.entry_obj(result, SH + "resultSeverity")
        if severity is not None and _local(str(severity)).lower() != finding["severity"]:
            return False
        rule = self.entry_obj(result, VSONT + "rule")
        if rule is not None and str(rule) != finding.get("rule"):
            return False
        kind = self.entry_obj(result, VSONT + "focusNodeKind")
        if kind is not None:
            focus = finding.get("focus_node") or ""
            is_blank = not focus.startswith("http")
            if (_local(str(kind)) == "BlankNode") != is_blank:
                return False
        return True

    def entry_obj(self, subject, predicate):
        rdflib = _rdflib()
        return next(self.graph.objects(subject, rdflib.URIRef(predicate)), None)

    def _render_expected(self, result) -> str:
        parts = []
        for predicate in (
            SH + "sourceShape",
            SH + "sourceConstraintComponent",
            SH + "resultPath",
            SH + "resultSeverity",
            VSONT + "rule",
        ):
            value = self.entry_obj(result, predicate)
            if value is not None:
                parts.append(_local(str(value)))
        return "/".join(parts) or "(empty)"

    def run_equivalence(self, entry: Entry) -> None:
        from rdflib.collection import Collection

        from tools.canon import canonical_hash

        documents = [_path_of(term) for term in Collection(self.graph, entry.action)]
        expected = str(entry.obj(entry.result, VSONT + "canonicalHash"))
        digests = [canonical_hash(document_graph(path)) for path in documents]
        for path, digest in zip(documents, digests):
            if digest != expected:
                raise Failure(
                    "%s canonicalizes to %s, the manifest pins %s"
                    % (os.path.relpath(path, REPO), digest[:16], expected[:16])
                )

    def run_export(self, entry: Entry) -> None:
        document = _path_of(entry.obj(entry.action, VSONT + "document"))
        exporter = _local(str(entry.obj(entry.action, VSONT + "exporter")))
        expected_path = _path_of(entry.obj(entry.result, VSONT + "expectedOutput"))
        with open(expected_path, encoding="utf-8") as handle:
            expected = handle.read()
        produced = self.export(document, exporter)
        if produced != expected:
            raise Failure(
                "the %s export differs from %s (%d bytes produced, %d frozen; "
                "first difference at byte %d)"
                % (
                    exporter,
                    os.path.relpath(expected_path, REPO),
                    len(produced),
                    len(expected),
                    _first_difference(produced, expected),
                )
            )

    def export(self, document: str, exporter: str) -> str:
        if exporter == "turtle":
            return turtle_of(document)
        if exporter == "caption":
            from tools.render.caption import render

            # The renderer returns the caption; the command writes a line.
            return render(document_graph(document)) + "\n"
        if exporter == "fol":
            from tools.render.fol import render

            return render(document_graph(document))
        if exporter == "canonical-nquads":
            from tools.canon import canonical_nquads

            return canonical_nquads(document_graph(document))
        raise Failure("no reference implementation for exporter %r" % exporter)

    # -- the driver ---------------------------------------------------------

    RUNNERS: Dict[str, str] = {
        "ParsePTest": "run_parse",
        "ParseXTest": "run_parse",
        "ValidationTest": "run_validation",
        "EquivalenceTest": "run_equivalence",
        "ExportTest": "run_export",
    }

    def run(self, selector: Optional[str], verbose: bool) -> Tuple[int, List[str]]:
        failures: List[str] = []
        ran = 0
        for entry in self.entries:
            if selector and selector not in entry.id:
                continue
            runner = self.RUNNERS.get(entry.kind)
            if runner is None:
                failures.append("%s: unknown test type %s" % (entry.id, entry.kind))
                continue
            ran += 1
            try:
                getattr(self, runner)(entry)
            except Failure as exc:
                failures.append("%s: %s" % (entry.id, exc))
                print("  FAIL  %-52s %s" % (entry.id, exc))
            except Exception as exc:  # noqa: BLE001 - a crash is a failure
                failures.append("%s: %s: %s" % (entry.id, type(exc).__name__, exc))
                print("  FAIL  %-52s %s: %s" % (entry.id, type(exc).__name__, exc))
            else:
                if verbose:
                    print("  ok    %-52s %s" % (entry.id, entry.name))
        return ran, failures


def _first_difference(left: str, right: str) -> int:
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return min(len(left), len(right))


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

CLAUSES = ["C%d" % n for n in range(1, 10)]


def named_shapes(shapes) -> List[str]:
    rdflib = _rdflib()
    return sorted(
        str(subject)
        for subject in shapes.subjects(rdflib.RDF.type, rdflib.URIRef(SH + "NodeShape"))
        if isinstance(subject, rdflib.URIRef)
    )


def spec_enums() -> List[str]:
    """§5.12's Enum column — the closed vocabularies, read from the spec."""
    from tools.grammar import extract_grammar as eg

    body = eg.section(eg.spec_text(), "5.12")
    enums = []
    for cells in eg.table_rows(body):
        if len(cells) < 2:
            continue
        ticked = eg._ticked(cells[0])
        if len(ticked) == 1 and ticked[0].startswith("vso:"):
            enums.append(ticked[0][len("vso:"):])
    if not enums:
        raise Failure("§5.12 lists no closed enumerations")
    return enums


def _section_key(section: str) -> tuple:
    """Sort "2.1" before "5.12" before "B" before "D.7", numerically."""
    parts = section.split(".")
    return tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part) for part in parts
    )


def spec_sections() -> List[str]:
    """The numbered §5 and §6 subsection headings, in document order."""
    with open(SPEC, encoding="utf-8") as handle:
        text = handle.read()
    return [
        match.group(1)
        for match in re.finditer(r"^### (5\.\d+|6\.\d+) ", text, re.MULTILINE)
    ]


class Coverage:
    """What the manifest covers, and — as precisely — what it does not."""

    def __init__(self, suite: Suite):
        self.suite = suite
        self.entries = suite.entries
        self.shapes = named_shapes(suite.shapes)
        self.enums = spec_enums()
        self.sections = spec_sections()
        self.exempt = self._exemptions()

    def _exemptions(self) -> Dict[str, str]:
        rdflib = _rdflib()
        out = {}
        for node in self.suite.graph.subjects(
            rdflib.RDF.type, rdflib.URIRef(VSONT + "CoverageExemptions")
        ):
            for record in self.suite.graph.objects(node, rdflib.URIRef(VSONT + "exempt")):
                shape = self.suite.graph.value(record, rdflib.URIRef(VSONT + "shape"))
                reason = self.suite.graph.value(record, rdflib.RDFS.comment)
                if shape is None or reason is None:
                    raise Failure("an exemption names no shape or gives no reason")
                out[str(shape)] = " ".join(str(reason).split())
        return out

    # -- the gate -----------------------------------------------------------

    def problems(self) -> List[str]:
        problems = []
        exercised = {
            str(entry.shape)
            for entry in self.entries
            if entry.shape is not None and entry.negative()
        }
        for shape in self.shapes:
            if shape in exercised or shape in self.exempt:
                continue
            problems.append(
                "shapes/vson-shapes.ttl declares %s and no negative entry trips "
                "it; add one, or exempt it in manifest.ttl with the property of "
                "the shape that makes it unreachable" % _local(shape)
            )
        for shape in sorted(set(self.exempt) - set(self.shapes)):
            problems.append(
                "manifest.ttl exempts %s, which the shapes file no longer "
                "declares" % _local(shape)
            )
        for shape in sorted(set(self.exempt) & exercised):
            problems.append(
                "manifest.ttl exempts %s and an entry trips it; the exemption is "
                "stale" % _local(shape)
            )

        rows = set(self.suite.patterns)
        pinned = {
            str(entry.obj(entry.result, VSONT + "errorRow"))
            for entry in self.entries
            if entry.kind == "ParseXTest" and entry.negative()
        }
        for row in sorted(rows - pinned, key=lambda r: int(r[1:])):
            problems.append("§D.7 %s has no negative entry" % row)
        for row in sorted(pinned - rows):
            problems.append("an entry pins §D.7 %s, which the specification does not define" % row)

        for enum in self.enums:
            positives = [e for e in self.entries if enum in e.enums and not e.negative()]
            negatives = [e for e in self.entries if enum in e.enums and e.negative()]
            if not positives:
                problems.append("§5.12 vso:%s has no positive entry" % enum)
            if not negatives:
                problems.append("§5.12 vso:%s has no negative entry" % enum)

        for clause in CLAUSES:
            positives = [e for e in self.entries if clause in e.clauses and not e.negative()]
            negatives = [e for e in self.entries if clause in e.clauses and e.negative()]
            if not positives:
                problems.append("clause %s has no positive entry" % clause)
            if not negatives:
                problems.append("clause %s has no negative entry" % clause)
        return problems

    # -- the table ----------------------------------------------------------

    def locus(self, entries: Sequence[Entry]) -> str:
        """Where a covered clause or section is actually enforced.

        Derived from the entries rather than declared, so the column cannot
        claim an enforcement the suite has no negative entry for. A row with
        positives only reads "no gate": the specification says something about
        that section and nothing in the conformance surface rejects a document
        that contradicts it — a producer obligation (§5.8, §5.9) or a construct
        conformance deliberately does not decide (§5.13).
        """
        loci = set()
        for entry in entries:
            # An equivalence or an export entry compares a hash or a byte
            # string, so a wrong value fails it whether or not the entry is
            # labelled negative — the comparison is the enforcement.
            if entry.kind == "EquivalenceTest":
                loci.add("canonical form")
                continue
            if entry.kind == "ExportTest":
                loci.add("exporter")
                continue
            if not entry.negative():
                continue
            if entry.kind in ("ParsePTest", "ParseXTest"):
                loci.add("parser")
            elif entry.kind == "ValidationTest":
                gate = entry.obj(entry.result, VSONT + "gate")
                loci.add(
                    {
                        "shacl": "SHACL",
                        "owl-consistency": "OWL 2 RL",
                        "c2": "C2 gate",
                    }.get(_local(str(gate)), "SHACL")
                )

        if not loci:
            return "no gate" if entries else "—"
        order = ["parser", "SHACL", "OWL 2 RL", "C2 gate", "canonical form", "exporter"]
        return " + ".join(sorted(loci, key=order.index))

    def table(self) -> str:
        lines = [
            "| Clause / section | Entries | + | − | Enforced by |",
            "|---|---|---|---|---|",
        ]
        for clause in CLAUSES:
            covering = [e for e in self.entries if clause in e.clauses]
            lines.append(self._row(clause, covering))
        for section in self.sections:
            covering = [e for e in self.entries if section in e.sections]
            lines.append(self._row("§" + section, covering))
        return "\n".join(lines)

    def _row(self, label: str, covering: Sequence[Entry]) -> str:
        positives = sum(1 for e in covering if not e.negative())
        negatives = sum(1 for e in covering if e.negative())
        return "| %s | %d | %d | %d | %s |" % (
            label,
            len(covering),
            positives,
            negatives,
            self.locus(covering),
        )

    def uncovered(self) -> List[str]:
        return [
            "§" + section
            for section in self.sections
            if not any(section in entry.sections for entry in self.entries)
        ]

    def tagged_sections(self) -> List[str]:
        """Every section any entry names, in the order the specification does.

        Wider than `self.sections` on purpose. §2.2's table is scoped to C1-C9
        and the numbered §5/§6 subsections, which is what a reader of a
        specification section can take in; entries also tag §2.1, §3.x, §4.x,
        §7, §9.x and the appendices, and those would be invisible if the map
        used the table's scope. A tag no row could ever show is a tag nobody
        maintains.
        """
        tagged = {section for entry in self.entries for section in entry.sections}
        return sorted(tagged | set(self.sections), key=_section_key)

    def map(self) -> str:
        """Clause and section -> the entry ids that cover it, one per line.

        The table §2.2 publishes gives counts, because a specification section
        listing 104 identifiers is a section nobody reads. This is the other
        half — the thing to run when the question is *which* entries reach a
        clause — and it is generated from the same fields, so the two cannot
        disagree.
        """
        lines = []
        for label, key in (
            [(clause, ("clauses", clause)) for clause in CLAUSES]
            + [("§" + section, ("sections", section)) for section in self.tagged_sections()]
        ):
            covering = [
                entry for entry in self.entries if key[1] in getattr(entry, key[0])
            ]
            if not covering:
                lines.append("%-8s uncovered" % label)
                continue
            lines.append(
                "%-8s %d %s — %s"
                % (
                    label,
                    len(covering),
                    "entry" if len(covering) == 1 else "entries",
                    self.locus(covering),
                )
            )
            for entry in covering:
                lines.append(
                    "         %s %s" % ("−" if entry.negative() else "+", entry.id)
                )
        return "\n".join(lines)


def spec_table() -> Optional[str]:
    """The coverage table as docs/vson.md §2.2 currently publishes it."""
    with open(SPEC, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(
        r"<!-- conformance-coverage:begin -->\n(.*?)\n<!-- conformance-coverage:end -->",
        text,
        re.S,
    )
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.conformance_runner",
        description="Run the VSON v1 conformance suite (docs/vson.md §2.2).",
    )
    ap.add_argument("--manifest", default=MANIFEST, help="manifest to run")
    ap.add_argument("--engine", default="pyshacl", help="SHACL engine (see --list-engines)")
    ap.add_argument("--list-engines", action="store_true", help="print the registry and exit")
    ap.add_argument("--filter", help="run only entries whose id contains this substring")
    ap.add_argument("--verbose", action="store_true", help="print every entry, not only failures")
    ap.add_argument(
        "--coverage-table",
        action="store_true",
        help="print the coverage table docs/vson.md §2.2 publishes, and exit",
    )
    ap.add_argument(
        "--coverage-map",
        action="store_true",
        help="print each clause and section with the entry ids covering it, and exit",
    )
    ap.add_argument(
        "--no-coverage",
        action="store_true",
        help="run the entries only; do not check the coverage claim",
    )
    return ap


def _list_engines() -> int:
    print("Registered SHACL engines:")
    for name, engine in sorted(ENGINES.items()):
        reason = engine.unavailable()
        print("  %-10s %s" % (name, reason or engine.describe()))
    print(
        "\nThe second-engine slot is open. Cross-validating this suite on a "
        "second\nSHACL implementation is what would establish that a passing "
        "verdict is a\nproperty of the shapes rather than of pyshacl; no "
        "adapter ships here because\nevery candidate needs a JVM and a "
        "downloaded distribution (Apache Jena,\nRDF4J, TopBraid), which "
        "`make check` may not assume. Registering one is\n"
        "`tools.conformance_runner.register(YourEngine())` — the protocol is on "
        "the\n`Engine` base class, and an adapter MUST run SHACL at "
        "inference=\"rdfs\" with\nwarnings counted, or its agreement "
        "establishes nothing."
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.list_engines:
        return _list_engines()

    engine = ENGINES.get(args.engine)
    if engine is None:
        print(
            "conformance: no adapter is registered under %r. Registered: %s. "
            "The second-engine slot is open and this run performed no "
            "cross-validation — see --list-engines." % (args.engine, ", ".join(sorted(ENGINES))),
            file=sys.stderr,
        )
        return 2
    reason = engine.unavailable()
    if reason:
        print("conformance: %s" % reason, file=sys.stderr)
        return 2

    try:
        suite = Suite(engine, args.manifest)
        suite.check_vocabulary()
    except Unavailable as exc:
        print("conformance: %s" % exc, file=sys.stderr)
        return 2
    except Failure as exc:
        print("conformance: %s" % exc, file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - a manifest that will not load
        print("conformance: could not load the manifest: %s: %s"
              % (type(exc).__name__, exc), file=sys.stderr)
        return 2

    coverage = Coverage(suite)
    if args.coverage_table:
        print(coverage.table())
        return 0
    if args.coverage_map:
        print(coverage.map())
        return 0

    print(
        "==> VSON v1 conformance suite %s — %d entries, engine %s"
        % (suite_version(suite), len(suite.entries), engine.describe())
    )
    ran, failures = suite.run(args.filter, args.verbose)
    counts: Dict[str, int] = {}
    for entry in suite.entries:
        if args.filter and args.filter not in entry.id:
            continue
        counts[entry.kind] = counts.get(entry.kind, 0) + 1
    print(
        "  %d entries run — %s"
        % (ran, ", ".join("%s %d" % (k.replace("Test", ""), v) for k, v in sorted(counts.items())))
    )

    if not args.no_coverage and not args.filter:
        problems = coverage.problems()
        for problem in problems:
            print("  FAIL  coverage: %s" % problem)
        failures.extend("coverage: " + problem for problem in problems)
        published = spec_table()
        if published is None:
            failures.append(
                "coverage: docs/vson.md carries no conformance-coverage block"
            )
            print("  FAIL  coverage: docs/vson.md carries no conformance-coverage block")
        elif published.strip() != coverage.table().strip():
            failures.append("coverage: docs/vson.md §2.2's table is not the one this suite generates")
            print(
                "  FAIL  coverage: docs/vson.md §2.2's table has drifted; "
                "regenerate it with --coverage-table"
            )
        else:
            print("  OK    coverage: %d shapes, %d exempt, §2.2's table matches"
                  % (len(coverage.shapes), len(coverage.exempt)))

    if failures:
        print("\n%d failure(s)." % len(failures))
        return 1
    print("  OK    every entry got its pinned verdict.")
    return 0


def suite_version(suite: Suite) -> str:
    rdflib = _rdflib()
    version = next(
        suite.graph.objects(
            suite.manifest, rdflib.URIRef("http://www.w3.org/2002/07/owl#versionInfo")
        ),
        None,
    )
    return "v%s" % version if version is not None else "(unversioned)"


if __name__ == "__main__":
    sys.exit(main())
