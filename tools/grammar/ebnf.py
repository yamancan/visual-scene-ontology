#!/usr/bin/env python3
"""A parser for the EBNF dialect `docs/vson.md` §D.1 defines.

§D.1 is short enough to quote in full: `{ x }` is zero or more `x`; `[ x ]` is
an optional `x`; `|` is alternation; `A - B` is set difference; `"…"` is a
literal, in either quote style; `"a".."z"` is a character range; `? … ?` is a
character set named in prose; `(* … *)` is a comment. UPPERCASE names are
terminals produced by the lexer, lowercase names are syntactic productions.

Two details §D.1 leaves implicit, and this parser fixes:

  * **Literals do not escape.** A literal runs from its opening quote to the
    next occurrence of the same quote character, with no escape convention —
    which is exactly why §D.2 writes the backslash as `"\\"` and the double
    quote as `'"'`, each in the quote style that does not collide.
  * **Precedence.** Tightest first: a range binds tighter than a difference,
    a difference tighter than concatenation, and concatenation tighter than
    alternation. Every use in the spec is unambiguous under that reading, and
    `A - B | C` never appears.

Nothing here knows what VSON is. It turns a block of §D.1 notation into a tree;
`lark_backend` and `gbnf_backend` turn that tree into something that runs.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


class EbnfError(Exception):
    """The block is not §D.1 notation."""


# ---------------------------------------------------------------------------
# Expression tree
# ---------------------------------------------------------------------------


class Expr:
    """Base of the expression tree. Subclasses compare by value."""

    _fields: Tuple[str, ...] = ()

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return all(getattr(self, f) == getattr(other, f) for f in self._fields)

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self) -> int:
        return hash((type(self).__name__,) + tuple(
            tuple(getattr(self, f)) if isinstance(getattr(self, f), list)
            else getattr(self, f)
            for f in self._fields
        ))

    def __repr__(self) -> str:
        args = ", ".join(repr(getattr(self, f)) for f in self._fields)
        return "%s(%s)" % (type(self).__name__, args)


class Ref(Expr):
    """A reference to another production."""

    _fields = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


class Lit(Expr):
    """A literal string."""

    _fields = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text


class Special(Expr):
    """A `? … ?` character set, named in prose."""

    _fields = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text


class Range(Expr):
    """`"a".."z"` — an inclusive character range."""

    _fields = ("lo", "hi")

    def __init__(self, lo: str, hi: str) -> None:
        if len(lo) != 1 or len(hi) != 1:
            raise EbnfError("a range bound must be one character: %r..%r" % (lo, hi))
        self.lo, self.hi = lo, hi


class Diff(Expr):
    """`A - B` — set difference."""

    _fields = ("left", "right")

    def __init__(self, left: Expr, right: Expr) -> None:
        self.left, self.right = left, right


class Seq(Expr):
    """Concatenation."""

    _fields = ("items",)

    def __init__(self, items: List[Expr]) -> None:
        self.items = items


class Alt(Expr):
    """Alternation."""

    _fields = ("items",)

    def __init__(self, items: List[Expr]) -> None:
        self.items = items


class Opt(Expr):
    """`[ x ]`."""

    _fields = ("item",)

    def __init__(self, item: Expr) -> None:
        self.item = item


class Rep(Expr):
    """`{ x }`."""

    _fields = ("item",)

    def __init__(self, item: Expr) -> None:
        self.item = item


class Grammar:
    """An ordered set of productions.

    `order` preserves the document order the spec wrote them in, which is what
    picks the start symbol: the first lowercase production of the block.
    """

    def __init__(self) -> None:
        self.rules: Dict[str, Expr] = {}
        self.order: List[str] = []

    def add(self, name: str, expr: Expr) -> None:
        if name in self.rules:
            raise EbnfError("production %r is declared twice" % name)
        self.rules[name] = expr
        self.order.append(name)

    def replace(self, name: str, expr: Expr) -> None:
        if name not in self.rules:
            raise EbnfError("production %r is not declared" % name)
        self.rules[name] = expr

    @staticmethod
    def is_terminal(name: str) -> bool:
        """§D.1: UPPERCASE names are terminals, lowercase are productions."""
        return name.upper() == name

    def terminals(self) -> List[str]:
        return [n for n in self.order if self.is_terminal(n)]

    def productions(self) -> List[str]:
        return [n for n in self.order if not self.is_terminal(n)]

    def start(self) -> str:
        for name in self.order:
            if not self.is_terminal(name):
                return name
        raise EbnfError("the block declares no syntactic production")

    def refs(self, expr: Expr) -> List[str]:
        """Every production name `expr` mentions, in order, with repeats."""
        out: List[str] = []

        def walk(e: Expr) -> None:
            if isinstance(e, Ref):
                out.append(e.name)
            elif isinstance(e, (Seq, Alt)):
                for item in e.items:
                    walk(item)
            elif isinstance(e, (Opt, Rep)):
                walk(e.item)
            elif isinstance(e, Diff):
                walk(e.left)
                walk(e.right)

        walk(expr)
        return out

    def reachable(self, start: Optional[str] = None) -> List[str]:
        """Production names reachable from `start`, in first-seen order."""
        seen: List[str] = []
        stack = [start or self.start()]
        while stack:
            name = stack.pop(0)
            if name in seen:
                continue
            if name not in self.rules:
                raise EbnfError("production %r is used but never declared" % name)
            seen.append(name)
            stack.extend(self.refs(self.rules[name]))
        return seen


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
      (?P<comment>\(\*.*?\*\))
    | (?P<special>\?[^?]*\?)
    | (?P<dotdot>\.\.)
    | (?P<punct>[=;|\-()\[\]{}])
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    | '(?P<sq>[^']*)'
    | "(?P<dq>[^"]*)"
    | (?P<space>\s+)
    | (?P<bad>\S)
    """,
    re.VERBOSE | re.DOTALL,
)


def _tokens(src: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for m in _TOKEN_RE.finditer(src):
        kind = m.lastgroup
        if kind in ("comment", "space"):
            continue
        if kind == "bad":
            raise EbnfError("unexpected character %r in the EBNF block" % m.group(0))
        if kind == "sq" or kind == "dq":
            out.append(("LIT", m.group(kind)))
        elif kind == "special":
            out.append(("SPECIAL", m.group(0)[1:-1].strip()))
        elif kind == "dotdot":
            out.append(("..", ".."))
        elif kind == "punct":
            out.append((m.group(0), m.group(0)))
        else:
            out.append(("NAME", m.group(0)))
    return out


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, toks: List[Tuple[str, str]]) -> None:
        self.toks = toks
        self.i = 0

    def peek(self) -> Optional[Tuple[str, str]]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, kind: str) -> str:
        tok = self.peek()
        if tok is None or tok[0] != kind:
            raise EbnfError("expected %s, got %r" % (kind, tok))
        self.i += 1
        return tok[1]

    def eat(self, kind: str) -> bool:
        tok = self.peek()
        if tok is not None and tok[0] == kind:
            self.i += 1
            return True
        return False

    def grammar(self) -> Grammar:
        g = Grammar()
        while self.peek() is not None:
            name = self.take("NAME")
            self.take("=")
            g.add(name, self.expr())
            self.take(";")
        return g

    def expr(self) -> Expr:
        items = [self.concat()]
        while self.eat("|"):
            items.append(self.concat())
        return items[0] if len(items) == 1 else Alt(items)

    def concat(self) -> Expr:
        items = [self.diff()]
        while self.peek() is not None and self.peek()[0] in ("NAME", "LIT", "SPECIAL", "(", "[", "{"):
            items.append(self.diff())
        return items[0] if len(items) == 1 else Seq(items)

    def diff(self) -> Expr:
        left = self.rng()
        if self.eat("-"):
            return Diff(left, self.rng())
        return left

    def rng(self) -> Expr:
        left = self.primary()
        if self.eat(".."):
            right = self.primary()
            if not isinstance(left, Lit) or not isinstance(right, Lit):
                raise EbnfError("a range needs literal bounds, got %r..%r" % (left, right))
            return Range(left.text, right.text)
        return left

    def primary(self) -> Expr:
        tok = self.peek()
        if tok is None:
            raise EbnfError("the block ends mid-expression")
        kind, value = tok
        if kind == "NAME":
            self.i += 1
            return Ref(value)
        if kind == "LIT":
            self.i += 1
            return Lit(value)
        if kind == "SPECIAL":
            self.i += 1
            return Special(value)
        if kind == "(":
            self.i += 1
            inner = self.expr()
            self.take(")")
            return inner
        if kind == "[":
            self.i += 1
            inner = self.expr()
            self.take("]")
            return Opt(inner)
        if kind == "{":
            self.i += 1
            inner = self.expr()
            self.take("}")
            return Rep(inner)
        raise EbnfError("unexpected %r in the EBNF block" % (value,))


def parse(src: str) -> Grammar:
    """Parse a §D.1-notation block into a `Grammar`."""
    return _Parser(_tokens(src)).grammar()
