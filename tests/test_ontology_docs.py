"""Documentation-coverage gate for the ontology files.

A vocabulary that ships without labels and comments cannot be read by anything
that consumes it — a term browser, a hover tooltip in the studio, or a person
opening the Turtle for the first time. v1.1 annotated the whole namespace; these
tests keep that from silently rotting:

  (a) Every IRI subject in the w3id.org/vson namespace, across all three
      ontology files, carries at least one rdfs:label and one rdfs:comment.
      Adding a term without documenting it fails here.

  (b) Each ontology document declares the publishing header it claims to have:
      an owl:Ontology typing plus dc:title, dc:license, owl:versionInfo, and the
      vann namespace-prefix hints a vocabulary registry reads.

  (c) The canonical name resolves to the whole vocabulary. `ontology/vso.ttl`
      declares `owl:imports` of both companion documents, because `vso:rcc`
      takes `rcc:` individuals and §5.9's temporal edges are `allen:`
      properties — a consumer that parses the core document alone holds a
      vocabulary whose values are undefined. The negative half is asserted too:
      that document really does yield zero companion-namespace IRIs on its own,
      which is what makes the import load-bearing rather than decorative.

Run: python3 -m unittest tests.test_ontology_docs

Skipped automatically if rdflib is not installed.
"""

from __future__ import annotations

import os
import unittest

try:
    import rdflib
    from rdflib.namespace import DCTERMS, OWL, RDF, RDFS

    from tools.shacl_helper import ONTOLOGY_FILES, ROOT
except ImportError:  # pragma: no cover — dependency probe for the skip guard
    rdflib = None
    ONTOLOGY_FILES = ()
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VSON_HOST = "w3id.org/vson"
VANN = "http://purl.org/vocab/vann/"

# The document IRI each ontology file declares its header on.
DOCUMENT_IRIS = {
    "ontology/vso.ttl": "https://w3id.org/vson/v1/ontology",
    "ontology/rcc8.ttl": "https://w3id.org/vson/v1/rcc8",
    "ontology/allen.ttl": "https://w3id.org/vson/v1/allen",
}


def _graph(rel_paths) -> "rdflib.Graph":
    g = rdflib.Graph()
    for rel in rel_paths:
        g.parse(os.path.join(ROOT, rel), format="turtle")
    return g


def _vson_subjects(g: "rdflib.Graph") -> list:
    """Every IRI subject minted in the project's own namespace.

    Blank nodes (the owl:AllDifferent / owl:AllDisjointClasses axiom carriers)
    are not terms and are not documented; external IRIs are somebody else's to
    document.
    """
    subs = {
        s
        for s in g.subjects()
        if isinstance(s, rdflib.URIRef) and VSON_HOST in str(s)
    }
    return sorted(subs, key=str)


@unittest.skipUnless(rdflib, "rdflib required")
class OntologyAnnotationCoverageTests(unittest.TestCase):
    """Every declared term is labelled and described."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = _graph(ONTOLOGY_FILES)
        cls.subjects = _vson_subjects(cls.graph)

    def test_ontology_files_are_the_three_expected(self) -> None:
        # Pins the coverage surface: a fourth ontology file must be added to
        # tools.shacl_helper.ONTOLOGY_FILES to be covered here, not forgotten.
        self.assertEqual(set(ONTOLOGY_FILES), set(DOCUMENT_IRIS))

    def test_every_term_has_a_label(self) -> None:
        missing = [
            str(s)
            for s in self.subjects
            if not list(self.graph.objects(s, RDFS.label))
        ]
        self.assertEqual(
            missing, [], msg="terms without rdfs:label: %s" % missing
        )

    def test_every_term_has_a_comment(self) -> None:
        missing = [
            str(s)
            for s in self.subjects
            if not list(self.graph.objects(s, RDFS.comment))
        ]
        self.assertEqual(
            missing, [], msg="terms without rdfs:comment: %s" % missing
        )

    def test_coverage_surface_is_not_empty(self) -> None:
        # Guards the two tests above against passing vacuously if the parse
        # silently yields nothing.
        self.assertGreater(len(self.subjects), 100)


@unittest.skipUnless(rdflib, "rdflib required")
class OntologyHeaderTests(unittest.TestCase):
    """Each ontology document carries a vocabulary-publishing header."""

    def test_each_file_declares_its_document_iri_as_an_ontology(self) -> None:
        for rel, iri in sorted(DOCUMENT_IRIS.items()):
            with self.subTest(file=rel):
                g = _graph([rel])
                doc = rdflib.URIRef(iri)
                self.assertIn((doc, RDF.type, OWL.Ontology), g)

    def test_each_header_carries_the_publishing_metadata(self) -> None:
        required = [
            ("dc:title", DCTERMS.title),
            ("dc:license", DCTERMS.license),
            ("owl:versionInfo", OWL.versionInfo),
            ("vann:preferredNamespacePrefix",
             rdflib.URIRef(VANN + "preferredNamespacePrefix")),
            ("vann:preferredNamespaceUri",
             rdflib.URIRef(VANN + "preferredNamespaceUri")),
        ]
        for rel, iri in sorted(DOCUMENT_IRIS.items()):
            g = _graph([rel])
            doc = rdflib.URIRef(iri)
            for name, prop in required:
                with self.subTest(file=rel, predicate=name):
                    self.assertTrue(
                        list(g.objects(doc, prop)),
                        msg="%s header is missing %s" % (rel, name),
                    )


@unittest.skipUnless(rdflib, "rdflib required")
class ImportsClosureTests(unittest.TestCase):
    """The core document names the two companions it cannot be read without."""

    CORE = "ontology/vso.ttl"
    COMPANIONS = (
        "https://w3id.org/vson/v1/rcc8",
        "https://w3id.org/vson/v1/allen",
    )

    @classmethod
    def setUpClass(cls) -> None:
        cls.core = _graph([cls.CORE])

    def test_core_imports_both_companion_documents(self) -> None:
        imported = {
            str(o)
            for o in self.core.objects(
                rdflib.URIRef(DOCUMENT_IRIS[self.CORE]), OWL.imports
            )
        }
        self.assertEqual(imported, set(self.COMPANIONS))

    def test_every_imported_name_is_a_document_this_repository_publishes(
        self,
    ) -> None:
        # An import of a name nothing serves is a dangling pointer that no
        # parse in this repository would notice, because nothing here follows
        # imports. DOCUMENT_IRIS is the set of names that do resolve (§5.1).
        for iri in self.COMPANIONS:
            with self.subTest(imported=iri):
                self.assertIn(iri, set(DOCUMENT_IRIS.values()))

    def test_the_core_document_alone_defines_no_companion_term(self) -> None:
        # The measurement the import exists for. If this ever stops being true
        # — if the eight RCC-8 individuals or the thirteen Allen properties
        # moved into vso.ttl — the import would be redundant and this file's
        # comment would be stating something false.
        for iri in self.COMPANIONS:
            prefix = "%s#" % iri
            found = {
                str(node)
                for triple in self.core
                for node in triple
                if isinstance(node, rdflib.URIRef)
                and str(node).startswith(prefix)
            }
            with self.subTest(namespace=prefix):
                self.assertEqual(found, set())

    def test_the_imported_documents_carry_those_terms(self) -> None:
        # The other half: the closure a consumer following the imports gets.
        merged = _graph(ONTOLOGY_FILES)
        for iri in self.COMPANIONS:
            prefix = "%s#" % iri
            terms = {
                str(s)
                for s in merged.subjects()
                if isinstance(s, rdflib.URIRef) and str(s).startswith(prefix)
            }
            with self.subTest(namespace=prefix):
                self.assertGreater(len(terms), 0)


if __name__ == "__main__":
    unittest.main()
