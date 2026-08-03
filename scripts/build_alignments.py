#!/usr/bin/env python3
"""Own the SKOS block at the end of `ontology/alignments.ttl`.

Six of VSON's value spaces are closed (docs/vson.md §5.12): the producer may
not invent a member, and the members are IRIs. That is a controlled vocabulary,
and the interchange form for a controlled vocabulary is SKOS. Publishing the
SKOS view by hand would mean maintaining a second copy of six lists and their
prose — the drift surface every gate in this repository exists to close — so
this script derives the view from `ontology/vso.ttl` instead, and
`tests/test_alignments.py` runs it in check mode inside `make check`.

What it derives, and from where
-------------------------------
For each of the six value classes below, one `skos:ConceptScheme`, and for each
individual of that class one `skos:Concept`:

    skos:prefLabel   <- that individual's rdfs:label,   copied
    skos:definition  <- that individual's rdfs:comment, copied
    skos:inScheme    <- the scheme derived from its class
    skos:topConceptOf / skos:hasTopConcept
                     <- every concept, because these vocabularies are flat

"Copied" is the load-bearing word: the generator never re-words. If a value's
comment changes in the ontology, the definition here changes with it or the
build goes red — which is the only property that makes a second rendering of a
vocabulary safe to publish.

What it does NOT own
--------------------
Everything above the marker: the header, the four recorded gaps, and every
`skos:closeMatch` / `skos:relatedMatch` toward an external vocabulary. Those
are judgements about two vocabularies and cannot be derived from either one, so
they are hand-written and reviewed, and `tests/test_alignments.py` constrains
their SHAPE (which predicates may appear, which namespaces they may reach)
rather than their content.

Why these six and not eight
---------------------------
`rcc:` and `allen:` are closed too, and neither is viewed here. The eight RCC-8
relations are individuals in their own document, which already carries their
GeoSPARQL alignment; the thirteen Allen relations are PROPERTIES, and a concept
scheme whose members are properties is a category error. `vso:dimension` is
closed only within the VSO namespace (§5.12) and takes document-namespace IRIs
as conformant values, so it is not a controlled vocabulary in the SKOS sense.

Exit codes
----------
  0  the block on disk is the block this script generates.
  1  it differs; `--write` is what fixes it.

Usage
-----
  python3 scripts/build_alignments.py            # check, the CI mode
  python3 scripts/build_alignments.py --write    # rewrite the block
"""

from __future__ import annotations

import argparse
import os
import sys

import rdflib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCE = "ontology/vso.ttl"
TARGET = "ontology/alignments.ttl"

VSO = "https://w3id.org/vson/v1/ontology#"
VSA = "https://w3id.org/vson/v1/alignments#"
DOCUMENT = "https://w3id.org/vson/v1/alignments"

MARKER = "# BEGIN GENERATED — scripts/build_alignments.py"

# (value class local name, scheme local name, the §5.12 property it values).
# Ordered as docs/vson.md §5.12 orders them, so the file reads in the order the
# specification's table reads.
SCHEMES = (
    ("IndividuationKind", "IndividuationScheme", "vso:individuation"),
    ("AnimacyKind", "AnimacyScheme", "vso:animacy"),
    ("CountabilityKind", "CountabilityScheme", "vso:countability"),
    ("Affordance", "AffordanceScheme", "vso:affordance"),
    ("Direction", "DirectionScheme", "vso:directional"),
    ("ProximityKind", "ProximityScheme", "vso:proximal"),
)

BLOCK_HEADER = """\
#################################################################
{marker}
#
# Do not edit by hand: `python3 scripts/build_alignments.py --write`
# regenerates it, and `make check` fails while it is stale.
#
# {schemes} concept scheme(s), {concepts} concept(s). Every skos:prefLabel below is
# the value's own rdfs:label and every skos:definition its own rdfs:comment,
# copied from ontology/vso.ttl — so this view cannot say something the
# vocabulary does not.
#################################################################

"""

SCHEME_BLOCK = """
# {property} — {count} value(s). {label}
vsa:{scheme}
    a skos:ConceptScheme ;
    rdfs:label "{label} scheme"@en ;
    rdfs:comment "SKOS view of the closed value vocabulary vso:{cls}, which is the value space of {property} (docs/vson.md §5.12)."@en ;
    rdfs:isDefinedBy <{document}> ;
    vs:term_status "stable" ;
    dc:source vso:{cls} ;
    skos:prefLabel "{label} scheme"@en ;
"""


def read(rel: str) -> str:
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


def turtle_literal(text: str) -> str:
    """A Turtle double-quoted literal body, escaped per the grammar."""
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def source_graph() -> "rdflib.Graph":
    graph = rdflib.Graph()
    graph.parse(os.path.join(REPO, SOURCE), format="turtle")
    return graph


def members(graph: "rdflib.Graph", cls: str) -> "list[tuple[str, str, str]]":
    """`(local name, label, comment)` for every individual of one value class.

    Sorted by local name so the block is a pure function of the vocabulary and
    not of rdflib's iteration order. A member missing either annotation is an
    error rather than a blank line: SKOS without a prefLabel is not a view of
    anything, and ontology/vso.ttl is gated to carry both on every term
    (tests/test_ontology_docs.py).
    """
    subject = rdflib.URIRef(VSO + cls)
    out = []
    for member in graph.subjects(rdflib.RDF.type, subject):
        if not isinstance(member, rdflib.URIRef):
            continue
        name = str(member)
        if not name.startswith(VSO):
            continue
        labels = [str(o) for o in graph.objects(member, rdflib.RDFS.label)]
        comments = [str(o) for o in graph.objects(member, rdflib.RDFS.comment)]
        if len(labels) != 1 or len(comments) != 1:
            raise LookupError(
                "%s: expected exactly one rdfs:label and one rdfs:comment, "
                "found %d and %d" % (name, len(labels), len(comments))
            )
        out.append((name[len(VSO):], labels[0], comments[0]))
    if not out:
        raise LookupError("vso:%s has no individuals in %s" % (cls, SOURCE))
    return sorted(out)


def block(graph: "rdflib.Graph") -> str:
    """The generated block, as it is written to disk."""
    sections = []
    total = 0
    for cls, scheme, prop in SCHEMES:
        found = members(graph, cls)
        total += len(found)
        label = _class_label(graph, cls)
        section = [
            SCHEME_BLOCK.format(
                property=prop,
                count=len(found),
                label=label,
                scheme=scheme,
                cls=cls,
                document=DOCUMENT,
            )
        ]
        tops = " ,\n        ".join("vso:%s" % name for name, _, _ in found)
        section.append("    skos:hasTopConcept %s .\n\n" % tops)
        for name, member_label, comment in found:
            section.append(
                "vso:%s\n"
                "    a skos:Concept ;\n"
                "    skos:inScheme vsa:%s ;\n"
                "    skos:topConceptOf vsa:%s ;\n"
                '    skos:prefLabel "%s"@en ;\n'
                '    skos:definition "%s"@en .\n'
                % (
                    name,
                    scheme,
                    scheme,
                    turtle_literal(member_label),
                    turtle_literal(comment),
                )
            )
        sections.append("".join(section))
    header = BLOCK_HEADER.format(
        marker=MARKER, schemes=len(SCHEMES), concepts=total
    )
    return header + "\n".join(sections).rstrip("\n") + "\n"


def _class_label(graph: "rdflib.Graph", cls: str) -> str:
    labels = [
        str(o)
        for o in graph.objects(rdflib.URIRef(VSO + cls), rdflib.RDFS.label)
    ]
    if len(labels) != 1:
        raise LookupError(
            "vso:%s carries %d rdfs:label(s); expected exactly one"
            % (cls, len(labels))
        )
    return labels[0]


def head(text: str) -> str:
    """Everything above the generated block, with one trailing newline."""
    cut = text.find(MARKER)
    if cut < 0:
        return text.rstrip("\n") + "\n"
    lines = text[:cut].splitlines()
    while lines and (not lines[-1].strip() or set(lines[-1].strip()) == {"#"}):
        lines.pop()
    return "\n".join(lines) + "\n"


def rendered() -> str:
    """The whole target file as this script would write it."""
    body = head(read(TARGET))
    return body + "\n" + block(source_graph())


def check(write: bool) -> int:
    current = read(TARGET)
    wanted = rendered()
    if current == wanted:
        print("  OK      %-24s SKOS view current" % TARGET)
        return 0
    if write:
        with open(os.path.join(REPO, TARGET), "w", encoding="utf-8") as fh:
            fh.write(wanted)
        print("  written %-24s SKOS view regenerated" % TARGET)
        return 0
    print("  STALE   %-24s SKOS view differs" % TARGET)
    print(
        "\nbuild-alignments: FAIL — the generated block is stale.\n"
        "\nRegenerate with:\n"
        "  python3 scripts/build_alignments.py --write"
    )
    return 1


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite the generated block instead of checking it",
    )
    args = parser.parse_args(argv)
    return check(args.write)


if __name__ == "__main__":
    sys.exit(main())
