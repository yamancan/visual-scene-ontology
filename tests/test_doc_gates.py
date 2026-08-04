"""Offline tests for the two documentation-truthfulness gates.

`scripts/check_md_anchors.py` and `scripts/check_counts_drift.py` both exist
because this repository's front page argues that a claim should be a thing you
can run, and two kinds of claim on it were not:

  * a citation — twenty-four links pointed at fragments GitHub does not mint,
    because five headings carried Pandoc `{#appendix-e}` attributes GFM has no
    extension for;
  * a count — the README said `555 Python tests` one line above the command
    that runs 571 of them.

Both gates run in `make check`. A gate that passes proves nothing on its own,
so what is established here is the same pair of things `tests/test_drift_gates`
establishes for the copy-drift gates:

  * each comparator goes red when fed the shape it exists to catch — a
    heading attribute, an anchor that resolves to nothing, a stated count that
    is not the computed one, a claim reworded out of the pattern that checks
    it;
  * each gate's own table still points at something real. A metric a claim
    names but nothing computes, or a claim pattern that matches nothing
    anywhere, would make a gate go quiet rather than red.

Run: python3 -m unittest tests.test_doc_gates
"""

import contextlib
import importlib.util
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")


def _script(name):
    """Import a module from scripts/ by path — same loader as
    tests/test_drift_gates.py."""
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(SCRIPTS, name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


anchors = _script("check_md_anchors")
counts = _script("check_counts_drift")


def _quiet(callable_, *args):
    """Run a gate entry point without letting its report into the test output."""
    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stdout(devnull):
            return callable_(*args)


class SlugMatchesGitHub(unittest.TestCase):
    """The slug is the renderer's, not a guess at it."""

    def test_pinned_vectors(self):
        for text, expected in anchors.SLUG_VECTORS:
            self.assertEqual(
                expected, anchors.gfm_slug(anchors.heading_text(text)), text
            )

    def test_em_dash_leaves_two_hyphens(self):
        # The whole reason the appendix links broke: a human writes
        # `#appendix-e`, GitHub mints `appendix-e--related-work-...`.
        self.assertEqual(
            "appendix-e--related-work-and-bibliography",
            anchors.gfm_slug(
                anchors.heading_text("Appendix E — Related work and bibliography")
            ),
        )

    def test_punctuation_is_deleted_not_replaced(self):
        self.assertEqual("52-vsoentity", anchors.gfm_slug("5.2 vso:Entity"))

    def test_hyphen_and_underscore_survive(self):
        self.assertEqual(
            "vson-x_mode", anchors.gfm_slug(anchors.heading_text("VSON-X_mode"))
        )

    def test_inline_markup_is_rendered_away(self):
        self.assertEqual(
            "run-make-check",
            anchors.gfm_slug(anchors.heading_text("Run `make check`")),
        )

    def test_duplicate_headings_get_numeric_suffixes(self):
        doc = anchors.Doc("t.md", "# A\n\n# A\n\n# A\n")
        self.assertEqual(["a", "a-1", "a-2"], [h[2] for h in doc.headings])


class AnchorGateGoesRed(unittest.TestCase):
    def test_resolving_anchor_passes(self):
        doc = anchors.Doc("t.md", "# Title Here\n\n[go](#title-here)\n")
        self.assertEqual([], anchors.check({"t.md": doc}))

    def test_broken_anchor_fails(self):
        doc = anchors.Doc("t.md", "# Title Here\n\n[go](#title-heer)\n")
        problems = anchors.check({"t.md": doc})
        self.assertTrue(problems)
        self.assertIn("matches no heading", problems[0])

    def test_pandoc_heading_attribute_fails(self):
        # The acceptance case: exactly the shipped bug.
        doc = anchors.Doc("t.md", "## Appendix E — Related work {#appendix-e}\n")
        problems = anchors.check({"t.md": doc})
        self.assertTrue(problems)
        self.assertIn("Pandoc", problems[0])

    def test_cross_file_anchor_is_resolved_in_the_target(self):
        # The target must exist on disk for the path half of the check, so the
        # two real files this repository ships stand in for invented ones.
        docs = {
            "README.md": anchors.Doc(
                "README.md", "[x](docs/vson.md#2-conformance)\n"
            ),
            "docs/vson.md": anchors.load_docs()["docs/vson.md"],
        }
        self.assertEqual([], anchors.check(docs))

    def test_missing_link_target_fails(self):
        doc = anchors.Doc("t.md", "[x](docs/nothing-here.md#a)\n")
        problems = anchors.check({"t.md": doc})
        self.assertTrue(problems)
        self.assertIn("does not exist", problems[0])

    def test_external_links_are_out_of_scope(self):
        doc = anchors.Doc(
            "t.md", "[x](https://example.org/a#b)\n[y](mailto:a@b#c)\n"
        )
        self.assertEqual([], anchors.check({"t.md": doc}))

    def test_fenced_code_is_not_parsed(self):
        doc = anchors.Doc("t.md", "```\n# Heading\n[x](#nowhere)\n```\n")
        self.assertEqual([], doc.headings)
        self.assertEqual([], doc.links)

    def test_inline_code_is_not_a_link(self):
        doc = anchors.Doc("t.md", "Write `[x](#nowhere)` to link.\n")
        self.assertEqual([], doc.links)

    def test_selftest_mode_is_green(self):
        self.assertEqual(0, _quiet(anchors.selftest))

    def test_the_repository_resolves(self):
        self.assertEqual(0, _quiet(anchors.main, []))


class CountsGateTableIsReal(unittest.TestCase):
    def test_every_claim_names_a_computed_metric(self):
        for claim in counts.CLAIMS:
            for metric in claim.metrics:
                self.assertIn(metric, counts.METRICS, claim.pattern.pattern)

    def test_every_sweep_names_a_computed_metric(self):
        for metric in counts.SWEEPS:
            self.assertIn(metric, counts.METRICS)

    def test_every_claim_captures_one_group_per_metric(self):
        for claim in counts.CLAIMS:
            self.assertGreaterEqual(
                claim.pattern.groups,
                len(claim.metrics),
                claim.pattern.pattern,
            )

    def test_every_claim_still_matches_the_prose(self):
        # A pattern that matches nothing is a number nobody checks.
        values = {name: -1 for name in counts.METRICS}
        problems = counts.check(values)
        self.assertEqual(
            [], [p for p in problems if "matches nothing in scope" in p]
        )

    def test_exempt_files_are_tracked_files(self):
        for rel in counts.EXEMPT:
            self.assertTrue(
                os.path.exists(os.path.join(REPO, rel)),
                f"{rel} is exempted but is not in the checkout",
            )

    def test_exempt_files_are_out_of_scope(self):
        in_scope = set(counts.scope())
        for rel in counts.EXEMPT:
            self.assertNotIn(rel, in_scope)


class CountsGateGoesRed(unittest.TestCase):
    """Fed a document whose numbers are wrong, the comparator must say so."""

    FAKE = None

    def setUp(self):
        self.FAKE = {name: 7 for name in counts.METRICS}

    def _check(self, text):
        with tempfile.TemporaryDirectory(dir=REPO) as directory:
            rel = os.path.relpath(
                os.path.join(directory, "scratch.md"), REPO
            )
            with open(os.path.join(REPO, rel), "w", encoding="utf-8") as fh:
                fh.write(text)
            return [
                p
                for p in counts.check(self.FAKE, [rel])
                if "matches nothing in scope" not in p
            ]

    def test_true_count_passes(self):
        self.assertEqual([], self._check("make check  # 7 Python tests\n"))

    def test_drifted_count_fails(self):
        # The acceptance case: the shipped bug, in miniature.
        problems = self._check("make check  # 555 Python tests\n")
        self.assertTrue(problems)
        self.assertIn("python_tests", problems[0])

    def test_drift_in_any_metric_fails(self):
        for text, metric in (
            ("the 9-entry conformance suite\n", "conformance_entries"),
            ("holds 9 competency questions\n", "cq_total"),
            ("the 9 executable competency questions\n", "cq_executed"),
            ("the 9 frozen canonical hashes\n", "canonical_hashes"),
            ("the 9-scene gallery\n", "gallery_scenes"),
            ("the 9-document corpus\n", "corpus_documents"),
            ("9 tests: 7 unit, 7 integration\n", "rust_tests"),
        ):
            with self.subTest(metric=metric):
                problems = self._check(text)
                self.assertTrue(problems, text)
                self.assertTrue(any(metric in p for p in problems), problems)

    def test_reworded_claim_is_unclassified_rather_than_invisible(self):
        problems = self._check("the suite runs 7  Python tests today\n")
        self.assertTrue(any("unclassified" in p for p in problems))

    def test_selftest_mode_is_green(self):
        self.assertEqual(0, _quiet(counts.selftest))


class CountsMatchTheTree(unittest.TestCase):
    """The metrics are computed from the artifacts, not read from a copy."""

    def test_cq_executed_never_exceeds_the_pack(self):
        self.assertLessEqual(counts.cq_executed(), counts.cq_total())

    def test_canonical_table_covers_every_shipped_document(self):
        # One row per gallery scene, per VSON-X counterpart, plus the throne
        # room: the table is the §4.6 denotation claim, so a document that
        # gains no row is a document nothing pins.
        self.assertEqual(
            counts.gallery_scenes() + counts.gallery_x_scenes() + 1,
            counts.canonical_hashes(),
        )

    def test_rust_totals_add_up(self):
        self.assertEqual(
            counts.rust_unit_tests() + counts.rust_integration_tests(),
            counts.rust_tests(),
        )

    def test_the_repository_agrees_with_its_own_prose(self):
        self.assertEqual(0, _quiet(counts.main, []))


if __name__ == "__main__":
    unittest.main()
