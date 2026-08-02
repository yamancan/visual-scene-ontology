"""Tests for the conformance suite's runner (`tools/conformance_runner.py`).

`make conformance` running green establishes that the 218 entries got their
pinned verdicts. It establishes nothing about whether the runner *can* go red,
and a gate nobody has seen fail is a gate nobody should trust — the same
reasoning `tests/test_live_claims.py` gives for the live gate. So the things
worth knowing about the runner are established here instead:

  * a pinned verdict that moves is caught — on the report *and* on the shape,
    the path, the severity and the count, not merely on conformance;
  * the coverage gate goes red for a new shape with no negative entry, for a
    stale exemption, and for a §D.7 row with no entry — the three ways the
    published coverage table could start lying;
  * the manifest's own vocabulary closure goes red on an undeclared term;
  * the `--engine` seam dispatches to whatever is registered, and refuses a
    name nothing is registered under rather than falling back to pyshacl and
    reporting a cross-validation that did not happen.

Every mutation is applied to a copy of the manifest in a temporary directory;
nothing here writes to `tests/conformance/`.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import tempfile
import unittest

try:
    import rdflib

    from tools import conformance_runner as cr
except ImportError:  # pragma: no cover - environment
    rdflib = None
    cr = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _suite(manifest: str = None) -> "cr.Suite":
    return cr.Suite(cr.ENGINES["pyshacl"], manifest or cr.MANIFEST)


def _quiet_main(argv):
    """`cr.main` with its report captured — `make check` prints enough already."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cr.main(argv)
    return code, out.getvalue() + err.getvalue()


@unittest.skipUnless(rdflib and cr, "rdflib + pyshacl required")
class ManifestStructureTests(unittest.TestCase):
    """The manifest is what the runner says it is."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = _suite()

    def test_the_declared_entry_count_is_the_listed_one(self) -> None:
        # Checked by the runner too; here so a truncated mf:entries list is a
        # named test failure rather than a shorter run nobody notices.
        declared = next(
            self.suite.graph.objects(
                self.suite.manifest, rdflib.URIRef(cr.VSONT + "entryCount")
            )
        )
        self.assertEqual(int(declared), len(self.suite.entries))

    def test_every_entry_has_a_type_the_runner_can_execute(self) -> None:
        for entry in self.suite.entries:
            with self.subTest(entry=entry.id):
                self.assertIn(entry.kind, cr.Suite.RUNNERS)

    def test_entry_ids_are_unique(self) -> None:
        ids = [entry.id for entry in self.suite.entries]
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_vocabulary_closure_holds(self) -> None:
        self.suite.check_vocabulary()

    def test_the_vocabulary_closure_goes_red_on_an_undeclared_term(self) -> None:
        suite = _suite()
        suite.graph.add(
            (
                rdflib.URIRef(cr.TESTS + "invented"),
                rdflib.URIRef(cr.VSONT + "notDeclaredAnywhere"),
                rdflib.Literal("x"),
            )
        )
        with self.assertRaises(cr.Failure) as caught:
            suite.check_vocabulary()
        self.assertIn("notDeclaredAnywhere", str(caught.exception))


@unittest.skipUnless(rdflib and cr, "rdflib + pyshacl required")
class MutationTests(unittest.TestCase):
    """A moved verdict is a red build. One mutation per pinned field."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = _suite()
        cls.by_id = {entry.id: entry for entry in cls.suite.entries}

    def _run(self, entry_id: str) -> None:
        entry = self.by_id[entry_id]
        getattr(self.suite, cr.Suite.RUNNERS[entry.kind])(entry)

    def _mutate(self, entry_id: str, predicate: str, value) -> None:
        """Replace one pinned object, run the entry, and expect a Failure."""
        entry = self.by_id[entry_id]
        result = entry.result
        subject = result
        if predicate.startswith(cr.SH) and predicate != cr.SH + "conforms":
            subject = next(self.suite.graph.objects(result, rdflib.URIRef(cr.SH + "result")))
        before = list(self.suite.graph.objects(subject, rdflib.URIRef(predicate)))
        self.suite.graph.remove((subject, rdflib.URIRef(predicate), None))
        self.suite.graph.add((subject, rdflib.URIRef(predicate), value))
        try:
            with self.assertRaises(cr.Failure):
                self._run(entry_id)
        finally:
            self.suite.graph.remove((subject, rdflib.URIRef(predicate), None))
            for old in before:
                self.suite.graph.add((subject, rdflib.URIRef(predicate), old))
        self._run(entry_id)  # restored: green again

    def test_a_wrong_source_shape_fails(self) -> None:
        self._mutate(
            "validate-neg-directional-viewer-min",
            cr.SH + "sourceShape",
            rdflib.URIRef("https://w3id.org/vson/v1/shapes#EventShape"),
        )

    def test_a_wrong_result_path_fails(self) -> None:
        self._mutate(
            "validate-neg-directional-viewer-min",
            cr.SH + "resultPath",
            rdflib.URIRef("https://w3id.org/vson/v1/ontology#lemma"),
        )

    def test_a_wrong_focus_node_fails(self) -> None:
        self._mutate(
            "validate-neg-directional-viewer-min",
            cr.SH + "focusNode",
            rdflib.URIRef("https://example.org/scenes/bad1#nothing"),
        )

    def test_a_wrong_severity_fails(self) -> None:
        self._mutate(
            "validate-neg-directional-viewer-min",
            cr.SH + "resultSeverity",
            rdflib.URIRef(cr.SH + "Warning"),
        )

    def test_a_wrong_gate_fails(self) -> None:
        self._mutate(
            "validate-neg-orphan-term",
            cr.VSONT + "gate",
            rdflib.URIRef(cr.VSONT + "shacl"),
        )

    def test_conforms_true_on_a_failing_document_fails(self) -> None:
        self._mutate(
            "validate-neg-directional-viewer-min",
            cr.SH + "conforms",
            rdflib.Literal(True),
        )

    def test_the_comparison_is_exhaustive(self) -> None:
        """Dropping one of three pinned results is a failure, not a pass.

        `bad_geometry_grammar.ttl` trips vss:GeometryShape three times. A
        subset comparison would call two-of-three a pass, which is how an
        over-firing shape survives a suite.
        """
        entry = self.by_id["validate-neg-geometry-grammar"]
        pinned = list(self.suite.graph.objects(entry.result, rdflib.URIRef(cr.SH + "result")))
        self.assertEqual(len(pinned), 3)
        dropped = pinned[0]
        self.suite.graph.remove((entry.result, rdflib.URIRef(cr.SH + "result"), dropped))
        try:
            with self.assertRaises(cr.Failure) as caught:
                self._run("validate-neg-geometry-grammar")
            self.assertIn("pins 2", str(caught.exception))
        finally:
            self.suite.graph.add((entry.result, rdflib.URIRef(cr.SH + "result"), dropped))
        self._run("validate-neg-geometry-grammar")

    def test_a_wrong_error_row_fails(self) -> None:
        entry = self.by_id["parse-x-neg-e14"]
        predicate = rdflib.URIRef(cr.VSONT + "errorRow")
        self.suite.graph.remove((entry.result, predicate, None))
        self.suite.graph.add((entry.result, predicate, rdflib.Literal("E1")))
        try:
            with self.assertRaises(cr.Failure) as caught:
                self._run("parse-x-neg-e14")
            self.assertIn("E14", str(caught.exception))
        finally:
            self.suite.graph.remove((entry.result, predicate, None))
            self.suite.graph.add((entry.result, predicate, rdflib.Literal("E14")))
        self._run("parse-x-neg-e14")

    def test_a_wrong_canonical_hash_fails(self) -> None:
        entry = self.by_id["equivalence-11-throne-room"]
        predicate = rdflib.URIRef(cr.VSONT + "canonicalHash")
        before = next(self.suite.graph.objects(entry.result, predicate))
        self.suite.graph.remove((entry.result, predicate, None))
        self.suite.graph.add((entry.result, predicate, rdflib.Literal("0" * 64)))
        try:
            with self.assertRaises(cr.Failure):
                self._run("equivalence-11-throne-room")
        finally:
            self.suite.graph.remove((entry.result, predicate, None))
            self.suite.graph.add((entry.result, predicate, before))
        self._run("equivalence-11-throne-room")

    def test_a_wrong_expected_output_fails(self) -> None:
        entry = self.by_id["export-caption-01-minimal"]
        predicate = rdflib.URIRef(cr.VSONT + "expectedOutput")
        before = next(self.suite.graph.objects(entry.result, predicate))
        with tempfile.TemporaryDirectory() as tmp:
            wrong = os.path.join(tmp, "wrong.txt")
            with open(wrong, "w", encoding="utf-8") as handle:
                handle.write("not the caption\n")
            self.suite.graph.remove((entry.result, predicate, None))
            self.suite.graph.add(
                (entry.result, predicate, rdflib.URIRef("file://" + wrong))
            )
            try:
                with self.assertRaises(cr.Failure):
                    self._run("export-caption-01-minimal")
            finally:
                self.suite.graph.remove((entry.result, predicate, None))
                self.suite.graph.add((entry.result, predicate, before))
        self._run("export-caption-01-minimal")


@unittest.skipUnless(rdflib and cr, "rdflib + pyshacl required")
class ErrorRowTests(unittest.TestCase):
    """§D.7's identifiers are decided against the specification's own table."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.patterns = cr.error_patterns()

    def test_every_row_in_the_spec_has_a_pattern(self) -> None:
        self.assertEqual(len(self.patterns), 18)

    def test_a_message_no_row_describes_matches_nothing(self) -> None:
        # The matcher has to be able to say "none", or an entry could pin any
        # row and the run would agree with it.
        self.assertEqual(cr.row_of("the parser fell over", self.patterns), [])

    def test_each_row_message_identifies_exactly_its_own_row(self) -> None:
        samples = {
            "E1": "unexpected character: '$'",
            "E3": "unknown concept after /: Knight",
            "E5": "unexpected EOF after handle 'alice'",
            "E14": "unknown spatial relation 'ZZ': expected one of ['DC']",
            "E16": "directional spatial fact requires a viewer anchor (^cam); see §4.10.2",
            "E17": "'beside' is not a symmetric proximal lemma; expected one of ['near']",
        }
        for row, message in samples.items():
            with self.subTest(row=row):
                self.assertEqual(cr.row_of(message, self.patterns), [row])


@unittest.skipUnless(rdflib and cr, "rdflib + pyshacl required")
class CoverageTests(unittest.TestCase):
    """The generated table cannot claim coverage the manifest lacks."""

    def setUp(self) -> None:
        self.suite = _suite()
        self.coverage = cr.Coverage(self.suite)

    def test_the_shipped_manifest_has_no_coverage_problem(self) -> None:
        self.assertEqual(self.coverage.problems(), [])

    def test_the_table_matches_the_one_the_specification_publishes(self) -> None:
        self.assertEqual(cr.spec_table().strip(), self.coverage.table().strip())

    def test_a_new_shape_without_a_negative_entry_fails(self) -> None:
        """The acceptance criterion, as a test.

        Adding a shape to shapes/vson-shapes.ttl and no entry to the manifest
        has to break the build; otherwise the coverage table starts describing
        a shapes file it has fallen behind.
        """
        self.suite.shapes.add(
            (
                rdflib.URIRef("https://w3id.org/vson/v1/shapes#NewlyAddedShape"),
                rdflib.RDF.type,
                rdflib.URIRef(cr.SH + "NodeShape"),
            )
        )
        coverage = cr.Coverage(self.suite)
        problems = coverage.problems()
        self.assertTrue(any("NewlyAddedShape" in problem for problem in problems), problems)

    def test_an_exemption_for_a_shape_that_is_gone_fails(self) -> None:
        coverage = cr.Coverage(self.suite)
        coverage.exempt["https://w3id.org/vson/v1/shapes#RemovedShape"] = "stale"
        self.assertTrue(
            any("RemovedShape" in problem for problem in coverage.problems())
        )

    def test_a_d7_row_without_an_entry_fails(self) -> None:
        coverage = cr.Coverage(self.suite)
        self.suite.patterns["E99"] = ["invented"]
        self.assertTrue(any("E99" in problem for problem in coverage.problems()))

    def test_every_exemption_states_a_reason(self) -> None:
        self.assertTrue(self.coverage.exempt)
        for shape, reason in self.coverage.exempt.items():
            with self.subTest(shape=shape):
                self.assertGreater(len(reason), 40, msg="a one-word reason is not one")

    def test_the_map_lists_the_entries_the_table_counts(self) -> None:
        """--coverage-map and --coverage-table cannot disagree.

        The table publishes counts because a section listing 104 identifiers is
        one nobody reads; the map is the other half. Both come from the same
        fields, and this is what says so.
        """
        text = self.coverage.map()
        for clause in cr.CLAUSES:
            covering = [e for e in self.coverage.entries if clause in e.clauses]
            with self.subTest(clause=clause):
                self.assertIn("%-8s %d entries" % (clause, len(covering)), text)
                for entry in covering:
                    self.assertIn(entry.id, text)

    def test_the_map_shows_every_section_an_entry_names(self) -> None:
        # The table is scoped to C1-C9 and §5/§6 — what a reader of a
        # specification section can take in. A tag outside that scope (§4.6,
        # §7, Appendix D.7) would otherwise be a tag no output ever shows,
        # which is a tag nobody maintains.
        tagged = {s for entry in self.coverage.entries for s in entry.sections}
        text = self.coverage.map()
        for section in sorted(tagged):
            with self.subTest(section=section):
                self.assertIn("§" + section, text)

    def test_the_map_still_names_the_uncovered_sections(self) -> None:
        text = self.coverage.map()
        for section in self.coverage.uncovered():
            with self.subTest(section=section):
                self.assertIn("%-8s uncovered" % section, text)

    def test_the_uncovered_sections_are_the_ones_the_spec_names(self) -> None:
        # §5.14/§5.15/§5.16 constrain a tool, §6.1/§6.2 are the envelope schema,
        # §6.3 is a reference table — all six are named in §2.2's prose. This
        # pins the list so a section that silently loses its coverage shows up.
        self.assertEqual(
            self.coverage.uncovered(),
            ["§5.14", "§5.15", "§5.16", "§6.1", "§6.2", "§6.3"],
        )


@unittest.skipUnless(rdflib and cr, "rdflib + pyshacl required")
class EngineSeamTests(unittest.TestCase):
    """The seam dispatches, and refuses rather than falling back."""

    def test_an_unregistered_engine_exits_two_and_runs_nothing(self) -> None:
        # Exit 2 is "no verdict". Falling back to pyshacl here would report a
        # cross-validation that did not happen, which is the one outcome worse
        # than not having a second engine.
        code, report = _quiet_main(["--engine", "jena", "--filter", "parse-p-01"])
        self.assertEqual(code, 2)
        self.assertIn("no cross-validation", report)

    def test_a_registered_engine_is_used(self) -> None:
        class CountingEngine(cr.Engine):
            name = "counting-test-engine"

            def __init__(self) -> None:
                self.calls = 0

            def unavailable(self):
                return None

            def describe(self) -> str:
                return "counting-test-engine (delegates to pyshacl)"

            def validate(self, data, shapes, ont):
                self.calls += 1
                return cr.ENGINES["pyshacl"].validate(data, shapes, ont)

        engine = CountingEngine()
        cr.register(engine)
        try:
            code, _report = _quiet_main(
                ["--engine", engine.name, "--filter", "validate-neg-directional-viewer"]
            )
        finally:
            del cr.ENGINES[engine.name]
        self.assertEqual(code, 0)
        self.assertEqual(engine.calls, 3)

    def test_pyshacl_is_registered_and_available(self) -> None:
        self.assertIn("pyshacl", cr.ENGINES)
        self.assertIsNone(cr.ENGINES["pyshacl"].unavailable())

    def test_the_second_engine_slot_is_documented_as_open(self) -> None:
        # The honest record: exactly one adapter ships. If a second one is ever
        # registered at import time this test is the notice to update §2.2's
        # "One engine" paragraph, which claims there is one.
        self.assertEqual(sorted(cr.ENGINES), ["pyshacl"])


@unittest.skipUnless(rdflib and cr, "rdflib + pyshacl required")
class ManifestLoadingTests(unittest.TestCase):
    """Loading failures are exit 2 — a run that could not happen is not a pass."""

    def test_a_manifest_that_will_not_parse_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = os.path.join(tmp, "manifest.ttl")
            with open(broken, "w", encoding="utf-8") as handle:
                handle.write("this is not turtle {{{")
            code, report = _quiet_main(["--manifest", broken])
            self.assertEqual(code, 2)
            self.assertIn("could not load the manifest", report)

    def test_a_miscounted_manifest_fails(self) -> None:
        # A truncated mf:entries list is the failure this guards: the run would
        # be shorter, every entry in it would pass, and the report would say so.
        with open(cr.MANIFEST, encoding="utf-8") as handle:
            text = handle.read()
        entries = len(_suite().entries)
        miscounted = text.replace(
            "vsont:entryCount %d ;" % entries, "vsont:entryCount 3 ;", 1
        )
        self.assertNotEqual(text, miscounted, "the count is not spelled as expected")
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "manifest.ttl")
            with open(copy, "w", encoding="utf-8") as handle:
                handle.write(miscounted)
            with self.assertRaises(cr.Failure) as caught:
                cr.Suite(cr.ENGINES["pyshacl"], copy)
        self.assertIn("declares 3 entries", str(caught.exception))

    def test_two_entry_counts_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "manifest.ttl")
            shutil.copyfile(cr.MANIFEST, copy)
            with open(copy, "a", encoding="utf-8") as handle:
                handle.write(
                    "\n<https://w3id.org/vson/v1/conformance/manifest>\n"
                    "    <https://w3id.org/vson/v1/conformance#entryCount> 3 .\n"
                )
            with self.assertRaises(cr.Failure):
                cr.Suite(cr.ENGINES["pyshacl"], copy)


if __name__ == "__main__":
    unittest.main()
