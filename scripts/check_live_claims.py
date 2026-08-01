#!/usr/bin/env python3
"""Check the dereference claims this repository publishes against the live web.

`README.md`, `docs/vson.md` §5.1 and `publish/index.html` all state the same
thing: the canonical VSON IRIs — `https://w3id.org/vson/v1/…` — dereference. A
GET on a *name* redirects to the *document* behind it. Nothing in the checkout
can establish that. It depends on a redirect rule in a repository this project
does not own (perma-id/w3id.org) and on a static host deployed by hand, either
of which can change without a commit here. That is exactly the shape of claim
that goes stale silently: the sentence keeps reading true long after it stopped
being true.

So the claims are written down once, here, as data — the five namespaces §5.1
names, plus the JSON-LD context and both JSON Schema `$id`s — and checked in
two hops per claim:

  1. the canonical name is requested *without following the redirect*, and its
     status and `Location` must equal what the repository documents;
  2. the target is then fetched, and must actually serve a document.

Hop 2 is what separates "a redirect rule exists" from "the name resolves to
something". A rule pointing at a 404 satisfies the first and falsifies the
sentence in the README.

Why this is NOT in `make check`
-------------------------------
`make check` runs on every push and must be answerable from the checkout alone.
A gate that depends on third-party DNS goes red for reasons the commit under
test did not cause, and a red build nobody caused is a build people stop
reading. This one is run deliberately — `make live-check` — when a dereference
claim changes, before a release, and after any edit to the w3id rule.

Exit codes
----------
  0  every claim holds.
  1  a claim is contradicted by the live response. Either the redirect broke or
     the documentation is wrong; the report names the file that says it.
  2  the check could not run — no network, DNS failure, timeout. Not a verdict
     on the claims. Keeping this off 1 is the point: "the documentation is
     wrong" and "I could not reach the network" are different findings, and a
     gate that reports them with the same code teaches people to ignore it.

Usage
-----
  python3 scripts/check_live_claims.py
  python3 scripts/check_live_claims.py --selftest   # offline, no requests
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
import urllib.error
import urllib.request

# Spelled once each. The canonical names are permanent; the host they currently
# redirect to is not, and a host move should be one edit here plus one in
# scripts/build_site.py — not a hunt through eight string literals.
W3ID_BASE = "https://w3id.org/vson/v1"
PAGES_BASE = "https://vson.pages.dev"

# Identifies the gate to the hosts it polls. It names the repository rather than
# a person or a product: whoever reads the w3id access log should be able to see
# what is asking and why without guessing.
USER_AGENT = "vson-live-check (+https://github.com/yamancan/visual-scene-ontology)"

DEFAULT_TIMEOUT = 20.0


@dataclasses.dataclass(frozen=True)
class Claim:
    """One documented dereference, as the repository states it.

    `published` is the path under `site/` that `scripts/build_site.py` writes —
    the same string on both sides of the deploy, which is what makes a rename
    detectable: `tests/test_live_claims.py` asserts every path here is one the
    build actually publishes, offline, before this gate ever runs.
    """

    name: str  # trailing path of the canonical IRI, under W3ID_BASE
    accept: str  # the Accept header a consumer of this document would send
    status: int  # the documented redirect status
    published: str  # the site/ path the redirect must land on
    documented_in: str  # where in this repository the claim is written down

    @property
    def iri(self) -> str:
        return "%s/%s" % (W3ID_BASE, self.name)

    @property
    def target(self) -> str:
        return "%s/%s" % (PAGES_BASE, self.published)


# The claim table. `status` values are what the live services answered when this
# table was written (2026-07-31, the day perma-id/w3id.org#6471 merged): 303 for
# the five namespace documents, which are names for things rather than the
# things themselves, and 302 for the context and schemas, which the w3id rule
# serves through a plain redirect. Do not "fix" a mismatch by editing a number
# here — a changed status is a changed contract, and the prose that describes it
# has to move with it.
CLAIMS = (
    Claim("ontology", "text/turtle", 303, "v1/ontology.ttl", "docs/vson.md §5.1"),
    Claim("rcc8", "text/turtle", 303, "v1/rcc8.ttl", "docs/vson.md §5.1"),
    Claim("allen", "text/turtle", 303, "v1/allen.ttl", "docs/vson.md §5.1"),
    Claim("shapes", "text/turtle", 303, "v1/shapes.ttl", "docs/vson.md §5.1"),
    Claim(
        "shapes-relaxed",
        "text/turtle",
        303,
        "v1/shapes-relaxed.ttl",
        "spec/CHANGELOG.md v1.2.0 (the fifth namespace)",
    ),
    Claim(
        "context.jsonld",
        "application/ld+json",
        302,
        "v1/context.jsonld",
        "docs/vson.md §4.4",
    ),
    Claim(
        "schema/vson-output.schema.json",
        "application/json",
        302,
        "v1/schema/vson-output.schema.json",
        "docs/vson.md §6.1 ($id)",
    ),
    Claim(
        "schema/vson-jsonld.schema.json",
        "application/json",
        302,
        "v1/schema/vson-jsonld.schema.json",
        "docs/vson.md Appendix A.2 ($id)",
    ),
)


@dataclasses.dataclass(frozen=True)
class Observation:
    """What one request actually returned. `error` set means it never arrived."""

    status: "int | None"
    location: "str | None" = None
    error: "str | None" = None


def evaluate_redirect(claim: Claim, observed: Observation) -> "list[str]":
    """Compare the first hop against the claim. Empty list means it holds.

    Pure by design: no I/O happens in here, so the comparison can be exercised
    offline — by `--selftest` and by `tests/test_live_claims.py` — which is the
    only way to know a gate is capable of going red without breaking the thing
    it watches.
    """
    problems = []
    if observed.status != claim.status:
        problems.append(
            "status %s, documented %s" % (observed.status, claim.status)
        )
    if observed.location != claim.target:
        problems.append(
            "redirects to %s, documented %s"
            % (observed.location or "(no Location header)", claim.target)
        )
    return problems


def evaluate_document(claim: Claim, observed: Observation) -> "list[str]":
    """Compare the second hop: the target must serve a document, not a 404."""
    if observed.status != 200:
        return ["%s serves %s, not 200" % (claim.target, observed.status)]
    return []


class _CaptureRedirect(urllib.request.HTTPRedirectHandler):
    """Report redirects instead of following them.

    Returning None tells urllib not to follow, so the 3xx surfaces as an
    HTTPError carrying the status and the `Location` header — which is the
    thing under test. Following would only prove that some host somewhere
    serves a document, never that the canonical name points at it.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def observe(url: str, accept: str, timeout: float, follow: bool) -> Observation:
    """One GET. `follow=False` captures the redirect rather than chasing it."""
    handlers = [] if follow else [_CaptureRedirect]
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(
        url, headers={"Accept": accept, "User-Agent": USER_AGENT}
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return Observation(response.status, response.headers.get("Location"))
    except urllib.error.HTTPError as exc:
        # A 3xx with _CaptureRedirect installed, or a genuine 4xx/5xx. Both are
        # answers from the server, so both are observations, not errors.
        return Observation(exc.code, exc.headers.get("Location"))
    except (urllib.error.URLError, OSError) as exc:
        return Observation(None, None, error=str(exc))


def check(timeout: float) -> int:
    print(
        "live-check: %d documented dereference(s), two hops each"
        % len(CLAIMS)
    )
    contradicted: "list[str]" = []
    unreachable: "list[str]" = []

    for claim in CLAIMS:
        redirect = observe(claim.iri, claim.accept, timeout, follow=False)
        if redirect.error is not None:
            unreachable.append(claim.iri)
            print("\n  UNREACHABLE  %s" % claim.iri)
            print("        %s" % redirect.error)
            continue

        problems = evaluate_redirect(claim, redirect)
        if not problems:
            document = observe(claim.target, claim.accept, timeout, follow=True)
            if document.error is not None:
                unreachable.append(claim.target)
                print("\n  UNREACHABLE  %s" % claim.target)
                print("        %s" % document.error)
                continue
            problems = evaluate_document(claim, document)

        if problems:
            contradicted.append(claim.iri)
            print("\n  FAIL  %s  [Accept: %s]" % (claim.iri, claim.accept))
            for problem in problems:
                print("        %s" % problem)
            print("        claimed in: %s" % claim.documented_in)
            continue

        print(
            "  ok    %s  %d -> %s"
            % (claim.iri, claim.status, claim.target)
        )

    if contradicted:
        print(
            "\nlive-check: FAIL — %d claim(s) contradicted by the live response:"
            % len(contradicted)
        )
        for iri in contradicted:
            print("  - %s" % iri)
        print(
            "\nEither the redirect broke or the documentation is wrong. Fix the\n"
            "one that is untrue — do not edit the expected status to match a\n"
            "response nobody intended."
        )
        return 1

    if unreachable:
        print(
            "\nlive-check: INCONCLUSIVE — %d request(s) never arrived:"
            % len(unreachable)
        )
        for url in unreachable:
            print("  - %s" % url)
        print("\nNothing is claimed about the claims. Re-run with a network.")
        return 2

    print("\nlive-check: %d claim(s) hold." % len(CLAIMS))
    return 0


def selftest() -> int:
    """Prove the comparators discriminate, without touching the network.

    A gate nobody has seen go red is a gate nobody should trust. This feeds the
    pure comparators a documented response and three wrong ones — a wrong
    status line, a wrong target, a missing `Location` header — and requires the
    first to pass and the rest to fail.
    """
    claim = CLAIMS[0]
    cases = (
        ("documented response", evaluate_redirect, Observation(claim.status, claim.target), False),
        ("wrong status line", evaluate_redirect, Observation(200, claim.target), True),
        ("wrong target", evaluate_redirect, Observation(claim.status, PAGES_BASE + "/v1/elsewhere.ttl"), True),
        ("no Location header", evaluate_redirect, Observation(claim.status, None), True),
        ("target serves 200", evaluate_document, Observation(200), False),
        ("target serves 404", evaluate_document, Observation(404), True),
    )

    print("live-check --selftest: %d comparator case(s), no requests" % len(cases))
    failures = []
    for label, comparator, observed, should_fail in cases:
        problems = comparator(claim, observed)
        if bool(problems) != should_fail:
            failures.append(label)
            print("  BROKEN  %-20s expected %s, got %s"
                  % (label, "a failure" if should_fail else "a pass", problems or "a pass"))
            continue
        print("  ok      %-20s %s" % (label, "red" if should_fail else "green"))

    if failures:
        print("\nlive-check --selftest: FAIL — the comparator does not discriminate.")
        return 1
    print("\nlive-check --selftest: the comparator goes red on a wrong claim.")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description="Check that the canonical VSON IRIs dereference as documented.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="exercise the comparators offline and exit; makes no requests",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="per-request timeout in seconds (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    return check(args.timeout)


if __name__ == "__main__":
    sys.exit(main())
