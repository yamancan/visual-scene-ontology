"""A prefix binding is syntax: the corpus says the same thing under either one.

`ontology/vso.ttl` publishes `vann:preferredNamespacePrefix "vson"` (the prefix
a registry, a term browser or a generated SPARQL header should bind), while
every Turtle document in this repository — and every example in the spec —
writes `@prefix vso:`. Those two facts are only safe together if a prefix
carries no meaning: a prefixed name is an abbreviation the parser expands before
any graph exists, so re-binding the VSO namespace must leave the triples alone.

That is what RDF says. It is also the whole argument for publishing a preferred
prefix no document uses, which makes it worth checking rather than asserting.
The check is cheap, so it runs over the corpus rather than over one file: the
three ontology documents, both SHACL profiles, and all 17 scene documents (the
16-scene gallery plus the throne room, compiled through the Penman transpiler).

For each document the graph is re-serialized twice — once with the VSO namespace
bound to `vso`, once bound to `vson` — and both serializations are parsed back:

  * each serialization MUST actually carry the binding it was given, and MUST
    use it on at least one term. Without this the test could pass by never
    changing anything, which is the failure mode a green test hides;
  * the two round-tripped graphs MUST be isomorphic to each other and to the
    source graph — same triples, blank nodes up to renaming;
  * the SHACL verdict MUST be identical under both bindings (checked on the
    canonical example, which is the shipped document with the widest term use).

Two invariants are pinned alongside, because the failure this initiative must
not cause is an IRI edit disguised as a prefix edit:

  * the ontology publishes prefix `vson` and namespace
    `https://w3id.org/vson/v1/ontology#` — the second unchanged from v1.2;
  * every project IRI in the ontology documents sits under one of the four
    published namespaces, so a mistyped namespace cannot ride along.

Run: python3 -m unittest tests.test_prefix_binding

Skipped automatically if rdflib is not installed.
"""

from __future__ import annotations

import glob
import os
import unittest

try:
    import rdflib

    from tools.penman import vson_penman as vp
    from tools.shacl_helper import ROOT
except ImportError:  # pragma: no cover — dependency probe for the skip guard
    rdflib = None
    vp = None
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VANN = "http://purl.org/vocab/vann/"
VSO_NS = "https://w3id.org/vson/v1/ontology#"
ONTOLOGY_IRI = "https://w3id.org/vson/v1/ontology"

# Every namespace the project mints terms in. A project IRI outside this set is
# a typo, not a namespace — nothing publishes it and nothing resolves it.
PUBLISHED_NAMESPACES = (
    VSO_NS,
    "https://w3id.org/vson/v1/rcc8#",
    "https://w3id.org/vson/v1/allen#",
    "https://w3id.org/vson/v1/shapes#",
)
# The document IRIs themselves — the subjects the owl:Ontology headers sit on,
# which are names of documents rather than namespaces of terms.
DOCUMENT_IRIS = (
    ONTOLOGY_IRI,
    "https://w3id.org/vson/v1/rcc8",
    "https://w3id.org/vson/v1/allen",
    "https://w3id.org/vson/v1/shapes",
    "https://w3id.org/vson/v1/shapes-relaxed",
    "https://w3id.org/vson/v1.2/ontology",
)

TURTLE_FILES = (
    "ontology/vso.ttl",
    "ontology/rcc8.ttl",
    "ontology/allen.ttl",
    "shapes/vson-shapes.ttl",
    "shapes/vson-shapes-relaxed.ttl",
    "examples/throne_room.ttl",
)
ONTOLOGY_FILES = TURTLE_FILES[:3]
CANONICAL_EXAMPLE = "examples/throne_room.ttl"

# The two bindings under test: the one every document writes, and the one the
# vocabulary publishes.
BINDINGS = ("vso", "vson")

# The one corpus document with no VSO-namespace IRI in any triple: the RCC-8
# value vocabulary mints its eight relations in its own namespace and names
# `vso:rcc` only in comments, which are not triples. A serializer drops a
# binding nothing uses, so there is nothing to assert about the binding there.
# Pinned rather than detected-and-skipped: a document that quietly stopped
# using the ontology would otherwise slip past the assertion that matters.
NO_VSO_TERMS = ("ontology/rcc8.ttl",)


def _scene_files() -> "list[str]":
    """The 17 scene documents, gallery first."""
    gallery = sorted(
        os.path.relpath(p, ROOT)
        for p in glob.glob(os.path.join(ROOT, "examples", "gallery", "*.vson"))
    )
    return gallery + ["examples/throne_room.vson"]


def _turtle_graph(text: str) -> "rdflib.Graph":
    graph = rdflib.Graph()
    graph.parse(data=text, format="turtle")
    return graph


def _source_graph(rel: str) -> "rdflib.Graph":
    """The document as a graph, whichever surface it ships in."""
    path = os.path.join(ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if rel.endswith(".vson"):
        text = vp.to_turtle(text)
    return _turtle_graph(text)


def _mentions_vso(graph: "rdflib.Graph") -> bool:
    """Does any triple carry an IRI in the VSO namespace?"""
    for triple in graph:
        for node in triple:
            if isinstance(node, rdflib.URIRef) and str(node).startswith(VSO_NS):
                return True
    return False


def _serialize_bound_to(graph: "rdflib.Graph", prefix: str) -> str:
    """The same triples, serialized with the VSO namespace bound to `prefix`.

    A fresh graph is used rather than re-binding the source: rdflib keeps the
    bindings it read from the file, and a second binding for one namespace
    would leave the serializer free to pick the original. This graph has never
    seen the VSO namespace before, so the binding it is given is the only one.
    """
    out = rdflib.Graph()
    for triple in graph:
        out.add(triple)
    out.bind(prefix, rdflib.Namespace(VSO_NS), override=True, replace=True)
    return out.serialize(format="turtle")


class PrefixBindingIsSyntax(unittest.TestCase):
    """Re-binding the VSO namespace changes bytes, never triples."""

    def _assert_binding_took(self, text: str, prefix: str, rel: str) -> None:
        declaration = "@prefix %s: <%s>" % (prefix, VSO_NS)
        self.assertIn(
            declaration,
            text,
            msg="%s: serialization does not declare %s" % (rel, declaration),
        )
        # The declaration alone proves nothing — the serializer could have
        # written every term as a full IRI. At least one term must be
        # abbreviated with it.
        self.assertGreater(
            text.count("%s:" % prefix),
            1,
            msg="%s: %r declared but never used" % (rel, prefix),
        )

    def _assert_invariant(self, rel: str) -> None:
        source = _source_graph(rel)
        self.assertGreater(len(source), 0, msg="%s parsed to nothing" % rel)

        uses_vso = _mentions_vso(source)
        self.assertEqual(
            uses_vso,
            rel not in NO_VSO_TERMS,
            msg="%s: VSO-namespace use changed; re-measure NO_VSO_TERMS" % rel,
        )

        round_tripped = {}
        for prefix in BINDINGS:
            text = _serialize_bound_to(source, prefix)
            if uses_vso:
                self._assert_binding_took(text, prefix, rel)
            round_tripped[prefix] = _turtle_graph(text)

        first, second = (round_tripped[p] for p in BINDINGS)
        self.assertTrue(
            first.isomorphic(second),
            msg="%s: the two prefix bindings do not denote the same graph"
            % rel,
        )
        for prefix in BINDINGS:
            self.assertTrue(
                source.isomorphic(round_tripped[prefix]),
                msg="%s: re-serializing under %r changed the graph"
                % (rel, prefix),
            )

    def test_ontology_and_shape_documents(self) -> None:
        for rel in TURTLE_FILES:
            with self.subTest(document=rel):
                self._assert_invariant(rel)

    def test_scene_corpus(self) -> None:
        for rel in _scene_files():
            with self.subTest(document=rel):
                self._assert_invariant(rel)

    def test_corpus_is_the_whole_gallery(self) -> None:
        # Anti-vacuity: a glob that silently matches nothing would make the
        # test above green by checking nothing.
        scenes = _scene_files()
        self.assertEqual(len(scenes), 17, msg=str(scenes))
        for rel in TURTLE_FILES:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), msg=rel)

    def test_both_comparators_can_go_red(self) -> None:
        # A green invariance test proves nothing unless the two things it
        # leans on — "the binding took" and "these are the same graph" — can
        # fail. Both are shown failing here, on the same document they pass on.
        source = _source_graph(CANONICAL_EXAMPLE)

        bound_to_vso = _serialize_bound_to(source, "vso")
        with self.assertRaises(AssertionError):
            self._assert_binding_took(bound_to_vso, "vson", CANONICAL_EXAMPLE)

        mutated = rdflib.Graph()
        for triple in source:
            mutated.add(triple)
        victim = sorted(mutated, key=lambda t: tuple(str(n) for n in t))[0]
        mutated.remove(victim)
        self.assertFalse(
            source.isomorphic(mutated),
            msg="isomorphic() cannot see a dropped triple: %s" % (victim,),
        )

    def test_shacl_verdict_is_the_same_under_both_bindings(self) -> None:
        from tools.shacl_helper import validate_graph

        source = _source_graph(CANONICAL_EXAMPLE)
        for prefix in BINDINGS:
            graph = _turtle_graph(_serialize_bound_to(source, prefix))
            conforms, report = validate_graph(graph)
            with self.subTest(prefix=prefix):
                self.assertTrue(conforms, msg=report)


class PublishedNamesDidNotMove(unittest.TestCase):
    """The prefix moved; no IRI did."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ontology = rdflib.Graph()
        for rel in ONTOLOGY_FILES:
            cls.ontology.parse(os.path.join(ROOT, rel), format="turtle")

    def _objects(self, local: str) -> "list[str]":
        return [
            str(o)
            for o in self.ontology.objects(
                rdflib.URIRef(ONTOLOGY_IRI), rdflib.URIRef(VANN + local)
            )
        ]

    def test_the_published_preferred_prefix_is_vson(self) -> None:
        # Not `vso`: that prefix is the Vehicle Sales Ontology's
        # (http://purl.org/vso/ns#, in LOV since 2010). docs/vson.md §5.1
        # records the decision; reverting it is a decision too, not a cleanup.
        self.assertEqual(self._objects("preferredNamespacePrefix"), ["vson"])

    def test_the_published_namespace_is_unchanged(self) -> None:
        self.assertEqual(self._objects("preferredNamespaceUri"), [VSO_NS])

    def test_every_project_iri_sits_under_a_published_name(self) -> None:
        stray = set()
        for triple in self.ontology:
            for node in triple:
                if not isinstance(node, rdflib.URIRef):
                    continue
                iri = str(node)
                if not iri.startswith("https://w3id.org/vson/"):
                    continue
                if iri in DOCUMENT_IRIS:
                    continue
                if not any(iri.startswith(ns) for ns in PUBLISHED_NAMESPACES):
                    stray.add(iri)
        self.assertEqual(sorted(stray), [])


if rdflib is None:  # pragma: no cover — dependency probe for the skip guard
    PrefixBindingIsSyntax = unittest.skip("rdflib required")(
        PrefixBindingIsSyntax
    )
    PublishedNamesDidNotMove = unittest.skip("rdflib required")(
        PublishedNamesDidNotMove
    )


if __name__ == "__main__":
    unittest.main()
