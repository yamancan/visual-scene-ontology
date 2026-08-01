"""Offline tests for the two copy-drift gates.

`scripts/check_spec_fragments.py` and `scripts/check_registry_drift.py` both
exist for the same reason: this repository states the same thing in several
places, and §2 of `docs/vson.md` ranks those places against each other, so a
copy that disagrees is not untidy — it is the specification asserting something
false. Both gates run in `make check`.

A gate that passes proves nothing on its own; it might be a working check or a
check that cannot fail. So the two things worth knowing are established here:

  * each comparator goes red when fed the drift shape it exists to catch —
    an enum quoted one value short, a registry copy missing a member, a
    spelled count left behind by a new member;
  * each gate's own table still points at something real. A JSON Pointer into a
    schema that no longer has that node, a rule for a heading that has been
    reworded away, a shape name with no `sh:in` — every one of those would make
    a gate go quiet rather than red.

Run: python3 -m unittest tests.test_drift_gates
"""

import contextlib
import importlib.util
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")


def _script(name):
    """Import a module from scripts/ by path — same loader as
    tests/test_live_claims.py, including the sys.modules registration that
    dataclass field resolution needs on Python 3.9."""
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(SCRIPTS, name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


try:
    import rdflib  # noqa: F401 — probe; both gates need it

    fragments = _script("check_spec_fragments")
    registry = _script("check_registry_drift")
except ImportError:  # pragma: no cover — dependency probe for the skip guards
    fragments = None
    registry = None


def _quiet(callable_, *args):
    """Run a gate entry point without letting its report into the test output."""
    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stdout(devnull):
            return callable_(*args)


@unittest.skipUnless(fragments, "rdflib + jsonschema required")
class FragmentComparatorGoesRed(unittest.TestCase):
    """The subset rule must contradict a fragment that contradicts the schema."""

    ARTIFACT = {
        "type": "string",
        "enum": ["1.0", "1.1"],
        "description": "the document abbreviates this away",
    }

    def test_exact_quote_passes(self):
        self.assertEqual(
            [], fragments.subset_problems({"enum": ["1.0", "1.1"]}, self.ARTIFACT, {})
        )

    def test_abbreviated_quote_passes(self):
        # Dropping `description` is what "reproduced inline" means; it must not
        # be a failure, or the gate would force the document to carry the whole
        # schema and nobody would keep it.
        self.assertEqual(
            [], fragments.subset_problems({"type": "string"}, self.ARTIFACT, {})
        )

    def test_enum_quoted_short_fails(self):
        # The acceptance case: exactly the shape of the shipped bug — §6.1
        # quoting ["1.0","1.0.5","1.1"] against a schema that admitted "1.2".
        problems = fragments.subset_problems({"enum": ["1.0"]}, self.ARTIFACT, {})
        self.assertTrue(problems)
        self.assertIn("1.1", problems[0])

    def test_enum_reordered_fails(self):
        self.assertTrue(
            fragments.subset_problems({"enum": ["1.1", "1.0"]}, self.ARTIFACT, {})
        )

    def test_key_the_artifact_does_not_carry_fails(self):
        # The second shipped bug: §6.1 keyed its conditional on `const: "1.1"`
        # after the schema had widened that clause to an `enum`.
        problems = fragments.subset_problems({"const": "1.1"}, self.ARTIFACT, {})
        self.assertTrue(problems)
        self.assertIn("absent from the artifact", problems[0])

    def test_required_may_be_a_subset_but_not_invented(self):
        artifact = {"required": ["a", "b"]}
        self.assertEqual([], fragments.subset_problems({"required": ["a"]}, artifact, {}))
        self.assertTrue(fragments.subset_problems({"required": ["c"]}, artifact, {}))

    def test_local_ref_is_followed(self):
        root = {"$defs": {"X": {"type": "object", "required": ["m"]}}}
        self.assertEqual(
            [],
            fragments.subset_problems(
                {"required": ["m"]}, {"$ref": "#/$defs/X"}, root
            ),
        )

    def test_shacl_in_comparator_is_order_sensitive(self):
        self.assertEqual([], fragments.enum_problems(["DC", "EC"], ["DC", "EC"], "x"))
        self.assertTrue(fragments.enum_problems(["EC", "DC"], ["DC", "EC"], "x"))

    def test_selftest_mode_is_green(self):
        self.assertEqual(0, _quiet(fragments.main, ["--selftest"]))


@unittest.skipUnless(fragments, "rdflib + jsonschema required")
class FragmentTableStillPointsAtSomething(unittest.TestCase):
    """Every rule must name a fragment that exists and an artifact node that does."""

    @classmethod
    def setUpClass(cls):
        cls.found = fragments.extract(fragments.read(fragments.SPEC))
        cls.keys = {f.key for f in cls.found}

    def test_the_span_is_not_empty(self):
        # A reworded §5 or §7 heading would empty the span and turn the gate
        # green by checking nothing.
        self.assertGreater(len(self.found), 10)

    def test_every_fragment_is_classified(self):
        unclassified = sorted(
            "%s (fragment %d)" % (f.heading, f.ordinal)
            for f in self.found
            if f.key not in fragments.RULES
        )
        self.assertEqual([], unclassified)

    def test_no_rule_points_at_a_fragment_that_is_gone(self):
        dead = sorted("%s (fragment %d)" % k for k in fragments.RULES if k not in self.keys)
        self.assertEqual([], dead)

    def test_every_schema_pointer_resolves(self):
        for key, rule in sorted(fragments.RULES.items()):
            if rule["kind"] != "schema":
                continue
            with self.subTest(fragment=key[0]):
                root = fragments.load_schema(rule["file"])
                fragments.resolve_pointer(root, rule["pointer"])  # raises if gone

    def test_every_named_shape_carries_one_sh_in(self):
        graph = rdflib.Graph()
        graph.parse(os.path.join(REPO, fragments.SHAPES), format="turtle")
        for key, rule in sorted(fragments.RULES.items()):
            if rule["kind"] != "shacl-in":
                continue
            for pointer, shape in sorted(rule["paths"].items()):
                with self.subTest(shape=shape):
                    self.assertTrue(fragments.shape_in_list(graph, shape))

    def test_the_table_still_checks_something(self):
        # Guards the cheapest way to make this gate meaningless: reclassifying
        # awkward fragments as illustrative until nothing is compared.
        kinds = [rule["kind"] for rule in fragments.RULES.values()]
        for kind in ("schema", "shacl-in", "instance"):
            self.assertIn(kind, kinds)

    def test_the_typescript_mirror_matches_the_schema(self):
        # The one restatement outside the document. Asserted here as well as in
        # the gate so a web-side rename shows up in `make check`'s test run.
        source = fragments.read(fragments.TYPES_TS)
        schema = fragments.load_schema(fragments.OUTPUT_SCHEMA)
        self.assertEqual(
            schema["properties"]["version"]["enum"],
            fragments.union_members(source),
        )

    def test_the_version_enum_admits_the_current_spec_version(self):
        # §6.1's enum is what a producer writes into the wire. The acceptance
        # case for the v1.3 conflict resolution: a 1.3 envelope must validate.
        import jsonschema

        schema = fragments.load_schema(fragments.OUTPUT_SCHEMA)
        envelope = {
            "scene_id": "gate_13",
            "version": "1.3",
            "vson_p": "(s / Composition :depicts (a / PhysicalObject :class Apple))",
            "vson_t": "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n",
            "conformance": {"conforms": True},
        }
        jsonschema.Draft202012Validator(schema).validate(envelope)

        # …and the conditional must still bite at 1.3: both surfaces empty is
        # the case the allOf clause exists to reject. If "1.3" were added to the
        # enum and not to the clause, this would silently pass.
        envelope["vson_p"] = ""
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(envelope)


@unittest.skipUnless(registry, "rdflib required")
class RegistryComparatorGoesRed(unittest.TestCase):
    """The registry comparator must contradict a copy that has drifted."""

    SOURCE = ["Alpha", "Beta", "Gamma"]

    def test_same_membership_in_any_order_passes(self):
        self.assertEqual(
            [], registry.copy_problems(self.SOURCE, ["Gamma", "Alpha", "Beta"], "x")
        )

    def test_missing_member_fails(self):
        # The measured drift: vson-x-semantics §3.2.1 and the VSON-X SKILL.md
        # both carried twenty names against the ontology's twenty-one.
        problems = registry.copy_problems(self.SOURCE, ["Alpha", "Beta"], "x")
        self.assertTrue(problems)
        self.assertIn("Gamma", problems[0])

    def test_invented_member_fails(self):
        self.assertTrue(
            registry.copy_problems(self.SOURCE, self.SOURCE + ["Delta"], "x")
        )

    def test_duplicated_member_fails(self):
        self.assertTrue(
            registry.copy_problems(self.SOURCE, self.SOURCE + ["Beta"], "x")
        )

    def test_spelled_count_must_track_the_registry(self):
        self.assertEqual([], registry.count_word_problems("the twenty-one axes", 21, "x"))
        self.assertTrue(registry.count_word_problems("the twenty axes", 21, "x"))
        self.assertTrue(registry.count_word_problems("no number here", 21, "x"))

    def test_hyphenated_word_boundary_holds(self):
        # A plain \btwenty\b matches inside "twenty-one", which would let a
        # stale "twenty" hide behind the correct word.
        self.assertEqual([], registry.count_word_problems("twenty-one axes", 21, "x"))
        self.assertTrue(registry.count_word_problems("twenty-one and twenty", 21, "x"))

    def test_selftest_mode_is_green(self):
        self.assertEqual(0, _quiet(registry.main, ["--selftest"]))


@unittest.skipUnless(registry, "rdflib required")
class RegistryGateStillReadsEveryCopy(unittest.TestCase):
    """Each of the five copies must still be where the gate looks for it."""

    @classmethod
    def setUpClass(cls):
        cls.graph = rdflib.Graph()
        cls.graph.parse(os.path.join(REPO, registry.ONTOLOGY), format="turtle")
        cls.source = registry.ontology_individuals(cls.graph)

    def test_the_source_parses_as_a_real_registry(self):
        self.assertGreater(len(self.source), 8)

    def test_every_copy_is_found(self):
        spec = registry.read(registry.SPEC)
        copies = {
            "owl:AllDifferent": registry.ontology_all_different(self.graph),
            "§5.5.1 table": registry.md_table_names(
                registry.section(spec, registry.SPEC_SECTION)
            ),
            "§3.2.1 list": registry.md_inline_names(
                registry.section(registry.read(registry.X_SEMANTICS), registry.X_SECTION)
            ),
            "SKILL.md line": registry.md_inline_names(
                registry.marked_line(
                    registry.read(registry.SKILL), registry.SKILL_MARKER
                )
            ),
        }
        for where, names in sorted(copies.items()):
            with self.subTest(copy=where):
                self.assertTrue(names, "%s: the gate found no list" % where)

    def test_the_live_gate_is_green(self):
        # The end-to-end assertion. Reported quietly: a passing suite prints its
        # own summary and nothing else.
        self.assertEqual(0, _quiet(registry.check))

    def test_the_fragment_gate_is_green(self):
        self.assertEqual(0, _quiet(fragments.check))

    def test_the_ontology_is_still_the_only_place_a_member_is_declared(self):
        # The single-source claim, stated as data: every name in every copy is
        # a term ontology/vso.ttl declares. json.dumps keeps the failure message
        # readable when a copy carries something unexpected.
        spec = registry.read(registry.SPEC)
        table = registry.md_table_names(registry.section(spec, registry.SPEC_SECTION))
        self.assertEqual(
            [], sorted(set(table) - set(self.source)), json.dumps(sorted(table))
        )


if __name__ == "__main__":
    unittest.main()
