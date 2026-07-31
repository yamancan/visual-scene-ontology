"""Gate for the published JSON-LD context (`ontology/context.jsonld`).

The context is the one artefact in this repository that is *only* names. It
carries no shapes and no axioms, so nothing else in the gate matrix notices when
it goes wrong — a mistyped prefix or a term pointing at an IRI the ontology never
declares still parses as JSON, still loads in a JSON-LD processor, and silently
produces a graph whose subjects and predicates no VSON shape can select. SHACL
targets by IRI, so the failure mode is a *vacuous pass*, not an error.

Three things are therefore checked here:

  (a) Every term in the context resolves to a subject that actually exists in
      `ontology/vso.ttl`. A term naming an undeclared property fails.
  (b) The prefix bindings and `@vocab` equal the namespaces in
      `cli/src/penman/routing-tables.json` — the single site where the project
      mints its namespaces, and the file both emitters read. If a future rename
      moves the routing table and forgets this file, the two disagree here.
      Any other IRI the document references under the project root (the SHACL
      shapes, for instance) must sit under the same versioned root.
  (c) The term set equals the reference-property keys of
      `tools/schema/vson-jsonld.schema.json`, and is not empty — the
      anti-vacuity floor, so (a) cannot pass by having nothing to check.

Run: python3 -m unittest tests.test_jsonld_context

The resolution test is skipped automatically if rdflib is not installed; the
name-level tests need nothing but the standard library.
"""

from __future__ import annotations

import json
import os
import re
import unittest

try:
    import rdflib
except ImportError:  # pragma: no cover — dependency probe for the skip guard
    rdflib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONTEXT_FILE = os.path.join(ROOT, "ontology", "context.jsonld")
ROUTING_TABLES = os.path.join(
    ROOT, "cli", "src", "penman", "routing-tables.json"
)
JSONLD_SCHEMA = os.path.join(
    ROOT, "tools", "schema", "vson-jsonld.schema.json"
)
VSO_TTL = os.path.join(ROOT, "ontology", "vso.ttl")

# Prefixes the context is expected to bind, each read from the routing table
# under the same key. `xsd` is here because a JSON-LD author writing a typed
# literal needs it and the routing table already pins the W3C IRI.
EXPECTED_PREFIXES = ("vso", "rcc", "allen", "xsd")

# Every IRI the context mints must sit under the project's versioned root; this
# finds them all, including the ones written in prose inside "_doc".
PROJECT_IRI = re.compile(r"https://w3id\.org/vson/[^\s\"'<>)]*")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _terms(context: dict) -> dict:
    """The term definitions: context entries that are not keywords/prefixes."""
    return {
        key: value
        for key, value in context.items()
        if not key.startswith("@") and isinstance(value, dict)
    }


class ContextNamespaceTests(unittest.TestCase):
    """The context names what the routing table mints, and nothing else."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = _load(CONTEXT_FILE)
        cls.context = cls.document["@context"]
        cls.namespaces = _load(ROUTING_TABLES)["namespaces"]
        with open(CONTEXT_FILE, encoding="utf-8") as fh:
            cls.raw = fh.read()

    def test_document_explains_itself(self) -> None:
        # The "_doc" sibling is what a person dereferencing the context reads
        # first; JSON-LD processors ignore it. Losing it is losing the only
        # explanation the published file carries.
        self.assertIn("_doc", self.document)
        self.assertIn("SHACL", self.document["_doc"])

    def test_prefixes_equal_the_routing_table(self) -> None:
        for prefix in EXPECTED_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertEqual(
                    self.context.get(prefix),
                    self.namespaces[prefix],
                    msg="context prefix %r disagrees with "
                        "cli/src/penman/routing-tables.json" % prefix,
                )

    def test_vocab_is_the_ontology_namespace(self) -> None:
        self.assertEqual(self.context.get("@vocab"), self.namespaces["vso"])

    def test_every_project_iri_sits_under_the_versioned_root(self) -> None:
        # Root derived from the routing table, never written out here: that is
        # what makes this test survive the next namespace rename.
        vso_ns = self.namespaces["vso"]
        self.assertTrue(vso_ns.endswith("ontology#"), msg=vso_ns)
        root = vso_ns[: -len("ontology#")]

        found = PROJECT_IRI.findall(self.raw)
        self.assertTrue(found, msg="no project IRI in the context at all")
        strays = sorted({iri for iri in found if not iri.startswith(root)})
        self.assertEqual(
            strays,
            [],
            msg="IRIs outside the versioned root %r: %s" % (root, strays),
        )
        # The shapes root is referenced in "_doc"; it must be one of them.
        self.assertIn(root + "shapes.ttl", found)


class ContextTermTests(unittest.TestCase):
    """The term set is the JSON-LD schema's reference properties."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.context = _load(CONTEXT_FILE)["@context"]
        cls.terms = _terms(cls.context)

    def test_term_set_is_not_vacuous(self) -> None:
        # Anti-vacuity floor: the resolution test below iterates these terms,
        # and an empty mapping would make it pass without checking anything.
        self.assertGreater(len(self.terms), 5)

    def test_terms_match_the_jsonld_schema_properties(self) -> None:
        schema_keys = {
            key
            for key in _load(JSONLD_SCHEMA)["properties"]
            if not key.startswith("@")
        }
        self.assertEqual(set(self.terms), schema_keys)

    def test_every_term_is_declared_id_valued(self) -> None:
        # All seven are reference properties: their JSON values are @id
        # references, not strings. Without "@type": "@id" a processor would
        # materialize them as plain literals and every shape targeting the
        # referenced node would select nothing.
        for name, definition in sorted(self.terms.items()):
            with self.subTest(term=name):
                self.assertEqual(definition.get("@type"), "@id")
                self.assertTrue(definition.get("@id"), msg="term lacks @id")


@unittest.skipUnless(rdflib, "rdflib required")
class ContextResolutionTests(unittest.TestCase):
    """Every term points at a subject the ontology actually declares."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.context = _load(CONTEXT_FILE)["@context"]
        cls.terms = _terms(cls.context)
        cls.graph = rdflib.Graph()
        cls.graph.parse(VSO_TTL, format="turtle")
        cls.subjects = {str(s) for s in cls.graph.subjects()}

    def _expand(self, compact: str) -> str:
        """Resolve a term's "@id" against the context's prefixes/@vocab."""
        if ":" in compact:
            prefix, local = compact.split(":", 1)
            base = self.context.get(prefix)
            if base is not None:
                return base + local
            return compact
        return self.context["@vocab"] + compact

    def test_ontology_graph_is_not_empty(self) -> None:
        self.assertGreater(len(self.subjects), 100)

    def test_every_term_resolves_to_a_vso_ttl_subject(self) -> None:
        missing = []
        for name, definition in sorted(self.terms.items()):
            iri = self._expand(definition["@id"])
            if iri not in self.subjects:
                missing.append("%s -> %s" % (name, iri))
        self.assertEqual(
            missing,
            [],
            msg="context terms with no subject in ontology/vso.ttl: %s"
                % missing,
        )


if __name__ == "__main__":
    unittest.main()
