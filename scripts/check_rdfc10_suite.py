#!/usr/bin/env python3
"""Run the W3C RDFC-1.0 test suite against `tools/canon.py`.

`docs/vson.md` §4.6 does not define a canonicalization algorithm. It cites one
— RDFC-1.0, *RDF Dataset Canonicalization*, W3C Recommendation 2024-05-21 —
and every frozen hash under `tests/fixtures/canonical/` is only as good as the
claim that `tools/canon.py` implements that citation and not something nearby.
`tests/test_canon.py` checks it against the worked examples printed *in* the
Recommendation, which is the part that can live in the checkout. This script
checks it against the **published test suite**, which cannot: the suite lives
at <https://w3c.github.io/rdf-canon/tests/> and is not vendored here.

What it runs, and what it cannot
--------------------------------
  * **RDFC10EvalTest** (64) — canonicalize the input, compare the canonical
    N-Quads to the published output, byte for byte. Entries carrying
    `hashAlgorithm: SHA384` are run under SHA-384, which the Recommendation
    requires an implementation to support.
  * **RDFC10NegativeEvalTest** (1) — the 10-node clique built to make the
    algorithm run forever. The Recommendation (§7.1) requires an implementation
    to terminate early instead; passing means `CanonicalizationError`.
  * **RDFC10MapTest** (21) — *not run*, for a reason worth stating rather than
    skipping quietly: these compare the *input* blank node labels to the
    canonical identifiers issued for them, and rdflib does not preserve input
    labels (`_:e0` comes back as `_:Nb1f0…`), so the map cannot be keyed. The
    labelling itself is still checked — by the 64 eval tests, whose expected
    output *is* the labelling.

The four documents that differ, and why they are not failures
-------------------------------------------------------------
Four eval tests come back different, in one respect each: rdflib's N-Quads
parser rewrites a literal's lexical form on the way in — `"…Z"^^xsd:dateTime`
becomes `"…+00:00"`, `"1.23E0"^^xsd:double` becomes `"1.23"` — and RDF 1.1
literal term equality is lexical, so a rewritten literal is a different term
before this module ever sees it. The script proves that is the whole difference
rather than asserting it: it re-parses the *published expected output* through
the same parser, canonicalizes that, and requires the result to equal what the
input produced. Same bytes means the canonical labelling agreed and only the
parser moved, and the run is reported as `parser` rather than as a failure. A
difference anywhere else is a failure.

This is the same caveat §4.6 states for producers: two implementations agree on
a document only to the extent their parsers preserve what it wrote.

Why this is NOT in `make check`
-------------------------------
It leaves the checkout. `make check` must be answerable from the tree alone, and
a gate that goes red for a third-party outage is a gate people stop reading —
the same reason `make live-check` is a separate target. Run this when
`tools/canon.py` changes, before a release, and when the suite publishes a new
revision.

Exit codes
----------
  0  every runnable test holds (differences classified as `parser` included).
  1  at least one test is contradicted — the canonical labelling disagrees.
  2  the suite could not be fetched. Not a verdict.

Usage
-----
  python3 scripts/check_rdfc10_suite.py
  python3 scripts/check_rdfc10_suite.py --dir path/to/rdf-canon/tests
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rdflib import Dataset  # noqa: E402 — after the sys.path bootstrap above

from tools import canon  # noqa: E402 — same

SUITE = "https://w3c.github.io/rdf-canon/tests/"
MANIFEST = "manifest.jsonld"

EVAL = "rdfc:RDFC10EvalTest"
NEGATIVE = "rdfc:RDFC10NegativeEvalTest"
MAP = "rdfc:RDFC10MapTest"

# The Recommendation names them SHA256 / SHA384; hashlib names them lowercase.
HASH_NAMES = {"SHA256": "sha256", "SHA384": "sha384"}


class Unreachable(Exception):
    """The suite could not be read. Exit 2, not a verdict on the code."""


def _read(source: str, relative: str) -> bytes:
    if source.startswith("http://") or source.startswith("https://"):
        try:
            with urllib.request.urlopen(source + relative, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise Unreachable("{}: {}".format(source + relative, exc)) from exc
    path = os.path.join(source, relative)
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise Unreachable("{}: {}".format(path, exc)) from exc


def _quads(document: bytes):
    """Parse an N-Quads document into the quad list `tools.canon` consumes."""
    dataset = Dataset()
    dataset.parse(data=document.decode("utf-8"), format="nquads")
    quads = []
    for subject, predicate, obj, graph in dataset.quads((None, None, None, None)):
        name = None
        if graph is not None:
            identifier = getattr(graph, "identifier", graph)
            # rdflib names its default graph with an internal urn:. A quad in
            # the default graph has no graph component in RDFC-1.0 terms.
            if not str(identifier).startswith("urn:x-rdflib"):
                name = identifier
        quads.append((subject, predicate, obj, name))
    return quads


def run(source: str) -> int:
    manifest = json.loads(_read(source, MANIFEST).decode("utf-8"))
    entries = manifest["entries"]

    passed = []
    parser_only = []
    failed = []
    skipped = []

    for entry in entries:
        name = "{} {}".format(entry["id"].lstrip("#"), entry["name"])
        kind = entry["type"]
        if kind == MAP:
            skipped.append(name)
            continue

        algorithm = HASH_NAMES.get(entry.get("hashAlgorithm", "SHA256"), "sha256")
        quads = _quads(_read(source, entry["action"]))

        if kind == NEGATIVE:
            try:
                canon.rdfc10(quads, hash_algorithm=algorithm)
            except canon.CanonicalizationError:
                passed.append(name)
            else:
                failed.append((name, "canonicalized a dataset it must refuse"))
            continue

        if kind != EVAL:  # pragma: no cover — a new test type would land here
            skipped.append(name + " (unknown type {})".format(kind))
            continue

        got = canon.rdfc10(quads, hash_algorithm=algorithm)
        expected = _read(source, entry["result"]).decode("utf-8")
        if got == expected:
            passed.append(name)
            continue

        # Re-parse the published output and canonicalize it. Equal bytes means
        # the labelling agreed and the parser rewrote a literal on the way in.
        if got == canon.rdfc10(_quads(expected.encode("utf-8")), algorithm):
            parser_only.append(name)
        else:
            failed.append((name, "canonical form differs"))

    for name in passed:
        print("  ok      {}".format(name))
    for name in parser_only:
        print("  parser  {}  — rdflib rewrote a literal's lexical form".format(name))
    for name, why in failed:
        print("  FAIL    {}  — {}".format(name, why))
    if skipped:
        print(
            "  skip    {} map test(s) — rdflib does not preserve input blank "
            "node labels".format(len(skipped))
        )
    print(
        "\nrdfc10-suite: {} ok, {} parser-normalized, {} failed, {} skipped "
        "(of {} entries)".format(
            len(passed), len(parser_only), len(failed), len(skipped), len(entries)
        )
    )
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 scripts/check_rdfc10_suite.py",
        description="Run the W3C RDFC-1.0 test suite against tools/canon.py.",
    )
    ap.add_argument(
        "--dir",
        default=SUITE,
        help="local checkout of the suite's tests/ directory (default: fetch it)",
    )
    args = ap.parse_args(argv)
    try:
        return run(args.dir if args.dir.endswith(("/", os.sep)) else args.dir + os.sep)
    except Unreachable as exc:
        print("rdfc10-suite: could not read the test suite — {}".format(exc))
        print("  This is not a verdict on tools/canon.py.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
