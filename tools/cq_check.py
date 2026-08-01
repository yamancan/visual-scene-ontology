#!/usr/bin/env python3
"""Competency-question gate — run `queries/` against the shipped corpus.

docs/vson.md §5.14. A competency question (Grüninger & Fox 1995; the NeOn
methodology's CQ artefact) is a question the vocabulary must be able to answer.
Written down, it is a design record. Written down *as a query, against a corpus,
compared to a frozen answer*, it is a test — and the difference is the whole
point of this directory. Every claim §1–§5 makes about what VSON can express is
either reachable by one of these queries or it is not made good on.

The pack is **SPARQL 1.1**, run by rdflib, over **asserted triples only**: no
entailment regime, no reasoner, no TBox in the corpus. A reviewer with any
SPARQL 1.1 engine and this repository can reproduce every answer, which is the
property a competency-question suite exists to have. Where a question needs a
class hierarchy the queries name the asserted classes with `VALUES`, rather than
relying on `rdfs:subClassOf` entailment the corpus does not carry.

The corpus
----------
Seventeen documents — the 16-scene gallery (`examples/gallery/*.vson`, compiled
to VSON-T by the reference Penman transpiler) plus `examples/throne_room.ttl`,
the hand-authored canonical scene. Each is loaded into its own **named graph**,
and each document's namespace is rewritten from the transpiler's shared
`https://example.org/scenes/anonymous#` to a per-document
`https://example.org/scenes/<stem>#`. Without that rewrite all sixteen gallery
scenes would share one namespace and `:scene`, `:cam` and `:alice` would be the
same node in every one of them — the corpus would answer questions about a
scene that does not exist. With it, `?doc` is a real document identity and a
cross-document question (CQ-26) is a real join.

No file in `examples/` is modified: the rewrite is a string substitution on the
transpiler's output, in memory, at load time.

The frozen answers
------------------
`queries/expected/<stem>.txt` holds the rendered result of `queries/<stem>.rq`,
byte-for-byte. The rendering is defined in `render_result` below and is not a
W3C result format: it is prefixed, sorted by the query's own `ORDER BY`, and
readable, so a reviewer can see the answer without running anything. Three
properties keep a frozen answer honest:

  * every `SELECT` carries an `ORDER BY` — the fixture's row order is the
    query's, not the engine's;
  * duplicate rendered rows are rejected — two identical rows make the order
    engine-dependent, so a query that produces them is under-specified;
  * blank nodes in a result are rejected — `examples/throne_room.ttl` writes its
    Quality nodes as blank nodes, whose labels rdflib mints per parse, so a
    fixture containing one would be frozen to a value that changes on the next
    run. Project the stable IRI the question is actually about.

Regenerating a fixture is `--freeze`, and it is an authoring step, never a fix:
a red gate means the corpus changed or the query changed, and which one it was
is the thing to establish before the fixture moves.

Documented-future queries
-------------------------
A query whose header carries `Status: documented-future` is **not executed**
and has **no fixture**. It records a question the notation can express and this
engine cannot run — today, exactly one: the §5.11 confidence question written
once across both the RDF-star quoted-triple form and the RDF 1.1
`vso:Annotation` form. rdflib 7.6 parses neither `<< s p o >>` nor RDF 1.2's
`<<( s p o )>>`, in Turtle or in SPARQL.

That claim is not taken on trust. For every documented-future query this gate
*asserts the engine rejects it*, and fails if the engine accepts — so the day
rdflib gains SPARQL-star, this file goes red and says to promote the query and
freeze its answer. A skip nobody re-checks is a skip that outlives its reason.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.cq_check [--verbose]
    python3 -m tools.cq_check --freeze     # rewrite every expected fixture
    python3 -m tools.cq_check --list       # the CQ table, no execution

Exit 0 — every executable CQ matches its frozen answer, every documented-future
         CQ is still unrunnable here.
Exit 1 — at least one does not.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from typing import Dict, List, Optional, Tuple

import rdflib
from rdflib import BNode, Dataset, Literal, URIRef

from tools.penman import vson_penman as vp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUERIES = os.path.join(ROOT, "queries")
EXPECTED = os.path.join(QUERIES, "expected")

# The namespace the Penman transpiler emits for a document that declares none.
# Every gallery scene lands on it, which is exactly why the loader rewrites it.
ANON_NS = "https://example.org/scenes/anonymous#"
# The hand-authored canonical scene declares its own, and it is rewritten on the
# same rule so that one substitution documents the whole corpus.
THRONE_NS = "https://example.org/scenes/throne_room#"
SCENE_BASE = "https://example.org/scenes/"

# Rendering prefixes. Everything else prints as a full IRI in angle brackets.
PREFIXES: List[Tuple[str, str]] = [
    ("vso", "https://w3id.org/vson/v1/ontology#"),
    ("rcc", "https://w3id.org/vson/v1/rcc8#"),
    ("allen", "https://w3id.org/vson/v1/allen#"),
    ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
    ("xsd", "http://www.w3.org/2001/XMLSchema#"),
]

UNBOUND = "UNBOUND"

# Header keys every .rq MUST state, and the two it MAY.
REQUIRED_KEYS = ("Question", "Persona", "Spec", "Form")
OPTIONAL_KEYS = ("Status", "Note")
PERSONAS = ("P1", "P2", "P3")
FORMS = ("ASK", "SELECT")
DOCUMENTED_FUTURE = "documented-future"


# --------------------------------------------------------------------------
# The corpus
# --------------------------------------------------------------------------
def corpus_documents() -> List[Tuple[str, str]]:
    """(stem, repo-relative path) for the 17 corpus documents, in fixed order."""
    docs = []
    for path in sorted(glob.glob(os.path.join(ROOT, "examples", "gallery", "*.vson"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        docs.append((stem, os.path.relpath(path, ROOT)))
    docs.append(("throne_room", os.path.join("examples", "throne_room.ttl")))
    return docs


def build_corpus() -> Dataset:
    """Load the 17 documents, one named graph each, namespaces disambiguated."""
    dataset = Dataset(default_union=True)
    for stem, rel in corpus_documents():
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        turtle = source if rel.endswith(".ttl") else vp.to_turtle(source)
        turtle = turtle.replace(ANON_NS, SCENE_BASE + stem + "#")
        turtle = turtle.replace(THRONE_NS, SCENE_BASE + stem + "#")
        dataset.graph(URIRef(SCENE_BASE + stem)).parse(data=turtle, format="turtle")
    return dataset


# --------------------------------------------------------------------------
# Rendering — the frozen-fixture format
# --------------------------------------------------------------------------
def render_term(term) -> str:
    """One RDF term, in the fixture's notation.

    Corpus IRIs lose the shared base, so a node reads `11_throne_room#alice` and
    a document reads `throne_room`. VSO/RCC/Allen/RDF(S)/XSD IRIs are prefixed.
    Literals keep their lexical form and carry a prefixed datatype unless they
    are plain or `xsd:string`, which the corpus writes interchangeably.
    """
    if term is None:
        return UNBOUND
    if isinstance(term, BNode):
        raise ValueError(
            "blank node in a result row: a frozen fixture cannot hold one "
            "(rdflib mints its label per parse). Project the stable IRI."
        )
    if isinstance(term, URIRef):
        iri = str(term)
        if iri.startswith(SCENE_BASE):
            return iri[len(SCENE_BASE):]
        for prefix, namespace in PREFIXES:
            if iri.startswith(namespace):
                return "%s:%s" % (prefix, iri[len(namespace):])
        return "<%s>" % iri
    if isinstance(term, Literal):
        lexical = '"%s"' % str(term).replace("\\", "\\\\").replace('"', '\\"')
        if term.language:
            return "%s@%s" % (lexical, term.language)
        datatype = term.datatype
        if datatype is None or str(datatype) == str(rdflib.XSD.string):
            return lexical
        return "%s^^%s" % (lexical, render_term(URIRef(str(datatype))))
    return str(term)


def render_result(name: str, form: str, result) -> str:
    """The whole fixture body for one query result."""
    lines = ["# %s" % name, "# form: %s" % form]
    if form == "ASK":
        lines.append("")
        lines.append("true" if bool(result) else "false")
        return "\n".join(lines) + "\n"

    variables = [str(v) for v in result.vars]
    rows = []
    for row in result:
        rows.append("\t".join(render_term(row[v]) for v in result.vars))
    duplicates = sorted({row for row in rows if rows.count(row) > 1})
    if duplicates:
        raise ValueError(
            "duplicate result row(s) — the fixture's order would be "
            "engine-dependent; add DISTINCT or project a distinguishing "
            "variable:\n  " + "\n  ".join(duplicates[:3])
        )
    lines.append("# rows: %d" % len(rows))
    lines.append("")
    lines.append("\t".join("?" + v for v in variables))
    lines.extend(rows)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# The .rq header
# --------------------------------------------------------------------------
class Query:
    """One competency question: its file, its header, its text."""

    def __init__(self, path: str, text: str, header: Dict[str, str]) -> None:
        self.path = path
        self.text = text
        self.header = header
        self.name = os.path.splitext(os.path.basename(path))[0]

    @property
    def form(self) -> str:
        return self.header.get("Form", "").split()[0] if self.header.get("Form") else ""

    @property
    def documented_future(self) -> bool:
        return self.header.get("Status", "").startswith(DOCUMENTED_FUTURE)

    @property
    def fixture(self) -> str:
        return os.path.join(EXPECTED, self.name + ".txt")


def parse_header(text: str) -> Dict[str, str]:
    """`# Key: value` lines from the leading comment block; continuations join."""
    header: Dict[str, str] = {}
    key: Optional[str] = None
    for raw in text.splitlines():
        if not raw.startswith("#"):
            break
        body = raw[1:].strip()
        if not body:
            key = None
            continue
        marker = body.split(":", 1)
        if len(marker) == 2 and marker[0].strip() in REQUIRED_KEYS + OPTIONAL_KEYS:
            key = marker[0].strip()
            header[key] = marker[1].strip()
        elif key is not None:
            header[key] = (header[key] + " " + body).strip()
    return header


def load_queries() -> List[Query]:
    queries = []
    for path in sorted(glob.glob(os.path.join(QUERIES, "CQ-*.rq"))):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        queries.append(Query(path, text, parse_header(text)))
    return queries


def header_problems(query: Query) -> List[str]:
    """Everything a header must state, checked here so the gate can rely on it."""
    problems = []
    for required in REQUIRED_KEYS:
        if not query.header.get(required):
            problems.append("header states no %s" % required)
    persona = query.header.get("Persona", "")
    if persona and persona.split()[0].rstrip(",") not in PERSONAS:
        problems.append("Persona must start with one of %s" % ", ".join(PERSONAS))
    spec = query.header.get("Spec", "")
    if spec and "§" not in spec:
        problems.append("Spec must cite at least one § section")
    form = query.form
    if form and form not in FORMS:
        problems.append("Form must be one of %s" % ", ".join(FORMS))
    if form == "SELECT" and "ORDER BY" not in query.text:
        problems.append("a SELECT with no ORDER BY has an engine-dependent row order")
    status = query.header.get("Status")
    if status and not status.startswith(DOCUMENTED_FUTURE):
        problems.append("the only Status this gate knows is '%s'" % DOCUMENTED_FUTURE)
    return problems


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
def run_one(dataset: Dataset, query: Query) -> str:
    """Execute and render, twice, asserting the engine agreed with itself."""
    first = render_result(query.name, query.form, dataset.query(query.text))
    second = render_result(query.name, query.form, dataset.query(query.text))
    if first != second:
        raise ValueError(
            "two runs of this query disagreed — the ORDER BY does not "
            "determine the row order"
        )
    return first


def engine_rejects(dataset: Dataset, query: Query) -> Optional[str]:
    """None when the engine really cannot run it; else why the skip is stale."""
    try:
        dataset.query(query.text)
    except Exception:  # noqa: BLE001 — any rejection is the claim being checked
        return None
    return "this engine now accepts the query: promote it and freeze its answer"


def check(freeze: bool = False, verbose: bool = False) -> int:
    queries = load_queries()
    if not queries:
        print("cq-check: FAIL — no queries/CQ-*.rq found")
        return 1

    dataset = build_corpus()
    documents = corpus_documents()
    triples = sum(
        len(dataset.graph(URIRef(SCENE_BASE + stem))) for stem, _ in documents
    )
    print(
        "cq-check: %d competency question(s) over %d document(s), %d triple(s)"
        % (len(queries), len(documents), triples)
    )

    failures: List[str] = []
    executed = 0
    deferred = 0

    for query in queries:
        problems = header_problems(query)
        if problems:
            failures.append(query.name)
            print("\n  FAIL  %s  (header)" % query.name)
            for problem in problems:
                print("        %s" % problem)
            continue

        if query.documented_future:
            deferred += 1
            stale = engine_rejects(dataset, query)
            if stale is None and os.path.exists(query.fixture):
                stale = "a documented-future query must have no frozen answer"
            if stale:
                failures.append(query.name)
                print("\n  FAIL  %s  (documented-future)" % query.name)
                print("        %s" % stale)
                continue
            print(
                "  skip  %-40s %s — %s"
                % (query.name, query.form, query.header["Status"])
            )
            continue

        try:
            rendered = run_one(dataset, query)
        except Exception as exc:  # noqa: BLE001 — reported, not raised
            failures.append(query.name)
            print("\n  FAIL  %s  (execution)" % query.name)
            print("        %s: %s" % (type(exc).__name__, exc))
            continue

        executed += 1
        if freeze:
            os.makedirs(EXPECTED, exist_ok=True)
            with open(query.fixture, "w", encoding="utf-8") as handle:
                handle.write(rendered)
            print("  froze %-40s %s" % (query.name, query.form))
            continue

        if not os.path.exists(query.fixture):
            failures.append(query.name)
            print("\n  FAIL  %s  no frozen answer at %s" % (query.name, query.fixture))
            continue
        with open(query.fixture, encoding="utf-8") as handle:
            expected = handle.read()
        if rendered != expected:
            failures.append(query.name)
            print("\n  FAIL  %s  answer changed" % query.name)
            for line in _diff(expected, rendered):
                print("        %s" % line)
            continue
        summary = _summary(rendered)
        print("  ok    %-40s %-6s %s" % (query.name, query.form, summary))
        if verbose:
            for line in rendered.splitlines():
                print("          %s" % line)

    orphans = _orphan_fixtures(queries)
    for orphan in orphans:
        failures.append(os.path.basename(orphan))
        print("\n  FAIL  %s  frozen answer with no query" % os.path.basename(orphan))

    if failures:
        print(
            "\ncq-check: FAIL — %d of %d competency question(s):"
            % (len(failures), len(queries))
        )
        for name in failures:
            print("  - %s" % name)
        print(
            "\nA changed answer is a changed corpus or a changed query. Establish\n"
            "which before running --freeze: the fixture is the evidence, and\n"
            "regenerating it to match a regression erases the only record of it."
        )
        return 1

    print(
        "\ncq-check: OK — %d executed against the corpus, %d documented-future"
        % (executed, deferred)
    )
    return 0


def _summary(rendered: str) -> str:
    for line in rendered.splitlines():
        if line.startswith("# rows: "):
            return "%s row(s)" % line[len("# rows: "):]
    return rendered.strip().splitlines()[-1]


def _diff(expected: str, actual: str) -> List[str]:
    """First few differing lines, side by side — enough to name the change."""
    exp = expected.splitlines()
    act = actual.splitlines()
    out = []
    for index in range(max(len(exp), len(act))):
        left = exp[index] if index < len(exp) else "(absent)"
        right = act[index] if index < len(act) else "(absent)"
        if left != right:
            out.append("line %d  frozen: %s" % (index + 1, left))
            out.append("line %d  now:    %s" % (index + 1, right))
        if len(out) >= 8:
            out.append("...")
            break
    return out


def _orphan_fixtures(queries: List[Query]) -> List[str]:
    known = {query.fixture for query in queries}
    if not os.path.isdir(EXPECTED):
        return []
    return sorted(
        path
        for path in glob.glob(os.path.join(EXPECTED, "*.txt"))
        if path not in known
    )


def listing() -> int:
    """The CQ table: id, persona, form, question. No corpus, no execution."""
    for query in load_queries():
        status = "future" if query.documented_future else query.form.lower()
        print(
            "%-34s %-3s %-7s %s"
            % (
                query.name,
                query.header.get("Persona", "?").split()[0].rstrip(","),
                status,
                query.header.get("Question", ""),
            )
        )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run queries/ against the 17-document VSON corpus.",
    )
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="rewrite every expected fixture from the current corpus",
    )
    parser.add_argument(
        "--list", action="store_true", help="print the CQ table and exit"
    )
    parser.add_argument("--verbose", action="store_true", help="echo every answer")
    args = parser.parse_args(argv)
    if args.list:
        return listing()
    return check(freeze=args.freeze, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
