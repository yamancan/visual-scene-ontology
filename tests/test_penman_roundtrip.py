"""
Round-trip and parse tests for the VSON-P transpiler.

Run from the repo root: python3 -m unittest tests.test_penman_roundtrip
"""

from __future__ import annotations

import os
import unittest

from tools.penman import vson_penman as vp

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(name: str) -> str:
    with open(os.path.join(ROOT, "examples", name), "r", encoding="utf-8") as f:
        return f.read()


class TokenizerTests(unittest.TestCase):
    def test_smoke(self) -> None:
        toks = vp.tokenize("(a / Foo :bar baz)")
        kinds = [t.kind for t in toks]
        self.assertEqual(kinds, ["(", "ID", "/", "ID", "ROLE", "ID", ")"])

    def test_strings_and_numbers(self) -> None:
        toks = vp.tokenize('(a / Foo :name "Alice" :age 30)')
        # ( a / Foo :name "Alice" :age 30 )
        # 0 1 2 3   4     5       6    7  8
        self.assertEqual(toks[4].kind, "ROLE")
        self.assertEqual(toks[4].value, "name")
        self.assertEqual(toks[5].kind, "STR")
        self.assertEqual(toks[5].value, "Alice")
        self.assertEqual(toks[7].kind, "NUM")
        self.assertEqual(toks[7].value, "30")

    def test_unit_literal(self) -> None:
        toks = vp.tokenize("(c / CameraView :focalLength 35mm)")
        unit = [t for t in toks if t.kind == "UNIT"]
        self.assertEqual(len(unit), 1)
        self.assertEqual(unit[0].value, "35mm")

    def test_comment_skipped(self) -> None:
        toks = vp.tokenize("# leading\n(a / Foo) # trailing")
        kinds = [t.kind for t in toks]
        self.assertEqual(kinds, ["(", "ID", "/", "ID", ")"])

    def test_string_escapes_decoded(self) -> None:
        # \n / \t / \" decode to the true characters at lex time, so the token
        # carries the real string value (re-encoded for Turtle at emit time).
        toks = vp.tokenize(r'(a / Foo :name "x\ny\t\"z\"")')
        s = [t for t in toks if t.kind == "STR"][0]
        self.assertEqual(s.value, 'x\ny\t"z"')

    def test_unknown_escape_keeps_backslash(self) -> None:
        # An escape outside the closed Turtle ECHAR set keeps its backslash
        # verbatim rather than silently dropping it ("C:\path" stays intact).
        toks = vp.tokenize(r'(a / Foo :path "C:\path")')
        s = [t for t in toks if t.kind == "STR"][0]
        self.assertEqual(s.value, r"C:\path")


class ParserTests(unittest.TestCase):
    def test_simple_node(self) -> None:
        # Bare ID in target position is a Ref (potentially reentrant or
        # constant — distinguished at emit time).
        ast = vp.parse("(a / Foo :bar baz)")
        self.assertEqual(ast.var, "a")
        self.assertEqual(ast.concept, "Foo")
        self.assertEqual(len(ast.edges), 1)
        role, target = ast.edges[0]
        self.assertEqual(role, "bar")
        self.assertIsInstance(target, vp.Ref)
        self.assertEqual(target.var, "baz")

    def test_nested(self) -> None:
        ast = vp.parse("(a / Foo :child (b / Bar :name \"x\"))")
        self.assertEqual(len(ast.edges), 1)
        role, child = ast.edges[0]
        self.assertEqual(role, "child")
        self.assertIsInstance(child, vp.Node)
        self.assertEqual(child.concept, "Bar")

    def test_trailing_tokens_rejected(self) -> None:
        # A well-formed top-level node followed by more tokens is malformed,
        # not silently truncated.
        with self.assertRaises(SyntaxError):
            vp.parse("(a / Foo) (b / Bar)")


class EmitterTests(unittest.TestCase):
    def test_concept_emits_rdf_type(self) -> None:
        ttl = vp.to_turtle("(a / PhysicalObject)")
        self.assertIn("a <https://w3id.org/vson/v1/ontology#PhysicalObject>", ttl)

    def test_role_iri(self) -> None:
        ttl = vp.to_turtle("(a / Event :agent (b / PhysicalObject))")
        self.assertIn("<https://w3id.org/vson/v1/ontology#agent>", ttl)

    def test_allen_routing(self) -> None:
        ttl = vp.to_turtle(
            "(c / Composition :temporal (e1 :before e2))"
        )
        self.assertIn("<https://w3id.org/vson/v1/allen#before>", ttl)

    def test_rcc_routing(self) -> None:
        ttl = vp.to_turtle(
            "(c / Composition :depicts (sf / SpatialFact :rcc EC))"
        )
        self.assertIn("<https://w3id.org/vson/v1/rcc8#EC>", ttl)

    def test_string_escapes_emit_valid_turtle(self) -> None:
        # A source `\n` round-trips through emit as a Turtle escape, never a raw
        # newline (which would be unparseable Turtle). Parity guard for the
        # decode-at-lex / encode-at-emit pipeline.
        ttl = vp.to_turtle(r'(s / SceneContext :venue "a\nb")')
        self.assertIn(r'"a\nb"', ttl)
        self.assertNotIn('"a\nb"', ttl)  # no raw newline inside the literal
        import rdflib

        g = rdflib.Graph()
        g.parse(data=ttl, format="turtle")  # must not raise
        val = [str(o) for s, p, o in g if "venue" in str(p)][0]
        self.assertEqual(val, "a\nb")

    def test_unknown_escape_round_trips_through_turtle(self) -> None:
        # A literal backslash (from an unknown source escape) emits as a Turtle
        # \\ and parses back to the original bytes — no silent corruption.
        ttl = vp.to_turtle(r'(s / SceneContext :venue "C:\path")')
        import rdflib

        g = rdflib.Graph()
        g.parse(data=ttl, format="turtle")  # must not raise
        val = [str(o) for s, p, o in g if "venue" in str(p)][0]
        self.assertEqual(val, r"C:\path")

    def test_underscore_var_is_blank_node(self) -> None:
        # '_'-prefixed vars become blank nodes; the full var is the injective
        # label (no lstrip collapse, no empty label).
        ttl = vp.to_turtle("(s / Composition :hasFact (_sf / SpatialFact :rcc EC))")
        self.assertIn("_:_sf a ", ttl)
        self.assertFalse(any(ln.startswith(":_sf") for ln in ttl.splitlines()))


class ThroneRoomTests(unittest.TestCase):
    def test_throne_room_parses(self) -> None:
        src = read("throne_room.vson")
        ast = vp.parse(src)
        self.assertEqual(ast.concept, "Composition")
        # Must have at least one :depicts edge per VSON-S CompositionShape
        depicts = [r for r, _ in ast.edges if r == "depicts"]
        self.assertGreaterEqual(len(depicts), 1)

    def test_throne_room_emits_turtle(self) -> None:
        src = read("throne_room.vson")
        ttl = vp.to_turtle(src)
        # Spot checks: critical reified nodes are present
        self.assertIn("a <https://w3id.org/vson/v1/ontology#Event>", ttl)
        self.assertIn("a <https://w3id.org/vson/v1/ontology#Stative>", ttl)
        self.assertIn("a <https://w3id.org/vson/v1/ontology#SpatialFact>", ttl)
        self.assertIn("a <https://w3id.org/vson/v1/ontology#CameraView>", ttl)
        self.assertIn("a <https://w3id.org/vson/v1/ontology#VisualStyle>", ttl)
        self.assertIn("a <https://w3id.org/vson/v1/ontology#SceneContext>", ttl)
        self.assertIn("a <https://w3id.org/vson/v1/ontology#Composition>", ttl)
        # Trait properties
        self.assertIn("<https://w3id.org/vson/v1/ontology#individuation>", ttl)
        self.assertIn("<https://w3id.org/vson/v1/ontology#animacy>", ttl)
        # Causation and temporal
        self.assertIn("<https://w3id.org/vson/v1/ontology#causes>", ttl)
        self.assertIn("<https://w3id.org/vson/v1/allen#before>", ttl)
        # SpatialFact viewer (Talmy resolution)
        self.assertIn("<https://w3id.org/vson/v1/ontology#viewer>", ttl)


if __name__ == "__main__":
    unittest.main()
