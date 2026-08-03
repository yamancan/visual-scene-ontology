"""Gates for `ontology/alignments.ttl` — the additive alignment layer.

An alignment file is the one artifact in a vocabulary that can assert something
false about a THIRD party. Three things therefore have to hold at once, and no
one of them implies the others:

  (a) **It reaches only real terms.** Every subject is a term the VSON
      vocabulary actually declares, and every object is in one of the external
      namespaces this file documents. An alignment to a term that does not
      exist — on either side — is worse than no alignment, because it looks
      checkable and is not.

  (b) **It imports no entailment.** Only `skos:closeMatch` and
      `skos:relatedMatch` appear. `owl:sameAs`, `owl:equivalentClass`,
      `owl:equivalentProperty`, `rdfs:subClassOf`, `rdfs:subPropertyOf` and
      `skos:exactMatch` are each a reasoning commitment this project has not
      made and its documents do not warrant; docs/vson.md §5.17 says so
      normatively and this is where that sentence is enforced.

  (c) **It is additive, and nothing loads it.** Parsing it introduces no VSO
      term, and it is absent from the ontology's `owl:imports` closure and from
      `tools.shacl_helper.ONTOLOGY_FILES`. That is what lets docs/vson.md §8
      compatibility hold through a release that adds alignments: a consumer
      that never fetches this file sees the same graph and the same verdict.

The SKOS view below the marker gets two independent checks. It is validated
against a SKOS integrity shapes graph with pyshacl — meta-SHACL, the same
engine the project's own gate runs — and it is compared term-by-term with
`ontology/vso.ttl`, which SHACL cannot do because the source vocabulary is not
in the file under test. Both matter: the first says the view is well-formed
SKOS, the second says it is a view of THIS vocabulary and not of a stale copy.

Run: python3 -m unittest tests.test_alignments

Skipped automatically if rdflib is not installed; the meta-SHACL cases are
skipped on their own if pyshacl is not.
"""

from __future__ import annotations

import importlib.util
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

try:
    import pyshacl
except ImportError:  # pragma: no cover — optional for this module
    pyshacl = None

ALIGNMENTS = "ontology/alignments.ttl"
DOCUMENT = "https://w3id.org/vson/v1/alignments"
VSA_NS = DOCUMENT + "#"
VSO_NS = "https://w3id.org/vson/v1/ontology#"

SKOS = "http://www.w3.org/2004/02/skos/core#"
CLOSE_MATCH = SKOS + "closeMatch"
RELATED_MATCH = SKOS + "relatedMatch"

# The only two predicates an alignment statement may use here.
ALIGNMENT_PREDICATES = (CLOSE_MATCH, RELATED_MATCH)

# Predicates that would import an entailment, and are therefore forbidden
# anywhere in this file.
FORBIDDEN = (
    "http://www.w3.org/2002/07/owl#sameAs",
    "http://www.w3.org/2002/07/owl#equivalentClass",
    "http://www.w3.org/2002/07/owl#equivalentProperty",
    "http://www.w3.org/2002/07/owl#imports",
    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "http://www.w3.org/2000/01/rdf-schema#subPropertyOf",
    SKOS + "exactMatch",
    SKOS + "broadMatch",
    SKOS + "narrowMatch",
)

# Every external namespace this file is allowed to reach, and the appendix
# section in docs/vson.md that cites it. A new alignment target is a deliberate
# edit here, not a silent addition to the Turtle.
ALIGNED_NAMESPACES = {
    "http://purl.org/nemo/gufo#": "gUFO — Appendix E.3",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "RDF 1.1 — Appendix E.6",
    "http://www.w3.org/ns/oa#": "Web Annotation — Appendix E.6",
    "http://xmlns.com/foaf/0.1/": "FOAF — Appendix E.6",
}

# The four alignments that were looked for and not minted. Each is recorded as
# an rdfs:comment on the document; the leading token is what this test pins, so
# that dropping a gap record fails rather than passing quietly.
RECORDED_GAPS = (
    "GAP — ISO 24617-7:2020",
    "GAP — the vision datasets' label vocabularies",
    "GAP — PROV-O",
    "GAP — schema:ImageObject",
)

# SKOS integrity conditions, as shapes. Deliberately small: these are the
# conditions a SKOS consumer relies on, not a restatement of the SKOS
# Recommendation.
SKOS_SHAPES = """
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

<urn:vson:skos:ConceptShape>
    a sh:NodeShape ;
    sh:targetClass skos:Concept ;
    sh:property [
        sh:path skos:prefLabel ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:languageIn ( "en" ) ;
        sh:message "A concept needs exactly one English prefLabel." ;
    ] ;
    sh:property [
        sh:path skos:definition ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:languageIn ( "en" ) ;
        sh:message "A concept needs exactly one English definition." ;
    ] ;
    sh:property [
        sh:path skos:inScheme ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:class skos:ConceptScheme ;
        sh:message "A concept belongs to exactly one declared scheme." ;
    ] ;
    sh:property [
        sh:path skos:topConceptOf ;
        sh:class skos:ConceptScheme ;
        sh:message "topConceptOf must name a declared scheme." ;
    ] .

<urn:vson:skos:SchemeShape>
    a sh:NodeShape ;
    sh:targetClass skos:ConceptScheme ;
    sh:property [
        sh:path skos:prefLabel ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:message "A scheme needs exactly one prefLabel." ;
    ] ;
    sh:property [
        sh:path skos:hasTopConcept ;
        sh:minCount 1 ;
        sh:class skos:Concept ;
        sh:message "A scheme names top concepts, and each one is a concept." ;
    ] .
"""


def _script(name):
    """Import a module from scripts/ by path — the loader the sibling
    documentation and drift gates already use."""
    scripts = os.path.join(ROOT, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(scripts, name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _graph(paths):
    graph = rdflib.Graph()
    for rel in paths:
        graph.parse(os.path.join(ROOT, rel), format="turtle")
    return graph


def _predicates(graph):
    return {str(p) for _s, p, _o in graph}


@unittest.skipIf(rdflib is None, "rdflib not installed")
class TheFileIsWellFormed(unittest.TestCase):
    """It parses, it declares itself, and it records its gaps."""

    @classmethod
    def setUpClass(cls):
        cls.graph = _graph([ALIGNMENTS])
        cls.document = rdflib.URIRef(DOCUMENT)

    def test_it_parses_and_states_something(self):
        self.assertGreater(len(self.graph), 0, "alignments.ttl is empty")

    def test_it_declares_a_publishing_header(self):
        self.assertIn(
            (self.document, RDF.type, OWL.Ontology),
            self.graph,
            "the document declares no owl:Ontology header",
        )
        for predicate in (
            RDFS.label,
            DCTERMS.title,
            DCTERMS.license,
            OWL.versionInfo,
        ):
            self.assertTrue(
                list(self.graph.objects(self.document, predicate)),
                "the header carries no %s" % predicate,
            )

    def test_every_recorded_gap_is_present(self):
        comments = [
            str(o) for o in self.graph.objects(self.document, RDFS.comment)
        ]
        for gap in RECORDED_GAPS:
            self.assertTrue(
                any(c.startswith(gap) for c in comments),
                "the %r record is missing; a gap that stops being written "
                "down stops being a gap and becomes a silence" % gap,
            )


@unittest.skipIf(rdflib is None, "rdflib not installed")
class TheAlignmentsReachRealTerms(unittest.TestCase):
    """Both ends of every alignment resolve to something that exists."""

    @classmethod
    def setUpClass(cls):
        cls.graph = _graph([ALIGNMENTS])
        vocabulary = _graph(ONTOLOGY_FILES)
        cls.declared = {
            str(s)
            for s in vocabulary.subjects()
            if isinstance(s, rdflib.URIRef)
        }
        cls.alignments = [
            (str(s), str(p), str(o))
            for s, p, o in cls.graph
            if str(p) in ALIGNMENT_PREDICATES
        ]

    def test_there_are_alignments_at_all(self):
        # The core vocabulary had zero external alignment before this file.
        self.assertGreater(
            len(self.alignments), 0, "no alignment statement in the file"
        )

    def test_every_subject_is_a_declared_vson_term(self):
        for subject, predicate, obj in self.alignments:
            self.assertTrue(
                subject.startswith(VSO_NS),
                "%s is not a VSON term but is aligned by this file" % subject,
            )
            self.assertIn(
                subject,
                self.declared,
                "%s <%s> %s: the subject is not declared by the vocabulary"
                % (subject, predicate, obj),
            )

    def test_every_object_is_in_a_documented_namespace(self):
        for subject, predicate, obj in self.alignments:
            namespace = next(
                (ns for ns in ALIGNED_NAMESPACES if obj.startswith(ns)), None
            )
            self.assertIsNotNone(
                namespace,
                "%s <%s> %s: the target is in no documented namespace; add it "
                "to ALIGNED_NAMESPACES with its Appendix E citation, or drop "
                "the alignment" % (subject, predicate, obj),
            )

    def test_no_alignment_points_back_into_this_project(self):
        for subject, predicate, obj in self.alignments:
            self.assertFalse(
                obj.startswith(VSO_NS) or obj.startswith(VSA_NS),
                "%s <%s> %s: an alignment to this project's own namespace is "
                "not an alignment" % (subject, predicate, obj),
            )


@unittest.skipIf(rdflib is None, "rdflib not installed")
class ItImportsNoEntailment(unittest.TestCase):
    """The whole claim of §5.17, as a test."""

    @classmethod
    def setUpClass(cls):
        cls.graph = _graph([ALIGNMENTS])

    def test_no_forbidden_predicate_appears(self):
        used = _predicates(self.graph)
        for predicate in FORBIDDEN:
            self.assertNotIn(
                predicate,
                used,
                "%s appears in %s; every predicate in FORBIDDEN commits a "
                "reasoner to something docs/vson.md §5.17 says this layer "
                "does not claim" % (predicate, ALIGNMENTS),
            )

    def test_the_forbidden_gate_can_go_red(self):
        # A gate nobody has seen fail is a gate nobody should trust.
        poisoned = rdflib.Graph()
        poisoned += self.graph
        poisoned.add(
            (
                rdflib.URIRef(VSO_NS + "Endurant"),
                OWL.equivalentClass,
                rdflib.URIRef("http://purl.org/nemo/gufo#Endurant"),
            )
        )
        self.assertIn(str(OWL.equivalentClass), _predicates(poisoned))

    def test_nothing_in_the_repository_loads_it(self):
        self.assertNotIn(
            ALIGNMENTS,
            ONTOLOGY_FILES,
            "the alignment layer must not join the graph every gate loads",
        )
        core = _graph(["ontology/vso.ttl"])
        imported = {str(o) for o in core.objects(None, OWL.imports)}
        self.assertNotIn(
            DOCUMENT,
            imported,
            "ontology/vso.ttl imports the alignment layer; the canonical name "
            "would then carry alignment claims a consumer did not ask for",
        )

    def test_it_introduces_no_vson_term(self):
        vocabulary = _graph(ONTOLOGY_FILES)
        known = {
            str(node)
            for triple in vocabulary
            for node in triple
            if isinstance(node, rdflib.URIRef)
        }
        for triple in self.graph:
            for node in triple:
                if not isinstance(node, rdflib.URIRef):
                    continue
                name = str(node)
                if not name.startswith(VSO_NS):
                    continue
                self.assertIn(
                    name,
                    known,
                    "%s is named by the alignment layer and by nothing in the "
                    "vocabulary — this file may view VSON terms, never mint "
                    "them" % name,
                )


@unittest.skipIf(rdflib is None, "rdflib not installed")
class TheSkosViewIsAViewOfThisVocabulary(unittest.TestCase):
    """Generated, and comparable term-by-term with the source it views."""

    @classmethod
    def setUpClass(cls):
        cls.graph = _graph([ALIGNMENTS])
        cls.vocabulary = _graph(["ontology/vso.ttl"])
        cls.builder = _script("build_alignments")
        cls.skos = rdflib.Namespace(SKOS)

    def test_the_generated_block_is_current(self):
        with open(os.path.join(ROOT, ALIGNMENTS), encoding="utf-8") as fh:
            current = fh.read()
        self.assertEqual(
            current,
            self.builder.rendered(),
            "the SKOS view is stale; regenerate with "
            "`python3 scripts/build_alignments.py --write`",
        )

    def test_every_scheme_views_its_whole_value_class(self):
        for cls_name, scheme_name, _prop in self.builder.SCHEMES:
            scheme = rdflib.URIRef(VSA_NS + scheme_name)
            self.assertIn(
                (scheme, RDF.type, self.skos.ConceptScheme),
                self.graph,
                "%s is not declared a skos:ConceptScheme" % scheme,
            )
            viewed = {
                str(s) for s in self.graph.subjects(self.skos.inScheme, scheme)
            }
            declared = {
                str(s)
                for s in self.vocabulary.subjects(
                    RDF.type, rdflib.URIRef(VSO_NS + cls_name)
                )
            }
            self.assertEqual(
                viewed,
                declared,
                "%s views %d value(s); vso:%s declares %d"
                % (scheme, len(viewed), cls_name, len(declared)),
            )

    def test_every_label_and_definition_is_copied_not_reworded(self):
        concepts = list(self.graph.subjects(RDF.type, self.skos.Concept))
        self.assertGreater(len(concepts), 0, "the SKOS view has no concepts")
        for concept in concepts:
            label = str(
                next(iter(self.graph.objects(concept, self.skos.prefLabel)))
            )
            definition = str(
                next(iter(self.graph.objects(concept, self.skos.definition)))
            )
            source_label = str(
                next(iter(self.vocabulary.objects(concept, RDFS.label)))
            )
            source_comment = str(
                next(iter(self.vocabulary.objects(concept, RDFS.comment)))
            )
            self.assertEqual(label, source_label, "%s: prefLabel" % concept)
            self.assertEqual(
                definition, source_comment, "%s: definition" % concept
            )

    def test_a_reworded_source_comment_moves_the_view(self):
        """The cannot-diverge property, demonstrated rather than asserted.

        Edit a value's comment in a copy of the vocabulary and the generated
        block changes — which is what makes the equality above a gate on the
        vocabulary rather than a tautology about one file.
        """
        source = _graph(["ontology/vso.ttl"])
        before = self.builder.block(source)
        above = rdflib.URIRef(VSO_NS + "above")
        old = next(iter(source.objects(above, RDFS.comment)))
        source.remove((above, RDFS.comment, old))
        source.add((above, RDFS.comment, rdflib.Literal("Reworded.", lang="en")))
        self.assertNotEqual(before, self.builder.block(source))


@unittest.skipIf(rdflib is None, "rdflib not installed")
@unittest.skipIf(pyshacl is None, "pyshacl not installed")
class TheSkosViewPassesMetaShacl(unittest.TestCase):
    """SKOS integrity, checked by the engine the project's own gate runs."""

    @classmethod
    def setUpClass(cls):
        cls.graph = _graph([ALIGNMENTS])
        cls.shapes = rdflib.Graph()
        cls.shapes.parse(data=SKOS_SHAPES, format="turtle")

    def _validate(self, data):
        conforms, _report, text = pyshacl.validate(
            data, shacl_graph=self.shapes, advanced=False
        )
        return conforms, text

    def test_the_view_conforms(self):
        conforms, text = self._validate(self.graph)
        self.assertTrue(conforms, text)

    def test_a_concept_without_a_scheme_is_rejected(self):
        broken = rdflib.Graph()
        broken += self.graph
        broken.add(
            (
                rdflib.URIRef("urn:vson:test:orphan"),
                RDF.type,
                rdflib.URIRef(SKOS + "Concept"),
            )
        )
        conforms, _text = self._validate(broken)
        self.assertFalse(
            conforms, "meta-SHACL accepted a concept with no scheme"
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
