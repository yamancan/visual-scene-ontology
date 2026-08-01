#!/usr/bin/env python3
"""Keep the closed Dimension registry to one list, spelled in five places.

`vso:dimension` is closed under the VSO namespace: the admissible values are
exactly the `vso:Dimension` individuals declared in `ontology/vso.ttl`, and any
other IRI in that slot under the VSO namespace is an orphan term, non-conformant
by clause C2 (`docs/vson.md` §2). One list — written down five times:

  1. `ontology/vso.ttl`      the `vso:Dimension` individuals. THE SOURCE.
  2. `ontology/vso.ttl`      the `owl:AllDifferent` list over them. A member
                             missing here is a member that can silently
                             `owl:sameAs`-collapse under prp-fp, because
                             `vso:dimension` is an `owl:FunctionalProperty`.
  3. `docs/vson.md` §5.5.1   the registry table, with a Bearer/Reading gloss.
  4. `docs/vson-x-semantics.md` §3.2.1  the closed list for the VSON-X surface,
                             whose `*key` → PascalCase derivation mints a
                             VSO-namespace IRI mechanically. A key outside the
                             registry is a C2 failure, not a warning.
  5. `skills/vson-extractor-x/SKILL.md`  the same list, as the extractor skill
                             states it to a model.

Copies 1 and 2 were already pinned against each other by
`tests/test_shapes_gate.py`. Nothing compared them to the prose, and the prose
had drifted: copies 4 and 5 carried twenty names against the ontology's
twenty-one, omitting `vso:Eye` — the second Persona invariant of `docs/vson.md`
§5.3.4's own worked example. A portrait scene emitting `*eye blue` therefore
produced a `vso:` IRI the skill's own list did not contain.

Two copies are deliberately NOT checked here, because they are subsets by
design and say so:

  * `skills/vson-extractor/SKILL.md` and `tools/extractor/prompts/` state the
    ten (respectively eight) dimensions the *Penman* extractor is prompted to
    emit. A prompt naming fewer axes than the registry is a tuning decision;
    naming one the registry does not carry would be the bug, and the C2
    coverage test in `tests/` catches that from the corpus side.
  * `tools/extractor/baseline/ablations/` are frozen prompt variants of a
    measured experiment. Editing one would invalidate the comparison it exists
    to support.

This gate also checks the *spelled* count. "The twenty-one dimensions below"
is a copy of the registry too — a shorter one, and the one a reader trusts
first.

Exit codes
----------
  0  every copy carries the same names.
  1  a copy has drifted, or a spelled count is wrong.

Usage
-----
  python3 scripts/check_registry_drift.py
  python3 scripts/check_registry_drift.py --selftest   # comparators only
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import rdflib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ONTOLOGY = "ontology/vso.ttl"
SPEC = "docs/vson.md"
X_SEMANTICS = "docs/vson-x-semantics.md"
SKILL = "skills/vson-extractor-x/SKILL.md"

VSO = rdflib.Namespace("https://w3id.org/vson/v1/ontology#")
OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")

SPEC_SECTION = "#### 5.5.1 Dimension registry"
SPEC_ENUM_SECTION = "### 5.12 Reserved + closed enumerations"
X_SECTION = "#### 3.2.1 Closed dimensions"
# SKILL.md has no heading over its list — it is one labelled line among the
# skill's other closed vocabularies, so the label is the anchor.
SKILL_MARKER = "**Quality dimensions**"

# Number words a registry sentence plausibly reaches for. Bounded on purpose:
# the point is to catch a stale "twenty" left behind by a twenty-first member,
# not to build a spell-out library.
COUNT_WORDS = {
    18: "eighteen",
    19: "nineteen",
    20: "twenty",
    21: "twenty-one",
    22: "twenty-two",
    23: "twenty-three",
    24: "twenty-four",
    25: "twenty-five",
}


def read(rel: str) -> str:
    with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
        return handle.read()


# --------------------------------------------------------------------------
# Readers — one per copy. Each returns local names in the order it states them.
# --------------------------------------------------------------------------
def section(markdown: str, heading_prefix: str) -> str:
    """The body of one markdown section, up to the next heading of any level.

    Returns "" when the heading is absent, which the caller reports: a section
    that has been renamed away is a copy this gate has stopped watching, and
    that has to be visible rather than silently green.
    """
    lines = markdown.split("\n")
    body: "list[str]" = []
    inside = False
    for line in lines:
        if line.startswith(heading_prefix):
            inside = True
            continue
        if inside and line.startswith("#"):
            break
        if inside:
            body.append(line)
    return "\n".join(body)


def ontology_individuals(graph: "rdflib.Graph") -> "list[str]":
    """The `vso:Dimension` individuals. Sorted: RDF has no document order."""
    return sorted(
        str(s).split("#")[-1] for s in graph.subjects(rdflib.RDF.type, VSO.Dimension)
    )


def ontology_all_different(graph: "rdflib.Graph") -> "list[str]":
    """The one owl:AllDifferent list that carries dimensions, in list order."""
    declared = set(ontology_individuals(graph))
    found = []
    for node in graph.subjects(rdflib.RDF.type, OWL.AllDifferent):
        for head in graph.objects(node, OWL.distinctMembers):
            members = [str(i).split("#")[-1] for i in graph.items(head)]
            if set(members) & declared:
                found.append(members)
    if len(found) != 1:
        raise LookupError(
            "the dimension registry must sit in exactly one owl:AllDifferent "
            "list; found %d" % len(found)
        )
    return found[0]


def md_table_names(body: str) -> "list[str]":
    """Local names from the first column of a `| \\`vso:X\\` | ... |` table."""
    return re.findall(r"^\|\s*`vso:(\w+)`\s*\|", body, re.MULTILINE)


def marked_line(text: str, marker: str) -> str:
    """The first line carrying a label, or "" — reported like a lost section."""
    for line in text.split("\n"):
        if marker in line:
            return line
    return ""


def md_inline_names(body: str) -> "list[str]":
    """Names from the first backticked, comma-or-space separated list in a body.

    Both spellings ship: `docs/vson-x-semantics.md` §3.2.1 comma-separates,
    `SKILL.md` space-separates. One reader for both, because the thing being
    compared is the set of names, not the punctuation between them.
    """
    for line in body.split("\n"):
        match = re.search(r"`([A-Z][A-Za-z0-9,\s]*)`", line)
        if not match:
            continue
        names = [n for n in re.split(r"[,\s]+", match.group(1)) if n]
        if len(names) > 1:
            return names
    return []


# --------------------------------------------------------------------------
# Comparators — pure, so --selftest and the unit tests exercise them offline.
# --------------------------------------------------------------------------
def copy_problems(source: "list[str]", copy: "list[str]", where: str) -> "list[str]":
    """One copy against the source list. Order is not compared; membership is.

    Order carries meaning in none of the five copies — the ontology groups its
    individuals by theme, §5.5.1 follows the same grouping, and the VSON-X list
    follows neither. Membership is the contract.
    """
    problems = []
    missing = sorted(set(source) - set(copy))
    extra = sorted(set(copy) - set(source))
    duplicated = sorted({n for n in copy if copy.count(n) > 1})
    if missing:
        problems.append("%s is missing %s" % (where, ", ".join(missing)))
    if extra:
        problems.append(
            "%s names %s, which %s does not declare"
            % (where, ", ".join(extra), ONTOLOGY)
        )
    if duplicated:
        problems.append("%s names %s twice" % (where, ", ".join(duplicated)))
    return problems


def count_word_problems(body: str, count: int, where: str) -> "list[str]":
    """The spelled count in prose must be the count of the registry.

    Hyphen-aware boundaries: a plain `\\btwenty\\b` matches inside
    "twenty-one", so a stale "twenty" would hide behind the correct word.
    """
    if count not in COUNT_WORDS:
        return ["%s: %d is outside the spelled-count vocabulary" % (where, count)]
    problems = []
    expected = COUNT_WORDS[count]
    if not re.search(r"(?<![\w-])%s(?![\w-])" % expected, body):
        problems.append(
            "%s: the registry has %d members and the prose never says "
            "'%s'" % (where, count, expected)
        )
    for number, word in sorted(COUNT_WORDS.items()):
        if number == count:
            continue
        if re.search(r"(?<![\w-])%s(?![\w-])" % word, body):
            problems.append(
                "%s: prose says '%s' for a registry of %d — say '%s'"
                % (where, word, count, expected)
            )
    return problems


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
def check() -> int:
    graph = rdflib.Graph()
    graph.parse(os.path.join(REPO, ONTOLOGY), format="turtle")
    source = ontology_individuals(graph)

    spec = read(SPEC)
    spec_body = section(spec, SPEC_SECTION)
    enum_body = section(spec, SPEC_ENUM_SECTION)
    x_body = section(read(X_SEMANTICS), X_SECTION)
    skill_body = marked_line(read(SKILL), SKILL_MARKER)

    copies = (
        ("%s owl:AllDifferent" % ONTOLOGY, ontology_all_different(graph)),
        ("%s §5.5.1 table" % SPEC, md_table_names(spec_body)),
        ("%s §3.2.1 list" % X_SEMANTICS, md_inline_names(x_body)),
        ("%s dimension line" % SKILL, md_inline_names(skill_body)),
    )

    print(
        "registry-check: %d vso:Dimension individual(s) in %s, %d copy/copies"
        % (len(source), ONTOLOGY, len(copies))
    )
    failures: "list[str]" = []

    for where, names in copies:
        if not names:
            failures.append(where)
            print("\n  FAIL  %s  no list found" % where)
            print(
                "        The section or line this gate reads has been renamed "
                "or removed.\n        Point scripts/check_registry_drift.py at "
                "the copy's new home."
            )
            continue
        problems = copy_problems(source, names, where)
        if problems:
            failures.append(where)
            print("\n  FAIL  %s  (%d name(s))" % (where, len(names)))
            for problem in problems:
                print("        %s" % problem)
            continue
        print("  ok    %-46s %d names" % (where, len(names)))

    for where, body in (
        ("%s §5.5.1 prose" % SPEC, spec_body),
        ("%s §5.12 row" % SPEC, enum_body),
    ):
        problems = count_word_problems(body, len(source), where)
        if problems:
            failures.append(where)
            print("\n  FAIL  %s" % where)
            for problem in problems:
                print("        %s" % problem)
            continue
        print("  ok    %-46s says '%s'" % (where, COUNT_WORDS[len(source)]))

    if failures:
        print(
            "\nregistry-check: FAIL — %d copy/copies disagree with %s:"
            % (len(failures), ONTOLOGY)
        )
        for where in failures:
            print("  - %s" % where)
        print(
            "\n%s is the single source. Add the member there first, then bring "
            "every\ncopy to it — a copy that leads is a dimension some producer "
            "will mint and\nsome consumer will reject." % ONTOLOGY
        )
        return 1

    print("\nregistry-check: one registry, %d copy/copies agree." % len(copies))
    return 0


def selftest() -> int:
    """Prove the comparators go red on each drift shape, offline."""
    source = ["Alpha", "Beta", "Gamma"]
    cases = (
        ("same set", copy_problems(source, ["Gamma", "Alpha", "Beta"], "x"), False),
        ("member missing", copy_problems(source, ["Alpha", "Beta"], "x"), True),
        ("member invented", copy_problems(source, source + ["Delta"], "x"), True),
        ("member duplicated", copy_problems(source, source + ["Beta"], "x"), True),
        ("count spelled right", count_word_problems("the twenty-one axes", 21, "x"), False),
        ("count spelled stale", count_word_problems("the twenty axes", 21, "x"), True),
        ("count word absent", count_word_problems("the axes below", 21, "x"), True),
        (
            "hyphen boundary holds",
            count_word_problems("twenty-one, not twenty-two", 21, "x"),
            True,
        ),
    )

    readers = (
        ("table reader", md_table_names("| `vso:Color` | Entity | c |\n| x | y | z |"), ["Color"]),
        ("comma list reader", md_inline_names("`Color, Weight`."), ["Color", "Weight"]),
        ("space list reader", md_inline_names("**Q** — `Color Weight`."), ["Color", "Weight"]),
        ("renamed section", md_inline_names("nothing here"), []),
        (
            "label anchor",
            md_inline_names(marked_line("`Other List`\n**Q** — `Color Weight`.", "**Q**")),
            ["Color", "Weight"],
        ),
        ("label renamed", [marked_line("**Q** — `Color`.", "**R**")], [""]),
    )

    print("registry-check --selftest: %d case(s)" % (len(cases) + len(readers)))
    failures = []
    for label, problems, should_fail in cases:
        if bool(problems) != should_fail:
            failures.append(label)
            print(
                "  BROKEN  %-22s expected %s, got %s"
                % (label, "a failure" if should_fail else "a pass", problems or "a pass")
            )
            continue
        print("  ok      %-22s %s" % (label, "red" if should_fail else "green"))

    for label, found, expected in readers:
        if found != expected:
            failures.append(label)
            print("  BROKEN  %-22s read %s, expected %s" % (label, found, expected))
            continue
        print("  ok      %-22s %s" % (label, found or "(nothing found)"))

    if failures:
        print("\nregistry-check --selftest: FAIL — the comparators do not discriminate.")
        return 1
    print("\nregistry-check --selftest: every comparator goes red on drift.")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description="Check the five copies of the closed Dimension registry.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="exercise the comparators and exit; reads no repository file",
    )
    args = parser.parse_args(argv)
    return selftest() if args.selftest else check()


if __name__ == "__main__":
    sys.exit(main())
