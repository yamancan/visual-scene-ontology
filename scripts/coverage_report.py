#!/usr/bin/env python3
"""Measure what share of a dataset's vocabulary the mapping tables reach.

This is the arithmetic behind [docs/eval/coverage.md](../docs/eval/coverage.md),
kept in one place so the document cannot drift from the data. It reads two
things and invents nothing:

  * the **measured vocabulary files** under ``docs/eval/vocab/`` — one row per
    source predicate or attribute with its token count, each file carrying the
    URL, sha256 and retrieval date of the dump it was counted from, and the
    method used to count it;
  * the **mapping tables** under ``tools/importers/mappings/`` — the same data
    the importers run on.

and reports, per dataset and axis:

  * **vocabulary (type) coverage** — how many distinct source strings the table
    decides, out of how many the dump contains;
  * **token coverage** — what share of the dump's occurrences those strings
    account for.

The two are different numbers and the difference is the finding: an open
vocabulary can be 1% covered by type and 93% covered by token.

Neither number says a conversion is *correct*. A mapping the table calls
``approximate`` is counted as covered, and the note beside it is what says
what was lost — see the ``approximate`` column and docs/vson.md §2.1.

Usage
-----
  python3 scripts/coverage_report.py            # print the table
  python3 scripts/coverage_report.py --write    # write it into coverage.md
  python3 scripts/coverage_report.py --check    # fail if coverage.md is stale

Exit codes: 0 current, 1 stale (``--check``), 2 the inputs could not be read.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOCAB = os.path.join(REPO, "docs", "eval", "vocab")
MAPPINGS = os.path.join(REPO, "tools", "importers", "mappings")
DOC = os.path.join(REPO, "docs", "eval", "coverage.md")

BEGIN = "<!-- coverage:begin -->"
END = "<!-- coverage:end -->"

#: (vocabulary file, mapping table, section of the table it is measured
#: against). The third element is what makes this a measurement of the shipped
#: table rather than of a hand-kept list.
AXES = (
    ("gqa-relations.tsv", "gqa", "predicates"),
    ("gqa-attributes.tsv", "gqa", "attributes"),
    ("vg-predicates.tsv", "vg", "predicates"),
    ("vg-attributes.tsv", "vg", "attributes"),
    ("psg-predicates.tsv", "psg", "predicates"),
)


class Vocabulary(object):
    """One measured vocabulary file: its header and its rows."""

    def __init__(self, path):
        self.path = path
        self.header = {}
        self.rows = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.rstrip("\n")
                if line.startswith("# ---"):
                    continue
                if line.startswith("#"):
                    key, _, value = line[1:].partition(":")
                    self.header[key.strip()] = value.strip()
                    continue
                if line.startswith("count\t"):
                    continue
                if not line:
                    continue
                count, _, name = line.partition("\t")
                self.rows.append((name, None if count == "-" else int(count)))

    @property
    def has_counts(self):
        return self.header.get("token_counts", "").startswith("none") is False

    @property
    def total_types(self):
        return int(self.header["total_types"])

    @property
    def total_tokens(self):
        value = self.header.get("total_tokens", "unknown")
        return None if value == "unknown" else int(value)

    @property
    def complete(self):
        """True when the file lists every type in the measured vocabulary."""
        return len(self.rows) == self.total_types


def outcome(entry):
    if entry is None:
        return "unmapped"
    if entry["kind"] == "drop":
        return "dropped"
    return entry["fidelity"]


def measure(vocabulary, table, section):
    """Classify every row, and total it by type and by token."""
    entries = table[section]
    types = {"exact": 0, "approximate": 0, "dropped": 0, "unmapped": 0}
    tokens = {"exact": 0, "approximate": 0, "dropped": 0, "unmapped": 0}
    listed_tokens = 0
    for name, count in vocabulary.rows:
        verdict = outcome(entries.get(name))
        types[verdict] += 1
        if count is not None:
            tokens[verdict] += count
            listed_tokens += count

    if not vocabulary.complete:
        # Every type the table covers is listed, so an unlisted type is an
        # uncovered one: the residual is the remainder, not an unknown.
        types["unmapped"] += vocabulary.total_types - len(vocabulary.rows)
        if vocabulary.total_tokens is not None:
            tokens["unmapped"] += vocabulary.total_tokens - listed_tokens

    covered_types = types["exact"] + types["approximate"]
    decided_types = covered_types + types["dropped"]
    covered_tokens = tokens["exact"] + tokens["approximate"]
    decided_tokens = covered_tokens + tokens["dropped"]
    return {
        "types": types,
        "tokens": tokens,
        "total_types": vocabulary.total_types,
        "total_tokens": vocabulary.total_tokens,
        "covered_types": covered_types,
        "decided_types": decided_types,
        "covered_tokens": covered_tokens,
        "decided_tokens": decided_tokens,
        # Entries the table carries that this vocabulary never used: spelling
        # variants of another dataset, or a stale row.
        "table_entries": len(entries),
        "unused_entries": len(
            set(entries) - {name for name, _ in vocabulary.rows}
        ),
    }


def percent(part, whole):
    if not whole:
        return "n/a"
    return "%.2f%%" % (100.0 * part / whole)


def render():
    """The generated block: two tables and the residual heads."""
    lines = []
    lines.append("| Dataset | Axis | Vocabulary (types) | Expressed | "
                 "Dropped with a reason | Not yet decided |")
    lines.append("|---|---|---|---|---|---|")
    token_rows = []
    residuals = []
    for filename, dataset, section in AXES:
        vocabulary = Vocabulary(os.path.join(VOCAB, filename))
        with open(os.path.join(MAPPINGS, "%s.json" % dataset),
                  encoding="utf-8") as handle:
            table = json.load(handle)
        result = measure(vocabulary, table, section)
        axis = vocabulary.header["axis"]
        lines.append(
            "| %s | %s | %d | %d (%s) | %d (%s) | %d (%s) |"
            % (dataset.upper(), axis, result["total_types"],
               result["covered_types"],
               percent(result["covered_types"], result["total_types"]),
               result["types"]["dropped"],
               percent(result["types"]["dropped"], result["total_types"]),
               result["types"]["unmapped"],
               percent(result["types"]["unmapped"], result["total_types"])))
        if result["total_tokens"] is None:
            token_rows.append(
                "| %s | %s | — | — | — | — |" % (dataset.upper(), axis)
            )
            continue
        token_rows.append(
            "| %s | %s | %d | %d (%s) | %d (%s) | %d (%s) |"
            % (dataset.upper(), axis, result["total_tokens"],
               result["covered_tokens"],
               percent(result["covered_tokens"], result["total_tokens"]),
               result["tokens"]["dropped"],
               percent(result["tokens"]["dropped"], result["total_tokens"]),
               result["tokens"]["unmapped"],
               percent(result["tokens"]["unmapped"], result["total_tokens"])))
        residuals.append((dataset, axis, vocabulary, table[section]))

    lines.append("")
    lines.append("| Dataset | Axis | Occurrences (tokens) | Expressed | "
                 "Dropped with a reason | Not yet decided |")
    lines.append("|---|---|---|---|---|---|")
    lines.extend(token_rows)

    lines.append("")
    lines.append("**Exact and approximate, separately.** An `approximate` "
                 "mapping is one the table itself marks as losing or adding "
                 "something, with a note beside it saying what.")
    lines.append("")
    lines.append("| Dataset | Axis | Exact (types) | Approximate (types) | "
                 "Exact (tokens) | Approximate (tokens) |")
    lines.append("|---|---|---|---|---|---|")
    for filename, dataset, section in AXES:
        vocabulary = Vocabulary(os.path.join(VOCAB, filename))
        with open(os.path.join(MAPPINGS, "%s.json" % dataset),
                  encoding="utf-8") as handle:
            table = json.load(handle)
        result = measure(vocabulary, table, section)
        if result["total_tokens"] is None:
            lines.append(
                "| %s | %s | %d | %d | — | — |"
                % (dataset.upper(), vocabulary.header["axis"],
                   result["types"]["exact"], result["types"]["approximate"]))
            continue
        lines.append(
            "| %s | %s | %d | %d | %s | %s |"
            % (dataset.upper(), vocabulary.header["axis"],
               result["types"]["exact"], result["types"]["approximate"],
               percent(result["tokens"]["exact"], result["total_tokens"]),
               percent(result["tokens"]["approximate"],
                       result["total_tokens"])))

    lines.append("")
    lines.append("**Why a drop is a drop.** Every dropped entry carries a "
                 "reason, so the residual is grouped rather than lumped. "
                 "Reasons are shown abbreviated; the tables carry them in "
                 "full.")
    lines.append("")
    lines.append("| Dataset | Axis | Reason | Types | Tokens |")
    lines.append("|---|---|---|---|---|")
    for filename, dataset, section in AXES:
        vocabulary = Vocabulary(os.path.join(VOCAB, filename))
        with open(os.path.join(MAPPINGS, "%s.json" % dataset),
                  encoding="utf-8") as handle:
            table = json.load(handle)
        entries = table[section]
        by_reason = {}
        for name, count in vocabulary.rows:
            entry = entries.get(name)
            if not entry or entry["kind"] != "drop":
                continue
            types, tokens = by_reason.get(entry["reason"], (0, 0))
            by_reason[entry["reason"]] = (
                types + 1, tokens + (count or 0)
            )
        for reason in sorted(by_reason, key=lambda r: (-by_reason[r][1], r)):
            types, tokens = by_reason[reason]
            short = reason.split(";")[0].strip()
            if len(short) > 64:
                short = short[:61].rstrip() + "…"
            lines.append(
                "| %s | %s | %s | %d | %s |"
                % (dataset.upper(), vocabulary.header["axis"], short, types,
                   "—" if vocabulary.total_tokens is None else str(tokens)))

    lines.append("")
    lines.append("**The viewer that is not there (C5).** A source predicate "
                 "that becomes a `vso:directional` value cannot be written "
                 "without a `vso:viewer`, and none of these datasets has one. "
                 "This is how much of each corpus that clause reaches.")
    lines.append("")
    lines.append("| Dataset | Axis | Directional types | Directional tokens | "
                 "Share of all tokens |")
    lines.append("|---|---|---|---|---|")
    for filename, dataset, section in AXES:
        if section != "predicates":
            continue
        vocabulary = Vocabulary(os.path.join(VOCAB, filename))
        with open(os.path.join(MAPPINGS, "%s.json" % dataset),
                  encoding="utf-8") as handle:
            table = json.load(handle)
        entries = table[section]
        types, tokens = 0, 0
        for name, count in vocabulary.rows:
            entry = entries.get(name)
            if not entry or not entry.get("directional"):
                continue
            types += 1
            if count is not None:
                tokens += count
        total = vocabulary.total_tokens
        lines.append(
            "| %s | %s | %d | %s | %s |"
            % (dataset.upper(), vocabulary.header["axis"], types,
               "—" if total is None else str(tokens),
               "—" if total is None else percent(tokens, total)))

    lines.append("")
    lines.append("**The ranked residual** — the most frequent source strings "
                 "the tables do not decide, which is where the next mapping "
                 "work is and what the scope boundary looks like from inside.")
    lines.append("")
    for dataset, axis, vocabulary, entries in residuals:
        residual = [
            (name, count) for name, count in vocabulary.rows
            if name not in entries and count is not None
        ]
        residual.sort(key=lambda pair: (-pair[1], pair[0]))
        if not residual:
            lines.append("- **%s %s** — none: every measured type is decided."
                         % (dataset.upper(), axis))
            continue
        head = ", ".join(
            "`%s` (%d)" % (name, count) for name, count in residual[:12]
        )
        lines.append("- **%s %s** — %s" % (dataset.upper(), axis, head))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true",
                        help="write the block into docs/eval/coverage.md")
    parser.add_argument("--check", action="store_true",
                        help="fail if docs/eval/coverage.md is stale")
    args = parser.parse_args(argv)

    try:
        block = render()
    except (OSError, KeyError, ValueError) as error:
        sys.stderr.write("coverage-report: could not measure: %s\n" % error)
        return 2

    if not (args.write or args.check):
        sys.stdout.write(block)
        return 0

    try:
        with open(DOC, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as error:
        sys.stderr.write("coverage-report: %s\n" % error)
        return 2
    if BEGIN not in text or END not in text:
        sys.stderr.write(
            "coverage-report: %s carries no %s / %s markers\n"
            % (DOC, BEGIN, END)
        )
        return 2
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    updated = head + BEGIN + "\n\n" + block + "\n" + END + tail

    if args.write:
        with open(DOC, "w", encoding="utf-8") as handle:
            handle.write(updated)
        sys.stdout.write("  wrote %s\n" % os.path.relpath(DOC, REPO))
        return 0

    if updated != text:
        sys.stderr.write(
            "coverage-report: docs/eval/coverage.md does not match the "
            "measured vocabularies and the shipped mapping tables. "
            "Re-run with --write, and check what moved before you do.\n"
        )
        return 1
    sys.stdout.write("  OK docs/eval/coverage.md matches the measurement\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
