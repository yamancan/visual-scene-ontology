"""Canonical form and denotation equality — docs/vson.md §4.6.

Four things are checked here, in the order they have to hold.

  (a) **The algorithm is RDFC-1.0, and not merely something deterministic.**
      `Rdfc10ConformanceTests` runs the worked examples published *in* the
      Recommendation (W3C REC-rdf-canon-20240521 §4.4.2, §4.6.2, §4.8.2) and
      compares the canonical labels, the first-degree hashes and the N-degree
      hash to the values printed there. A canonicalizer that agrees with
      itself proves nothing; these vectors are the outside authority. The
      shared-hash example is the load-bearing one — it is the case where two
      blank nodes tie at first degree and the gossip-path search has to break
      the tie, which is the half of the algorithm a simple sort-and-hash
      implementation gets wrong without ever noticing.

  (b) **The two §4.6 normalizations do what the section says.**
      `NormalizationTests` pins N1 and N2 one clause at a time, including the
      exclusions: a `vso:CameraView` is *not* anonymized, an IRI outside the
      document namespace is *not* anonymized, and N1 never merges two nodes
      the document distinguished.

  (c) **The frozen hashes.** `FrozenCorpusTests` recomputes the canonical
      hash of all 29 shipped documents and compares it to
      `tests/fixtures/canonical/hashes.txt`, and compares the canonical
      N-Quads of the throne room to `11_throne_room.nq` byte for byte. This is
      the regression gate the section exists to give: a transpiler or emitter
      change that alters what a document denotes turns this red, and one that
      only alters how it is written does not.

  (d) **The cross-syntax oracle.** `CrossSyntaxTests` is the claim §4 makes
      most often, made checkable: each of the twelve VSON-P / VSON-X gallery
      pairs canonicalizes to the *same bytes*. `tools/vson_x/equiv.py`, the
      fast isomorphism heuristic `make x-check` runs, is checked against the
      oracle on every pair — agreeing on the positives is not enough, so a
      known-different pair is checked too.

Run: python3 -m unittest tests.test_canon
"""

from __future__ import annotations

import os
import unittest

from rdflib import BNode, Graph, Literal, URIRef

from tools import canon
from tools.canon import VSO
from tools.vson_x.equiv import graph_equivalent

REPO = canon.REPO
GALLERY = os.path.join(REPO, "examples", "gallery")
GALLERY_X = os.path.join(REPO, "examples", "gallery-x")

# The gallery scenes that exist in both surfaces. Kept in step with
# tests/test_vson_x_roundtrip.py — that file asserts isomorphism through the
# Rust CLI, this one asserts byte-identical canonical forms through the Python
# transpiler, and they cover the same twelve pairs on purpose.
PAIRS = (
    "01_minimal",
    "02_quality",
    "03_spatial_topology",
    "04_directional_with_viewer",
    "05_possession_stative",
    "06_event_with_instrument",
    "07_ditransitive",
    "08_collective",
    "09_mass_substance",
    "10_geometry_bbox",
    "11_throne_room",
    "12_persona",
)

EX = "http://example.com/#"
VOCAB = "http://example.org/vocab#"


def _quads(*triples):
    return [(s, p, o, None) for s, p, o in triples]


def _graph(turtle: str) -> Graph:
    graph = Graph()
    graph.parse(data=turtle, format="turtle")
    return graph


SCENE_PREFIX = (
    "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n"
    "@prefix : <https://example.org/scenes/anonymous#> .\n"
)


class Rdfc10ConformanceTests(unittest.TestCase):
    """The Recommendation's own worked examples, hash for hash."""

    def test_unique_hashes_example_2(self):
        # REC-rdf-canon-20240521 §4.4.2 Example 2, and the first-degree hashes
        # of its Table 2.
        quads = _quads(
            (URIRef(EX + "p"), URIRef(EX + "q"), BNode("e0")),
            (URIRef(EX + "p"), URIRef(EX + "r"), BNode("e1")),
            (BNode("e0"), URIRef(EX + "s"), URIRef(EX + "u")),
            (BNode("e1"), URIRef(EX + "t"), URIRef(EX + "u")),
        )
        state = canon._Canonicalizer(quads)
        self.assertEqual(
            state.run(),
            "<http://example.com/#p> <http://example.com/#q> _:c14n0 .\n"
            "<http://example.com/#p> <http://example.com/#r> _:c14n1 .\n"
            "_:c14n0 <http://example.com/#s> <http://example.com/#u> .\n"
            "_:c14n1 <http://example.com/#t> <http://example.com/#u> .\n",
        )
        self.assertEqual(
            state.hash_first_degree("e0"),
            "21d1dd5ba21f3dee9d76c0c00c260fa6f5d5d65315099e553026f4828d0dc77a",
        )
        self.assertEqual(
            state.hash_first_degree("e1"),
            "6fa0b9bdb376852b5743ff39ca4cbf7ea14d34966b2828478fbf222e7c764473",
        )

    def test_shared_hashes_example_3(self):
        # REC-rdf-canon-20240521 §4.4.2 Example 3. e0 and e1 tie at first
        # degree (Table 5), so the canonical identifiers of Table 9 can only
        # be reached through Hash N-Degree Quads.
        quads = _quads(
            (URIRef(EX + "p"), URIRef(EX + "q"), BNode("e0")),
            (URIRef(EX + "p"), URIRef(EX + "q"), BNode("e1")),
            (BNode("e0"), URIRef(EX + "p"), BNode("e2")),
            (BNode("e1"), URIRef(EX + "p"), BNode("e3")),
            (BNode("e2"), URIRef(EX + "r"), BNode("e3")),
        )
        state = canon._Canonicalizer(quads)
        self.assertEqual(
            state.run(),
            "<http://example.com/#p> <http://example.com/#q> _:c14n2 .\n"
            "<http://example.com/#p> <http://example.com/#q> _:c14n3 .\n"
            "_:c14n0 <http://example.com/#r> _:c14n1 .\n"
            "_:c14n2 <http://example.com/#p> _:c14n1 .\n"
            "_:c14n3 <http://example.com/#p> _:c14n0 .\n",
        )
        self.assertEqual(
            state.canonical.issued,
            {"e2": "c14n0", "e3": "c14n1", "e1": "c14n2", "e0": "c14n3"},
        )
        self.assertEqual(
            state.hash_first_degree("e0"),
            "3b26142829b8887d011d779079a243bd61ab53c3990d550320a17b59ade6ba36",
        )
        self.assertEqual(state.hash_first_degree("e0"), state.hash_first_degree("e1"))

    def test_double_circle_n_degree_example(self):
        # REC-rdf-canon-20240521 §4.8.2: two blank nodes pointing at each
        # other twice — an automorphism, where every first-degree hash is
        # equal and the recursion in Hash N-Degree Quads is what terminates.
        quads = _quads(
            (BNode("e0"), URIRef(VOCAB + "next"), BNode("e1")),
            (BNode("e0"), URIRef(VOCAB + "prev"), BNode("e1")),
            (BNode("e1"), URIRef(VOCAB + "next"), BNode("e0")),
            (BNode("e1"), URIRef(VOCAB + "prev"), BNode("e0")),
        )
        state = canon._Canonicalizer(quads)
        self.assertEqual(
            state.run(),
            "_:c14n0 <http://example.org/vocab#next> _:c14n1 .\n"
            "_:c14n0 <http://example.org/vocab#prev> _:c14n1 .\n"
            "_:c14n1 <http://example.org/vocab#next> _:c14n0 .\n"
            "_:c14n1 <http://example.org/vocab#prev> _:c14n0 .\n",
        )

        fresh = canon._Canonicalizer(quads)
        for quad in fresh.quads:
            for _position, identifier in fresh._bnodes_of(quad):
                bucket = fresh.bnode_to_quads.setdefault(identifier, [])
                if quad not in bucket:
                    bucket.append(quad)
        self.assertEqual(
            fresh.hash_first_degree("e1"),
            "60dc8fc7b5481014b6ea38efb05455676d1e93e19b99119ab294941dacc16b3b",
        )
        issuer = canon._IdentifierIssuer("b")
        issuer.issue("e0")
        digest, issued = fresh.hash_n_degree("e0", issuer)
        self.assertEqual(
            digest,
            "e332b4b59e1c4794ee72a4df0f63723326ffb6d6a5c0d0cb4d2dd8d8d5ebf5a4",
        )
        self.assertEqual(issued.issued, {"e0": "b0", "e1": "b1"})

    def test_canonical_nquads_escaping(self):
        # Appendix A of the Recommendation: ECHAR for the seven listed
        # characters, UCHAR (lowercase \u, uppercase hex) for the control
        # characters that have none, no datatype on an xsd:string literal,
        # and every other character as itself in UTF-8.
        literal = Literal('tab\there "quoted" \\ back\nnewline \x00 \x7f é')
        line = canon.quad_to_nquads(
            (URIRef(EX + "s"), URIRef(EX + "p"), literal, None), lambda b: "x"
        )
        self.assertEqual(
            line,
            "<http://example.com/#s> <http://example.com/#p> "
            '"tab\\there \\"quoted\\" \\\\ back\\nnewline \\u0000 \\u007F é" .\n',
        )

    def test_typed_literal_keeps_its_datatype(self):
        line = canon.quad_to_nquads(
            (
                URIRef(EX + "s"),
                URIRef(EX + "p"),
                Literal("0.95", datatype=URIRef("http://www.w3.org/2001/XMLSchema#decimal")),
                None,
            ),
            lambda b: "x",
        )
        self.assertTrue(line.endswith('"0.95"^^<http://www.w3.org/2001/XMLSchema#decimal> .\n'))

    def test_poison_budget_is_enforced(self):
        # §7.1 of the Recommendation requires an implementation to terminate
        # early rather than run forever. The double circle needs one recursive
        # call per node, so a budget of one is enough to prove the guard is
        # wired to the recursion and not merely declared.
        quads = _quads(
            (BNode("e0"), URIRef(VOCAB + "next"), BNode("e1")),
            (BNode("e0"), URIRef(VOCAB + "prev"), BNode("e1")),
            (BNode("e1"), URIRef(VOCAB + "next"), BNode("e0")),
            (BNode("e1"), URIRef(VOCAB + "prev"), BNode("e0")),
        )
        with self.assertRaises(canon.CanonicalizationError):
            canon.rdfc10(quads, call_limit=1)


class NormalizationTests(unittest.TestCase):
    """N1 and N2, one clause at a time."""

    def test_n1_named_and_blank_quality_denote_the_same_scene(self):
        named = _graph(
            SCENE_PREFIX
            + ":apple a vso:PhysicalObject ; vso:hasQuality :q1 .\n"
            + ":q1 a vso:Quality ; vso:dimension vso:Color ; vso:value :red .\n"
        )
        blank = _graph(
            SCENE_PREFIX
            + ":apple a vso:PhysicalObject ; vso:hasQuality "
            + "[ a vso:Quality ; vso:dimension vso:Color ; vso:value :red ] .\n"
        )
        self.assertTrue(canon.denotes_same(named, blank))

    def test_n1_is_injective(self):
        # Two Quality nodes with the same dimension are still two qualities.
        # A rule that merged them would make every "same scene" verdict
        # suspect, so this is the property N1 must not lose.
        two = _graph(
            SCENE_PREFIX
            + ":apple a vso:PhysicalObject ; vso:hasQuality :q1, :q2 .\n"
            + ":q1 a vso:Quality ; vso:dimension vso:Color ; vso:value :red .\n"
            + ":q2 a vso:Quality ; vso:dimension vso:Color ; vso:value :green .\n"
        )
        one = _graph(
            SCENE_PREFIX
            + ":apple a vso:PhysicalObject ; vso:hasQuality :q1 .\n"
            + ":q1 a vso:Quality ; vso:dimension vso:Color ; vso:value :red .\n"
        )
        self.assertFalse(canon.denotes_same(two, one))
        self.assertEqual(len(canon.canonical_graph(two)), len(two))

    def test_n1_leaves_camera_views_named(self):
        # The exclusion §4.6 states: a CameraView is a referent (C5), so its
        # name is the author's and renaming it changes the document.
        named = _graph(SCENE_PREFIX + ":cam a vso:CameraView ; vso:angle 'low' .\n")
        other = _graph(SCENE_PREFIX + ":cam2 a vso:CameraView ; vso:angle 'low' .\n")
        self.assertFalse(canon.denotes_same(named, other))

    def test_n1_is_scoped_to_the_document_namespace(self):
        inside = _graph(
            SCENE_PREFIX
            + ":q1 a vso:Quality ; vso:dimension vso:Color ; vso:value :red .\n"
        )
        outside = _graph(
            SCENE_PREFIX
            + "@prefix other: <https://example.org/other#> .\n"
            + "other:q1 a vso:Quality ; vso:dimension vso:Color ; vso:value :red .\n"
        )
        self.assertFalse(canon.denotes_same(inside, outside))
        self.assertNotIn(
            "https://example.org/scenes/anonymous#q1",
            canon.canonical_nquads(inside),
        )
        self.assertIn("https://example.org/other#q1", canon.canonical_nquads(outside))

    def test_n2_composition_edges_are_interchangeable(self):
        depicts = _graph(SCENE_PREFIX + ":scene a vso:Composition ; vso:depicts :f .\n")
        has_fact = _graph(SCENE_PREFIX + ":scene a vso:Composition ; vso:hasFact :f .\n")
        occurs = _graph(SCENE_PREFIX + ":scene a vso:Composition ; vso:occurs :f .\n")
        self.assertTrue(canon.denotes_same(depicts, has_fact))
        self.assertTrue(canon.denotes_same(depicts, occurs))

    def test_n2_does_not_touch_other_predicates(self):
        quality = _graph(SCENE_PREFIX + ":scene a vso:Composition ; vso:hasQuality :f .\n")
        depicts = _graph(SCENE_PREFIX + ":scene a vso:Composition ; vso:depicts :f .\n")
        self.assertFalse(canon.denotes_same(quality, depicts))

    def test_hash_is_blind_to_blank_node_labels_and_statement_order(self):
        graph = canon.load_graph(os.path.join(GALLERY, "11_throne_room.vson"))
        shuffled = Graph()
        for prefix, namespace in graph.namespaces():
            shuffled.bind(prefix, namespace)
        relabel = {}
        for subject, predicate, obj in sorted(graph, key=lambda t: str(t[2]), reverse=True):
            if isinstance(subject, BNode):
                relabel.setdefault(subject, BNode())
            if isinstance(obj, BNode):
                relabel.setdefault(obj, BNode())
            shuffled.add(
                (relabel.get(subject, subject), predicate, relabel.get(obj, obj))
            )
        self.assertEqual(canon.canonical_hash(graph), canon.canonical_hash(shuffled))

    def test_hash_moves_when_the_scene_does(self):
        graph = canon.load_graph(os.path.join(GALLERY, "02_quality.vson"))
        before = canon.canonical_hash(graph)
        for subject, predicate, obj in list(graph):
            if predicate == VSO.value:
                graph.remove((subject, predicate, obj))
                graph.add((subject, predicate, Literal("green")))
                break
        self.assertNotEqual(before, canon.canonical_hash(graph))

    def test_the_canonical_form_is_a_fixed_point(self):
        for name in ("examples/throne_room.ttl", "examples/gallery/11_throne_room.vson"):
            graph = canon.load_graph(os.path.join(REPO, name))
            nquads = canon.canonical_nquads(graph)
            reparsed = Graph()
            # A VSON document has no named graphs, so its canonical N-Quads
            # are also N-Triples — parsed here as N-Triples only because
            # rdflib's N-Quads parser routes through a deprecated Dataset API.
            reparsed.parse(data=nquads, format="nt")
            self.assertEqual(canon.canonical_nquads(reparsed), nquads, name)


class FrozenCorpusTests(unittest.TestCase):
    """The frozen hashes of every shipped document."""

    def test_manifest_matches_the_corpus(self):
        frozen = {(surface, path): digest for digest, surface, path in canon.frozen_rows()}
        moved = []
        for digest, surface, path in canon.corpus_rows():
            if frozen.get((surface, path)) != digest:
                moved.append(
                    "  {}\n    frozen {}\n    now    {}".format(
                        path, frozen.get((surface, path)), digest
                    )
                )
        self.assertEqual(
            moved,
            [],
            "canonical hashes moved — a document, a transpiler or an emitter "
            "changed what a scene denotes:\n" + "\n".join(moved) + "\n"
            "Re-freeze with `python3 -m tools.canon --freeze` only after "
            "establishing which.",
        )

    def test_manifest_covers_every_shipped_document(self):
        rows = canon.frozen_rows()
        self.assertEqual(len(rows), 1 + 16 + 12)
        self.assertEqual([path for _d, _s, path in rows], canon.corpus_paths())

    def test_the_seventeen_scenes_are_seventeen_scenes(self):
        # One hash per surface-independent scene: the 16 gallery scenes plus
        # the hand-authored canonical one, all distinct. A collision here
        # would mean the corpus ships the same scene twice under two names.
        digests = [
            digest
            for digest, surface, _path in canon.frozen_rows()
            if surface != "VSON-X"
        ]
        self.assertEqual(len(set(digests)), 17)

    def test_witness_bytes_are_frozen(self):
        with open(canon.WITNESS, encoding="utf-8") as handle:
            frozen = handle.read()
        self.assertEqual(
            canon.canonical_nquads(
                canon.load_graph(os.path.join(GALLERY, canon.WITNESS_STEM + ".vson"))
            ),
            frozen,
        )
        self.assertEqual(
            canon.canonical_nquads(
                canon.load_graph(os.path.join(GALLERY_X, canon.WITNESS_STEM + ".x.vson"))
            ),
            frozen,
        )


class CrossSyntaxTests(unittest.TestCase):
    """Generated below — one method per VSON-P / VSON-X gallery pair."""

    def test_the_heuristic_and_the_oracle_disagree_about_nothing(self):
        # equiv.graph_equivalent is what `make x-check` runs: isomorphism
        # after the same two normalizations, which is fast and cannot produce
        # a canonical form. It has to agree with §4.6 on both answers, so a
        # known-different pair is checked beside the identical ones.
        left = canon.load_graph(os.path.join(GALLERY, "01_minimal.vson"))
        right = canon.load_graph(os.path.join(GALLERY, "02_quality.vson"))
        self.assertFalse(graph_equivalent(left, right))
        self.assertFalse(canon.denotes_same(left, right))

    def test_equal_canonical_form_implies_perfect_agreement(self):
        # §4.6 is the exact test and §5.15 the graded one, and this is the
        # implication between them: same canonical form ⇒ F1 = 1.0.
        from tools.metrics import smatch

        report = smatch.compare_paths(
            os.path.join(GALLERY, "11_throne_room.vson"),
            os.path.join(GALLERY_X, "11_throne_room.x.vson"),
        )
        self.assertEqual(report.f1, 1.0)

    def test_the_converse_does_not_hold(self):
        # F1 = 1.0 does not imply the same canonical form: the metric compares
        # document-local IRIs by local name, §4.6 compares them as written.
        # Rebasing a document leaves the metric at 1.0 and moves every hash.
        from tools.metrics import smatch

        source = os.path.join(GALLERY, "01_minimal.vson")
        original = canon.load_graph(source)
        rebased = Graph()
        rebased.bind("", "https://example.org/scenes/other#")
        for prefix, namespace in original.namespaces():
            if prefix:
                rebased.bind(prefix, namespace)
        for subject, predicate, obj in original:
            rebased.add(tuple(_rebase(term) for term in (subject, predicate, obj)))
        self.assertNotEqual(
            canon.canonical_hash(original), canon.canonical_hash(rebased)
        )
        self.assertEqual(
            smatch.compare(
                smatch.build_document(original, "original"),
                smatch.build_document(rebased, "rebased"),
            ).f1,
            1.0,
        )


def _rebase(term):
    old = "https://example.org/scenes/anonymous#"
    new = "https://example.org/scenes/other#"
    if isinstance(term, URIRef) and str(term).startswith(old):
        return URIRef(new + str(term)[len(old) :])
    return term


def _make_pair_test(stem: str):
    def test(self):
        penman = canon.load_graph(os.path.join(GALLERY, stem + ".vson"))
        compact = canon.load_graph(os.path.join(GALLERY_X, stem + ".x.vson"))
        self.assertEqual(
            canon.canonical_nquads(penman),
            canon.canonical_nquads(compact),
            "VSON-P and VSON-X do not denote the same scene for " + stem,
        )
        # And the heuristic that stands in for this in `make x-check` agrees.
        self.assertTrue(graph_equivalent(compact, penman))

    test.__name__ = "test_" + stem
    return test


for _stem in PAIRS:
    setattr(CrossSyntaxTests, "test_" + _stem, _make_pair_test(_stem))


if __name__ == "__main__":
    unittest.main()
