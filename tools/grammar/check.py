#!/usr/bin/env python3
"""`make grammar-check` — the spec's grammars, generated and run. §D.10.

Appendix B and Appendix D are the normative grammars for the two syntaxes VSON
authors write by hand. Until v1.3 they were prose that happened to be formatted
as EBNF: nothing executed them, so the only way to know whether a production
described the shipped parser was to read both and hope. This gate executes
them.

What it establishes, in order:

  1. **The blocks are grammars.** They parse as §D.1 notation and translate,
     with no rule left unhandled, into a parser generator's input that builds.
     A production nobody can compile is not a specification.
  2. **They accept what this repository ships.** Every VSON-P scene and every
     VSON-X scene in `examples/` parses under the generated parser AND under
     the reference implementation. A grammar that rejects the corpus is wrong
     about the language; a corpus the grammar alone accepts is a corpus the
     reference cannot read.
  3. **§D.3's closed vocabularies are closed, and are one list.** The five
     token sets in the spec, the five counts the spec spells out beside them,
     the reference lexer's own constants and — for the RCC set — the routing
     table the emitter reads are compared against each other, and an
     out-of-vocabulary token in each position is rejected.
  4. **§D.7's `Decided by` column is true.** One negative fixture per error
     row: the reference parser MUST reject every one, and the generated parser
     MUST reject exactly the rows the column calls `grammar`. A row that says
     `grammar` and survives the generated parser is a grammar weaker than the
     spec claims; a row that says `parser` and dies in the generated parser is
     a column that has fallen behind a grammar that got stronger.
  5. **The committed GBNF is what the spec generates.** `tools/grammar/vson-x.gbnf`
     is regenerated and compared byte for byte, re-read as GBNF, and its
     language is checked to still contain every shipped VSON-X scene.

Exit codes
----------
  0  every claim above holds.
  1  one does not — the message says which.
  2  the dev extra is missing (`pip install -e ".[dev]"`), so nothing ran.

Usage
-----
  python3 -m tools.grammar.check
  python3 -m tools.grammar.check --write-gbnf   # regenerate the artifact
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Callable, Dict, List

from tools.grammar import build, ebnf, extract_grammar, gbnf_backend, lark_backend

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(REPO, "tests", "fixtures", "grammar")
GBNF_PATH = os.path.join(REPO, "tools", "grammar", "vson-x.gbnf")
ROUTING_TABLES = os.path.join(REPO, "cli", "src", "penman", "routing-tables.json")

#: Which corpus each grammar has to accept, and which reference implementation
#: has to agree. The reference module is named, not re-implemented: the point
#: of the gate is that two independent readings of the same productions land on
#: the same verdict.
CORPORA = {
    "penman": {
        "reference": "tools.penman.vson_penman",
        "files": ["examples/throne_room.vson", "examples/gallery/*.vson"],
    },
    "vson-x": {
        "reference": "tools.vson_x.vson_x",
        "files": ["examples/gallery-x/*.x.vson", "tests/fixtures/grammar/positive/*.x.vson"],
    },
}

#: §D.3's terminals, and the constant each is spelled a second time as inside
#: the reference lexer. The names differ because the module predates the
#: appendix; the sets must not.
LEXER_CONSTANTS = {
    "TRAIT_KEYWORD": "TRAIT_KEYWORDS",
    "CONCEPT": "CONCEPT_KINDS",
    "RCC_TOKEN": "RCC_TOKENS",
    "DIR_TOKEN": "DIRECTIONAL_TOKENS",
    "SYM_LEMMA": "SYMMETRIC_LEMMAS",
}


class Failure(Exception):
    """A claim in the module docstring does not hold."""


def _reference(module: str) -> Callable[[str], object]:
    import importlib

    return importlib.import_module(module).parse


def _accepts(parse: Callable[[str], object], text: str) -> bool:
    try:
        parse(text)
        return True
    except Exception:
        return False


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _expand(patterns: List[str]) -> List[str]:
    out: List[str] = []
    for pattern in patterns:
        out.extend(sorted(glob.glob(os.path.join(REPO, pattern))))
    return out


# ---------------------------------------------------------------------------
# 1 + 2 — the grammars build, and accept the corpus
# ---------------------------------------------------------------------------


def check_grammars(report: List[str]) -> Dict[str, build.SpecGrammar]:
    grammars = {}
    for name in sorted(CORPORA):
        spec = build.load(name)
        parser = spec.parser()
        grammars[name] = spec
        rules = len(spec.grammar.productions())
        terms = len(spec.lark.terminals)
        report.append(
            "  OK  %-7s %2d productions, %2d terminals, LALR(1) built from the spec"
            % (name, rules, terms)
        )
        reference = _reference(CORPORA[name]["reference"])
        files = _expand(CORPORA[name]["files"])
        if not files:
            raise Failure("%s has an empty positive corpus" % name)
        for path in files:
            text = _read(path)
            rel = os.path.relpath(path, REPO)
            if not _accepts(parser.parse, text):
                raise Failure("the generated %s parser rejects %s" % (name, rel))
            if not _accepts(reference, text):
                raise Failure("the reference %s parser rejects %s" % (name, rel))
        report.append(
            "  OK  %-7s %2d documents accepted by the generated parser and by %s"
            % (name, len(files), CORPORA[name]["reference"])
        )
    return grammars


# ---------------------------------------------------------------------------
# 3 — §D.3's closed vocabularies
# ---------------------------------------------------------------------------


def check_vocabularies(spec: build.SpecGrammar, report: List[str]) -> None:
    from tools.vson_x import vson_x

    declared = spec.closed_vocabularies()
    counts = extract_grammar.vocabulary_counts(spec.spec_text)
    if set(declared) != set(counts):
        raise Failure(
            "§D.3 states counts for %s but declares productions for %s"
            % (sorted(counts), sorted(declared))
        )
    for name, members in sorted(declared.items()):
        if len(members) != len(set(members)):
            raise Failure("%s lists a token twice" % name)
        if len(members) != counts[name]:
            raise Failure(
                "§D.3 says %s has %d tokens; the production declares %d"
                % (name, counts[name], len(members))
            )
        constant = LEXER_CONSTANTS.get(name)
        if constant is None:
            raise Failure("no reference-lexer constant is mapped to %s" % name)
        shipped = getattr(vson_x, constant)
        if set(members) != set(shipped):
            raise Failure(
                "%s and %s.%s differ: spec-only %s, lexer-only %s"
                % (
                    name,
                    vson_x.__name__,
                    constant,
                    sorted(set(members) - set(shipped)),
                    sorted(set(shipped) - set(members)),
                )
            )
    with open(ROUTING_TABLES, "r", encoding="utf-8") as fh:
        routing = json.load(fh)
    if set(declared["RCC_TOKEN"]) != set(routing["rcc_values"]):
        raise Failure("RCC_TOKEN and routing-tables.json rcc_values differ")
    report.append(
        "  OK  §D.3   %d closed vocabularies agree with their counts, the "
        "reference lexer and routing-tables.json" % len(declared)
    )


def check_vocabulary_closure(spec: build.SpecGrammar, report: List[str]) -> None:
    parser = spec.parser()
    reference = _reference(CORPORA["vson-x"]["reference"])
    declared = sorted(spec.closed_vocabularies())
    found = sorted(
        os.path.basename(p)[: -len(".x.vson")]
        for p in glob.glob(os.path.join(FIXTURES, "vocabulary", "*.x.vson"))
    )
    if found != declared:
        raise Failure(
            "vocabulary fixtures %s do not match the closed vocabularies %s"
            % (found, declared)
        )
    for name in declared:
        path = os.path.join(FIXTURES, "vocabulary", "%s.x.vson" % name)
        text = _read(path)
        if _accepts(parser.parse, text):
            raise Failure("the generated parser accepts an out-of-%s token" % name)
        if _accepts(reference, text):
            raise Failure("the reference parser accepts an out-of-%s token" % name)
    report.append(
        "  OK  §D.3   %d out-of-vocabulary tokens rejected by both parsers" % len(declared)
    )


# ---------------------------------------------------------------------------
# 4 — §D.7's Decided-by column
# ---------------------------------------------------------------------------


def check_error_rows(spec: build.SpecGrammar, report: List[str]) -> None:
    parser = spec.parser()
    reference = _reference(CORPORA["vson-x"]["reference"])
    rows = extract_grammar.error_rows(spec.spec_text)
    fixtures: Dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(FIXTURES, "negative", "*.x.vson"))):
        match = re.match(r"(E\d+)_", os.path.basename(path))
        if match is None:
            raise Failure("%s is not named for a §D.7 row" % os.path.basename(path))
        if match.group(1) in fixtures:
            raise Failure("two fixtures claim §D.7 row %s" % match.group(1))
        fixtures[match.group(1)] = path
    missing = [row for row, _ in rows if row not in fixtures]
    orphan = [row for row in fixtures if row not in {r for r, _ in rows}]
    if missing or orphan:
        raise Failure(
            "§D.7 rows without a fixture: %s; fixtures without a row: %s"
            % (missing or "none", orphan or "none")
        )
    by_grammar = 0
    for row, decided in rows:
        text = _read(fixtures[row])
        rel = os.path.relpath(fixtures[row], REPO)
        if _accepts(reference, text):
            raise Failure("§D.7 %s: the reference parser accepts %s" % (row, rel))
        rejected = not _accepts(parser.parse, text)
        if decided == "grammar":
            by_grammar += 1
            if not rejected:
                raise Failure(
                    "§D.7 %s says `grammar` but the generated parser accepts %s"
                    % (row, rel)
                )
        elif rejected:
            raise Failure(
                "§D.7 %s says `parser` but the generated parser already rejects %s "
                "— the column is behind the grammar" % (row, rel)
            )
    report.append(
        "  OK  §D.7   %d rows, %d decided by the grammar and %d by the parser, "
        "split as the column says" % (len(rows), by_grammar, len(rows) - by_grammar)
    )


# ---------------------------------------------------------------------------
# 5 — the constrained-decoding artifact
# ---------------------------------------------------------------------------


def generate_gbnf(spec: build.SpecGrammar) -> str:
    """GBNF for the VSON-X grammar, from a tree the Lark rules never touched."""
    translator = lark_backend.Translator(
        ebnf.parse(spec.ebnf_source), spec.scanner_order, None
    )
    return gbnf_backend.translate(translator)


def check_gbnf(spec: build.SpecGrammar, report: List[str], write: bool) -> None:
    generated = generate_gbnf(spec)
    if write:
        with open(GBNF_PATH, "w", encoding="utf-8") as fh:
            fh.write(generated)
        report.append("  OK  gbnf    wrote %s" % os.path.relpath(GBNF_PATH, REPO))
    else:
        if not os.path.exists(GBNF_PATH):
            raise Failure(
                "%s is missing; run `make grammar-gbnf`" % os.path.relpath(GBNF_PATH, REPO)
            )
        if _read(GBNF_PATH) != generated:
            raise Failure(
                "%s has drifted from the spec; run `make grammar-gbnf`"
                % os.path.relpath(GBNF_PATH, REPO)
            )
    rules = gbnf_backend.read(_read(GBNF_PATH))
    import lark

    matcher = lark.Lark(
        gbnf_backend.to_lark(rules),
        start=gbnf_backend.ROOT_RULE,
        parser="earley",
        lexer="dynamic",
        ambiguity="resolve",
    )
    corpus = _expand(["examples/gallery-x/*.x.vson"])
    for path in corpus:
        if not _accepts(matcher.parse, _read(path)):
            raise Failure(
                "the GBNF does not admit %s" % os.path.relpath(path, REPO)
            )
    report.append(
        "  OK  gbnf    %d rules, re-read as GBNF, admits all %d shipped VSON-X scenes"
        % (len(rules.order), len(corpus))
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(write_gbnf: bool = False) -> int:
    report: List[str] = []
    try:
        grammars = check_grammars(report)
        check_vocabularies(grammars["vson-x"], report)
        check_error_rows(grammars["vson-x"], report)
        check_vocabulary_closure(grammars["vson-x"], report)
        check_gbnf(grammars["vson-x"], report, write_gbnf)
    except (Failure, extract_grammar.ExtractionError, ebnf.EbnfError,
            lark_backend.TranslationError, gbnf_backend.GbnfError) as exc:
        for line in report:
            print(line)
        print("grammar-check: FAILED — %s" % exc, file=sys.stderr)
        return 1
    for line in report:
        print(line)
    return 0


def _main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--write-gbnf",
        action="store_true",
        help="regenerate tools/grammar/vson-x.gbnf instead of comparing it",
    )
    args = ap.parse_args(argv[1:])
    try:
        import lark  # noqa: F401
    except ImportError:
        print(
            "grammar-check: lark is not installed. It is a dev dependency, not a\n"
            "               runtime one: `pip install -e \".[dev]\"` (or `make deps`).\n"
            "               This gate does not skip itself — a check that cannot run\n"
            "               is not a check that passed.",
            file=sys.stderr,
        )
        return 2
    return run(args.write_gbnf)


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
