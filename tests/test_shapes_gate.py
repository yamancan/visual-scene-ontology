"""Gate tests for the shape files and the ontology they mirror.

Three properties that the repo previously asserted only in prose:

  (a) Conformance clause C2 (docs/vson.md §2) — "no orphan VSO terms". Every
      IRI a corpus document mints under a VSON namespace must be declared as a
      subject in ontology/vso.ttl, rcc8.ttl or allen.ttl. Nothing enforced this,
      so vso:occurs and six Quality dimensions shipped undeclared while the docs
      described them. The sweep itself moved to tools/c2_check.py in v1.3, when
      `vson validate` gained it as a third gate; these tests drive that module,
      with the negative controls the corpus sweep alone cannot supply.

  (b) The range-mirrored sh:class checks are not vacuous. Validation runs with
      inference="rdfs" (C3), so a `sh:class C` sitting on a property whose
      rdfs:range is already C is entailed onto every value node and can never
      fail on its own. The `sh:not` guards beside it are what give the check
      teeth. These tests pin that a wrongly-typed value really is rejected —
      remove a guard and they fail.

  (c) shapes/vson-shapes-relaxed.ttl carries the same shapes as the strict file,
      and accepts every strict-conforming document. Both are claims made in that
      file's own rdfs:comment header; neither was tested.

Run: python3 -m unittest tests.test_shapes_gate

Skipped automatically if rdflib / pyshacl / owlrl are not installed.
"""

from __future__ import annotations

import glob
import os
import unittest

try:
    import pyshacl
    import rdflib

    from tools.c2_check import declared_terms, orphans_in
    from tools.owlrl_check import clashes_for
    from tools.penman import vson_penman as vp
    from tools.shacl_helper import ONTOLOGY_FILES, ROOT, validate_graph
except ImportError:  # pragma: no cover — dependency probe for the skip guards
    pyshacl = None
    rdflib = None
    clashes_for = None
    declared_terms = None
    orphans_in = None
    vp = None
    ONTOLOGY_FILES = ()
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    validate_graph = None

VSO_NS = "https://w3id.org/vson/v1/ontology#"
SH_NS = "http://www.w3.org/ns/shacl#"
VSS_NS = "https://w3id.org/vson/v1/shapes#"

STRICT_SHAPES = "shapes/vson-shapes.ttl"
RELAXED_SHAPES = "shapes/vson-shapes-relaxed.ttl"

_HAVE_DEPS = bool(
    rdflib and pyshacl and vp and validate_graph and clashes_for and orphans_in
)

# A minimal directional scene, mirroring the Turtle that
# examples/gallery/04_directional_with_viewer.vson transpiles to: one camera,
# two objects, one SpatialFact carrying :directional and a :viewer. Written out
# by hand so the bad variant differs from the good one in exactly one triple.
_SCENE_PREFIX = """
@prefix vso: <https://w3id.org/vson/v1/ontology#> .
@prefix rcc: <https://w3id.org/vson/v1/rcc8#> .
@prefix :    <https://example.org/scenes/gate#> .

:scene a vso:Composition ;
    vso:framedBy :cam ;
    vso:viewedBy :cam ;
    vso:depicts  :lamp , :chair ;
    vso:hasFact  :sf .

:cam a vso:CameraView ; vso:angle "eye_level" ; vso:framing "wide_shot" .

:lamp a vso:PhysicalObject ;
    vso:individuation vso:Generic ; vso:animacy vso:Inert ;
    vso:countability vso:Count ; vso:class :Lamp .

:chair a vso:PhysicalObject ;
    vso:individuation vso:Generic ; vso:animacy vso:Inert ;
    vso:countability vso:Count ; vso:class :Furniture .

:sf a vso:SpatialFact ;
    vso:figure :lamp ; vso:ground :chair ;
    vso:directional vso:left_of ; vso:rcc rcc:DC ;
"""

GOOD_SCENE = _SCENE_PREFIX + "    vso:viewer :cam .\n"

# The only difference: the viewer is a PhysicalObject rather than the camera.
# :ghost is deliberately NOT a vso:depicts target — pointing the viewer at an
# already-depicted object would entail that object into vso:CameraView (hence
# vso:Frame) and trip vss:FrameNotDepictedShape as well, so the document would
# fail even with the vacuity guard removed and the test would prove nothing.
BAD_VIEWER_SCENE = (
    _SCENE_PREFIX
    + """    vso:viewer :ghost .

:ghost a vso:PhysicalObject ;
    vso:individuation vso:Generic ; vso:animacy vso:Inert ;
    vso:countability vso:Count ; vso:class :Bystander .
"""
)

# Distinguishing fragments of each guard's sh:message. Asserting on these is
# what makes a failure attributable to the guard under test rather than to some
# unrelated shape that happens to fire on the same document.
VIEWER_GUARD_MSG = "never an Entity"
AGENT_GUARD_MSG = "vso:agent must reference an Endurant"
INVARIANT_GUARD_MSG = "an invariant may not be"
FRAMEDBY_GUARD_MSG = "vso:framedBy must reference a Frame"
EXPERIENCER_GUARD_MSG = "vso:experiencer must reference an Endurant"
BELIEF_EXPERIENCER_GUARD_MSG = "BeliefState must have exactly one experiencer"


def _corpus() -> list:
    """Every VSON-P document the repo ships: the gallery plus throne_room."""
    files = sorted(glob.glob(os.path.join(ROOT, "examples", "gallery", "*.vson")))
    files.append(os.path.join(ROOT, "examples", "throne_room.vson"))
    return files


def _emit(path: str) -> "rdflib.Graph":
    """Transpile a VSON-P document and parse the emitted Turtle."""
    with open(path, encoding="utf-8") as fh:
        ttl = vp.to_turtle(fh.read())
    g = rdflib.Graph()
    g.parse(data=ttl, format="turtle")
    return g


def _parse(rel_path: str) -> "rdflib.Graph":
    g = rdflib.Graph()
    g.parse(os.path.join(ROOT, rel_path), format="turtle")
    return g


def _doc(ttl: str) -> "rdflib.Graph":
    g = rdflib.Graph()
    g.parse(data=ttl, format="turtle")
    return g


_ONT_CACHE = {}


def _ontology() -> "rdflib.Graph":
    if "g" not in _ONT_CACHE:
        g = rdflib.Graph()
        for f in ONTOLOGY_FILES:
            g.parse(os.path.join(ROOT, f), format="turtle")
        _ONT_CACHE["g"] = g
    return _ONT_CACHE["g"]


def _validate_relaxed(data: "rdflib.Graph"):
    """Same ont_graph / inference / allow_warnings config as
    tools.shacl_helper.validate_graph, but against the relaxed profile."""
    conforms, _, report = pyshacl.validate(
        data,
        shacl_graph=_parse(RELAXED_SHAPES),
        ont_graph=_ontology(),
        inference="rdfs",
        abort_on_first=False,
        allow_warnings=True,
    )
    return conforms, report


def _vss_node_shapes(rel_path: str) -> set:
    """Local names of every vss: subject typed sh:NodeShape in a shapes file."""
    g = _parse(rel_path)
    sh_node_shape = rdflib.URIRef(SH_NS + "NodeShape")
    return {
        str(s)[len(VSS_NS) :]
        for s in g.subjects(rdflib.RDF.type, sh_node_shape)
        if isinstance(s, rdflib.URIRef) and str(s).startswith(VSS_NS)
    }


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl + owlrl required")
class C2OrphanTermTests(unittest.TestCase):
    """C2: every VSON-namespace IRI a document asserts must be declared.

    The sweep itself now lives in `tools.c2_check`, because `vson validate` runs
    it as its third gate (docs/vson.md §2). These tests exercise that module
    rather than restating it: one implementation, checked here and shipped in
    the verifier.
    """

    def test_ontology_declares_every_vson_term_the_corpus_uses(self) -> None:
        for path in _corpus():
            rel = os.path.relpath(path, ROOT)
            with self.subTest(document=rel):
                orphans = orphans_in(_emit(path))
                self.assertEqual(
                    orphans,
                    [],
                    msg=(
                        f"{rel} asserts VSON terms with no declaration in the "
                        f"ontology files (C2 violation): {orphans}"
                    ),
                )

    def test_an_unregistered_dimension_is_reported(self) -> None:
        # The negative control. Without it the sweep above would pass just as
        # well if declared_terms() returned everything, or orphans_in() nothing.
        # docs/vson.md §5.5.1 names this exact case: a vso: dimension outside
        # the twenty-one-member registry is an orphan term, not a warning.
        doc = _doc(
            GOOD_SCENE
            + "\n:lamp vso:hasQuality :q .\n"
            + ":q a vso:Quality ; vso:dimension vso:Ambience ; vso:value \"warm\" .\n"
        )
        self.assertEqual(orphans_in(doc), [VSO_NS + "Ambience"])

    def test_a_document_namespace_dimension_is_not_an_orphan(self) -> None:
        # The other half of §5.5.1: the registry is closed *within the VSO
        # namespace* only. A gate that flagged :Layout would reject documents
        # the specification permits, which §8.2 forbids.
        doc = _doc(
            GOOD_SCENE
            + "\n:lamp vso:hasQuality :q .\n"
            + ":q a vso:Quality ; vso:dimension :Layout ; vso:value \"triangular\" .\n"
        )
        self.assertEqual(orphans_in(doc), [])

    def test_the_shipped_c2_fixture_is_rejected_for_c2_alone(self) -> None:
        # tests/fixtures/bad_orphan_term.ttl is the fixture cli/tests/
        # golden_validate.rs drives the third gate with. It has to fail C2 and
        # pass SHACL: if a shape ever started rejecting it, the CLI test would
        # still be green while proving nothing about the C2 gate.
        doc = _parse("tests/fixtures/bad_orphan_term.ttl")
        self.assertEqual(orphans_in(doc), [VSO_NS + "Ambience"])
        conforms, report = validate_graph(doc)
        self.assertTrue(conforms, msg=report)

    def test_rcc8_and_allen_terms_are_declared_too(self) -> None:
        # C2 names three ontology files, not one. rcc:DC appears in the corpus
        # and is declared in ontology/rcc8.ttl; a sweep that only loaded
        # vso.ttl would call it an orphan.
        self.assertIn("https://w3id.org/vson/v1/rcc8#DC", declared_terms())
        self.assertIn("https://w3id.org/vson/v1/allen#before", declared_terms())

    def test_occurs_is_declared(self) -> None:
        # Named explicitly: the gallery emitted vso:occurs long before the
        # ontology declared it, which is the exact hole the sweep above closes.
        ont = _parse("ontology/vso.ttl")
        occurs = rdflib.URIRef(VSO_NS + "occurs")
        self.assertIn(occurs, set(ont.subjects()))
        self.assertIn(
            rdflib.URIRef("http://www.w3.org/2002/07/owl#ObjectProperty"),
            set(ont.objects(occurs, rdflib.RDF.type)),
        )


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl + owlrl required")
class DimensionRegistryClosureTests(unittest.TestCase):
    """The closed dimension registry is one list, not three.

    `vso:dimension` is an `owl:FunctionalProperty`, so two dimensions on one
    Quality collapse to `owl:sameAs` under prp-fp. Only pairwise distinctness
    turns that collapse into a reported clash — which means a `vso:Dimension`
    individual left out of the `owl:AllDifferent` list is a dimension that can
    silently merge with another. Before v1.1 the TBox declared eight, the spec
    listed three more, and the corpus emitted six more still.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.ont = _parse("ontology/vso.ttl")
        cls.declared = {
            str(s)
            for s in cls.ont.subjects(
                rdflib.RDF.type, rdflib.URIRef(VSO_NS + "Dimension")
            )
        }

    def _all_different(self) -> set:
        """Members of the one owl:AllDifferent list that carries dimensions."""
        owl_ns = "http://www.w3.org/2002/07/owl#"
        found = []
        for node in self.ont.subjects(
            rdflib.RDF.type, rdflib.URIRef(owl_ns + "AllDifferent")
        ):
            for head in self.ont.objects(
                node, rdflib.URIRef(owl_ns + "distinctMembers")
            ):
                items = {str(i) for i in self.ont.items(head)}
                if items & self.declared:
                    found.append(items)
        self.assertEqual(
            len(found),
            1,
            msg="the dimension registry must sit in exactly one "
            "owl:AllDifferent list; found %d" % len(found),
        )
        return found[0]

    def test_every_declared_dimension_is_pairwise_distinct(self) -> None:
        declared = self.declared
        self.assertGreater(len(declared), 8, msg="registry parsed as near-empty")
        missing = sorted(declared - self._all_different())
        self.assertEqual(
            missing,
            [],
            msg=(
                "vso:Dimension individuals absent from the owl:AllDifferent "
                "list, so they can sameAs-collapse under prp-fp: %s" % missing
            ),
        )

    def test_all_different_names_no_undeclared_dimension(self) -> None:
        extra = sorted(self._all_different() - self.declared)
        self.assertEqual(
            extra,
            [],
            msg=(
                "the dimension owl:AllDifferent list names IRIs that are not "
                "declared vso:Dimension individuals: %s" % extra
            ),
        )

    def test_registry_covers_every_dimension_the_corpus_emits(self) -> None:
        # The C2 sweep above would catch these too, but only as anonymous
        # orphan IRIs. Naming the registry in the failure message is what tells
        # a contributor which list to extend.
        declared = self.declared
        dim = rdflib.URIRef(VSO_NS + "dimension")
        used = set()
        for path in _corpus():
            for _, _, obj in _emit(path).triples((None, dim, None)):
                if isinstance(obj, rdflib.URIRef) and str(obj).startswith(VSO_NS):
                    used.add(str(obj))
        self.assertGreater(len(used), 0, msg="corpus emitted no dimensions")
        self.assertEqual(
            sorted(used - declared),
            [],
            msg="corpus emits VSO dimensions the registry does not declare",
        )


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl + owlrl required")
class VacuityRegressionTests(unittest.TestCase):
    """The range-mirrored sh:class checks must be able to fail."""

    def test_control_scene_conforms(self) -> None:
        # Guards the tests below against passing for the wrong reason: the only
        # difference between this document and the bad ones is the viewer edge.
        conforms, report = validate_graph(_doc(GOOD_SCENE))
        self.assertTrue(conforms, msg=report)

    def test_physical_object_viewer_fails_shacl(self) -> None:
        # vso:viewer rdfs:range vso:CameraView, so `sh:class vso:CameraView`
        # alone is entailed and vacuous. The `sh:not [ sh:class vso:Entity ]`
        # guard on vss:DirectionalNeedsViewerShape is what rejects this.
        conforms, report = validate_graph(_doc(BAD_VIEWER_SCENE))
        self.assertFalse(
            conforms,
            msg="a SpatialFact whose vso:viewer is a PhysicalObject must not "
            "conform — the vacuity guard on vss:DirectionalNeedsViewerShape "
            "is missing or ineffective",
        )
        self.assertIn(VIEWER_GUARD_MSG, report)

    def test_physical_object_viewer_is_owl_inconsistent(self) -> None:
        # Same document, second gate: PhysicalObject ⇒ Entity by subclass while
        # the viewer range entails CameraView ⇒ Frame, and Frame is
        # owl:disjointWith Entity. clashes_for() takes any data graph, so the
        # per-document form of the gate applies here directly.
        self.assertTrue(clashes_for(_doc(BAD_VIEWER_SCENE)))
        self.assertEqual(clashes_for(_doc(GOOD_SCENE)), [])

    def test_perdurant_agent_fails_shacl(self) -> None:
        # vso:agent rdfs:range vso:Endurant — same vacuity trap, guarded by
        # sh:not against Perdurant and Frame on vss:EventShape. The agent here
        # is another Event: Endurant is entailed from the range while Perdurant
        # is asserted, and the two are disjoint.
        conforms, report = validate_graph(
            _doc(
                GOOD_SCENE
                + """
:strike a vso:Event ; vso:lemma "strike" ; vso:agent :charge .
:charge a vso:Event ; vso:lemma "charge" .
:scene vso:occurs :strike , :charge .
"""
            )
        )
        self.assertFalse(conforms)
        self.assertIn(AGENT_GUARD_MSG, report)

    def test_non_quality_persona_invariant_fails_shacl(self) -> None:
        # vso:hasInvariant rdfs:range vso:Quality. NB the guard cannot name
        # vso:Entity (Quality is rdfs:subClassOf Entity) — it names Quality's
        # disjoint siblings instead, which is what rejects this document.
        # :thing carries a dimension and a value so that vss:QualityShape is
        # satisfied and the only remaining violation is the guard under test.
        conforms, report = validate_graph(
            _doc(
                GOOD_SCENE
                + """
:alice a vso:Persona ; vso:hasInvariant :thing .
:thing a vso:PhysicalObject ; vso:dimension vso:Hair ; vso:value "auburn" .
"""
            )
        )
        self.assertFalse(conforms)
        self.assertIn(INVARIANT_GUARD_MSG, report)

    def test_entity_typed_framed_by_fails_shacl(self) -> None:
        # vso:framedBy rdfs:range vso:Frame. The target is not depicted, so
        # vss:FrameNotDepictedShape cannot fire instead of the guard.
        conforms, report = validate_graph(
            _doc(
                GOOD_SCENE
                + """
:scene vso:framedBy :backdrop .
:backdrop a vso:PhysicalObject ;
    vso:individuation vso:Generic ; vso:animacy vso:Inert ;
    vso:countability vso:Count ; vso:class :Backdrop .
"""
            )
        )
        self.assertFalse(conforms)
        self.assertIn(FRAMEDBY_GUARD_MSG, report)

    def test_perdurant_stative_experiencer_fails_shacl(self) -> None:
        conforms, report = validate_graph(
            _doc(
                GOOD_SCENE
                + """
:gaze a vso:Stative ; vso:lemma "look_at" ; vso:experiencer :charge .
:charge a vso:Event ; vso:lemma "charge" .
:scene vso:occurs :gaze , :charge .
"""
            )
        )
        self.assertFalse(conforms)
        self.assertIn(EXPERIENCER_GUARD_MSG, report)

    def test_perdurant_belief_experiencer_fails_shacl(self) -> None:
        conforms, report = validate_graph(
            _doc(
                GOOD_SCENE
                + """
:bs a vso:BeliefState ; vso:experiencer :charge ; vso:proposition :ann .
:charge a vso:Event ; vso:lemma "charge" .
:ann a vso:Annotation ;
    vso:annotatedSubject :lamp ;
    vso:annotatedPredicate vso:figure ;
    vso:annotatedObject :chair .
:scene vso:hasFact :bs , :ann ; vso:occurs :charge .
"""
            )
        )
        self.assertFalse(conforms)
        self.assertIn(BELIEF_EXPERIENCER_GUARD_MSG, report)

    def test_well_typed_persona_invariant_conforms(self) -> None:
        conforms, report = validate_graph(
            _doc(
                GOOD_SCENE
                + """
:alice a vso:Persona ;
    vso:hasInvariant [ a vso:Quality ; vso:dimension vso:Hair ; vso:value "auburn" ] .
:chair vso:embodies :alice .
"""
            )
        )
        self.assertTrue(conforms, msg=report)


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl + owlrl required")
class RelaxedProfileDriftTests(unittest.TestCase):
    """The two claims in the relaxed file's own header, made testable."""

    def test_same_shape_set_as_strict(self) -> None:
        strict = _vss_node_shapes(STRICT_SHAPES)
        relaxed = _vss_node_shapes(RELAXED_SHAPES)
        self.assertEqual(
            strict,
            relaxed,
            msg=(
                "shapes/vson-shapes-relaxed.ttl claims to carry the same shapes "
                "as the strict profile. Missing from relaxed: "
                f"{sorted(strict - relaxed)}; extra in relaxed: "
                f"{sorted(relaxed - strict)}"
            ),
        )
        self.assertIn("CompositionShape", strict)  # non-empty sanity check

    def test_strict_conforming_corpus_also_conforms_relaxed(self) -> None:
        for path in _corpus():
            rel = os.path.relpath(path, ROOT)
            with self.subTest(document=rel):
                data = _emit(path)
                strict_ok, strict_report = validate_graph(data)
                self.assertTrue(strict_ok, msg=strict_report)
                relaxed_ok, relaxed_report = _validate_relaxed(data)
                self.assertTrue(
                    relaxed_ok,
                    msg=(
                        f"{rel} conforms under strict but not under relaxed — "
                        "the relaxed profile made some shape stricter.\n"
                        + relaxed_report
                    ),
                )

    def test_relaxed_still_rejects_structural_errors(self) -> None:
        # The relaxed profile downgrades completeness constraints only; the
        # structural floor (here: a Composition with no vso:depicts) stays a
        # Violation, so "relaxed" never degenerates into "accepts anything".
        conforms, _ = _validate_relaxed(
            _doc(
                "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n"
                "@prefix : <https://example.org/scenes/gate#> .\n"
                ":scene a vso:Composition ; vso:framedBy :cam .\n"
                ":cam a vso:CameraView .\n"
            )
        )
        self.assertFalse(conforms)


if __name__ == "__main__":
    unittest.main()
