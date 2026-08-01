#!/usr/bin/env python3
"""Assemble `site/` — the dereferenceable surface for the VSON namespace.

Every canonical VSON IRI is a `https://w3id.org/vson/v1/...` name. A name that
returns 404 is still a valid identifier, but nothing can *follow* it: no term
browser, no `rdflib.Graph().parse(<iri>)`, no reviewer reading the ontology the
way the spec says to. This script takes the tracked sources and lays them out
under the exact paths those IRIs redirect to, so a static host (Cloudflare
Pages) can serve them.

It is a copy step with assertions, not a build step: nothing here rewrites,
minifies or generates content. `site/` is git-ignored and reproducible from the
tracked tree at any time — `make site`.

The assertions exist because a publish surface fails silently. A truncated
Turtle file still uploads; a stale version number in the landing page still
renders; a re-appearing legacy IRI still returns 200. So, before anything is
declared publishable:

  * every published .ttl parses with rdflib and carries triples;
  * every published .json / .jsonld parses;
  * no published byte names the withdrawn namespace host, with exactly one
    carve-out — the single `owl:priorVersion` line in the ontology, which
    records the versionIRI a prior release actually declared (see the LEGACY
    IRI comment in ontology/vso.ttl). The host itself is imported from
    scripts/check_legacy_iri.py, the gate whose job is to spell it and which
    pins that same occurrence to 1; spelling it a second time here would put
    the dead name back into the tree the repo-wide gate guards;
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

# The one published line allowed to name the legacy host. Matched precisely —
# an `owl:priorVersion` pointing at a versioned ontology document on that host
# and nothing else. The version segment is loose because a release bumps it;
# the shape of the line is not.
PRIOR_VERSION = re.compile(
    r"^\s*owl:priorVersion\s+<https://%s/v[0-9.]+/ontology>\s*;\s*$"
    % re.escape(LEGACY_HOST)
)
PRIOR_VERSION_FILE = "v1/ontology.ttl"

# The landing page states one version; this is where it states it.
VERSION_MARKER = re.compile(r'id="version"[^>]*>([^<]*)<')
INDEX = "index.html"
ONTOLOGY_TTL = "ontology/vso.ttl"


def published(rel: str) -> str:
    return os.path.join(SITE, rel)


def assemble() -> "list[str]":
    """Copy the tracked sources into a freshly emptied site/."""
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    for src, dst in COPY:
        target = published(dst)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(os.path.join(REPO, src), target)
        print("  copied  %-38s <- %s" % (dst, src))
    return [dst for _, dst in COPY]


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
        if rel != PRIOR_VERSION_FILE:
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


def check_headers(paths: "list[str]", failures: "list[str]") -> None:
    """Every exact-path rule in _headers names a published file."""
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
    for rule in rules:
        if "*" in rule:
            continue
        if rule.lstrip("/") not in paths:
            failures.append(
                "_headers rule %r names a path that was not published" % rule
            )
    print("  OK      %-38s %d rule(s)" % ("_headers", len(rules)))


def main() -> int:
    print("==> Assembling %s" % os.path.relpath(SITE, REPO))
    paths = assemble()

    failures: "list[str]" = []
    check_parses(paths, failures)
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
