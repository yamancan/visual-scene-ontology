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

  (d) The annotation layer `scripts/annotate_ontology.py` generates is present
      and current: `rdfs:isDefinedBy` on every term naming the document that
      declares it, `vs:term_status` on every term, and a language tag on every
      label and comment. All three were at zero coverage through v1.3, and all
      three matter to a consumer holding a MERGED graph — the imports closure,
      or `site/v1/vson-full.ttl` — where the file a term arrived in is no
      longer visible. The generator is run in check mode here, so a term added
      by hand without the layer fails inside `make check` rather than shipping.

  (e) The publishing metadata a citation tool reads, including the one field
      that is a copy: `dc:bibliographicCitation` restates CITATION.cff, and a
      release that bumps one and forgets the other fails here.

Run: python3 -m unittest tests.test_ontology_docs

Skipped automatically if rdflib is not installed.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
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
VS = "http://www.w3.org/2003/06/sw-vocab-status/ns#"
CITATION = "CITATION.cff"

# The document IRI each ontology file declares its header on.
DOCUMENT_IRIS = {
    "ontology/vso.ttl": "https://w3id.org/vson/v1/ontology",
    "ontology/rcc8.ttl": "https://w3id.org/vson/v1/rcc8",
    "ontology/allen.ttl": "https://w3id.org/vson/v1/allen",
}


def _script(name):
    """Import a module from scripts/ by path — the loader tests/test_drift_gates
    and tests/test_live_claims already use."""
    scripts = os.path.join(ROOT, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(scripts, name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


annotate = _script("annotate_ontology") if rdflib else None


def _graph(rel_paths) -> "rdflib.Graph":
    g = rdflib.Graph()
    for rel in rel_paths:
        g.parse(os.path.join(ROOT, rel), format="turtle")
    return g


def _citation_fields() -> "dict[str, str]":
    """The four CITATION.cff fields the ontology headers restate.

    A three-key line reader rather than a YAML parse: adding a YAML dependency
    to read four scalars off a flat file would be a dependency this repository
    does not otherwise need. The file is CFF 1.2, whose top-level scalars are
    plain `key: value` lines; `authors` is the one nested read. A person entry
    (`given-names` + `family-names`) composes as "Given Family"; an entity
    entry (`- name:`) is taken verbatim.
    """
    fields: "dict[str, str]" = {}
    given = family = None
    with open(os.path.join(ROOT, CITATION), encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            for key in ("title", "version", "date-released", "repository-code"):
                prefix = key + ":"
                if line.startswith(prefix) and key not in fields:
                    fields[key] = stripped[len(prefix):].strip().strip('"')
            if stripped.startswith("- name:") and "author" not in fields:
                fields["author"] = stripped[len("- name:"):].strip().strip('"')
            if stripped.startswith("- given-names:") and given is None:
                given = stripped[len("- given-names:"):].strip().strip('"')
            elif stripped.startswith("given-names:") and given is None:
                given = stripped[len("given-names:"):].strip().strip('"')
            if stripped.startswith("family-names:") and family is None:
                family = stripped[len("family-names:"):].strip().strip('"')
    if "author" not in fields and given and family:
        fields["author"] = f"{given} {family}"
    return fields


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


def _terms(g: "rdflib.Graph") -> list:
    """Every VSON-namespace IRI subject that is a term rather than a document.

    A document IRI is the subject of its own `owl:Ontology` header; it names a
    document, and a document is not defined by itself.
    """
    documents = set(DOCUMENT_IRIS.values())
    return [s for s in _vson_subjects(g) if str(s) not in documents]


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
            ("dc:created", DCTERMS.created),
            ("dc:issued", DCTERMS.issued),
            ("dc:publisher", DCTERMS.publisher),
            ("dc:bibliographicCitation", DCTERMS.bibliographicCitation),
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
class GeneratedAnnotationLayerTests(unittest.TestCase):
    """`rdfs:isDefinedBy`, `vs:term_status` and the language tags."""

    TERM_STATUS = rdflib.URIRef(VS + "term_status") if rdflib else None
    LANGUAGE = "en"

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = _graph(ONTOLOGY_FILES)
        cls.terms = _terms(cls.graph)

    def test_the_generated_layer_is_current(self) -> None:
        # The one assertion that catches a term added by hand: the files must
        # equal what scripts/annotate_ontology.py would write for them. It is
        # run in memory — nothing here writes to the checkout.
        stale = [
            rel
            for rel in sorted(annotate.DOCUMENTS)
            if annotate.read(rel) != annotate.annotate(rel, annotate.read(rel))
        ]
        self.assertEqual(
            stale,
            [],
            msg="stale annotation layer in %s — regenerate with "
            "`python3 scripts/annotate_ontology.py --write` and re-sync the "
            "CLI mirror" % stale,
        )

    def test_the_generator_agrees_with_this_file_about_the_documents(
        self,
    ) -> None:
        self.assertEqual(annotate.DOCUMENTS, DOCUMENT_IRIS)

    def test_the_generators_own_selftest_is_green(self) -> None:
        # The transform's edge cases — a `#` inside an IRI, a `"` inside a
        # prose comment, an already-tagged literal — live in the script beside
        # the code they check. This runs them inside `make check` so a rewrite
        # of the scanner cannot pass by never being executed.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = annotate.selftest()
        self.assertEqual(code, 0, msg=buffer.getvalue())

    def test_every_term_says_which_document_defines_it(self) -> None:
        missing = [
            str(s)
            for s in self.terms
            if not list(self.graph.objects(s, RDFS.isDefinedBy))
        ]
        self.assertEqual(
            missing, [], msg="terms without rdfs:isDefinedBy: %s" % missing
        )

    def test_isdefinedby_names_the_document_the_term_is_minted_in(self) -> None:
        # A term whose isDefinedBy points at another document would send a
        # consumer to a file that does not declare it — worse than no triple.
        wrong = []
        for term in self.terms:
            defining = sorted(
                str(o) for o in self.graph.objects(term, RDFS.isDefinedBy)
            )
            expected = [str(term).rsplit("#", 1)[0]]
            if defining != expected:
                wrong.append((str(term), defining, expected))
        self.assertEqual(wrong, [], msg="misdirected rdfs:isDefinedBy: %s" % wrong)

    def test_every_term_carries_a_term_status(self) -> None:
        missing = [
            str(s)
            for s in self.terms
            if not list(self.graph.objects(s, self.TERM_STATUS))
        ]
        self.assertEqual(
            missing, [], msg="terms without vs:term_status: %s" % missing
        )

    def test_every_term_status_is_one_the_vs_vocabulary_defines(self) -> None:
        allowed = {"stable", "testing", "unstable", "archaic"}
        found = {
            str(o) for o in self.graph.objects(None, self.TERM_STATUS)
        }
        self.assertTrue(found)
        self.assertEqual(found - allowed, set())

    def test_every_label_and_comment_carries_a_language_tag(self) -> None:
        untagged = []
        for predicate in (RDFS.label, RDFS.comment):
            for subject, _, obj in self.graph.triples((None, predicate, None)):
                if not isinstance(obj, rdflib.Literal):
                    continue
                if obj.language == self.LANGUAGE:
                    continue
                untagged.append((str(subject), str(predicate), str(obj)[:40]))
        self.assertEqual(
            untagged, [], msg="labels/comments without @en: %s" % untagged
        )

    def test_the_annotated_surface_is_the_measured_one(self) -> None:
        # Guards every assertion above against passing vacuously, and pins the
        # count the commit that introduced the layer measured: 183 terms across
        # the three documents, 186 labels and 186 comments (the three document
        # IRIs carry a label and a comment but are not terms).
        self.assertEqual(len(self.terms), 183)
        self.assertEqual(len(list(self.graph.triples((None, RDFS.label, None)))), 186)
        self.assertEqual(
            len(list(self.graph.triples((None, RDFS.comment, None)))), 186
        )


@unittest.skipUnless(rdflib, "rdflib required")
class BibliographicCitationTests(unittest.TestCase):
    """The one header field that is a copy of another tracked file."""

    def test_citation_cff_states_the_fields_the_headers_restate(self) -> None:
        fields = _citation_fields()
        self.assertEqual(
            sorted(fields),
            ["author", "date-released", "repository-code", "title", "version"],
            msg="CITATION.cff no longer states the fields this gate reads: %s"
            % fields,
        )

    def test_each_header_restates_citation_cff(self) -> None:
        fields = _citation_fields()
        year = fields["date-released"].split("-")[0]
        for rel, iri in sorted(DOCUMENT_IRIS.items()):
            g = _graph([rel])
            cited = sorted(
                str(o)
                for o in g.objects(
                    rdflib.URIRef(iri), DCTERMS.bibliographicCitation
                )
            )
            with self.subTest(file=rel):
                self.assertEqual(len(cited), 1)
                citation = cited[0]
                for name, value in (
                    ("author", fields["author"]),
                    ("year", year),
                    ("title", fields["title"]),
                    ("release", fields["version"]),
                    ("repository", fields["repository-code"]),
                    ("the file itself", CITATION),
                ):
                    with self.subTest(field=name):
                        self.assertIn(value, citation)


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
