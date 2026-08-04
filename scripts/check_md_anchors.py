#!/usr/bin/env python3
"""Fail the build on any in-repo Markdown link whose anchor does not resolve.

`docs/vson.md` is a single-file spec with an eighteen-entry table of contents
and cross-references running the length of it. Every one of those is an anchor
into a heading of the same file, and every one of them was written by hand
against a slug nobody computed. That does not survive contact with a renderer:
through v1.3 the five appendix headings carried Pandoc-style `{#appendix-a}`
attributes, which GitHub does not implement — it renders the braces as heading
text and mints its own slug — so twenty-four links in this repository pointed
at fragments that did not exist: twenty-two inside the spec, one in a module
docstring, and the README's one citation into Appendix E.7, the paragraph that
retracts the SpatialFact novelty claim.

A broken anchor is not a formatting lag. It is a link that silently does
nothing: the browser stays where it is, the reader concludes the cited
paragraph does not exist, and no test anywhere notices. On a project whose
thesis is that a claim should be checkable, an uncheckable citation is the
worst kind of prose.

This gate computes what the renderer computes.

What it checks
--------------
For every tracked `*.md` file:

  1. **No heading carries a trailing attribute block.** `{#id}`, `{.class}`,
     `{key=value}` are Pandoc/kramdown syntax. GitHub Flavored Markdown has no
     heading-attribute extension, so the braces render as literal text *and*
     become part of the slug. Writing one is always a bug here; the gate says
     so at the heading rather than at every link that trusted it.

  2. **Every link resolves.** Each inline link, each reference definition and
     each `<a href>` is split into a path and a fragment.

       * a path is resolved relative to the linking file and must exist in the
         checkout;
       * a fragment on a Markdown target must equal the GFM slug of a heading
         in that file, or an explicit `<a name>` / `id=` anchor in it;
       * a fragment on a non-Markdown target (`ontology/vso.ttl#Entity`) is a
         name in that file's own vocabulary, not a heading, and is left alone;
       * external `http(s):`/`mailto:` targets are out of scope — this gate
         answers from the tree, like every other gate in `make check`. Live
         URLs are `make live-check`'s job.

  3. **Markdown links written outside Markdown resolve too.** A module
     docstring citing `([Appendix E](../docs/vson.md#…))` is a link a reader
     follows and a link that rots; `tools/canon.py` carried one of the
     twenty-four broken ones. Every tracked non-Markdown file is swept for
     `](path.md#fragment)` and each hit is checked on the same terms.

The slug algorithm
------------------
GitHub's, as implemented by `github-slugger`: render the heading's inline
markup down to text, lowercase it, delete every punctuation and symbol
character except `-` and `_`, replace each remaining space with `-`, and
disambiguate a repeated slug with `-1`, `-2`, ... in document order. An em dash
between two spaces therefore leaves *two* hyphens, which is why the correct
anchor for `## Appendix E — Related work and bibliography` is
`#appendix-e--related-work-and-bibliography` and not the `-` a human would
guess. Guessing is the failure mode this gate exists to remove.

`--selftest` runs the slugger against pinned heading/slug pairs — including
that one — and asserts the checker can go red at all. A gate nobody has seen
fail is a gate nobody should trust.

Exit codes
----------
  0  every anchor resolves.
  1  at least one does not, or a heading carries an attribute block.

Usage
-----
  python3 scripts/check_md_anchors.py
  python3 scripts/check_md_anchors.py --selftest
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# The slug algorithm
# ---------------------------------------------------------------------------

# github-slugger deletes ASCII punctuation and a long list of Unicode
# punctuation and symbol code points. Both sets are exactly "Unicode general
# category P* or S*", minus the two characters GitHub keeps: the hyphen-minus
# it also uses as the space replacement, and the underscore.
_SLUG_KEEP = {"-", "_"}


def gfm_slug(text: str) -> str:
    """Return the anchor GitHub mints for a heading rendered as `text`."""
    out = []
    for ch in text.lower():
        if ch in _SLUG_KEEP:
            out.append(ch)
        elif ch == " ":
            out.append("-")
        elif unicodedata.category(ch)[0] in ("P", "S"):
            continue
        else:
            out.append(ch)
    return "".join(out)


# Inline constructs whose *rendered text* is what the slug is computed from.
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)")
_REF_LINK = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
_HTML_TAG = re.compile(r"<[^>\s][^>]*>")
_CODE_SPAN = re.compile(r"`+")
_ASTERISKS = re.compile(r"\*+")


def _strip_underscore_emphasis(text: str) -> str:
    """Drop `_` emphasis delimiters, keep intraword underscores.

    CommonMark does not open or close emphasis on an underscore run that has a
    word character on both sides, which is what keeps `snake_case` intact —
    and GitHub's slugger keeps `_` as a slug character, so getting this wrong
    changes the anchor.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "_":
            out.append(text[i])
            i += 1
            continue
        j = i
        while j < n and text[j] == "_":
            j += 1
        before = text[i - 1] if i > 0 else ""
        after = text[j] if j < n else ""
        if before.isalnum() and after.isalnum():
            out.append(text[i:j])
        i = j
    return "".join(out)


def heading_text(raw: str) -> str:
    """Reduce a heading's markdown source to the text a renderer shows."""
    text = raw
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    text = _REF_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub("", text)
    text = _CODE_SPAN.sub("", text)
    text = _ASTERISKS.sub("", text)
    text = _strip_underscore_emphasis(text)
    text = text.replace("\\", "")
    return text.strip()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_ATX = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*$")
_CLOSING_HASHES = re.compile(r"\s+#+\s*$")
# Pandoc / kramdown heading attributes: `{#id}`, `{.cls}`, `{#id .cls key=v}`.
_ATTR_BLOCK = re.compile(r"\{[#.:][^}]*\}\s*$|\{[^}]*=[^}]*\}\s*$")

_INLINE_LINK = re.compile(
    r"\]\(\s*<?([^)>\s]*)>?(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
_REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^>\s]+)>?")
_HREF = re.compile(r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
_NAMED_ANCHOR = re.compile(r"<a\b[^>]*\bname\s*=\s*[\"']([^\"']+)[\"']", re.I)
_ID_ANCHOR = re.compile(r"<[a-zA-Z][^>]*\bid\s*=\s*[\"']([^\"']+)[\"']")

_EXTERNAL = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)")


def strip_code_spans(line: str) -> str:
    """Blank out inline code so a link *shown* as source is not read as one."""
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        if line[i] != "`":
            out.append(line[i])
            i += 1
            continue
        j = i
        while j < n and line[j] == "`":
            j += 1
        run = j - i
        # A code span opened by a run of `run` backticks is closed by the next
        # run of exactly that length (CommonMark §6.1).
        k = j
        close = -1
        while k < n:
            if line[k] == "`":
                e = k
                while e < n and line[e] == "`":
                    e += 1
                if e - k == run:
                    close = k
                    break
                k = e
            else:
                k += 1
        if close == -1:
            out.append(line[i:j])
            i = j
            continue
        out.append(" " * (close + run - i))
        i = close + run
    return "".join(out)


class Doc:
    """One Markdown file: its anchors, its links, and its heading defects."""

    def __init__(self, relpath: str, text: str) -> None:
        self.relpath = relpath
        self.anchors: set[str] = set()
        self.headings: list[tuple[int, str, str]] = []  # line, text, slug
        self.links: list[tuple[int, str]] = []  # line, target
        self.attr_headings: list[tuple[int, str]] = []  # line, raw heading

        seen: dict[str, int] = {}
        fence: str | None = None
        for lineno, line in enumerate(text.splitlines(), 1):
            m = _FENCE.match(line)
            if m:
                marker = m.group(1)[0]
                if fence is None:
                    fence = marker
                    continue
                if marker == fence:
                    fence = None
                continue
            if fence is not None:
                continue

            atx = _ATX.match(line)
            if atx:
                raw = _CLOSING_HASHES.sub("", atx.group(2))
                if _ATTR_BLOCK.search(raw):
                    self.attr_headings.append((lineno, raw))
                slug = gfm_slug(heading_text(raw))
                n = seen.get(slug, 0)
                seen[slug] = n + 1
                final = slug if n == 0 else f"{slug}-{n}"
                self.anchors.add(final)
                self.headings.append((lineno, raw, final))
                continue

            self.anchors.update(_NAMED_ANCHOR.findall(line))
            self.anchors.update(_ID_ANCHOR.findall(line))

            bare = strip_code_spans(line)
            for target in _INLINE_LINK.findall(bare):
                self.links.append((lineno, target))
            ref = _REF_DEF.match(bare)
            if ref:
                self.links.append((lineno, ref.group(1)))
            for target in _HREF.findall(bare):
                self.links.append((lineno, target))


def _ls_files(*patterns: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *patterns],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(p for p in out.splitlines() if p)


def tracked_markdown() -> list[str]:
    return _ls_files("*.md")


def load_docs() -> dict[str, Doc]:
    docs: dict[str, Doc] = {}
    for rel in tracked_markdown():
        with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
            docs[rel] = Doc(rel, fh.read())
    return docs


# A Markdown link into a Markdown file, written in a file that is not one.
_FOREIGN_LINK = re.compile(r"\]\(([^)\s]*\.md#[^)\s]+)\)")

# `cli/assets/` is a byte-identical mirror of repository originals, maintained
# and enforced by scripts/check_embedded_assets.py. Its copies are checked
# where the originals live: a relative link inside a mirrored file is written
# against the original's directory, so resolving it against the mirror's would
# report a break in a file nobody edits.
MIRROR_PREFIX = "cli/assets/"


def foreign_links() -> list[tuple[str, int, str]]:
    """`(file, line, target)` for every `](*.md#…)` outside the Markdown."""
    hits: list[tuple[str, int, str]] = []
    md = set(tracked_markdown())
    for rel in _ls_files():
        if rel in md or rel.startswith(MIRROR_PREFIX):
            continue
        path = os.path.join(REPO, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue  # binary, or gone: nothing to read a link out of
        if ".md#" not in text:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for target in _FOREIGN_LINK.findall(line):
                hits.append((rel, lineno, target))
    return hits


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def _near(fragment: str, anchors: set[str]) -> str:
    """The most plausible intended anchor, for the failure message."""
    import difflib

    hit = difflib.get_close_matches(fragment, sorted(anchors), n=1, cutoff=0.4)
    return f"  did you mean #{hit[0]} ?" if hit else ""


def _check_link(
    docs: dict[str, Doc], rel: str, lineno: int, target: str
) -> str | None:
    """One link. `None` if it resolves, the failure line if it does not."""
    if not target or _EXTERNAL.match(target):
        return None
    path, _, fragment = target.partition("#")
    fragment = fragment.strip()

    if path:
        resolved = os.path.normpath(os.path.join(os.path.dirname(rel), path))
        if resolved.startswith(".."):
            return None  # outside the checkout; not ours to check
        if not os.path.exists(os.path.join(REPO, resolved)):
            return f"{rel}:{lineno}: link target does not exist: {target}"
    else:
        resolved = rel

    if not fragment or resolved not in docs:
        # A fragment on a non-Markdown file names something in that file's own
        # vocabulary — an IRI in a Turtle document, say — and not a heading.
        return None

    anchors = docs[resolved].anchors
    if fragment in anchors:
        return None
    where = "" if resolved == rel else f" in {resolved}"
    return (
        f"{rel}:{lineno}: anchor #{fragment} matches no heading"
        f"{where}.{_near(fragment, anchors)}"
    )


def check(
    docs: dict[str, Doc], extra: "list[tuple[str, int, str]] | None" = None
) -> list[str]:
    failures: list[str] = []

    # Mirrored copies are read as link *targets* but never as link sources —
    # see MIRROR_PREFIX.
    sources = {
        rel: doc
        for rel, doc in sorted(docs.items())
        if not rel.startswith(MIRROR_PREFIX)
    }

    for rel, doc in sources.items():
        for lineno, raw in doc.attr_headings:
            failures.append(
                f"{rel}:{lineno}: heading carries a Pandoc/kramdown attribute "
                f"block, which GitHub renders as literal text and folds into "
                f"the slug: {raw!r}"
            )

    links = [
        (rel, lineno, target)
        for rel, doc in sources.items()
        for lineno, target in doc.links
    ]
    links.extend(extra or [])

    for rel, lineno, target in links:
        failure = _check_link(docs, rel, lineno, target)
        if failure:
            failures.append(failure)

    return failures


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

SLUG_VECTORS = [
    # The one this gate was written for: two spaces around a deleted em dash
    # leave two hyphens.
    ("Appendix E — Related work and bibliography", "appendix-e--related-work-and-bibliography"),
    ("2.1 What conformance establishes", "21-what-conformance-establishes"),
    ("Appendix D — VSON-X grammar (normative)", "appendix-d--vson-x-grammar-normative"),
    # Inline code is rendered away before the slug is computed; the `--format`
    # inside it keeps both its hyphens, and the space before it adds a third.
    (
        "5.16 Machine-readable validation reports (`vson validate --format`)",
        "516-machine-readable-validation-reports-vson-validate---format",
    ),
    ("**Bold** and *italic*", "bold-and-italic"),
    ("A/B & C: d?", "ab--c-d"),
    ("snake_case survives", "snake_case-survives"),
    ("§5.9 vso:Quality", "59-vsoquality"),
]


def selftest() -> int:
    bad = 0
    for text, expected in SLUG_VECTORS:
        got = gfm_slug(heading_text(text))
        status = "OK  " if got == expected else "FAIL"
        if got != expected:
            bad += 1
        print(f"  {status} {text!r} -> {got!r}")
        if got != expected:
            print(f"       expected {expected!r}")

    # Dedupe: the second identical heading gets -1.
    doc = Doc("t.md", "# Same\n\n# Same\n\n# Same\n")
    if [h[2] for h in doc.headings] != ["same", "same-1", "same-2"]:
        print(f"  FAIL duplicate-heading suffixes: {[h[2] for h in doc.headings]}")
        bad += 1
    else:
        print("  OK   duplicate headings get -1, -2 suffixes")

    # Headings and links inside a fence are not headings or links.
    doc = Doc("t.md", "```\n# Not a heading\n[x](#nowhere)\n```\n")
    if doc.headings or doc.links:
        print("  FAIL fenced code was read as markdown")
        bad += 1
    else:
        print("  OK   fenced code is not parsed for headings or links")

    # The gate can go red: a link to a slug nothing mints.
    broken = {"t.md": Doc("t.md", "# Title\n\n[go](#titel)\n")}
    if not check(broken):
        print("  FAIL a broken anchor did not fail the check")
        bad += 1
    else:
        print("  OK   a broken anchor fails the check")

    # The gate can go red: a Pandoc attribute on a heading.
    pandoc = {"t.md": Doc("t.md", "# Title {#title}\n")}
    if not check(pandoc):
        print("  FAIL a Pandoc heading attribute did not fail the check")
        bad += 1
    else:
        print("  OK   a Pandoc heading attribute fails the check")

    print("  selftest: " + ("OK" if bad == 0 else f"{bad} FAILED"))
    return 1 if bad else 0


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="comparators only")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    docs = load_docs()
    foreign = foreign_links()
    failures = check(docs, foreign)

    targets = [t for d in docs.values() for _, t in d.links] + [
        t for _, _, t in foreign
    ]
    n_links = sum(1 for t in targets if t and not _EXTERNAL.match(t))
    n_anchored = sum(
        1 for t in targets if t and not _EXTERNAL.match(t) and "#" in t
    )

    if failures:
        for f in failures:
            print(f"  FAIL {f}")
        print(
            f"\nanchor-check: FAILED — {len(failures)} unresolved "
            f"in {len(docs)} tracked markdown files"
        )
        return 1

    print(
        f"  OK {len(docs)} markdown files + {len(foreign)} link(s) from "
        f"non-markdown sources: {n_links} in-repo links, {n_anchored} of them "
        f"anchored, every anchor resolves"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
