"""Offline tests for the live-claims gate (`scripts/check_live_claims.py`).

That gate is the only one in this repository that talks to the network, which
means it is the only one whose correctness cannot be established by running it:
a green result could be a working check or a check that cannot fail. So the two
things worth knowing about it are established here instead, from the checkout,
with no requests at all:

  * the comparator goes red when fed a wrong status line or a wrong target —
    a gate nobody has seen fail is a gate nobody should trust;
  * every redirect target in the claim table is a path `scripts/build_site.py`
    actually publishes. The live gate cannot catch a stale claim table by
    itself: rename a published path and both the redirect and the expectation
    would be wrong together, agreeing with each other about a 404.

These run inside `make check`. The gate they describe deliberately does not —
see the module docstring in `scripts/check_live_claims.py`.
"""

import contextlib
import importlib.util
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")


def _script(name):
    """Import a module from scripts/ by path.

    scripts/ goes on sys.path first because those modules import each other by
    bare name (`build_site` imports `check_legacy_iri`), which is the sys.path[0]
    they get when run directly as `python3 scripts/<name>.py` — the way every
    Makefile target invokes them.

    The sys.modules registration is not bookkeeping: under `from __future__
    import annotations` every dataclass field type is a string, and dataclasses
    resolves those through `sys.modules[cls.__module__]`. Executing a module
    that is not registered there raises AttributeError on Python 3.9 — the
    maintainer's system Python, which pyproject.toml pins as the floor.
    """
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(SCRIPTS, name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


live = _script("check_live_claims")
build_site = _script("build_site")


class ComparatorGoesRed(unittest.TestCase):
    """The claim comparator must contradict a response that contradicts it."""

    def setUp(self):
        self.claim = live.CLAIMS[0]

    def test_documented_response_passes(self):
        observed = live.Observation(self.claim.status, self.claim.target)
        self.assertEqual([], live.evaluate_redirect(self.claim, observed))

    def test_wrong_status_line_fails(self):
        # The acceptance case: feed the documented target with an undocumented
        # status and the gate has to say so.
        observed = live.Observation(200, self.claim.target)
        problems = live.evaluate_redirect(self.claim, observed)
        self.assertTrue(problems)
        self.assertIn("status 200", problems[0])

    def test_wrong_target_fails(self):
        observed = live.Observation(
            self.claim.status, live.PAGES_BASE + "/v1/elsewhere.ttl"
        )
        problems = live.evaluate_redirect(self.claim, observed)
        self.assertTrue(problems)
        self.assertIn("elsewhere.ttl", problems[0])

    def test_missing_location_header_fails(self):
        observed = live.Observation(self.claim.status, None)
        self.assertTrue(live.evaluate_redirect(self.claim, observed))

    def test_target_must_serve_a_document(self):
        self.assertEqual([], live.evaluate_document(self.claim, live.Observation(200)))
        self.assertTrue(live.evaluate_document(self.claim, live.Observation(404)))

    def test_selftest_mode_is_green(self):
        # `--selftest` is the same discrimination check, runnable by hand
        # without a network. If it ever disagrees with the cases above, one of
        # the two is lying about what the gate does. Its report is swallowed:
        # a passing test suite should print its own summary and nothing else.
        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull):
                exit_code = live.main(["--selftest"])
        self.assertEqual(0, exit_code)


class ClaimTableMatchesThePublishSurface(unittest.TestCase):
    """Every claimed redirect target must be a document the build publishes."""

    def test_targets_are_published_paths(self):
        published = {dst for _, dst in build_site.COPY}
        for claim in live.CLAIMS:
            self.assertIn(
                claim.published,
                published,
                "%s expects a redirect to %s, which scripts/build_site.py does "
                "not publish" % (claim.iri, claim.published),
            )

    def test_claims_are_canonical_names(self):
        for claim in live.CLAIMS:
            self.assertTrue(
                claim.iri.startswith("https://w3id.org/vson/v1/"),
                "%s is not a canonical VSON name" % claim.iri,
            )

    def test_every_claim_names_a_file_that_says_it(self):
        # `documented_in` is the actionable half of a failure report: it tells
        # whoever reads the red build which sentence to go fix. A pointer at a
        # file that no longer exists would send them nowhere.
        for claim in live.CLAIMS:
            path = claim.documented_in.split()[0]
            self.assertTrue(
                os.path.isfile(os.path.join(REPO, path)),
                "%s points at %s, which does not exist" % (claim.iri, path),
            )

    def test_the_five_namespaces_are_all_claimed(self):
        # docs/vson.md §5.1 and the v1.2.0 changelog entry both say "all five
        # namespaces". If one is ever dropped from the table, the gate would go
        # green while a documented name went unchecked.
        namespaces = {"ontology", "rcc8", "allen", "shapes", "shapes-relaxed"}
        self.assertTrue(namespaces.issubset({c.name for c in live.CLAIMS}))


if __name__ == "__main__":
    unittest.main()
