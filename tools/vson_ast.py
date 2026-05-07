"""
Shared AST types for VSON concrete-syntax parsers.

This module is the single source of truth for the abstract syntax tree
shape that any VSON parser produces. Both the existing Penman reference
(tools/penman/vson_penman.py) and the upcoming VSON-X parser
(tools/vson_x/) consume and produce these types so they share the same
emitter pipeline (AST -> Turtle) without divergence.

The types here are deliberately minimal and free of I/O — they're pure
dataclasses. Tokenizers, parsers, and emitters live in their respective
syntax-specific modules.

Phase B Week B1 deliverable per the v1.1 plan: extract format-agnostic
types into a shared module so VSON-X can plug in without copying or
re-implementing the AST.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union


@dataclass
class Ref:
    """A reference to a previously-declared node, by variable name."""

    var: str


@dataclass
class Lit:
    """A literal value: string, number, or unit-typed token (e.g. '35mm')."""

    value: str
    is_string: bool = False
    is_number: bool = False


@dataclass
class Node:
    """A reified node with a variable identifier and zero or more typed edges.

    `concept` is the optional concept (class) name that follows the `/`
    sigil in Penman or the analogous declaration in other surface forms.
    `edges` is the ordered list of (role-name, target) pairs the node
    bears; targets are themselves Term values (Node, Ref, or Lit).
    """

    var: str
    concept: Optional[str]
    edges: List[Tuple[str, "Term"]] = field(default_factory=list)


# Recursive type alias: a Term is either a nested Node, a back-reference,
# or a literal.
Term = Union[Node, Ref, Lit]


@dataclass
class Triple:
    """A single RDF triple (subject, predicate, object) as N-Triples-style
    tokens. The fields hold their fully-rendered IRI / literal forms so
    `render()` can simply join them.
    """

    s: str
    p: str
    o: str

    def render(self) -> str:
        return f"{self.s} {self.p} {self.o} ."


__all__ = ["Ref", "Lit", "Node", "Term", "Triple"]
