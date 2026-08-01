#!/usr/bin/env python3
"""Mechanical translation from §D.1 notation to llama.cpp GBNF. §D.10.

GBNF is the grammar format llama.cpp accepts for constrained decoding: the
sampler is restricted, token by token, to continuations the grammar can still
complete. Translating Appendix D into it makes VSON-X a syntax a model cannot
leave — which is a different and much weaker claim than making it a syntax a
model cannot get wrong. §D.10 states the difference; this module states the
mechanics.

Why GBNF, and not a vendor's structured-output schema: it is an open format
with a public parser, it is not tied to one provider or one model, and a file
in it is useful to anybody running an open model locally with no account, no
key and no request. The other constrained-decoding formats in circulation
read the same kind of grammar, so a GBNF is the artifact they can be derived
from rather than a dead end.

The rules
---------

  G1  Every production, terminal or not, becomes a GBNF rule. GBNF is
      scannerless: it has no lexer, so §D.1's uppercase/lowercase split has no
      meaning here beyond naming.
  G2  Names are lowercased and `_` becomes `-`, because llama.cpp's name
      scanner accepts only letters, digits and `-`. The mapping must stay
      injective; a collision is a hard error.
  G3  The start production becomes `root`, wrapped in optional whitespace.
  G4  `{ x }` becomes `(x)*`, `[ x ]` becomes `(x)?`, alternation and
      concatenation carry over.
  G5  A character set — a literal of one character, a range, or an alternation
      of those — becomes a GBNF character class. `CHAR - X` becomes a negated
      class. There is no universal class in GBNF and none is needed: `CHAR`
      only ever appears under a difference.
  G6  Whitespace is explicit, because there is no lexer to discard it. A
      separator goes into every gap between two elements: `ws` where the two
      may abut, `wsr` where they may not. Both admit the discarded terminals
      of §D.2 — a comment separates two tokens exactly as a space does.
  G7  A gap takes the REQUIRED separator only when every derivation on the
      left ends with an identifier character and every derivation on the right
      begins with one. Where the analysis cannot prove both, the separator is
      optional. That direction is deliberate: it can never reject a document
      the reference lexer accepts, and §D.10 records what it costs.
  G8  A closed vocabulary is emitted as a plain alternation, with no guard.
      Rule T8's lookahead has no GBNF equivalent, so `EC` matching the front
      of `ECb` is prevented by G7's separator or not at all.
  G9  The item-boundary rule of §D.4 has no GBNF equivalent either — GBNF has
      no lookahead — so the `handle` production is emitted exactly as §D.5
      writes it. The result is ambiguous, which a constrained-decoding engine
      does not mind: it tracks every stack the input is still consistent with,
      and the grammar's job is to say which characters may come next, not
      which parse is meant.
  G10 A difference between two token languages — `MOD = IDENT - TRAIT_KEYWORD`
      — cannot be written in GBNF either. The minuend is emitted alone and the
      exclusion is dropped, which widens the language. Every such relaxation is
      listed in the generated file's header, so the artifact says what it gave
      up rather than leaving a reader to find out.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Set, Tuple

from tools.grammar import ebnf, lark_backend

WS_RULE = "ws"
WS_REQUIRED_RULE = "wsr"
ROOT_RULE = "root"

#: llama.cpp's `is_word_char` for rule names: letters, digits and `-` only.
_NAME_OK = re.compile(r"[a-z0-9-]+")


class GbnfError(Exception):
    """A construct with no documented GBNF rule."""


def gbnf_name(name: str) -> str:
    """Rule G2."""
    out = name.lower().replace("_", "-").strip("-")
    if not _NAME_OK.fullmatch(out):
        raise GbnfError("%r has no legal GBNF name" % name)
    return out


def _lit(text: str) -> str:
    body = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return '"%s"' % body


class GbnfTranslator:
    """§D.1 notation in, GBNF out."""

    def __init__(self, translator: lark_backend.Translator) -> None:
        self.g = translator.g
        self.lark = translator
        self._in_terminal = False
        self.word_chars = self._word_chars()
        self._nullable: Dict[str, bool] = {}
        self._first: Dict[str, bool] = {}
        self._last: Dict[str, bool] = {}
        self.relaxations: List[str] = []
        self._analyse()

    # -- the identifier character set (G7) --------------------------------
    def _word_chars(self) -> Set[str]:
        """Characters that can continue an identifier.

        Two tokens may abut when at least one side's boundary character is
        outside this set: `*color` needs no space after `~scene`, but `strike`
        and `boar` do.
        """
        ident = self.lark.ident
        if ident is None:
            return set()
        body = self.lark._continuation_class()
        chars: Set[str] = set()
        for m in re.finditer(r"(?:\\.|[^\\])-(?:\\.|[^\\])|\\.|[^\\]", body):
            piece = m.group(0)
            if len(piece) >= 3 and piece[-2] == "-":
                lo, hi = piece[0], piece[-1]
                chars.update(chr(c) for c in range(ord(lo), ord(hi) + 1))
            else:
                chars.add(piece[-1])
        return chars

    def _is_word(self, ch: str) -> bool:
        return ch in self.word_chars

    # -- nullable / first / last, by fixpoint (G7) ------------------------
    def _analyse(self) -> None:
        names = self.g.reachable()
        self._nullable = {n: False for n in names}
        self._first = {n: True for n in names}
        self._last = {n: True for n in names}
        for _ in range(len(names) + 2):
            changed = False
            for n in names:
                expr = self.g.rules[n]
                for table, fn in (
                    (self._nullable, self.nullable),
                    (self._first, self.first_word),
                    (self._last, self.last_word),
                ):
                    value = fn(expr)
                    if table[n] != value:
                        table[n] = value
                        changed = True
            if not changed:
                break

    def nullable(self, expr: ebnf.Expr) -> bool:
        if isinstance(expr, (ebnf.Opt, ebnf.Rep)):
            return True
        if isinstance(expr, ebnf.Ref):
            return self._nullable.get(expr.name, False)
        if isinstance(expr, ebnf.Seq):
            return all(self.nullable(i) for i in expr.items)
        if isinstance(expr, ebnf.Alt):
            return any(self.nullable(i) for i in expr.items)
        return False

    def first_word(self, expr: ebnf.Expr) -> bool:
        """Does EVERY derivation start with an identifier character?"""
        if isinstance(expr, ebnf.Lit):
            return bool(expr.text) and self._is_word(expr.text[0])
        if isinstance(expr, ebnf.Range):
            return self._is_word(expr.lo) and self._is_word(expr.hi)
        if isinstance(expr, ebnf.Special):
            return False
        if isinstance(expr, ebnf.Diff):
            return False
        if isinstance(expr, ebnf.Ref):
            return self._first.get(expr.name, False)
        if isinstance(expr, ebnf.Alt):
            return all(self.first_word(i) for i in expr.items)
        if isinstance(expr, (ebnf.Opt, ebnf.Rep)):
            return False
        if isinstance(expr, ebnf.Seq):
            for item in expr.items:
                if not self.first_word(item):
                    return False
                if not self.nullable(item):
                    return True
            return False
        return False

    def last_word(self, expr: ebnf.Expr) -> bool:
        """Does EVERY derivation end with an identifier character?"""
        if isinstance(expr, ebnf.Lit):
            return bool(expr.text) and self._is_word(expr.text[-1])
        if isinstance(expr, ebnf.Range):
            return self._is_word(expr.lo) and self._is_word(expr.hi)
        if isinstance(expr, (ebnf.Special, ebnf.Diff)):
            return False
        if isinstance(expr, ebnf.Ref):
            return self._last.get(expr.name, False)
        if isinstance(expr, ebnf.Alt):
            return all(self.last_word(i) for i in expr.items)
        if isinstance(expr, (ebnf.Opt, ebnf.Rep)):
            return False
        if isinstance(expr, ebnf.Seq):
            for item in reversed(expr.items):
                if not self.last_word(item):
                    return False
                if not self.nullable(item):
                    return True
            return False
        return False

    # -- emission ---------------------------------------------------------
    def _sep(self, left: Optional[bool], right_word: bool) -> str:
        """The separator for one gap (G6, G7).

        Inside a terminal there is no gap to fill: a terminal is one token, and
        §D.2's whitespace rule is about the space *between* tokens. The plain
        space returned there is emission padding, removed by the final
        whitespace collapse.
        """
        if self._in_terminal or left is None:
            return " "
        return " %s " % (WS_REQUIRED_RULE if left and right_word else WS_RULE)

    def _char_class(self, expr: ebnf.Expr) -> Optional[str]:
        """Rule G5, or None if the expression is not a character set."""
        if isinstance(expr, ebnf.Diff):
            try:
                left = self.lark._class_body(expr.left)
                right = self.lark._class_body(expr.right)
            except lark_backend.TranslationError:
                return None
            if left is not lark_backend.UNIVERSAL or right is lark_backend.UNIVERSAL:
                return None
            return "[^%s]" % self._rewrite_class(right)
        try:
            body = self.lark._class_body(expr)
        except lark_backend.TranslationError:
            return None
        if body is lark_backend.UNIVERSAL:
            return None
        return "[%s]" % self._rewrite_class(body)

    @staticmethod
    def _rewrite_class(body: str) -> str:
        """Re-escape a Python class body for GBNF (same syntax, fewer escapes)."""
        out = []
        i = 0
        while i < len(body):
            if body[i] == "\\" and i + 1 < len(body):
                nxt = body[i + 1]
                out.append("\\" + nxt if nxt in "\\]^-[nrt" else nxt)
                i += 2
                continue
            out.append(body[i])
            i += 1
        return "".join(out)

    def _emit(self, expr: ebnf.Expr, left: Optional[bool]) -> Tuple[str, Optional[bool]]:
        if isinstance(expr, ebnf.Lit):
            return self._sep(left, self._is_word(expr.text[0])) + _lit(expr.text), (
                self._is_word(expr.text[-1])
            )
        if isinstance(expr, (ebnf.Range, ebnf.Special, ebnf.Diff)):
            cls = self._char_class(expr)
            if cls is not None:
                word = self.first_word(expr)
                return self._sep(left, word) + cls, self.last_word(expr)
            # Rule G10 — a difference of token languages, not of character sets.
            if isinstance(expr, ebnf.Diff) and isinstance(expr.left, ebnf.Ref):
                right = (
                    expr.right.name if isinstance(expr.right, ebnf.Ref) else "the subtrahend"
                )
                note = "`%s - %s` is emitted as `%s`" % (
                    expr.left.name, right, gbnf_name(expr.left.name)
                )
                if note not in self.relaxations:
                    self.relaxations.append(note)
                return self._emit(expr.left, left)
            raise GbnfError("no rule for %r" % (expr,))
        if isinstance(expr, ebnf.Ref):
            name = expr.name
            if name not in self.g.rules:
                raise GbnfError("rule %r is used but never declared" % name)
            return (
                self._sep(left, self._first.get(name, False)) + gbnf_name(name),
                self._last.get(name, False),
            )
        if isinstance(expr, ebnf.Alt):
            cls = self._char_class(expr)
            if cls is not None:
                return self._sep(left, self.first_word(expr)) + cls, self.last_word(expr)
            texts, afters = [], []
            for item in expr.items:
                text, after = self._emit(item, left)
                texts.append(text.strip())
                afters.append(after)
            return " ( %s )" % " | ".join(texts), all(bool(a) for a in afters)
        if isinstance(expr, ebnf.Seq):
            parts = []
            cur = left
            for item in expr.items:
                text, cur = self._emit(item, cur)
                parts.append(text)
            return "".join(parts), cur
        if isinstance(expr, ebnf.Opt):
            text, after = self._emit(expr.item, left)
            return " (%s )?" % text, (left and after) if left is not None else after
        if isinstance(expr, ebnf.Rep):
            first, after = self._emit(expr.item, left)
            rest, _ = self._emit(expr.item, after)
            return " (%s (%s )* )?" % (first, rest), (
                (left and after) if left is not None else after
            )
        raise GbnfError("no rule for %r" % (expr,))

    def emit(self) -> str:
        start = self.g.start()
        ignored = [gbnf_name(t) for t in self.lark.ignored_terminals()]
        space = "[ \\t\\r\\n]"
        gap = " | ".join([space] + ignored)
        lines = [
            "# Generated from docs/vson.md by tools/grammar/gbnf_backend.py.",
            "# Do not edit: edit the spec, then run `make grammar-gbnf`.",
            "# What this constrains, and what it does not: docs/vson.md §D.10.",
            "",
            "%s ::= %s %s %s" % (ROOT_RULE, WS_RULE, gbnf_name(start), WS_RULE),
            "%s ::= ( %s )*" % (WS_RULE, gap),
            "%s ::= ( %s )+" % (WS_REQUIRED_RULE, gap),
            "",
        ]
        names = list(self.g.reachable(start))
        for term in self.lark.ignored_terminals():
            if term not in names:
                names.append(term)
                names.extend(self.g.refs(self.g.rules[term]))
        seen: Set[str] = set()
        names = [n for n in names if not (n in seen or seen.add(n))]

        bodies: Dict[str, str] = {}
        for name in names:
            gname = gbnf_name(name)
            if gname in bodies:
                raise GbnfError("two productions map to the GBNF name %r" % gname)
            expr = self.g.rules[name]
            if isinstance(expr, ebnf.Special) and self._char_class(expr) is None:
                continue  # a prose set that only ever appears under a difference
            self._in_terminal = self.g.is_terminal(name)
            body, _ = self._emit(expr, None)
            self._in_terminal = False
            bodies[gname] = " ".join(body.split())

        # A production only another production's regex needed — `NEWLINE` under
        # a difference, say — has no reader here, and an unreachable rule in a
        # decoding grammar is noise a maintainer has to re-derive. Drop it.
        wanted = {gbnf_name(start)}
        wanted.update(gbnf_name(t) for t in self.lark.ignored_terminals())
        changed = True
        while changed:
            changed = False
            for gname in list(wanted):
                for word in re.findall(r"[a-z][a-z0-9-]*", bodies.get(gname, "")):
                    if word in bodies and word not in wanted:
                        wanted.add(word)
                        changed = True
        rules = [
            "%s ::= %s" % (gname, bodies[gname])
            for gname in (gbnf_name(n) for n in names)
            if gname in bodies and gname in wanted
        ]
        if self.relaxations:
            lines[3:3] = ["# Relaxed on translation (rule G10):"] + [
                "#   - %s" % note for note in self.relaxations
            ]
        return "\n".join(lines + rules) + "\n"


def translate(translator: lark_backend.Translator) -> str:
    """GBNF source for one §D.1 grammar."""
    return GbnfTranslator(translator).emit()


# ---------------------------------------------------------------------------
# Reading a GBNF back
# ---------------------------------------------------------------------------
#
# The committed artifact is checked, not asserted. Reading it back proves the
# file is GBNF that a parser can accept; translating what was read into Lark
# proves the language it defines still contains every scene this repository
# ships. Neither is llama.cpp — see §D.10 for what remains unverified here.


_GBNF_TOKEN = re.compile(
    r"""
      (?P<comment>\#[^\n]*)
    | (?P<define>::=)
    | (?P<punct>[()|*+?])
    | (?P<name>[a-zA-Z0-9-]+)
    | "(?P<lit>(?:[^"\\]|\\.)*)"
    | \[(?P<cls>(?:[^\]\\]|\\.)*)\]
    | (?P<space>\s+)
    | (?P<bad>\S)
    """,
    re.VERBOSE,
)


class GbnfRules:
    """A parsed GBNF file: rule name -> Lark-shaped body text."""

    def __init__(self, order: List[str], bodies: Dict[str, str], refs: Dict[str, Set[str]]):
        self.order = order
        self.bodies = bodies
        self.refs = refs


def read(source: str) -> GbnfRules:
    """Parse GBNF text. Raises GbnfError on anything llama.cpp would reject."""
    toks: List[Tuple[str, str]] = []
    for m in _GBNF_TOKEN.finditer(source):
        kind = m.lastgroup
        if kind in ("comment", "space"):
            continue
        if kind == "bad":
            raise GbnfError("unexpected character %r" % m.group(0))
        toks.append((kind, m.group(kind)))

    order: List[str] = []
    bodies: Dict[str, str] = {}
    refs: Dict[str, Set[str]] = {}
    i = 0
    while i < len(toks):
        if toks[i][0] != "name" or i + 1 >= len(toks) or toks[i + 1][0] != "define":
            raise GbnfError("expected `name ::=`, got %r" % (toks[i],))
        name = toks[i][1]
        if name in bodies:
            raise GbnfError("rule %r is defined twice" % name)
        i += 2
        start = i
        while i < len(toks) and not (
            toks[i][0] == "name" and i + 1 < len(toks) and toks[i + 1][0] == "define"
        ):
            i += 1
        body = toks[start:i]
        if not body:
            raise GbnfError("rule %r has an empty body" % name)
        order.append(name)
        bodies[name] = _lark_body(body)
        refs[name] = {v for k, v in body if k == "name"}
    if ROOT_RULE not in bodies:
        raise GbnfError("no `root` rule")
    for name, used in refs.items():
        missing = sorted(used - set(bodies))
        if missing:
            raise GbnfError("rule %r references undefined %s" % (name, ", ".join(missing)))
    return GbnfRules(order, bodies, refs)


def _lark_body(body: Sequence[Tuple[str, str]]) -> str:
    """One GBNF rule body, respelled as a Lark rule body.

    Both notations spell alternation, grouping and repetition the same way; the
    only translation is that a GBNF character class becomes an inline Lark
    regexp and a GBNF literal becomes a Lark string.
    """
    out = []
    for kind, value in body:
        if kind == "name":
            out.append(value.replace("-", "_"))
        elif kind == "lit":
            out.append('"%s"' % value)
        elif kind == "cls":
            out.append("/[%s]/" % value)
        else:
            out.append(value)
    return " ".join(out)


def to_lark(rules: GbnfRules) -> str:
    """A scannerless Lark grammar with the same language as the GBNF."""
    lines = []
    for name in rules.order:
        lines.append("%s : %s" % (name.replace("-", "_"), rules.bodies[name]))
    return "\n".join(lines) + "\n"
