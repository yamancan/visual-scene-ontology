"""
Round-trip and parse tests for the VSON-P transpiler.

Run: python3 -m unittest tests.test_penman_roundtrip
or:  python3 tests/test_penman_roundtrip.py
"""

from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "penman"))

import vson_penman as vp  # noqa: E402


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


class EmitterTests(unittest.TestCase):
    def test_concept_emits_rdf_type(self) -> None:
        ttl = vp.to_turtle("(a / PhysicalObject)")
        self.assertIn("a <https://vson.dev/v1/ontology#PhysicalObject>", ttl)

    def test_role_iri(self) -> None:
        ttl = vp.to_turtle("(a / Event :agent (b / PhysicalObject))")
        self.assertIn("<https://vson.dev/v1/ontology#agent>", ttl)

    def test_allen_routing(self) -> None:
        ttl = vp.to_turtle(
            "(c / Composition :temporal (e1 :before e2))"
        )
        self.assertIn("<https://vson.dev/v1/allen#before>", ttl)

    def test_rcc_routing(self) -> None:
        ttl = vp.to_turtle(
            "(c / Composition :depicts (sf / SpatialFact :rcc EC))"
        )
        self.assertIn("<https://vson.dev/v1/rcc8#EC>", ttl)


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
        self.assertIn("a <https://vson.dev/v1/ontology#Event>", ttl)
        self.assertIn("a <https://vson.dev/v1/ontology#Stative>", ttl)
        self.assertIn("a <https://vson.dev/v1/ontology#SpatialFact>", ttl)
        self.assertIn("a <https://vson.dev/v1/ontology#CameraView>", ttl)
        self.assertIn("a <https://vson.dev/v1/ontology#VisualStyle>", ttl)
        self.assertIn("a <https://vson.dev/v1/ontology#SceneContext>", ttl)
        self.assertIn("a <https://vson.dev/v1/ontology#Composition>", ttl)
        # Trait properties
        self.assertIn("<https://vson.dev/v1/ontology#individuation>", ttl)
        self.assertIn("<https://vson.dev/v1/ontology#animacy>", ttl)
        # Causation and temporal
        self.assertIn("<https://vson.dev/v1/ontology#causes>", ttl)
        self.assertIn("<https://vson.dev/v1/allen#before>", ttl)
        # SpatialFact viewer (Talmy resolution)
        self.assertIn("<https://vson.dev/v1/ontology#viewer>", ttl)


if __name__ == "__main__":
    unittest.main()
