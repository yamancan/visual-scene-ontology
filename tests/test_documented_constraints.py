"""The constraints docs/vson.md states, and the shapes that carry them.

`vso:bbox2d "banana"` and `vso:confidence "7.3"` were conformant VSON through
v1.2 — not because the specification permitted them, but because the value
spaces §5.4, §5.6, §5.10 and §5.11 define had never been transcribed into a
shape. docs/vson.md §8.2 governs closing a gap like that inside v1.x: the new
check may reject only documents the specification already declared
non-conformant, and it must not fire on a document the specification permits.

Four properties are gated here, none of which any other test file covers:

  (a) Every constraint the v1.3 sweep added still exists, in both profiles, and
      still cites the clause that authorizes it. SWEEP below is the inventory —
      a shape deleted, a message reworded past its citation, or a constraint
      that never reached the relaxed profile all fail here.

  (b) The `vso:bbox2d` pattern is byte-identical to the one
      tools/schema/vson-output.schema.json publishes. Two artifacts stating one
      regular expression is a copy, and copies drift (§2: the higher-ranked
      artifact wins, so a drifted shape is the bug).

  (c) The OWL characteristics table in docs/vson.md §5.8 is what ontology/vso.ttl
      declares — parsed out of the document, not restated here, so editing
      either side without the other fails.

  (d) A document that uses every one of these value spaces correctly still
      conforms, under both profiles. Without this control, (a) would pass just
      as well if the shapes rejected everything.

Run: python3 -m unittest tests.test_documented_constraints

Skipped automatically if rdflib / pyshacl are not installed.
"""

from __future__ import annotations

import json
import os
import re
import unittest

try:
    import pyshacl
    import rdflib

    from tools.shacl_helper import ONTOLOGY_FILES, ROOT, validate_graph
except ImportError:  # pragma: no cover — dependency probe for the skip guards
    pyshacl = None
    rdflib = None
    ONTOLOGY_FILES = ()
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    validate_graph = None

SH = "http://www.w3.org/ns/shacl#"
VSO_NS = "https://w3id.org/vson/v1/ontology#"
VSS_NS = "https://w3id.org/vson/v1/shapes#"
OWL_NS = "http://www.w3.org/2002/07/owl#"

STRICT_SHAPES = "shapes/vson-shapes.ttl"
RELAXED_SHAPES = "shapes/vson-shapes-relaxed.ttl"
OUTPUT_SCHEMA = "tools/schema/vson-output.schema.json"
SPEC = "docs/vson.md"

_HAVE_DEPS = bool(rdflib and pyshacl and validate_graph)

# --------------------------------------------------------------------------
# The inventory. One row per constraint the v1.3 value-space sweep added:
#
#   (node shape, property path, SHACL component, citation the message must carry)
#
# "citation" is the authorizing clause required by §8.2 — a numbered conformance
# clause (C5, C6) or the §5 subsection that defines the value space. It has to
# appear in the sh:message of the property shape carrying the constraint, so a
# reader who sees a violation can check the authorization without leaving the
# report. Rewording a message is fine; dropping its citation is not.
# --------------------------------------------------------------------------
SWEEP = (
    ("GeometryShape", "bbox2d", "pattern", "§5.4"),
    ("GeometryShape", "bbox2d", "datatype", "§5.4"),
    ("GeometryShape", "bbox2d", "maxCount", "§5.4"),
    ("GeometryShape", "position3d", "pattern", "§5.10"),
    ("GeometryShape", "scale3d", "pattern", "§5.10"),
    ("GeometryShape", "rotation", "pattern", "§5.10"),
    ("ConfidenceRangeShape", "probability", "minInclusive", "§5.11"),
    ("ConfidenceRangeShape", "probability", "maxInclusive", "§5.11"),
    ("ConfidenceRangeShape", "confidence", "minInclusive", "§5.11"),
    ("ConfidenceRangeShape", "confidence", "maxInclusive", "§5.11"),
    ("ConfidenceRangeShape", "visibleFraction", "minInclusive", "§5.10"),
    ("ConfidenceRangeShape", "visibleFraction", "maxInclusive", "§5.10"),
    ("LemmaShape", "lemma", "pattern", "§5.6"),
    ("EntityClassShape", "class", "maxCount", "§5.4"),
    ("CompositionShape", "viewedBy", "maxCount", "§5.2"),
    ("CompositionShape", "rendersAs", "maxCount", "§5.2"),
    ("SpatialFactShape", "rcc", "maxCount", "§5.7"),
    ("SpatialFactShape", "directional", "maxCount", "§5.7"),
    ("SpatialFactShape", "proximal", "maxCount", "§5.7"),
    ("DirectionalNeedsViewerShape", "viewer", "maxCount", "C5"),
    ("ProcessShape", "lemma", "maxCount", "C6"),
    ("StativeShape", "lemma", "maxCount", "C6"),
    ("EventShape", "lemma", "maxCount", "C6"),
)

# A scene exercising every value space the sweep constrains, all of it valid.
GOOD_VALUE_SPACES = """
@prefix vso: <https://w3id.org/vson/v1/ontology#> .
@prefix rcc: <https://w3id.org/vson/v1/rcc8#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix :    <https://example.org/scenes/values#> .

:scene a vso:Composition ;
    vso:framedBy :cam ; vso:viewedBy :cam ; vso:rendersAs :style ;
    vso:framedBy :style ;
    vso:depicts :lamp , :chair ;
    vso:hasFact :sf , :ann ;
    vso:occurs :burn , :hold .

:cam   a vso:CameraView  ; vso:angle "eye_level" ; vso:framing "wide_shot" .
:style a vso:VisualStyle ; vso:aesthetic "photographic" .

:lamp a vso:PhysicalObject ;
    vso:individuation vso:Generic ; vso:animacy vso:Inert ;
    vso:countability vso:Count ; vso:class :Lamp ;
    vso:bbox2d "0.10,0.60,0.80,0.30" ;
    vso:position3d "1.5,-2,3e-4" ;
    vso:scale3d "1,1,1" ;
    vso:rotation "0,0,0,1" ;
    vso:occludes :chair .

:chair a vso:PhysicalObject ;
    vso:individuation vso:Generic ; vso:animacy vso:Inert ;
    vso:countability vso:Count ; vso:class :Furniture ;
    vso:bbox2d "0,0,1,1" ;
    vso:rotation "0,0,0" ;
    vso:visibleFraction "0.4"^^xsd:decimal .

:sf a vso:SpatialFact ;
    vso:figure :lamp ; vso:ground :chair ;
    vso:rcc rcc:PO ; vso:directional vso:above ; vso:proximal vso:near ;
    vso:viewer :cam .

:ann a vso:Annotation ;
    vso:annotatedSubject :sf ; vso:annotatedPredicate vso:directional ;
    vso:annotatedObject vso:above ;
    vso:confidence "0.85"^^xsd:decimal ;
    vso:probability "1"^^xsd:integer .

:burn a vso:Process ; vso:lemma "burn" .
:hold a vso:Stative ; vso:lemma "look_at" ; vso:experiencer :chair .
"""

_CACHE: dict = {}


def _graph(rel_path: str) -> "rdflib.Graph":
    if rel_path not in _CACHE:
        g = rdflib.Graph()
        g.parse(os.path.join(ROOT, rel_path), format="turtle")
        _CACHE[rel_path] = g
    return _CACHE[rel_path]


def _ontology() -> "rdflib.Graph":
    if "__ont__" not in _CACHE:
        g = rdflib.Graph()
        for f in ONTOLOGY_FILES:
            g.parse(os.path.join(ROOT, f), format="turtle")
        _CACHE["__ont__"] = g
    return _CACHE["__ont__"]


def _read(rel_path: str) -> str:
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as fh:
        return fh.read()


def _property_shapes(g: "rdflib.Graph", shape: str, path: str) -> list:
    """Every property shape of `vss:<shape>` whose sh:path is `vso:<path>`."""
    node = rdflib.URIRef(VSS_NS + shape)
    out = []
    for ps in g.objects(node, rdflib.URIRef(SH + "property")):
        if (ps, rdflib.URIRef(SH + "path"), rdflib.URIRef(VSO_NS + path)) in g:
            out.append(ps)
    return out


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class SweepInventoryTests(unittest.TestCase):
    """Every constraint the sweep added, in both profiles, still citing its clause."""

    def test_every_swept_constraint_is_present_and_cited(self) -> None:
        for profile in (STRICT_SHAPES, RELAXED_SHAPES):
            g = _graph(profile)
            for shape, path, component, citation in SWEEP:
                with self.subTest(profile=profile, shape=shape, path=path, component=component):
                    shapes = _property_shapes(g, shape, path)
                    self.assertTrue(
                        shapes,
                        msg=f"{profile}: vss:{shape} has no property shape on vso:{path}",
                    )
                    carriers = [
                        ps
                        for ps in shapes
                        if (ps, rdflib.URIRef(SH + component), None) in g
                    ]
                    self.assertTrue(
                        carriers,
                        msg=(
                            f"{profile}: no property shape of vss:{shape} on "
                            f"vso:{path} carries sh:{component}"
                        ),
                    )
                    messages = [
                        str(m)
                        for ps in carriers
                        for m in g.objects(ps, rdflib.URIRef(SH + "message"))
                    ]
                    self.assertTrue(
                        any(citation in m for m in messages),
                        msg=(
                            f"{profile}: the sh:message for vss:{shape} / "
                            f"vso:{path} / sh:{component} must cite {citation} "
                            f"(docs/vson.md §8.2 requires the authorizing clause "
                            f"on the shape). Found: {messages}"
                        ),
                    )

    def test_value_space_constraints_match_across_profiles(self) -> None:
        # The rule shapes/vson-shapes-relaxed.ttl states in its header: a value
        # space is a value space in both profiles. Only *completeness*
        # (sh:minCount) is downgraded there, so no constraint listed in SWEEP
        # may carry sh:severity sh:Warning in the relaxed file.
        g = _graph(RELAXED_SHAPES)
        warning = rdflib.URIRef(SH + "Warning")
        for shape, path, component, _ in SWEEP:
            with self.subTest(shape=shape, path=path, component=component):
                for ps in _property_shapes(g, shape, path):
                    if (ps, rdflib.URIRef(SH + component), None) not in g:
                        continue
                    self.assertNotIn(
                        warning,
                        set(g.objects(ps, rdflib.URIRef(SH + "severity"))),
                        msg=(
                            f"vss:{shape} / vso:{path} / sh:{component} is a "
                            "value-space or integrity constraint and must not be "
                            "downgraded in the relaxed profile"
                        ),
                    )


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class BboxPatternParityTests(unittest.TestCase):
    """One regular expression, published twice."""

    def _schema_pattern(self) -> str:
        with open(os.path.join(ROOT, OUTPUT_SCHEMA), encoding="utf-8") as fh:
            schema = json.load(fh)
        return schema["$defs"]["GraphNode"]["properties"]["bbox2d"]["pattern"]

    def test_shape_pattern_is_byte_identical_to_the_schema(self) -> None:
        expected = self._schema_pattern()
        for profile in (STRICT_SHAPES, RELAXED_SHAPES):
            g = _graph(profile)
            patterns = [
                str(p)
                for ps in _property_shapes(g, "GeometryShape", "bbox2d")
                for p in g.objects(ps, rdflib.URIRef(SH + "pattern"))
            ]
            with self.subTest(profile=profile):
                self.assertEqual(
                    patterns,
                    [expected],
                    msg=(
                        f"{profile} and {OUTPUT_SCHEMA} state different bbox2d "
                        "patterns. docs/vson.md §5.4 quotes the schema's; the "
                        "shape must match it exactly."
                    ),
                )

    def test_the_documented_pattern_is_the_normalized_one(self) -> None:
        # Guards the units decision itself: a pattern that admits "120,44,300,220"
        # would satisfy the parity test above if both copies drifted together.
        pattern = re.compile(self._schema_pattern())
        self.assertTrue(pattern.match("0.10,0.60,0.80,0.30"))
        self.assertTrue(pattern.match("0,0,1,1"))
        self.assertFalse(pattern.match("120,44,300,220"))
        self.assertFalse(pattern.match("banana"))


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class OwlCharacteristicsTableTests(unittest.TestCase):
    """docs/vson.md §5.8's OWL-characteristics column, pinned to the TBox.

    The table has published `vso:properPartOf` as irreflexive since v1.0; the
    ontology first asserted it in v1.3. Rows are read out of the document, so
    the pin follows the table instead of restating it.
    """

    KEYWORDS = {
        "owl:TransitiveProperty": OWL_NS + "TransitiveProperty",
        "transitive": OWL_NS + "TransitiveProperty",
        "irreflexive": OWL_NS + "IrreflexiveProperty",
        "symmetric": OWL_NS + "SymmetricProperty",
    }

    def _rows(self) -> "list[tuple[str, str]]":
        """(local name, characteristics cell) for every row of the §5.8 table."""
        text = _read(SPEC)
        start = text.index("### 5.8 Mereology")
        end = text.index("### 5.9", start)
        rows = []
        for line in text[start:end].split("\n"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 3 or not cells[0].startswith("`vso:"):
                continue
            rows.append((cells[0].strip("`").split(":")[1], cells[2]))
        return rows

    def test_the_table_has_the_five_mereology_rows(self) -> None:
        self.assertEqual(
            [name for name, _ in self._rows()],
            ["partOf", "hasPart", "properPartOf", "overlaps", "disjoint"],
        )

    def test_every_documented_characteristic_is_asserted(self) -> None:
        ont = _graph("ontology/vso.ttl")
        for name, cell in self._rows():
            prop = rdflib.URIRef(VSO_NS + name)
            types = set(ont.objects(prop, rdflib.RDF.type))
            for keyword, iri in self.KEYWORDS.items():
                if keyword not in cell:
                    continue
                with self.subTest(property=name, characteristic=keyword):
                    self.assertIn(
                        rdflib.URIRef(iri),
                        types,
                        msg=(
                            f"docs/vson.md §5.8 documents vso:{name} as {keyword}; "
                            "ontology/vso.ttl does not declare it"
                        ),
                    )
            for other in re.findall(r"inverse of `(\w+)`", cell):
                target = rdflib.URIRef(VSO_NS + other)
                with self.subTest(property=name, inverse=other):
                    self.assertTrue(
                        (prop, rdflib.URIRef(OWL_NS + "inverseOf"), target) in ont
                        or (target, rdflib.URIRef(OWL_NS + "inverseOf"), prop) in ont,
                        msg=f"§5.8 documents vso:{name} as the inverse of vso:{other}",
                    )
            for parent in re.findall(r"sub-property of `(\w+)`", cell):
                with self.subTest(property=name, parent=parent):
                    self.assertIn(
                        rdflib.URIRef(VSO_NS + parent),
                        set(ont.objects(prop, rdflib.RDFS.subPropertyOf)),
                        msg=f"§5.8 documents vso:{name} as a sub-property of vso:{parent}",
                    )

    def test_irreflexivity_is_checked_and_not_merely_declared(self) -> None:
        # owlrl 7.1.4 materializes nothing from owl:IrreflexiveProperty (prp-irp's
        # head is a contradiction, which has nowhere to go in an RDF closure), so
        # tools/owlrl_check.py checks it directly. Without this test the axiom
        # would be a declaration no gate reads.
        from tools.owlrl_check import clashes_for

        head = (
            "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n"
            "@prefix : <https://example.org/scenes/irp#> .\n"
            ":c a vso:Composition ; vso:depicts :a , :b .\n"
            ":a a vso:PhysicalObject .\n:b a vso:PhysicalObject .\n"
        )

        def clashes(body: str) -> list:
            g = rdflib.Graph()
            g.parse(data=head + body, format="turtle")
            return clashes_for(g)

        self.assertEqual(clashes(":a vso:properPartOf :b .\n"), [])
        self.assertTrue(clashes(":a vso:properPartOf :a .\n"))
        # A two-step cycle is only reflexive after transitivity is materialized.
        self.assertTrue(
            clashes(":a vso:properPartOf :b . :b vso:properPartOf :a .\n")
        )


@unittest.skipUnless(_HAVE_DEPS, "rdflib + pyshacl required")
class PositiveControlTests(unittest.TestCase):
    """The sweep constrains value spaces; it does not forbid using them."""

    def _doc(self) -> "rdflib.Graph":
        g = rdflib.Graph()
        g.parse(data=GOOD_VALUE_SPACES, format="turtle")
        return g

    def test_every_value_space_used_correctly_conforms_strict(self) -> None:
        conforms, report = validate_graph(self._doc())
        self.assertTrue(conforms, msg=report)

    def test_every_value_space_used_correctly_conforms_relaxed(self) -> None:
        conforms, _, report = pyshacl.validate(
            self._doc(),
            shacl_graph=_graph(RELAXED_SHAPES),
            ont_graph=_ontology(),
            inference="rdfs",
            abort_on_first=False,
            allow_warnings=True,
        )
        self.assertTrue(conforms, msg=report)


if __name__ == "__main__":
    unittest.main()
