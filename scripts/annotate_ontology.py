#!/usr/bin/env python3
"""Own the annotation layer of the three ontology documents.

A term browser, a vocabulary registry and a consumer holding one term IRI out
of a merged graph all ask the same two questions of a vocabulary, and through
v1.3 this one answered neither:

  * **Which document defines this term?** Measured 2026-08-01: `rdfs:isDefinedBy`
    appeared 0 times across all 183 terms. Merge the trio — which is exactly
    what `owl:imports` now tells a consumer to do, and what
    `site/v1/vson-full.ttl` serves in one fetch — and nothing in the resulting
    graph says which of the three documents a given term came from. The term
    still resolves, because every VSON term IRI is `<document>#<name>`; but
    that is a convention a consumer has to know, not a triple it can follow.

  * **What language is this label in?** Measured the same day: 0 of 186 labels
    and 0 of 186 comments carried a language tag. An untagged literal is not
    "English", it is *unspecified* — a consumer building a multilingual term
    browser cannot tell a label it should show an English reader from one it
    should not, and cannot add a second language without first guessing what
    the first one was.

Both are mechanical, both are easy to half-do by hand, and a hand-maintained
annotation layer rots one forgotten term at a time. So this script owns them
instead, and `tests/test_ontology_docs.py` runs it in check mode inside
`make check`: a term added without either annotation fails the build with the
command that fixes it.

What it owns
------------
  1. **`@en` on every `rdfs:label` and `rdfs:comment` literal.** Applied in
     place, leaving the hand-written formatting and the prose comments alone —
     the ontology files are written to be read, and a parse-and-reserialize
     would throw every comment in them away. A literal that already carries a
     language tag or a datatype is left untouched, which is what makes the
     transform idempotent.

  2. **A generated block at the end of each file** carrying, for every term the
     file declares, `rdfs:isDefinedBy` naming that file's document IRI and
     `vs:term_status "stable"`. Generated rather than hand-written because it
     is derived data: the term list comes from parsing the file above the
     block, so it cannot disagree with what the file declares.

What it does NOT own: everything else. The `owl:Ontology` header, the axioms,
the comments and the term declarations are hand-written and stay that way. This
script rewrites literals and appends a block; it never reorders, reformats or
reserializes.

Why `vs:term_status "stable"` on every term
-------------------------------------------
`http://www.w3.org/2003/06/sw-vocab-status/ns#term_status` has four values —
`stable`, `testing`, `unstable`, `archaic`. Every term in these files ships in
a released vocabulary version whose IRIs §8.1 declares immutable within v1.x,
which is what `stable` says. A term introduced as provisional would need its
own value, and stating it would then be an edit to this script's policy, not a
silent default — which is the point of writing the policy down here.

Exit codes
----------
  0  every file already carries the annotation layer this script generates.
  1  at least one file differs; `--write` is what fixes it.

Usage
-----
  python3 scripts/annotate_ontology.py            # check, the CI mode
  python3 scripts/annotate_ontology.py --write    # rewrite the three files
  python3 scripts/annotate_ontology.py --selftest # the transform, offline
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import rdflib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# file -> the document IRI its header sits on. The same pairing
# tests/test_ontology_docs.py pins; a fourth ontology file has to be added in
# both places to be covered by either.
DOCUMENTS = {
    "ontology/vso.ttl": "https://w3id.org/vson/v1/ontology",
    "ontology/rcc8.ttl": "https://w3id.org/vson/v1/rcc8",
    "ontology/allen.ttl": "https://w3id.org/vson/v1/allen",
}

VS = "http://www.w3.org/2003/06/sw-vocab-status/ns#"
TERM_STATUS = "stable"
LANGUAGE = "en"

# The predicates whose literal objects get the language tag.
TAGGED = ("rdfs:label", "rdfs:comment")

MARKER = "# BEGIN GENERATED — scripts/annotate_ontology.py"

BLOCK_HEADER = """\
#################################################################
{marker}
#
# Do not edit by hand: `python3 scripts/annotate_ontology.py --write`
# regenerates it, and `make check` fails while it is stale.
#
# One line per term this document declares, carrying the two annotations a
# consumer of a MERGED graph cannot recover from the term IRI alone:
#
#   rdfs:isDefinedBy  the document to fetch for this term. VSON merges — the
#                     header imports the two companion documents, and
#                     site/v1/vson-full.ttl serves all three in one file — so
#                     "which document is this term from" stops being answerable
#                     by looking at where the bytes came from.
#   vs:term_status    "stable": this term ships in a released vocabulary
#                     version whose IRIs docs/vson.md §8.1 declares immutable
#                     within v1.x. <http://www.w3.org/2003/06/sw-vocab-status/ns#>
#
# {count} term(s).
#################################################################

"""


def read(rel: str) -> str:
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


def segments(text: str) -> "list[tuple[str, str]]":
    """Split Turtle into `(kind, chunk)` pairs, concatenating back to `text`.

    Four kinds: `comment` (`#` to end of line), `literal` (a quoted string),
    `iri` (`<…>`) and `code` (everything else). The split has to happen in one
    pass because all three of the delimited kinds can contain the others'
    delimiters: `#` sits inside every namespace IRI in the prologue, `"` sits
    inside prose comments, and `<` sits inside prose comments too. Classifying
    them separately — strip comments, then find strings — misreads all three.
    """
    out: "list[tuple[str, str]]" = []
    i = 0
    n = len(text)
    start = 0

    def flush(upto: int) -> None:
        if start < upto:
            out.append(("code", text[start:upto]))

    while i < n:
        ch = text[i]
        if ch == "#":
            flush(i)
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(("comment", text[i:end]))
            i = start = end
        elif ch == '"':
            flush(i)
            end = i + 1
            while end < n and text[end] != '"':
                end += 2 if text[end] == "\\" else 1
            end = min(end + 1, n)
            out.append(("literal", text[i:end]))
            i = start = end
        elif ch == "<":
            flush(i)
            end = text.find(">", i)
            if end < 0:  # not an IRI after all — a stray `<` in code
                i += 1
                continue
            out.append(("iri", text[i : end + 1]))
            i = start = end + 1
        else:
            i += 1
    flush(n)
    return out


_PREDICATE = re.compile(r"(?:%s)\s*$" % "|".join(re.escape(p) for p in TAGGED))


def add_language_tags(text: str) -> str:
    """Tag every `rdfs:label` / `rdfs:comment` literal with `@en`.

    Idempotent: a literal already followed by `@…` or `^^…` is left alone, so
    running this over its own output is a no-op — which is what lets the check
    mode be "the file equals what this function would write".
    """
    parts = segments(text)
    out: "list[str]" = []
    pending = False
    for index, (kind, chunk) in enumerate(parts):
        out.append(chunk)
        if kind == "comment":
            continue  # a comment between predicate and object decides nothing
        if kind == "code":
            if _PREDICATE.search(chunk):
                pending = True
            elif chunk.strip():
                pending = False
            continue
        if kind == "iri":
            pending = False
            continue
        # a literal
        if not pending:
            continue
        pending = False
        following = parts[index + 1][1] if index + 1 < len(parts) else ""
        if following.startswith("@") or following.startswith("^^"):
            continue
        out.append("@%s" % LANGUAGE)
    return "".join(out)


def head(text: str) -> str:
    """Everything above the generated block, with one trailing newline."""
    cut = text.find(MARKER)
    if cut < 0:
        return text.rstrip("\n") + "\n"
    # Back up over the `###` rule line the marker sits under, and over the
    # blank lines separating the block from the hand-written body.
    lines = text[:cut].splitlines()
    while lines and (not lines[-1].strip() or set(lines[-1].strip()) == {"#"}):
        lines.pop()
    return "\n".join(lines) + "\n"


def terms(rel: str, body: str) -> "tuple[str, list[str]]":
    """`(prefix, term local names)` for one file's hand-written body.

    The prefix is read off the file's own `@prefix` declarations rather than
    assumed, so the block writes the same binding the document above it writes.
    The document IRI is not a term: it names the document, and a document is
    not defined by itself.
    """
    graph = rdflib.Graph()
    graph.parse(data=body, format="turtle", publicID=DOCUMENTS[rel])
    namespace = DOCUMENTS[rel] + "#"
    bound = sorted(
        prefix for prefix, uri in graph.namespaces() if str(uri) == namespace
    )
    if not bound:
        raise LookupError(
            "%s declares no @prefix for its own namespace <%s>"
            % (rel, namespace)
        )
    local = sorted(
        {
            str(s)[len(namespace):]
            for s in graph.subjects()
            if isinstance(s, rdflib.URIRef) and str(s).startswith(namespace)
        }
    )
    return bound[0], local


def block(rel: str, body: str) -> str:
    """The generated block for one file, as it is written to disk."""
    prefix, declared = terms(rel, body)
    document = DOCUMENTS[rel]
    width = max((len(name) for name in declared), default=0) + len(prefix) + 1
    lines = [BLOCK_HEADER.format(marker=MARKER, count=len(declared))]
    for name in declared:
        subject = "%s:%s" % (prefix, name)
        lines.append(
            '%-*s rdfs:isDefinedBy <%s> ; vs:term_status "%s" .\n'
            % (width, subject, document, TERM_STATUS)
        )
    return "".join(lines)


def annotate(rel: str, text: str) -> str:
    """The whole transform: tagged literals above, generated block below."""
    body = add_language_tags(head(text))
    return body + "\n" + block(rel, body)


def check(write: bool) -> int:
    failures: "list[str]" = []
    for rel in sorted(DOCUMENTS):
        current = read(rel)
        wanted = annotate(rel, current)
        if current == wanted:
            print("  OK      %-20s annotation layer current" % rel)
            continue
        if write:
            with open(os.path.join(REPO, rel), "w", encoding="utf-8") as fh:
                fh.write(wanted)
            print("  written %-20s annotation layer regenerated" % rel)
            continue
        failures.append(rel)
        print("  STALE   %-20s annotation layer differs" % rel)

    if failures:
        print(
            "\nannotate-ontology: FAIL — %d file(s) missing the annotation "
            "layer:\n  %s\n\nRegenerate with:\n"
            "  python3 scripts/annotate_ontology.py --write\n"
            "  python3 scripts/check_embedded_assets.py --sync"
            % (len(failures), "\n  ".join(failures))
        )
        return 1
    return 0


def selftest() -> int:
    """The transform's two rules, on inputs no ontology file happens to have."""
    cases = (
        # (name, input, expected)
        (
            "tags an untagged label",
            'ex:A rdfs:label "A" .',
            'ex:A rdfs:label "A"@en .',
        ),
        (
            "leaves an already-tagged label alone",
            'ex:A rdfs:label "A"@fr .',
            'ex:A rdfs:label "A"@fr .',
        ),
        (
            "leaves a typed literal alone",
            'ex:A rdfs:label "A"^^xsd:string .',
            'ex:A rdfs:label "A"^^xsd:string .',
        ),
        (
            "tags neither dc:title nor a bare string",
            'ex:A dc:title "A" ; ex:p "B" .',
            'ex:A dc:title "A" ; ex:p "B" .',
        ),
        (
            "a quote inside a prose comment starts no literal",
            '# the "vso" prefix\nex:A rdfs:label "A" .',
            '# the "vso" prefix\nex:A rdfs:label "A"@en .',
        ),
        (
            "a # inside an IRI starts no comment",
            '@prefix ex: <http://e.org/ns#> .\nex:A rdfs:label "A" .',
            '@prefix ex: <http://e.org/ns#> .\nex:A rdfs:label "A"@en .',
        ),
        (
            "a # inside a literal starts no comment",
            'ex:A ex:p "a#b" ; rdfs:label "A" .',
            'ex:A ex:p "a#b" ; rdfs:label "A"@en .',
        ),
        (
            "the predicate and its literal may sit on separate lines",
            'ex:A rdfs:comment\n     "A" .',
            'ex:A rdfs:comment\n     "A"@en .',
        ),
        (
            "an intervening IRI object cancels the pending tag",
            'ex:A rdfs:label ex:B ; ex:p "C" .',
            'ex:A rdfs:label ex:B ; ex:p "C" .',
        ),
    )
    failures = []
    for name, source, expected in cases:
        got = add_language_tags(source)
        if got != expected:
            failures.append("%s: got %r, want %r" % (name, got, expected))
            continue
        if add_language_tags(got) != got:
            failures.append("%s: not idempotent" % name)
            continue
        print("  OK      %s" % name)

    round_trip = add_language_tags(cases[0][1])
    if add_language_tags(round_trip) != round_trip:
        failures.append("the transform is not idempotent")

    for name, source, _ in cases:
        if "".join(chunk for _, chunk in segments(source)) != source:
            failures.append("%s: segments() does not concatenate back" % name)

    if failures:
        print("\nannotate-ontology selftest: FAIL")
        for line in failures:
            print("  - %s" % line)
        return 1
    print("\nannotate-ontology selftest: %d case(s) green" % len(cases))
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite the ontology files instead of reporting on them",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="check the transform against hand-written cases, offline",
    )
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    print("==> Ontology annotation layer (%d file(s))" % len(DOCUMENTS))
    return check(args.write)


if __name__ == "__main__":
    sys.exit(main())
