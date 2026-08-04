#!/usr/bin/env python3
"""Check every counted claim in this repository's prose against the count.

The README's thesis is that a number on this page is a thing you can run. It
said `555 Python tests` while the suite ran 571 — a number nobody had run in
three releases, printed one line above the command that prints the real one.
Nothing noticed, because nothing compared them. That is the same failure the
copy-drift gates already catch for schema fragments and for the dimension
registry (`scripts/check_spec_fragments.py`, `scripts/check_registry_drift.py`);
this one catches it for counts.

What it checks
--------------
Each entry in `CLAIMS` names a metric, a regular expression, and the reason the
claim exists. Every file in scope — every tracked `*.md` outside `EXEMPT`, plus
the `Makefile` — is scanned with every expression, and:

  * **every match must state the computed value.** A number that has drifted is
    a failure at the line that states it.
  * **every claim must still match something.** A pattern that matches nothing
    anywhere in scope fails. This is a floor, not a pin: adding a restatement
    is free and is checked from the moment it lands, but deleting the last one
    fails, because a receipt that quietly disappears is how a page stops being
    checkable — and a pattern nothing matches is a number nobody checks.
  * **no counted claim escapes classification.** Each metric also carries a
    deliberately looser `sweep` expression. A sweep hit that no `CLAIMS` pattern
    covers is reported as unclassified rather than ignored: a claim reworded out
    of the narrow pattern would otherwise pass by becoming invisible, which is
    exactly how `555` survived.

Where the values come from
--------------------------
Every metric is computed from the tree, offline, by the same artifact the claim
is about: the test count comes from unittest discovery in a subprocess (what
`make test` runs), the conformance entry count from the manifest's own
`mf:entries` collection (what `make conformance` executes), the competency
questions from `queries/`, the canonical hashes from the frozen table. Nothing
here reads a number out of a second copy of the prose.

What is NOT in scope
--------------------
`spec/CHANGELOG.md` and the other files in `EXEMPT` are dated records. "48
Python tests" in a v1.0 entry is true *of v1.0* and rewriting it to today's
number would falsify the history. A record of what was is not a claim about
what is.

Exit codes
----------
  0  every counted claim matches the count.
  1  at least one has drifted, has vanished, or is unclassified.
  2  a metric could not be computed, which is not a verdict.

Usage
-----
  python3 scripts/check_counts_drift.py
  python3 scripts/check_counts_drift.py --show      # print the computed values
  python3 scripts/check_counts_drift.py --selftest  # comparators only
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Unavailable(Exception):
    """A metric could not be computed. Exit 2 — not a verdict."""


# ---------------------------------------------------------------------------
# The metrics, each computed from the artifact the claim is about
# ---------------------------------------------------------------------------


def python_tests() -> int:
    """Test cases `make test` discovers — `python3 -m unittest discover -s tests`.

    Counted in a subprocess, with the loader rather than a run: importing every
    test module into this gate's own process is a side effect a gate should not
    have, and running them would make `make check` run its suite twice.
    """
    code = (
        "import unittest, sys\n"
        "loader = unittest.TestLoader()\n"
        "suite = loader.discover('tests')\n"
        "if loader.errors:\n"
        "    sys.stderr.write('\\n'.join(loader.errors))\n"
        "    raise SystemExit(3)\n"
        "print(suite.countTestCases())\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise Unavailable(
            "unittest discovery over tests/ failed: "
            + (proc.stderr.strip().splitlines() or ["no output"])[-1]
        )
    return int(proc.stdout.strip())


_RUST_TEST = re.compile(r"^\s*#\[test\]\s*$", re.M)


def _rust_test_attributes(*roots: str) -> int:
    total = 0
    for root in roots:
        base = os.path.join(REPO, root)
        if not os.path.isdir(base):
            raise Unavailable(f"{root} is not in the checkout")
        for dirpath, _dirs, names in os.walk(base):
            for name in sorted(names):
                if not name.endswith(".rs"):
                    continue
                with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                    total += len(_RUST_TEST.findall(fh.read()))
    return total


def rust_unit_tests() -> int:
    """`#[test]` functions inside the crate — what `cargo test` runs as unit tests."""
    return _rust_test_attributes("cli/src")


def rust_integration_tests() -> int:
    """`#[test]` functions under `cli/tests/` — one binary per file."""
    return _rust_test_attributes("cli/tests")


def rust_tests() -> int:
    return rust_unit_tests() + rust_integration_tests()


def conformance_entries() -> int:
    """Length of the `mf:entries` collection in `tests/conformance/manifest.ttl`.

    Read through the runner's own loader, so the gate and the suite cannot
    disagree about what an entry is. The manifest also *states* a count
    (`vsont:entryCount`); the runner already refuses to run when the stated
    count and the listed nodes disagree, so this counts the nodes.
    """
    try:
        import rdflib
        from rdflib.collection import Collection

        from tools import conformance_runner as runner
    except ImportError as exc:  # pragma: no cover — dependency probe
        raise Unavailable(f"the conformance manifest needs rdflib: {exc}")

    graph = runner.load_graph(runner.MANIFEST)
    mf = rdflib.Namespace(runner.MF)
    manifests = list(graph.subjects(rdflib.RDF.type, mf.Manifest))
    if len(manifests) != 1:
        raise Unavailable(
            f"expected exactly one mf:Manifest, found {len(manifests)}"
        )
    head = next(graph.objects(manifests[0], mf.entries), None)
    if head is None:
        raise Unavailable("the manifest declares no mf:entries")
    return len(Collection(graph, head))


def cq_total() -> int:
    """Competency questions shipped in `queries/`."""
    return len(glob.glob(os.path.join(REPO, "queries", "*.rq")))


def cq_executed() -> int:
    """Those with a frozen answer beside them — the ones `make cq-check` runs."""
    return len(glob.glob(os.path.join(REPO, "queries", "expected", "*.txt")))


def canonical_hashes() -> int:
    """Rows in the frozen §4.6 table — one per shipped document."""
    path = os.path.join(REPO, "tests", "fixtures", "canonical", "hashes.txt")
    with open(path, encoding="utf-8") as fh:
        return sum(
            1
            for line in fh
            if line.strip() and not line.lstrip().startswith("#")
        )


def gallery_scenes() -> int:
    return len(glob.glob(os.path.join(REPO, "examples", "gallery", "*.vson")))


def gallery_x_scenes() -> int:
    return len(
        glob.glob(os.path.join(REPO, "examples", "gallery-x", "*.x.vson"))
    )


def corpus_documents() -> int:
    """The competency-question corpus: the gallery plus the throne room."""
    return gallery_scenes() + 1


METRICS = {
    "python_tests": python_tests,
    "rust_tests": rust_tests,
    "rust_unit_tests": rust_unit_tests,
    "rust_integration_tests": rust_integration_tests,
    "conformance_entries": conformance_entries,
    "cq_total": cq_total,
    "cq_executed": cq_executed,
    "canonical_hashes": canonical_hashes,
    "gallery_scenes": gallery_scenes,
    "gallery_x_scenes": gallery_x_scenes,
    "corpus_documents": corpus_documents,
}


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

# Dated records. A number in one of these is true of the release it describes;
# asserting it against today's tree would demand that history be falsified.
EXEMPT = {
    "spec/CHANGELOG.md": "release notes — every count is as of its release",
    "spec/vson-spec-v0.1-deprecated.md": "a withdrawn document, kept as a record",
    "docs/strategy/extractor-architecture.md": "a dated design note, not a claim about the tree",
    "docs/strategy/productization.md": "a dated plan",
    "docs/strategy/ui-flows.md": "a dated plan",
    "tools/extractor/baseline/results.md": "a measurement record carrying its own method and date",
    "tools/extractor/baseline/ablations/no_decision_policies.md": "a measurement record",
    "tools/extractor/baseline/ablations/no_shacl_section.md": "a measurement record",
    "tools/extractor/baseline/ablations/no_worked_example.md": "a measurement record",
}

# `cli/assets/` is a byte-identical mirror maintained by
# scripts/check_embedded_assets.py; its copies are checked at the original.
MIRROR_PREFIX = "cli/assets/"

EXTRA_FILES = ["Makefile"]


def scope() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = [
        p
        for p in out.splitlines()
        if p and p not in EXEMPT and not p.startswith(MIRROR_PREFIX)
    ]
    return sorted(files + EXTRA_FILES)


# ---------------------------------------------------------------------------
# The claims
# ---------------------------------------------------------------------------


class Claim:
    def __init__(self, metrics, pattern, why):
        self.metrics = (metrics,) if isinstance(metrics, str) else tuple(metrics)
        self.pattern = re.compile(pattern)
        self.why = why


# Every regex captures one group per metric it names, in order.
CLAIMS = [
    Claim(
        "python_tests",
        r"(\d+) Python tests",
        "the Quick start annotation on `make check` — the number that drifted",
    ),
    Claim(
        ("rust_tests", "rust_unit_tests", "rust_integration_tests"),
        r"(\d+) tests: (\d+) unit, (\d+) integration",
        "cli/README.md Verification, beside the `cargo test` that prints it",
    ),
    Claim(
        "rust_integration_tests",
        r"The (\d+) integration tests split",
        "cli/README.md's per-file breakdown of the integration binaries",
    ),
    Claim(
        ("rust_tests", "rust_unit_tests"),
        r"(\d+) tests \((\d+) lib unit",
        "docs/vson.md §10, the Rust CLI row of the implementations table",
    ),
    Claim(
        "conformance_entries",
        r"(\d+)[- ]entr(?:y|ies)(?= conformance suite| at suite)",
        "the suite that defines conformance (§2.2)",
    ),
    Claim(
        "cq_total",
        r"(\d+) competency questions",
        "the pack `queries/` ships",
    ),
    Claim(
        "cq_executed",
        r"(\d+) executable competency questions",
        "the subset with a frozen answer — what `make cq-check` runs",
    ),
    Claim(
        "cq_executed",
        r"(\d+) of them run by CI",
        "the same subset, stated in the README lead",
    ),
    Claim(
        ("cq_executed", "cq_total"),
        r"(\d+) of the (\d+) questions",
        "docs/vson.md Appendix E.4 on why the pack stops where it does",
    ),
    Claim(
        "canonical_hashes",
        r"(\d+) frozen(?: canonical)? hashes",
        "the frozen §4.6 table — one row per shipped document",
    ),
    Claim(
        "gallery_scenes",
        r"(\d+)[- ]scene (?:gallery|example gallery)",
        "the example gallery, counted wherever it is introduced",
    ),
    Claim(
        "gallery_scenes",
        r"gallery/ \((\d+) scenes",
        "the repository map's line for examples/",
    ),
    Claim(
        "gallery_scenes",
        r"all (\d+) gallery scenes|(?:the|full) (\d+) gallery scenes",
        "the corpus the parity and worker gates run over",
    ),
    Claim(
        "corpus_documents",
        r"(\d+)[- ]document (?:corpus|gallery)",
        "the competency-question corpus: the gallery plus the throne room",
    ),
    Claim(
        "gallery_x_scenes",
        r"\((\d+) pairs\)",
        "`make x-check`'s VSON-X round-trip pairs",
    ),
    Claim(
        "gallery_x_scenes",
        r"All (\d+) gallery scenes that have a VSON-X counterpart",
        "the cross-syntax denotation claim of §4.6",
    ),
]

# Looser than the patterns above, on purpose: a hit here that no claim covers is
# a counted claim that has been reworded out of the gate's sight.
SWEEPS = {
    "python_tests": r"\d+[\s-]+Python tests",
    "canonical_hashes": r"\d+ frozen[\w\s]*hashes",
    "conformance_entries": r"\d+[- ]entr(?:y|ies)(?=[^.\n]*conformance)",
    "cq_total": r"\d+ competency questions",
    "cq_executed": r"\d+ executable competency questions",
    "rust_tests": r"\d+ tests\s*[:(]",
    "corpus_documents": r"\d+[- ]document (?:corpus|gallery)",
    "gallery_scenes": r"\d+[- ]scene (?:gallery|example gallery)|\d+ gallery scenes",
}


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def computed(names=None) -> dict:
    out = {}
    for name, fn in METRICS.items():
        if names and name not in names:
            continue
        out[name] = fn()
    return out


def read(rel: str) -> str:
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


def _line_of(text: str, pos: int) -> int:
    """1-indexed line holding byte offset `pos`."""
    return text.count("\n", 0, pos) + 1


def check(values: dict, files: "list[str] | None" = None) -> list[str]:
    failures: list[str] = []
    files = files if files is not None else scope()
    sources = {rel: read(rel) for rel in files}

    sites = {claim: 0 for claim in CLAIMS}
    covered: dict[str, set] = {rel: set() for rel in sources}

    for rel, text in sorted(sources.items()):

        def lineno(pos: int, _text: str = text) -> int:
            return _line_of(_text, pos)

        for claim in CLAIMS:
            for match in claim.pattern.finditer(text):
                sites[claim] += 1
                covered[rel].update(range(match.start(), match.end()))
                groups = [g for g in match.groups() if g is not None]
                if len(groups) != len(claim.metrics):
                    failures.append(
                        f"{rel}:{lineno(match.start())}: {claim.pattern.pattern!r} "
                        f"captured {len(groups)} number(s) for "
                        f"{len(claim.metrics)} metric(s) — fix the pattern"
                    )
                    continue
                for metric, stated in zip(claim.metrics, groups):
                    real = values[metric]
                    if int(stated) != real:
                        failures.append(
                            f"{rel}:{lineno(match.start())}: claims {metric} "
                            f"= {stated}, the tree has {real} — "
                            f"{match.group(0)!r}"
                        )

    for metric, pattern in sorted(SWEEPS.items()):
        rx = re.compile(pattern)
        for rel, text in sorted(sources.items()):
            for match in rx.finditer(text):
                if match.start() in covered[rel]:
                    continue
                failures.append(
                    f"{rel}:{_line_of(text, match.start())}: "
                    f"unclassified {metric} claim "
                    f"{match.group(0)!r} — no CLAIMS pattern covers it, so "
                    f"nothing checks the number in it"
                )

    for claim in CLAIMS:
        if sites[claim] < 1:
            failures.append(
                f"claim {claim.pattern.pattern!r} ({'/'.join(claim.metrics)}) "
                f"matches nothing in scope — {claim.why}. Either the claim was "
                f"deleted, in which case delete this entry, or it was reworded, "
                f"in which case the number in it is no longer checked."
            )

    return failures


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------


def selftest() -> int:
    bad = 0
    fake = {name: 7 for name in METRICS}

    good = "make check   # 7 Python tests\n"
    drifted = "make check   # 8 Python tests\n"

    def run(text: str) -> list[str]:
        import tempfile

        with tempfile.TemporaryDirectory(dir=REPO) as d:
            rel = os.path.relpath(os.path.join(d, "t.md"), REPO)
            with open(os.path.join(REPO, rel), "w", encoding="utf-8") as fh:
                fh.write(text)
            return [
                f
                for f in check(fake, [rel])
                if "matches nothing in scope" not in f
            ]

    if run(good):
        print("  FAIL a true count was reported as drift")
        bad += 1
    else:
        print("  OK   a true count passes")

    if not run(drifted):
        print("  FAIL a drifted count did not fail the check")
        bad += 1
    else:
        print("  OK   a drifted count fails the check")

    reworded = run("make check   # 8   Python tests today\n")
    if not any("unclassified" in f for f in reworded):
        print("  FAIL a reworded claim escaped the sweep")
        bad += 1
    else:
        print("  OK   a reworded claim is reported as unclassified")

    missing = [f for f in check(fake, []) if "matches nothing in scope" in f]
    if len(missing) != len(CLAIMS):
        print(f"  FAIL a deleted claim did not fail the check ({missing})")
        bad += 1
    else:
        print("  OK   a claim that has vanished fails the check")

    # Every metric a claim names must exist, or the claim checks nothing.
    for claim in CLAIMS:
        for metric in claim.metrics:
            if metric not in METRICS:
                print(f"  FAIL claim names unknown metric {metric!r}")
                bad += 1
    for metric in SWEEPS:
        if metric not in METRICS:
            print(f"  FAIL sweep names unknown metric {metric!r}")
            bad += 1
    print("  OK   every claim and sweep names a computed metric")

    print("  selftest: " + ("OK" if bad == 0 else f"{bad} FAILED"))
    return 1 if bad else 0


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--show", action="store_true", help="print computed values")
    ap.add_argument("--selftest", action="store_true", help="comparators only")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    try:
        values = computed()
    except Unavailable as exc:
        print(f"  UNAVAILABLE {exc}")
        return 2

    if args.show:
        for name, value in values.items():
            print(f"  {name:<24} {value}")
        return 0

    failures = check(values)
    if failures:
        for failure in failures:
            print(f"  FAIL {failure}")
        print(f"\ncounts-check: FAILED — {len(failures)} claim(s)")
        return 1

    print(
        f"  OK {len(CLAIMS)} counted claims over {len(scope())} files match "
        f"the tree ({values['python_tests']} Python tests, "
        f"{values['rust_tests']} Rust, "
        f"{values['conformance_entries']} conformance entries, "
        f"{values['cq_executed']}/{values['cq_total']} CQs, "
        f"{values['canonical_hashes']} canonical hashes)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
