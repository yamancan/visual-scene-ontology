#!/usr/bin/env python3
"""Pull the normative grammars out of `docs/vson.md`. The spec is the source.

`docs/vson.md` §2 ranks the spec above every other artifact in this repository,
so a grammar copied out of it is a second source that can disagree with the
first. This module refuses to make that copy: everything the translators need
is read out of the Markdown at run time.

What is extracted, and from where
---------------------------------

  * **Productions** — the fenced ` ```ebnf ` blocks of Appendix B (VSON-P) and
    of §D.2 / §D.3 / §D.5 (VSON-X), located by heading, concatenated in
    document order. §D.1 fixes the notation for all of them.
  * **Scanner order** — the numbered token table that opens Appendix B and
    §D.2. "At each position the scanner tries the alternatives below in order"
    is a normative statement about the lexer, and it is what makes `35mm` one
    `UNIT` rather than a `NUM` followed by an `IDENT`; the translator turns the
    row numbers into terminal priorities.
  * **Item-boundary sigils** — §D.4's lead-pattern table. The rule it states —
    a bare `IDENT` is a handle when the token after it is one of five sigils,
    and a positional ref otherwise — has no EBNF spelling, so the translator
    injects it, and takes the sigil set from that table rather than from a list
    of its own.
  * **Closed-vocabulary counts** — the "14 tokens", "12 tokens" … figures §D.3
    states in prose, checked against the sets the §D.3 block declares. A
    spelled count is a copy of the list too, and the one a reader trusts first.
  * **Parse-error rows** — §D.7's table, with the row identifier and the
    `Decided by` column. `make grammar-check` holds one negative fixture per
    row and asserts that split.

Exit codes (CLI)
----------------
  0  the requested block was found and printed.
  1  the spec does not carry it in the shape this module requires.

Usage
-----
  python3 -m tools.grammar.extract_grammar --grammar penman
  python3 -m tools.grammar.extract_grammar --grammar vson-x
  python3 -m tools.grammar.extract_grammar --scanner-order vson-x
  python3 -m tools.grammar.extract_grammar --error-rows
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC_PATH = os.path.join(REPO, "docs", "vson.md")


class ExtractionError(Exception):
    """The spec does not carry a block in the shape the translator needs."""


# ---------------------------------------------------------------------------
# Markdown navigation
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"^```(\w*)[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_ROW_RE = re.compile(r"^\|(.*)\|[ \t]*$", re.MULTILINE)


def spec_text(path: Optional[str] = None) -> str:
    with open(path or SPEC_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def section(text: str, title_prefix: str) -> str:
    """Body of the heading whose title starts with `title_prefix`.

    The body runs to the next heading of the same or a shallower level, so
    `section(text, "Appendix D")` carries §D.1 through §D.10 and
    `section(text, "D.3")` carries only that subsection.
    """
    matches = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2)
        if not title.startswith(title_prefix):
            continue
        end = len(text)
        for later in matches[i + 1:]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        return text[m.end():end]
    raise ExtractionError("docs/vson.md carries no heading starting %r" % title_prefix)


def fenced_blocks(text: str, lang: str = "ebnf") -> List[str]:
    """Every fenced block of the given language, in document order."""
    return [m.group(2) for m in _FENCE_RE.finditer(text) if m.group(1) == lang]


def table_rows(text: str) -> List[List[str]]:
    """Cells of every Markdown table row in `text`, separator rows dropped."""
    rows = []
    for m in _ROW_RE.finditer(text):
        cells = [c.strip() for c in m.group(1).split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        rows.append(cells)
    return rows


def _ticked(cell: str) -> List[str]:
    """The backticked spans of a table cell, in order."""
    return re.findall(r"`([^`]+)`", cell)


# ---------------------------------------------------------------------------
# The two grammars
# ---------------------------------------------------------------------------

#: Which headings carry which grammar. The value is the heading that opens the
#: scanner-order table, followed by the headings whose ```ebnf blocks make up
#: the productions — Appendix B keeps both under one heading; Appendix D splits
#: the lexical productions (§D.2), the closed vocabularies (§D.3) and the
#: syntactic productions (§D.5) across three.
#:
#: `lead_patterns` names the section carrying the item-boundary table of the
#: §D.4 kind, or is None for a grammar whose items need no such rule. VSON-P
#: brackets its nodes, so nothing in Appendix B depends on lookahead.
GRAMMARS = {
    "penman": {
        "scanner": "Appendix B",
        "blocks": ["Appendix B"],
        "lead_patterns": None,
    },
    "vson-x": {
        "scanner": "D.2",
        "blocks": ["D.2", "D.3", "D.5"],
        "lead_patterns": "D.4",
    },
}


def grammar_source(name: str, text: Optional[str] = None) -> str:
    """The EBNF of one grammar: every block of every section, concatenated."""
    if name not in GRAMMARS:
        raise ExtractionError("no such grammar: %r" % name)
    text = spec_text() if text is None else text
    out = []
    for heading in GRAMMARS[name]["blocks"]:
        blocks = fenced_blocks(section(text, heading))
        if not blocks:
            raise ExtractionError("%s carries no ```ebnf block" % heading)
        out.extend(blocks)
    return "\n".join(out)


def scanner_order(name: str, text: Optional[str] = None) -> Dict[str, int]:
    """Terminal name -> row number in the section's scanner-order table.

    Only rows whose Token cell is a single backticked ALL-CAPS name are
    returned: the sigil rows name literals the translator emits anonymously,
    and the last row is the lexical-error case, which is not a terminal.
    """
    text = spec_text() if text is None else text
    body = section(text, GRAMMARS[name]["scanner"])
    order: Dict[str, int] = {}
    highest = 0
    for cells in table_rows(body):
        if len(cells) < 2 or not re.fullmatch(r"\d+", cells[0]):
            continue
        highest = max(highest, int(cells[0]))
        ticked = _ticked(cells[1])
        if len(ticked) == 1 and re.fullmatch(r"[A-Z][A-Z0-9_]*", ticked[0]):
            order[ticked[0]] = int(cells[0])
    if not order:
        raise ExtractionError("%s carries no scanner-order table" % name)
    order["#rows"] = highest
    return order


def handle_lead_patterns(
    heading: str = "D.4", text: Optional[str] = None
) -> Tuple[List[str], List[str]]:
    """§D.4's handle rows: the follow sigils, and the items they select.

    A row reads ``| `[ "@" ] IDENT "/"` | `entity_tail` |``. The sigil is the
    lookahead §D.4 spends at the handle position; the item name is what the
    grammar reaches through `handle_item`. The translator needs both: the
    sigils to build the guarded terminal, the item names to find — without
    being told — which production of §D.5 the guard belongs to.
    """
    text = spec_text() if text is None else text
    body = section(text, heading)
    sigils: List[str] = []
    items: List[str] = []
    pattern = re.compile(r'^\[\s*"@"\s*\]\s+IDENT\s+"(.+)"$')
    for cells in table_rows(body):
        if len(cells) < 2:
            continue
        lead = _ticked(cells[0])
        item = _ticked(cells[1])
        if len(lead) != 1 or len(item) != 1:
            continue
        m = pattern.match(lead[0])
        if m:
            sigils.append(m.group(1))
            items.append(item[0])
    if not sigils:
        raise ExtractionError(
            "%s carries no `[ \"@\" ] IDENT \"<sigil>\"` rows" % heading
        )
    return sigils, items


def vocabulary_counts(text: Optional[str] = None) -> Dict[str, int]:
    """§D.3's spelled counts: terminal name -> the number of tokens it claims.

    Every paragraph opens ``**`NAME`** — <n> tokens``; `DIR_TOKEN` opens
    "9 tokens accepted, 6 conformant", and it is the accepted set the grammar
    admits.
    """
    text = spec_text() if text is None else text
    body = section(text, "D.3")
    counts = {}
    for m in re.finditer(r"\*\*`([A-Z][A-Z0-9_]*)`\*\*\s+—\s+(\d+)\s+tokens", body):
        counts[m.group(1)] = int(m.group(2))
    if not counts:
        raise ExtractionError("§D.3 states no token counts")
    return counts


def error_rows(text: Optional[str] = None) -> List[Tuple[str, str]]:
    """§D.7's parse-error table: (row id, `grammar` or `parser`)."""
    text = spec_text() if text is None else text
    body = section(text, "D.7")
    rows = []
    for cells in table_rows(body):
        if len(cells) < 4 or not re.fullmatch(r"E\d+", cells[0]):
            continue
        decided = cells[3].strip()
        if decided not in ("grammar", "parser"):
            raise ExtractionError(
                "§D.7 row %s has an unknown Decided-by value %r" % (cells[0], decided)
            )
        rows.append((cells[0], decided))
    if not rows:
        raise ExtractionError("§D.7 carries no identified error rows")
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--grammar", choices=sorted(GRAMMARS), help="print the EBNF")
    ap.add_argument("--scanner-order", choices=sorted(GRAMMARS))
    ap.add_argument("--sigils", action="store_true", help="print §D.4's handle sigils")
    ap.add_argument("--counts", action="store_true", help="print §D.3's spelled counts")
    ap.add_argument("--error-rows", action="store_true", help="print §D.7's rows")
    args = ap.parse_args(argv[1:])

    try:
        if args.grammar:
            sys.stdout.write(grammar_source(args.grammar))
        elif args.scanner_order:
            order = scanner_order(args.scanner_order)
            rows = order.pop("#rows")
            for name, row in sorted(order.items(), key=lambda kv: kv[1]):
                print("%2d/%d  %s" % (row, rows, name))
        elif args.sigils:
            sigils, items = handle_lead_patterns()
            for sigil, item in zip(sigils, items):
                print("%-3s %s" % (sigil, item))
        elif args.counts:
            for name, n in sorted(vocabulary_counts().items()):
                print("%-14s %d" % (name, n))
        elif args.error_rows:
            for row_id, decided in error_rows():
                print("%-4s %s" % (row_id, decided))
        else:
            ap.print_help()
    except ExtractionError as exc:
        print("extract_grammar: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
