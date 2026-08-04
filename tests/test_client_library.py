"""The `vson` package: its public surface, its verdicts, its loop, its bounds.

`vson` is a facade over `tools/` (see `vson/__init__.py`), which decides what is
worth testing here and what is not. The transpilers, the gates, the metric and
the canonical form are tested where they live — re-asserting them through the
facade would only prove the facade forwards. What is tested here is everything
the facade *adds*, and every one of those is a place it could silently lie:

  * **The surface exists and is typed.** A name promised in `__all__` that does
    not import is a broken contract with a consumer, and `__all__` is the whole
    contract. Each name is imported and its kind checked.
  * **Verdicts are right on both sides.** A conformant fixture and a known-bad
    one, checked for the verdict, the gate that fired and the message the repair
    loop feeds back.
  * **The loop converges, and stops.** A scripted `chat_fn` that fixes the
    document on round 0, 1 and 2, and one that never fixes it — the last is the
    case where `shacl_retries` must equal the bound and `conforms` must be
    `False` rather than an exception.
  * **The bounds are the studio's.** `MAX_REPAIR_RETRIES` and
    `SHACL_REPORT_SLICE_CHARS` are read back out of
    `web/src/lib/extract/limits.ts` and compared. Same for the two user prompts
    and the two prompt versions in `prompts/meta.ts`. TypeScript cannot import
    Python, so these are copies; this is the gate that keeps a copy from
    becoming a divergence.
  * **The envelope type round-trips a real envelope.** Against a *baked* one,
    read-only — `web/static/demos/**` is frozen and nothing here writes to it.

Run: python3 -m unittest tests.test_client_library
"""

from __future__ import annotations

import inspect
import json
import os
import re
import unittest

try:
    import rdflib  # noqa: F401 — probe: the whole package needs it

    import vson
except ImportError:  # pragma: no cover — dependency probe
    vson = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GOOD_P = os.path.join(REPO, "examples", "gallery", "01_minimal.vson")
GOOD_X = os.path.join(REPO, "examples", "gallery-x", "01_minimal.x.vson")
GOOD_T = os.path.join(REPO, "examples", "throne_room.ttl")
BAD_T = os.path.join(REPO, "tests", "fixtures", "bad_no_viewer.ttl")
BAD_P = os.path.join(REPO, "tests", "fixtures", "bad_no_viewer.vson")
LIMITS_TS = os.path.join(REPO, "web", "src", "lib", "extract", "limits.ts")
META_TS = os.path.join(REPO, "web", "src", "lib", "prompts", "meta.ts")
BAKED = os.path.join(REPO, "web", "static", "demos", "envelopes", "forest.json")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def bad_penman() -> str:
    """The C5 fixture with its comment header removed.

    `extract_penman` slices from the first `(` to the last `)`, and that
    fixture's header prose contains parentheses. A model reply does not; the
    header is a property of the fixture, not of the notation. The result is
    what `extract_penman` returns for a reply carrying it, trailing newline and
    all — so a test can compare the two directly.
    """
    text = read(BAD_P)
    return text[text.index("(scene") :].strip()


def repaired_penman() -> str:
    """The same document with the `vso:viewer` C5 wants."""
    return bad_penman().replace(
        ":directional left_of", ":directional left_of\n               :viewer cam"
    )


@unittest.skipUnless(vson, "rdflib + pyshacl required")
class SurfaceTests(unittest.TestCase):
    """Every name `__all__` promises is importable, and is what it says."""

    def test_every_public_name_resolves(self) -> None:
        missing = [name for name in vson.__all__ if not hasattr(vson, name)]
        self.assertEqual(missing, [], "promised by __all__, not importable")

    def test_no_duplicates_in_all(self) -> None:
        self.assertEqual(
            len(vson.__all__), len(set(vson.__all__)), "__all__ has a repeat"
        )

    def test_the_callables_are_callable_and_the_types_are_types(self) -> None:
        functions = (
            "validate to_turtle from_x turtle_of load sniff caption fol diff canon "
            "canonical_hash denotes_same envelope_errors response_format tool_schema "
            "ollama_format validate_and_repair build_repair_prompt extract_penman "
            "extract_vson_x looks_like_penman"
        ).split()
        for name in functions:
            self.assertTrue(callable(getattr(vson, name)), name)
        types = (
            "Verdict Finding Envelope Source SceneGraph GraphNode GraphEdge Traits "
            "Conformance Violation Extraction ChatTurn RepairRound RepairResult "
            "DiffReport VsonError VsonSyntaxError VsonResourceError"
        ).split()
        for name in types:
            self.assertTrue(inspect.isclass(getattr(vson, name)), name)

    def test_the_constants_carry_the_types_they_claim(self) -> None:
        for name in ("SKILL_PROMPT", "SKILL_X_PROMPT", "REPAIR_PROMPT_TEMPLATE",
                     "REPAIR_X_PROMPT_TEMPLATE", "EXTRACT_USER", "EXTRACT_USER_X",
                     "DEFAULT_SHAPES", "LATEST_ENVELOPE_VERSION", "__version__"):
            value = getattr(vson, name)
            self.assertIsInstance(value, str, name)
            self.assertTrue(value, name + " is empty")
        self.assertIsInstance(vson.ENVELOPE_SCHEMA, dict)
        self.assertIsInstance(vson.ENVELOPE_VERSIONS, list)
        self.assertIsInstance(vson.PROMPT_VERSIONS, dict)
        self.assertIsInstance(vson.MAX_REPAIR_RETRIES, int)
        self.assertIsInstance(vson.SHACL_REPORT_SLICE_CHARS, int)

    def test_the_error_hierarchy_is_one_tree(self) -> None:
        self.assertTrue(issubclass(vson.VsonSyntaxError, vson.VsonError))
        self.assertTrue(issubclass(vson.VsonResourceError, vson.VsonError))

    def test_an_unknown_attribute_still_raises_attribute_error(self) -> None:
        # The module defines __getattr__ for the lazy DiffReport alias; a
        # __getattr__ that returned None for everything else would turn every
        # typo into a silent None.
        with self.assertRaises(AttributeError):
            getattr(vson, "no_such_name")

    def test_the_version_is_the_one_pyproject_declares(self) -> None:
        pyproject = read(os.path.join(REPO, "pyproject.toml"))
        match = re.search(
            r"^\[project\]$.*?^version\s*=\s*\"([^\"]+)\"",
            pyproject,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, "pyproject.toml has no [project] version")
        self.assertEqual(vson.__version__, match.group(1))

    def test_the_package_is_declared_in_the_distribution(self) -> None:
        # A facade nobody can install is a facade nobody can import. The
        # find-directive must name it, or `pip install .` ships tools/ alone.
        pyproject = read(os.path.join(REPO, "pyproject.toml"))
        block = pyproject.split("[tool.setuptools.packages.find]", 1)[1]
        include = re.search(r"^include\s*=\s*\[([^\]]*)\]", block, re.MULTILINE)
        self.assertIsNotNone(include, "no include= under packages.find")
        self.assertIn("vson*", include.group(1))


@unittest.skipUnless(vson, "rdflib + pyshacl required")
class VerdictTests(unittest.TestCase):
    """The verdict, on good and bad, from every input form."""

    def test_a_conformant_document_conforms_and_names_no_gate(self) -> None:
        for source in (GOOD_P, GOOD_X, GOOD_T):
            verdict = vson.validate(source)
            self.assertTrue(verdict.conforms, source)
            self.assertIsNone(verdict.gate, source)
            self.assertEqual(verdict.findings, [], source)
            self.assertEqual(verdict.source, source)

    def test_a_clean_run_still_produces_a_report(self) -> None:
        # docs/vson.md §5.16: a caller that cannot tell "nothing was wrong" from
        # "the tool never ran" has learned nothing from a green build.
        record = vson.validate(GOOD_P).as_record()
        self.assertEqual(record["report"], "vson-validate-records/1")
        self.assertTrue(record["conforms"])
        self.assertIsNone(record["gate"])
        self.assertEqual(record["findings"], [])

    def test_a_violation_names_its_gate_shape_and_focus_node(self) -> None:
        verdict = vson.validate(BAD_T)
        self.assertFalse(verdict.conforms)
        self.assertEqual(verdict.gate, "shacl")
        self.assertEqual(len(verdict.findings), 1, verdict.findings)
        found = verdict.findings[0]
        self.assertEqual(found.gate, "shacl")
        self.assertEqual(found.severity, "violation")
        self.assertEqual(found.rule, "vson/shacl/DirectionalNeedsViewerShape")
        self.assertEqual(
            found.shape, "https://w3id.org/vson/v1/shapes#DirectionalNeedsViewerShape"
        )
        self.assertEqual(
            found.result_path, "https://w3id.org/vson/v1/ontology#viewer"
        )
        self.assertIn("vso:viewer", found.message)
        self.assertEqual(verdict.messages, [found.message])

    def test_the_records_survive_a_round_trip(self) -> None:
        found = vson.validate(BAD_T).findings[0]
        self.assertEqual(vson.Finding.from_record(found.as_record()), found)

    def test_the_report_text_is_a_function_of_the_findings_alone(self) -> None:
        # It goes into a repair prompt; two runs over one document must produce
        # the same prompt or nothing downstream is reproducible.
        first = vson.validate(BAD_T).report_text()
        self.assertEqual(first, vson.validate(BAD_T).report_text())
        self.assertIn("DirectionalNeedsViewerShape", first)

    def test_the_same_document_as_text_gets_the_same_verdict(self) -> None:
        from_path = vson.validate(BAD_P)
        from_text = vson.validate(read(BAD_P))
        self.assertEqual(from_path.conforms, from_text.conforms)
        self.assertEqual(from_path.gate, from_text.gate)
        self.assertEqual(
            [f.as_record() for f in from_path.findings],
            [f.as_record() for f in from_text.findings],
        )
        self.assertEqual(from_text.source, "<text>")

    def test_a_relaxed_run_validates_against_the_relaxed_file(self) -> None:
        # §5.16.6: a verifier asked for `relaxed` MUST validate against that
        # file or refuse — never validate strict and label the result relaxed.
        relaxed = os.path.join(REPO, "shapes", "vson-shapes-relaxed.ttl")
        self.assertTrue(os.path.isfile(relaxed))
        self.assertTrue(vson.validate(GOOD_P, shapes=relaxed).conforms)

    def test_the_syntax_sniffer_follows_5_16_5_plus_the_tilde(self) -> None:
        self.assertEqual(vson.sniff("(scene / Composition)"), "p")
        self.assertEqual(vson.sniff("# a comment\n\n  (scene / X)"), "p")
        self.assertEqual(vson.sniff("~scene\n  a /PhysicalObject"), "x")
        self.assertEqual(vson.sniff("@prefix vso: <x> ."), "t")
        self.assertEqual(vson.sniff(""), "t", "empty input is VSON-T, not an error")

    def test_an_unparseable_document_raises_rather_than_failing_a_gate(self) -> None:
        with self.assertRaises(vson.VsonSyntaxError):
            vson.to_turtle("(scene / Composition")
        with self.assertRaises(vson.VsonSyntaxError):
            vson.from_x("~scene\n  ((((")

    def test_the_renderers_and_the_metric_reach_the_same_graph(self) -> None:
        self.assertTrue(vson.caption(GOOD_P))
        self.assertIn("PhysicalObject(apple).", vson.fol(GOOD_P))
        self.assertTrue(vson.diff(GOOD_P, GOOD_P).identical)
        self.assertTrue(vson.denotes_same(GOOD_P, GOOD_X))
        self.assertEqual(
            vson.canonical_hash(GOOD_P), vson.canonical_hash(GOOD_X)
        )


@unittest.skipUnless(vson, "rdflib + pyshacl required")
class RepairLoopTests(unittest.TestCase):
    """0-, 1- and 2-round convergence, and the run that never converges."""

    def _scripted(self, replies):
        """A `chat_fn` that returns `replies[turn.round]` and records its turns."""
        seen = []

        def chat_fn(turn):
            seen.append(turn)
            return replies[turn.round]

        return chat_fn, seen

    def test_round_zero_convergence_makes_no_repair_call(self) -> None:
        chat_fn, seen = self._scripted([repaired_penman()])
        result = vson.validate_and_repair(chat_fn, image_or_doc=b"jpeg-bytes")
        self.assertTrue(result.conforms)
        self.assertEqual(result.shacl_retries, 0)
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(result.rounds), 1)
        self.assertIsNone(seen[0].reason)
        self.assertEqual(seen[0].attachment, b"jpeg-bytes")

    def test_one_repair_round_populates_shacl_retries_with_a_one(self) -> None:
        chat_fn, seen = self._scripted([bad_penman(), repaired_penman()])
        result = vson.validate_and_repair(chat_fn, image_or_doc="img")
        self.assertTrue(result.conforms)
        self.assertEqual(result.shacl_retries, 1)
        self.assertEqual([r.index for r in result.rounds], [0, 1])
        self.assertFalse(result.rounds[0].conforms)
        self.assertEqual(result.rounds[0].verdict.gate, "shacl")

    def test_two_repair_rounds_are_allowed_and_the_image_is_sent_once(self) -> None:
        chat_fn, seen = self._scripted(
            [bad_penman(), bad_penman(), repaired_penman()]
        )
        result = vson.validate_and_repair(chat_fn, image_or_doc="img")
        self.assertTrue(result.conforms)
        self.assertEqual(result.shacl_retries, 2)
        self.assertEqual([t.round for t in seen], [0, 1, 2])
        # The studio does not re-send the image on a repair round; nor does this.
        self.assertEqual([t.attachment for t in seen], ["img", None, None])

    def test_a_repair_round_is_told_why_it_exists(self) -> None:
        chat_fn, seen = self._scripted([bad_penman(), repaired_penman()])
        vson.validate_and_repair(chat_fn, image_or_doc="img")
        repair = seen[1]
        self.assertEqual(repair.round, 1)
        self.assertIn("vso:viewer", repair.reason)
        self.assertEqual(repair.document, bad_penman())
        # The reason is inside the prompt, and the prompt is the shipped
        # template with both placeholders filled.
        self.assertIn("vso:viewer", repair.user)
        self.assertIn(bad_penman(), repair.user)
        self.assertNotIn("{{FAILED_DOCUMENT}}", repair.user)
        self.assertNotIn("{{SHACL_REPORT}}", repair.user)

    def test_a_run_that_never_converges_stops_at_the_bound(self) -> None:
        chat_fn, seen = self._scripted([bad_penman()] * 8)
        result = vson.validate_and_repair(chat_fn, image_or_doc="img")
        self.assertFalse(result.conforms)
        self.assertEqual(result.shacl_retries, vson.MAX_REPAIR_RETRIES)
        self.assertEqual(len(seen), vson.MAX_REPAIR_RETRIES + 1)
        self.assertEqual(len(result.rounds), vson.MAX_REPAIR_RETRIES + 1)
        # Not converging is a result, not an exception.
        self.assertIsNotNone(result.verdict)
        self.assertFalse(result.verdict.conforms)

    def test_max_retries_zero_runs_exactly_one_model_call(self) -> None:
        chat_fn, seen = self._scripted([bad_penman()] * 4)
        result = vson.validate_and_repair(chat_fn, image_or_doc="img", max_retries=0)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result.shacl_retries, 0)
        self.assertFalse(result.conforms)

    def test_a_document_to_start_from_costs_no_model_call(self) -> None:
        def explode(turn):  # pragma: no cover — the assertion is that it never runs
            raise AssertionError("chat_fn must not be called")

        result = vson.validate_and_repair(explode, document=read(GOOD_P))
        self.assertTrue(result.conforms)
        self.assertEqual(result.shacl_retries, 0)
        self.assertEqual(len(result.rounds), 1)

    def test_a_transpile_failure_is_fed_back_as_the_reason(self) -> None:
        # Extractable — it opens and closes — but not a document the Penman
        # grammar accepts, so gate 1 never runs and the parse error is the
        # thing the model is shown.
        chat_fn, seen = self._scripted(["(scene / )", repaired_penman()])
        result = vson.validate_and_repair(chat_fn, image_or_doc="img")
        self.assertTrue(result.conforms)
        self.assertIsNotNone(result.rounds[0].error)
        self.assertIn("VSON-P parse error", seen[1].reason)
        self.assertIsNone(result.rounds[0].verdict, "nothing to validate")

    def test_a_reply_with_no_document_keeps_the_previous_one(self) -> None:
        # A spent round is a spent round; the next one still sees a real
        # document, and the same failure repeats visibly instead of becoming an
        # empty one.
        chat_fn, seen = self._scripted(
            [bad_penman(), "I'm sorry, Dave.", "I'm afraid I can't do that."]
        )
        result = vson.validate_and_repair(chat_fn, image_or_doc="img")
        self.assertEqual(result.document, bad_penman())
        self.assertEqual(result.shacl_retries, 2)
        self.assertFalse(result.conforms)

    def test_an_empty_first_reply_raises(self) -> None:
        with self.assertRaises(vson.VsonSyntaxError):
            vson.validate_and_repair(lambda turn: "no document here", image_or_doc="i")

    def test_neither_an_image_nor_a_document_is_a_usage_error(self) -> None:
        with self.assertRaises(ValueError):
            vson.validate_and_repair(lambda turn: "")
        with self.assertRaises(ValueError):
            vson.validate_and_repair(lambda t: "", image_or_doc="i", notation="q")
        with self.assertRaises(ValueError):
            vson.validate_and_repair(lambda t: "", image_or_doc="i", max_retries=-1)

    def test_an_exception_from_chat_fn_propagates(self) -> None:
        class Boom(Exception):
            pass

        def chat_fn(turn):
            raise Boom("network down")

        with self.assertRaises(Boom):
            vson.validate_and_repair(chat_fn, image_or_doc="img")

    def test_the_vson_x_flow_repairs_penman_drift(self) -> None:
        # Round 0 answers a VSON-X request in Penman. That is not an empty
        # reply, it is a drifted one, and saying so is what re-anchors `~`.
        chat_fn, seen = self._scripted([bad_penman(), read(GOOD_X)])
        result = vson.validate_and_repair(chat_fn, image_or_doc="img", notation="x")
        self.assertTrue(result.conforms)
        self.assertEqual(result.shacl_retries, 1)
        self.assertIn("DRIFT", result.rounds[0].error)
        self.assertEqual(seen[0].system, vson.SKILL_X_PROMPT)

    def test_the_system_prompt_defaults_to_the_skill_for_the_notation(self) -> None:
        chat_fn, seen = self._scripted([repaired_penman()])
        vson.validate_and_repair(chat_fn, image_or_doc="img")
        self.assertEqual(seen[0].system, vson.SKILL_PROMPT)
        self.assertEqual(seen[0].user, vson.EXTRACT_USER)

    def test_a_caller_supplied_system_prompt_claims_no_skill_version(self) -> None:
        chat_fn, _seen = self._scripted([repaired_penman()])
        result = vson.validate_and_repair(
            chat_fn, image_or_doc="img", system_prompt="you are a scene extractor"
        )
        self.assertIsNone(result.prompt_version)
        self.assertIsNone(result.to_envelope("s").extraction.prompt_version)

    def test_the_run_becomes_a_schema_valid_envelope(self) -> None:
        chat_fn, _seen = self._scripted([bad_penman(), repaired_penman()])
        result = vson.validate_and_repair(chat_fn, image_or_doc="img")
        envelope = result.to_envelope(
            "throne_room_01",
            source=vson.Source(kind="image", sha256="0" * 64),
        )
        self.assertEqual(envelope.errors(), [])
        self.assertEqual(envelope.version, vson.LATEST_ENVELOPE_VERSION)
        self.assertEqual(envelope.extraction.shacl_retries, 1)
        self.assertEqual(envelope.extraction.prompt_version, "skill@1.0.0")
        self.assertEqual(envelope.conformance.profile, "strict")
        self.assertTrue(envelope.conformance.conforms)
        self.assertTrue(envelope.vson_t)
        self.assertIsNone(envelope.vson_x)

    def test_a_failed_run_records_its_violations_in_the_envelope(self) -> None:
        chat_fn, _seen = self._scripted([bad_penman()] * 4)
        envelope = vson.validate_and_repair(chat_fn, image_or_doc="i").to_envelope("s")
        self.assertEqual(envelope.errors(), [])
        self.assertFalse(envelope.conformance.conforms)
        self.assertEqual(envelope.extraction.shacl_retries, 2)
        violation = envelope.conformance.violations[0]
        self.assertIn("DirectionalNeedsViewerShape", violation.shape)
        # The envelope's severity enum is capitalized; the record's is not.
        self.assertEqual(violation.severity, "Violation")

    def test_the_vson_x_envelope_puts_the_document_in_vson_x(self) -> None:
        chat_fn, _seen = self._scripted([read(GOOD_X)])
        envelope = vson.validate_and_repair(
            chat_fn, image_or_doc="i", notation="x"
        ).to_envelope("x_scene")
        self.assertEqual(envelope.errors(), [])
        self.assertEqual(envelope.vson_p, "", "§6.1: VSON-X mode empties vson_p")
        self.assertTrue(envelope.vson_x.startswith("~"))


@unittest.skipUnless(vson, "rdflib + pyshacl required")
class ExtractorTests(unittest.TestCase):
    """The tolerant reply readers the loop runs before anything else."""

    def test_a_fenced_reply_is_unwrapped(self) -> None:
        self.assertEqual(
            vson.extract_penman("Sure!\n```penman\n(a / B)\n```\nDone."), "(a / B)"
        )

    def test_prose_around_a_bare_tree_is_trimmed(self) -> None:
        self.assertEqual(vson.extract_penman("Here it is: (a / B) — enjoy"), "(a / B)")

    def test_a_reply_with_no_tree_is_none(self) -> None:
        self.assertIsNone(vson.extract_penman("I cannot help with that."))
        self.assertIsNone(vson.extract_penman(")unbalanced("))

    def test_a_comment_headed_vson_file_extracts_its_tree(self) -> None:
        # A chat_fn may hand back a complete .vson file, header comment and
        # all. Parentheses inside `#` comments must not anchor the slice —
        # validate() accepts the file, so the loop's extractor must too.
        with open(os.path.join(REPO, "examples", "throne_room.vson")) as fh:
            text = fh.read()
        doc = vson.extract_penman(text)
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertTrue(doc.startswith("(scene"))
        self.assertTrue(doc.endswith(")"))

    def test_a_trailing_comment_paren_does_not_anchor_the_end(self) -> None:
        self.assertEqual(
            vson.extract_penman("(a / B)\n# end (of file)\n"),
            "(a / B)",
        )

    def test_vson_x_extraction_is_line_anchored_and_keeps_the_newline(self) -> None:
        self.assertEqual(
            vson.extract_vson_x("Sure:\n~scene\n  a /PhysicalObject\n"),
            "~scene\n  a /PhysicalObject\n",
        )
        self.assertIsNone(vson.extract_vson_x("a ~ mid-line tilde"))

    def test_penman_drift_is_detectable(self) -> None:
        self.assertTrue(vson.looks_like_penman("  (scene / Composition)"))
        self.assertFalse(vson.looks_like_penman("~scene"))

    def test_the_repair_prompt_slices_an_unbounded_report(self) -> None:
        limit = vson.SHACL_REPORT_SLICE_CHARS
        prompt = vson.build_repair_prompt("(a / B)", "x" * 99999)
        self.assertIn("x" * limit, prompt)
        self.assertNotIn("x" * (limit + 1), prompt)

    def test_both_repair_templates_are_filled_in_full(self) -> None:
        for notation in ("p", "x"):
            prompt = vson.build_repair_prompt("DOC", "WHY", notation)
            self.assertIn("DOC", prompt)
            self.assertIn("WHY", prompt)
            self.assertNotIn("{{FAILED_DOCUMENT}}", prompt)
            self.assertNotIn("{{SHACL_REPORT}}", prompt)
        self.assertNotEqual(
            vson.build_repair_prompt("DOC", "WHY", "p"),
            vson.build_repair_prompt("DOC", "WHY", "x"),
        )
        with self.assertRaises(ValueError):
            vson.build_repair_prompt("DOC", "WHY", "t")


@unittest.skipUnless(vson, "rdflib + pyshacl required")
class BoundsDriftTests(unittest.TestCase):
    """The Python copies of the studio's constants, checked against the studio.

    TypeScript cannot import Python and Python cannot import TypeScript, so
    these values exist twice. The comment in `limits.ts` explains why the
    numbers matter — `shacl_retries` in live envelopes must stay on the same
    0-2 ceiling as the baked v1.2 demo corpus, or the field stops meaning the
    same thing across the envelopes this project has shipped. That argument
    covers this package's envelopes too, which is why the copy is checked
    rather than merely commented.
    """

    def _number(self, source: str, name: str) -> int:
        match = re.search(
            r"export const {}(?::\s*\w+)?\s*=\s*([0-9]+);".format(name), source
        )
        self.assertIsNotNone(match, "{} not found in limits.ts".format(name))
        return int(match.group(1))

    def _string(self, source: str, name: str) -> str:
        match = re.search(
            r"export const {}(?::\s*\w+)?\s*=\s*\n?\s*'((?:[^'\\]|\\.)*)';".format(name),
            source,
        )
        self.assertIsNotNone(match, "{} not found in meta.ts".format(name))
        return match.group(1).replace("\\'", "'").replace("\\`", "`")

    def test_the_retry_ceiling_is_the_studios(self) -> None:
        limits = read(LIMITS_TS)
        self.assertEqual(
            vson.MAX_REPAIR_RETRIES, self._number(limits, "MAX_REPAIR_RETRIES")
        )

    def test_the_report_slice_is_the_studios(self) -> None:
        limits = read(LIMITS_TS)
        self.assertEqual(
            vson.SHACL_REPORT_SLICE_CHARS,
            self._number(limits, "SHACL_REPORT_SLICE_CHARS"),
        )

    def test_the_extraction_instructions_are_the_studios(self) -> None:
        meta = read(META_TS)
        self.assertEqual(vson.EXTRACT_USER, self._string(meta, "BARE_EXTRACT_USER"))
        self.assertEqual(
            vson.EXTRACT_USER_X, self._string(meta, "BARE_EXTRACT_USER_X")
        )

    def test_the_prompt_versions_are_the_studios(self) -> None:
        meta = read(META_TS)
        for notation, variant in (("p", "skill"), ("x", "skill-x")):
            self.assertIn(
                "return '{}';".format(vson.PROMPT_VERSIONS[notation]),
                meta,
                "promptVersionFor({!r}) disagrees".format(variant),
            )

    def test_the_prompt_bodies_are_the_shipped_files(self) -> None:
        # Not a copy — a read. This asserts the read still lands on the file
        # the studio's ?raw import names, so a rename breaks both at once.
        self.assertEqual(
            vson.SKILL_PROMPT,
            read(os.path.join(REPO, "skills", "vson-extractor", "SKILL.md")),
        )
        self.assertEqual(
            vson.SKILL_X_PROMPT,
            read(os.path.join(REPO, "skills", "vson-extractor-x", "SKILL.md")),
        )
        self.assertIn("{{FAILED_DOCUMENT}}", vson.REPAIR_PROMPT_TEMPLATE)
        self.assertIn("{{SHACL_REPORT}}", vson.REPAIR_X_PROMPT_TEMPLATE)


@unittest.skipUnless(vson, "rdflib + pyshacl required")
class EnvelopeTypeTests(unittest.TestCase):
    """`Envelope` against the schema it was written from, and a real envelope."""

    def test_the_schema_is_the_shipped_file(self) -> None:
        with open(
            os.path.join(REPO, "tools", "schema", "vson-output.schema.json"),
            encoding="utf-8",
        ) as handle:
            self.assertEqual(vson.ENVELOPE_SCHEMA, json.load(handle))

    def test_the_versions_come_from_the_schemas_own_enum(self) -> None:
        self.assertEqual(
            vson.ENVELOPE_VERSIONS,
            vson.ENVELOPE_SCHEMA["properties"]["version"]["enum"],
        )
        self.assertEqual(vson.LATEST_ENVELOPE_VERSION, vson.ENVELOPE_VERSIONS[-1])

    def test_a_baked_envelope_round_trips(self) -> None:
        # Read-only. web/static/demos/** is frozen: these bytes are compared,
        # never rewritten.
        original = json.loads(read(BAKED))
        envelope = vson.Envelope.from_json(original)
        rebuilt = envelope.to_json()
        self.assertEqual(rebuilt, original)
        self.assertEqual(
            list(rebuilt), list(original), "top-level key order is the schema's"
        )
        self.assertEqual(vson.envelope_errors(rebuilt), [])

    def test_every_baked_envelope_round_trips(self) -> None:
        directory = os.path.dirname(BAKED)
        seen = 0
        for root, _dirs, files in os.walk(directory):
            for name in sorted(files):
                if not name.endswith(".json"):
                    continue
                document = json.loads(read(os.path.join(root, name)))
                if not isinstance(document, dict) or "scene_id" not in document:
                    continue  # index.json — a sha256 -> filename map
                seen += 1
                rebuilt = vson.Envelope.from_json(document).to_json()
                self.assertEqual(rebuilt, document, name)
        self.assertGreater(seen, 0, "no baked envelopes found to round-trip")

    def test_the_typed_fields_carry_what_the_json_said(self) -> None:
        envelope = vson.Envelope.from_json(json.loads(read(BAKED)))
        self.assertIsInstance(envelope.conformance, vson.Conformance)
        self.assertIsInstance(envelope.source, vson.Source)
        self.assertIsInstance(envelope.graph, vson.SceneGraph)
        self.assertIsInstance(envelope.graph.nodes[0], vson.GraphNode)
        self.assertIsInstance(envelope.graph.edges[0], vson.GraphEdge)
        self.assertIsInstance(envelope.extraction, vson.Extraction)
        self.assertIn(envelope.version, vson.ENVELOPE_VERSIONS)
        # The two keyword escapes.
        classed = [n for n in envelope.graph.nodes if n.class_]
        self.assertTrue(classed, "no node carries a class")
        self.assertTrue(envelope.graph.edges[0].from_)
        self.assertTrue(envelope.graph.edges[0].to)

    def test_an_absent_field_and_an_empty_one_stay_different(self) -> None:
        # §6.1's if/then rule turns on exactly this: vson_x absent is Penman
        # mode, vson_x empty is a v1.1+ envelope that satisfies neither branch.
        base = {
            "scene_id": "s",
            "version": "1.3",
            "vson_p": "(a / B)",
            "vson_t": ":a a vso:Composition .",
            "conformance": {"conforms": True},
        }
        self.assertNotIn("vson_x", vson.Envelope.from_json(base).to_json())
        with_empty = dict(base, vson_x="")
        self.assertEqual(vson.Envelope.from_json(with_empty).to_json(), with_empty)

    def test_the_schema_is_what_says_an_envelope_is_valid(self) -> None:
        broken = {
            "scene_id": "s",
            "version": "9.9",
            "vson_p": "(a / B)",
            "vson_t": ":a a vso:Composition .",
            "conformance": {"conforms": True},
        }
        errors = vson.envelope_errors(broken)
        self.assertTrue(errors)
        self.assertEqual(errors, sorted(errors), "errors must be ordered")
        self.assertTrue(any("9.9" in message for message in errors))

    def test_the_structured_output_bindings_nest_the_schema_where_they_say(self) -> None:
        # The wrapper shape is the only thing this repository owns here; whether
        # a vendor accepts a given schema is a fact about that vendor's API on
        # the day you call it, and no gate here can establish it.
        openai = vson.response_format()
        self.assertEqual(openai["type"], "json_schema")
        self.assertIs(openai["json_schema"]["schema"], vson.ENVELOPE_SCHEMA)
        self.assertFalse(openai["json_schema"]["strict"])
        anthropic = vson.tool_schema()
        self.assertIs(anthropic["input_schema"], vson.ENVELOPE_SCHEMA)
        self.assertTrue(anthropic["name"] and anthropic["description"])
        self.assertIs(vson.ollama_format(), vson.ENVELOPE_SCHEMA)
        other = {"type": "object"}
        self.assertIs(vson.response_format(other)["json_schema"]["schema"], other)
        self.assertIs(vson.tool_schema(other)["input_schema"], other)
        self.assertIs(vson.ollama_format(other), other)


if __name__ == "__main__":
    unittest.main()
