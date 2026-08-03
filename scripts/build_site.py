#!/usr/bin/env python3
"""Assemble `site/` — the dereferenceable surface for the VSON namespace.

Every canonical VSON IRI is a `https://w3id.org/vson/v1/...` name. A name that
returns 404 is still a valid identifier, but nothing can *follow* it: no term
browser, no `rdflib.Graph().parse(<iri>)`, no reviewer reading the ontology the
way the spec says to. This script takes the tracked sources and lays them out
under the exact paths those IRIs redirect to, so a static host (Cloudflare
Pages) can serve them.

It is a copy step with assertions and exactly one derived file. Nothing here
rewrites or minifies; `site/` is git-ignored and reproducible from the tracked
tree at any time — `make site`.

The one derived file is `v1/vson-full.ttl`, the merged distribution: the three
ontology documents concatenated, which is the import closure of the canonical
name in a single fetch. It is DERIVED and never tracked, because a tracked copy
of three tracked files is a drift surface — the thing every gate in this
repository exists to prevent. Concatenation rather than parse-and-reserialize
for the same reason the annotation generator works in place: reserializing
would throw away every prose comment in files that are written to be read, and
it would make the merged bytes a second, differently-formatted rendering of the
vocabulary rather than the three documents themselves.

The assertions exist because a publish surface fails silently. A truncated
Turtle file still uploads; a stale version number in the landing page still
renders; a re-appearing legacy IRI still returns 200. So, before anything is
declared publishable:

  * every published .ttl parses with rdflib and carries triples;
  * every published .json / .jsonld parses;
  * the merged distribution states exactly the union of its three sources —
    its triple count equals the sum of theirs, parsed apart, and it declares
    the same `owl:versionInfo`. Turtle concatenation is legal but not
    obviously safe (a re-declared prefix rebinds from that point on, a
    truncated source swallows the file after it), so the merge is checked
    against the arithmetic rather than assumed;
  * no published byte names the withdrawn namespace host, with exactly one
    carve-out — the single `owl:priorVersion` line in the ontology, which
    records the versionIRI a prior release actually declared (see the LEGACY
    IRI comment in ontology/vso.ttl), and the one copy of that line the merge
    carries. The host itself is imported from scripts/check_legacy_iri.py, the
    gate whose job is to spell it and which pins that same occurrence to 1;
    spelling it a second time here would put the dead name back into the tree
    the repo-wide gate guards;
  * the version the landing page shows equals the ontology's own
    `owl:versionInfo`, read from the Turtle rather than trusted;
  * every exact-path rule in `_headers` names a file that was actually
    published, so the Content-Type matrix cannot drift off the file set.

Exits non-zero on any failure, with every failure listed (not just the first).

Usage:
  python3 scripts/build_site.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys

import rdflib

# Same directory, so this resolves off sys.path[0] with no path juggling. The
# import is what keeps the withdrawn host spelled in exactly one place.
from check_legacy_iri import LEGACY_HOST

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "site")

# (tracked source, published path). The published paths ARE the IRI paths: the
# w3id.org redirect sends `https://w3id.org/vson/v1/ontology#Foo` here by
# appending `.ttl` to the namespace document, so a rename on the left is free
# and a rename on the right breaks every published name.
COPY = (
    ("ontology/vso.ttl", "v1/ontology.ttl"),
    ("ontology/rcc8.ttl", "v1/rcc8.ttl"),
    ("ontology/allen.ttl", "v1/allen.ttl"),
    ("shapes/vson-shapes.ttl", "v1/shapes.ttl"),
    ("shapes/vson-shapes-relaxed.ttl", "v1/shapes-relaxed.ttl"),
    # The alignment layer. Published, and named by no redirect rule: it is not
    # one of the five documents the w3id rule routes, and no claim in
    # scripts/check_live_claims.py asserts it dereferences. It ships because a
    # layer nobody can fetch aligns nothing — see the header of the file, and
    # docs/vson.md §5.17. It is NOT in MERGE_SOURCES below: the merged
    # distribution is the import closure of the canonical name, and the whole
    # point of this layer is that the canonical name does not import it.
    ("ontology/alignments.ttl", "v1/alignments.ttl"),
    ("ontology/context.jsonld", "v1/context.jsonld"),
    (
        "tools/schema/vson-output.schema.json",
        "v1/schema/vson-output.schema.json",
    ),
    (
        "tools/schema/vson-jsonld.schema.json",
        "v1/schema/vson-jsonld.schema.json",
    ),
    # Not a namespace document and not named by any IRI: the drafted, unfiled
    # prefix.cc registration. It ships because the claim it records — which
    # prefix this vocabulary asks registries for, and that nothing has been
    # filed — is a claim about the published surface, and this project states
    # its status where the documents are rather than only in the repository.
    (
        "publish/registry/prefix-cc.json",
        "v1/registry/prefix-cc.json",
    ),
    ("publish/index.html", "index.html"),
    ("publish/_headers", "_headers"),
)

# The merged distribution: the import closure of the canonical ontology name,
# in one fetch. Derived, never tracked (see the module docstring). The sources
# are listed in the order they are concatenated, which is also the order a
# reader wants them — core vocabulary first, then the two value vocabularies
# its header imports.
MERGED = "v1/vson-full.ttl"
MERGE_SOURCES = (
    ("ontology/vso.ttl", "https://w3id.org/vson/v1/ontology"),
    ("ontology/rcc8.ttl", "https://w3id.org/vson/v1/rcc8"),
    ("ontology/allen.ttl", "https://w3id.org/vson/v1/allen"),
)

# No build date, no host, no generated version string: the merged file must be
# byte-identical across two runs of the same checkout, or "reproducible from
# the tracked tree at any time" stops being true.
MERGE_PREAMBLE = """\
#################################################################
# VSON — the three ontology documents in one file.
#
# DERIVED. Generated by scripts/build_site.py by concatenating the tracked
# sources listed below; not tracked, not edited, and not a source. Every byte
# of it comes from one of those files.
#
# This is the import closure of <https://w3id.org/vson/v1/ontology>, whose
# header imports the other two — offered here for a consumer that cannot
# follow an owl:imports, or would rather make one request than three.
#
# It is a DISTRIBUTION, not a name. No IRI is minted for it and none is
# promised to resolve to it: cite the three canonical names below, which are
# what the terms in this file are defined by (rdfs:isDefinedBy on every term
# says which). Each section keeps its own owl:Ontology header, its own
# prologue and its own comments, exactly as that document ships.
#
# Sources, in order:
{sources}#################################################################

"""

MERGE_SECTION = """\

#################################################################
# {iri}
# from {rel}
#################################################################

"""

# The one published line allowed to name the legacy host. Matched precisely —
# an `owl:priorVersion` pointing at a versioned ontology document on that host
# and nothing else. The version segment is loose because a release bumps it;
# the shape of the line is not.
PRIOR_VERSION = re.compile(
    r"^\s*owl:priorVersion\s+<https://%s/v[0-9.]+/ontology>\s*;\s*$"
    % re.escape(LEGACY_HOST)
)
# The two published files that carry that line: the ontology, and the merge
# that contains the ontology.
PRIOR_VERSION_FILES = ("v1/ontology.ttl", MERGED)

# The landing page states one version; this is where it states it.
VERSION_MARKER = re.compile(r'id="version"[^>]*>([^<]*)<')
INDEX = "index.html"
ONTOLOGY_TTL = "ontology/vso.ttl"


def published(rel: str) -> str:
    return os.path.join(SITE, rel)


def assemble() -> "list[str]":
    """Copy the tracked sources into a freshly emptied site/, then merge."""
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    for src, dst in COPY:
        target = published(dst)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(os.path.join(REPO, src), target)
        print("  copied  %-38s <- %s" % (dst, src))
    merge()
    return [dst for _, dst in COPY] + [MERGED]


def merged_text() -> str:
    """The merged distribution, as bytes-to-be. A pure function of the tree."""
    sources = "".join(
        "#   %-40s %s\n" % (iri, rel) for rel, iri in MERGE_SOURCES
    )
    parts = [MERGE_PREAMBLE.format(sources=sources)]
    for rel, iri in MERGE_SOURCES:
        with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
            body = fh.read()
        parts.append(MERGE_SECTION.format(iri=iri, rel=rel))
        parts.append(body if body.endswith("\n") else body + "\n")
    return "".join(parts)


def merge() -> None:
    """Write the merged distribution from the tracked ontology sources."""
    target = published(MERGED)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(merged_text())
    print(
        "  merged  %-38s <- %s"
        % (MERGED, " + ".join(rel for rel, _ in MERGE_SOURCES))
    )


def check_parses(paths: "list[str]", failures: "list[str]") -> None:
    """Turtle parses with triples; JSON parses."""
    for rel in paths:
        if rel.endswith(".ttl"):
            try:
                graph = rdflib.Graph()
                graph.parse(published(rel), format="turtle")
            except Exception as exc:  # noqa: BLE001 — report, do not raise
                failures.append("%s does not parse as Turtle: %s" % (rel, exc))
                continue
            if not len(graph):
                failures.append("%s parses but is empty" % rel)
                continue
            print("  OK      %-38s triples=%d" % (rel, len(graph)))
        elif rel.endswith(".json") or rel.endswith(".jsonld"):
            try:
                with open(published(rel), encoding="utf-8") as fh:
                    json.load(fh)
            except Exception as exc:  # noqa: BLE001 — report, do not raise
                failures.append("%s does not parse as JSON: %s" % (rel, exc))
                continue
            print("  OK      %-38s parses as JSON" % rel)


def check_no_legacy_host(paths: "list[str]", failures: "list[str]") -> None:
    """No published byte names the withdrawn host, bar the one carve-out."""
    needle = LEGACY_HOST.encode("ascii")
    for rel in paths:
        with open(published(rel), "rb") as fh:
            blob = fh.read()
        count = blob.count(needle)
        if not count:
            continue
        hits = [
            line.decode("utf-8", "replace")
            for line in blob.splitlines()
            if needle in line
        ]
        if rel not in PRIOR_VERSION_FILES:
            failures.append(
                "%s names the legacy host %r (%d): %s"
                % (rel, LEGACY_HOST, count, hits[:3])
            )
            continue
        if count != 1 or len(hits) != 1:
            failures.append(
                "%s: expected exactly 1 legacy-host occurrence "
                "(owl:priorVersion), found %d: %s" % (rel, count, hits[:3])
            )
            continue
        if not PRIOR_VERSION.match(hits[0]):
            failures.append(
                "%s: the legacy-host line is not the allowed "
                "owl:priorVersion record: %r" % (rel, hits[0])
            )
            continue
        print("  OK      %-38s 1 legacy IRI, the owl:priorVersion "
              "record" % rel)


def check_version(failures: "list[str]") -> None:
    """The landing page shows the ontology's own owl:versionInfo."""
    graph = rdflib.Graph()
    graph.parse(os.path.join(REPO, ONTOLOGY_TTL), format="turtle")
    declared = sorted(
        str(o) for o in graph.objects(None, rdflib.OWL.versionInfo)
    )
    if len(set(declared)) != 1:
        failures.append(
            "%s declares %d distinct owl:versionInfo values (%s); the "
            "landing page can only state one" % (ONTOLOGY_TTL, len(set(declared)), declared)
        )
        return
    version = declared[0]

    with open(published(INDEX), encoding="utf-8") as fh:
        html = fh.read()
    shown = VERSION_MARKER.search(html)
    if not shown:
        failures.append(
            "%s has no id=\"version\" element for the build to check" % INDEX
        )
        return
    if shown.group(1).strip() != version:
        failures.append(
            "%s states version %r, %s declares owl:versionInfo %r"
            % (INDEX, shown.group(1).strip(), ONTOLOGY_TTL, version)
        )
        return
    print("  OK      %-38s version %s == %s owl:versionInfo"
          % (INDEX, version, ONTOLOGY_TTL))


def check_merged(failures: "list[str]") -> None:
    """The merge states the union of its sources, and nothing else.

    Two assertions, and the first is the one that matters. Turtle concatenation
    is legal, but it is legal in a way that fails quietly: a re-declared prefix
    rebinds from that point on, and a source whose last statement is unfinished
    swallows the beginning of the next one. Either would produce a file that
    still parses and still carries triples — the checks above would pass — while
    stating something other than the three documents. Comparing the merged
    triple count against the sum of the sources parsed APART is what catches
    both: a rebind changes which IRIs the triples name, a swallow loses
    statements, and both move the number.

    The count is a sum rather than a graph comparison because the sources share
    no triple: the three namespaces are disjoint and each document's blank
    nodes stay distinct through concatenation, so union size == sum of sizes.
    That is asserted here too — if a triple were ever shared, the sum would
    exceed the union and this would report it rather than the arithmetic
    silently becoming wrong.
    """
    counts = []
    apart = rdflib.Graph()
    for rel, _ in MERGE_SOURCES:
        graph = rdflib.Graph()
        try:
            graph.parse(os.path.join(REPO, rel), format="turtle")
        except Exception as exc:  # noqa: BLE001 — report, do not raise
            failures.append("%s does not parse as Turtle: %s" % (rel, exc))
            return
        counts.append(len(graph))
        apart += graph
    total = sum(counts)

    merged = rdflib.Graph()
    try:
        merged.parse(published(MERGED), format="turtle")
    except Exception as exc:  # noqa: BLE001 — report, do not raise
        failures.append("%s does not parse as Turtle: %s" % (MERGED, exc))
        return

    if len(apart) != total:
        failures.append(
            "%s: the %d source triple(s) merge to %d — the sources now share a "
            "triple, so the sum below is no longer the union"
            % (MERGED, total, len(apart))
        )
        return
    if len(merged) != total:
        failures.append(
            "%s states %d triple(s); its %d source(s) state %d apart"
            % (MERGED, len(merged), len(MERGE_SOURCES), total)
        )
        return

    versions = {str(o) for o in merged.objects(None, rdflib.OWL.versionInfo)}
    declared = {str(o) for o in apart.objects(None, rdflib.OWL.versionInfo)}
    if versions != declared:
        failures.append(
            "%s declares owl:versionInfo %s; its sources declare %s"
            % (MERGED, sorted(versions), sorted(declared))
        )
        return
    print(
        "  OK      %-38s %d triples = %s, version %s"
        % (
            MERGED,
            len(merged),
            " + ".join(str(n) for n in counts),
            "/".join(sorted(versions)),
        )
    )


def check_headers(paths: "list[str]", failures: "list[str]") -> None:
    """The typed paths and the published RDF/JSON documents are the same set.

    Both directions, because each one misses a different mistake. A rule for a
    path nobody published is dead configuration. A published document with no
    rule is worse and quieter: Cloudflare Pages guesses from the extension, and
    neither `.ttl` nor `.jsonld` is in its table, so the document goes out as
    `text/plain` and a content-negotiating RDF client refuses bytes that are
    perfectly correct. `.html` is exempt because the host does know that one.
    """
    with open(published("_headers"), encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    rules = [
        line.strip()
        for line in lines
        if line.startswith("/") and not line.strip().startswith("#")
    ]
    if not rules:
        failures.append("_headers declares no rules at all")
        return
    exact = {rule.lstrip("/") for rule in rules if "*" not in rule}
    for rule in sorted(exact):
        if rule not in paths:
            failures.append(
                "_headers rule %r names a path that was not published" % rule
            )
    for path in paths:
        if not path.endswith((".ttl", ".jsonld", ".json")):
            continue
        if path not in exact:
            failures.append(
                "%s is published with no Content-Type rule in _headers; a "
                "static host would serve it as text/plain" % path
            )
    print("  OK      %-38s %d rule(s)" % ("_headers", len(rules)))


def main() -> int:
    print("==> Assembling %s" % os.path.relpath(SITE, REPO))
    paths = assemble()

    failures: "list[str]" = []
    check_parses(paths, failures)
    check_merged(failures)
    check_no_legacy_host(paths, failures)
    check_version(failures)
    check_headers(paths, failures)

    if failures:
        print("\nbuild-site: FAIL — %d problem(s):" % len(failures))
        for failure in failures:
            print("  - %s" % failure)
        return 1

    print("\nbuild-site: %d file(s) published under %s/"
          % (len(paths), os.path.relpath(SITE, REPO)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
