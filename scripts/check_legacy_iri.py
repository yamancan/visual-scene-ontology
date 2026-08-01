#!/usr/bin/env python3
"""Fail the build on any occurrence of the legacy `vson.dev` host outside a
named, counted allowlist.

Through v1.1 every canonical VSON IRI was minted under `https://vson.dev/` — a
hostname the project never registered. v1.2 reminted all five namespaces under
`https://w3id.org/vson/` (docs/vson.md §5.1). A rename like that does not stay
done on its own: one merged branch, one copy-pasted snippet, one regenerated
fixture is enough to put the dead host back, and nothing else in the gate matrix
would notice. SHACL selects focus nodes by IRI, so a document that drifts back
to the old namespace does not fail validation — it selects zero focus nodes and
passes *vacuously*. This gate is the thing that notices.

The allowlist is an inventory, not an escape hatch. Every remaining occurrence
in the repository is enumerated below with the reason it is allowed to exist,
and pinned entries are checked with `==`, not `<=`: the gate fails when a
pinned file gains an occurrence AND when it loses one. Losing one is not an
error in the code, it is an error in this file — the inventory stopped being
true and has to be re-measured. That is the whole point of pinning.

Two kinds of entry:

  * a pinned count — the occurrences are known, enumerated and stable;
  * UNBOUNDED — a document whose job is to *record* what the project used to
    publish. Editing one of those means adding historical text, so a pinned
    count there would only measure how much history has been written down.

Everything not listed must be at zero.

Usage:
  python3 scripts/check_legacy_iri.py
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEGACY_HOST = "vson.dev"

# Sentinel for "any count, including zero" — see the module docstring.
UNBOUNDED = None

# path -> (allowed count or UNBOUNDED, why it is allowed)
#
# Counts were measured against the tree immediately after the namespace prose
# landed (docs(spec): rename the v1 namespace and amend the immutability
# clause). Re-measure, never widen, when one of them moves.
ALLOW: "dict[str, tuple[int | None, str]]" = {
    # --- pinned: every occurrence is known and enumerated -------------------
    "ontology/vso.ttl": (
        1,
        "owl:priorVersion, carrying a LEGACY IRI comment. That string is the "
        "versionIRI the prior release actually declared; rewriting it would "
        "assert a name that release never carried. It is a record, not a "
        "resolvable name. docs/vson.md §8 states it as the one exception to "
        "IRI immutability. v1.2 moved it forward to the versionIRI the v1.1.1 "
        "tag actually declared; the count stays 1.",
    ),
    "cli/assets/ontology/vso.ttl": (
        1,
        "the copy of ontology/vso.ttl the `vson` binary embeds, so it works "
        "outside a checkout (cli/src/commands/embed.rs). It carries the same "
        "owl:priorVersion record as the original and the same count, because "
        "scripts/check_embedded_assets.py fails the build unless the two files "
        "are byte-identical. Fix the original; the mirror follows.",
    ),
    "docs/vson.md": (
        4,
        "the migration prose itself: §5.1 names the withdrawn host twice "
        "(what v1.1 minted under, and what no longer validates), §8 names it "
        "twice more (the clause the rename broke, and the vso.ttl "
        "exception). All four are mentions of a dead name, none is a minted "
        "IRI.",
    ),
    # --- unbounded: documents whose job is to record ------------------------
    "spec/vson-spec-v1.md": (
        UNBOUNDED,
        "superseded v1.0 specification. Its namespace table is what v1.0 "
        "published; it is annotated with a banner, never rewritten.",
    ),
    "spec/vson-spec-v0.1-deprecated.md": (
        UNBOUNDED,
        "deprecated v0.1 specification, retained on the same terms as v1.0.",
    ),
    "spec/CHANGELOG.md": (
        UNBOUNDED,
        "release history. The v1.2.0 entry has to name the host it migrated "
        "off, and older entries describe the IRIs their releases shipped.",
    ),
    "docs/strategy/productization.md": (
        UNBOUNDED,
        "dated strategy draft. Its vson.dev / api.vson.dev / studio.vson.dev "
        "hostnames were aspirational and never registered; the banner says "
        "so and the body stays as written.",
    ),
    "docs/strategy/ui-flows.md": (
        UNBOUNDED,
        "dated strategy draft, annotated on the same terms.",
    ),
    "docs/strategy/extractor-architecture.md": (
        UNBOUNDED,
        "dated strategy draft, annotated on the same terms.",
    ),
    "scripts/check_legacy_iri.py": (
        UNBOUNDED,
        "this gate. It has to spell the string it hunts for, and it has to "
        "explain every entry above.",
    ),
}


def tracked_files() -> "list[str]":
    """Every path git tracks, repo-relative.

    git ls-files rather than a filesystem walk: the gate should judge what the
    repository publishes, not what happens to be lying in the working tree.
    Build output, node_modules and every other ignored artefact is out of
    scope by construction — those are derived from sources this gate already
    covers.
    """
    out = subprocess.run(
        ["git", "-C", REPO, "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    return sorted(p.decode("utf-8") for p in out.split(b"\0") if p)


def occurrences(path: str) -> "tuple[int, list[tuple[int, str]]]":
    """Count occurrences of the legacy host in one file, with located lines.

    Matching is done on bytes: a text decode would have to guess an encoding
    and could skip a file the gate is supposed to judge. The needle is ASCII,
    so byte matching is exact for every encoding in this repository.
    """
    with open(os.path.join(REPO, path), "rb") as fh:
        blob = fh.read()
    needle = LEGACY_HOST.encode("ascii")
    count = blob.count(needle)
    if not count:
        return 0, []
    hits = []
    for lineno, raw in enumerate(blob.splitlines(), start=1):
        if needle in raw:
            hits.append((lineno, raw.decode("utf-8", "replace").strip()))
    return count, hits


def main() -> int:
    files = tracked_files()
    print(f'iri-check: {len(files)} tracked file(s) scanned for "{LEGACY_HOST}"')

    found = {}
    for path in files:
        count, hits = occurrences(path)
        if count:
            found[path] = (count, hits)

    failures: "list[str]" = []

    # Unlisted files carrying the legacy host: the case this gate exists for.
    for path in sorted(found):
        if path in ALLOW:
            continue
        count, hits = found[path]
        failures.append(path)
        print(f"\n  FAIL  {path}  ({count} occurrence(s), not allowlisted)")
        for lineno, text in hits:
            print(f"          {lineno}: {text[:120]}")

    # Allowlisted files, reported one by one so the inventory stays readable.
    print("\n  allowlist:")
    for path in sorted(ALLOW):
        allowed, reason = ALLOW[path]
        count = found.get(path, (0, []))[0]
        if path not in files:
            failures.append(path)
            print(f"    STALE {path}  (allowlisted but not tracked)")
            continue
        if allowed is UNBOUNDED:
            print(f"    ok    {path}  {count} (unbounded) — {reason}")
            continue
        if count != allowed:
            failures.append(path)
            print(f"    DRIFT {path}  {count} != {allowed} pinned — {reason}")
            for lineno, text in found.get(path, (0, []))[1]:
                print(f"          {lineno}: {text[:120]}")
            continue
        print(f"    ok    {path}  {count}/{allowed} — {reason}")

    if failures:
        print(f"\niri-check: FAIL — {len(failures)} file(s) off the allowlist:")
        for path in failures:
            print(f"  - {path}")
        print(
            "\nFix the occurrence. Widen the allowlist only for a document whose "
            "job is\nto record what the project used to publish, and write the "
            "reason in ALLOW.\nIf a pinned file legitimately lost an occurrence, "
            "re-measure and lower the pin."
        )
        return 1

    total = sum(c for c, _ in found.values())
    print(f"\niri-check: {total} occurrence(s), all accounted for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
