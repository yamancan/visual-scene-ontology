#!/usr/bin/env python3
"""Mechanical translation from §D.1 notation to Lark. See docs/vson.md §D.10.

The point of the translation is that nobody re-types a production. A grammar
somebody transcribed by hand is a second source; a grammar a program derives is
a view. So every rule below is a *rewrite* of something the spec already says,
and the module refuses — loudly — to translate a construct it has no rule for,
rather than guessing and quietly producing a parser for a different language.

The rules
---------

  T1  A production keeps its name. UPPERCASE becomes a Lark terminal,
      lowercase a Lark rule (§D.1).
  T2  `{ x }` becomes `(x)*`, `[ x ]` becomes `(x)?`, `|` stays alternation and
      juxtaposition stays concatenation.
  T3  A literal becomes a Lark string in a rule, and the escaped regex of the
      same characters inside a terminal.
  T4  A terminal is emitted as ONE regular expression, with every terminal it
      references inlined. Lark can compose terminals itself; this translation
      does not use that, because T7, T8 and T11 need lookaheads, and a
      lookahead has to see the whole pattern.
  T5  `"a".."z"` becomes a regex character range.
  T6  `A - B` where A is a character set becomes a negated character class.
      Only `CHAR - …` occurs, and `CHAR` is the universal set (§D.2).
  T7  `A - B` where A is a token production shaped `HEAD { TAIL }` and B is an
      alternation of literals becomes a negative lookahead over B's members,
      each anchored by a negative lookahead on TAIL's character class, in front
      of A's own regex. This is `MOD = IDENT - TRAIT_KEYWORD`: `~Named` is not
      a modifier, `~Namedly` is.
  T8  A closed vocabulary — a terminal whose expression is an alternation of
      literals that the grammar's identifier terminal matches whole — gets a
      trailing negative lookahead on that terminal's continuation class.
      §D.2's scanner order makes an identifier maximal, so a keyword matches
      only a whole identifier and `Namedly` is an IDENT, not `Named` + `ly`.
  T9  Terminal priority comes from the scanner-order table: "the scanner tries
      the alternatives below in order", so a lower row number is a higher
      priority. A terminal the table does not list but which T7 or T8 derived
      from the identifier terminal ranks just above it; a terminal T11 injects
      ranks between the two.
  T10 A terminal the scanner-order table lists and no syntactic production
      references is one the lexer discards, so it becomes `%ignore`. §D.2's
      "whitespace, including newlines, only separates tokens" adds an
      `%ignore` for whitespace, which is the one line here with no production
      behind it.
  T11 §D.4's item-boundary rule has no EBNF spelling — EBNF has no lookahead.
      The production it governs is found structurally, as the one whose body is
      a single symbol followed by an alternation of exactly the item names
      §D.4's table lists, and the symbol it leads with is respelled as two
      guarded terminals: a bare handle, and an `@`-prefixed handle. Each
      carries a lookahead for §D.4's sigil set, with the ignored terminals of
      T10 allowed to intervene. Every other position keeps the plain
      identifier terminal, which is what leaves a trait keyword an ordinary
      IDENT outside `entity_tail` (§D.3) and a bare IDENT a positional ref
      inside an arglist (§D.4).
  T12 The generated parser is LALR(1) with a contextual lexer. §D.3's "in any
      other position these spellings are ordinary IDENTs" is a claim about
      which terminals are admissible where, and a contextual lexer is the
      mechanism that decides exactly that.

What the translation does not carry
-----------------------------------

The dispatch tables. §D.5 note 1 says it plainly: `kv` is one production and
its meaning is not. Which `*K V` becomes a Quality and which a direct property,
which lemma takes which roles, whether a directional fact found its viewer —
none of that is in the productions, so none of it is in the generated parser.
§D.7's `Decided by` column is the list of what that costs, and `make
grammar-check` asserts the column row by row.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from tools.grammar import ebnf


class TranslationError(Exception):
    """A construct this module has no documented rule for."""


UNIVERSAL = "\0universal\0"

#: The `? … ?` character sets §D.1 admits, and what each compiles to. A set
#: this table does not carry is a hard error: a prose-named character class
#: nobody translated is a silent hole in the generated parser.
SPECIALS = {
    "any Unicode code point": UNIVERSAL,
    "U+000A": "\n",
}


#: Control characters have to leave as escape sequences, not as themselves: a
#: Lark terminal is one line, and a raw newline inside `/…/` ends it.
_CONTROL = {"\n": "\\n", "\r": "\\r", "\t": "\\t", "\f": "\\f", "\v": "\\v"}


def _esc_class(ch: str) -> str:
    """Escape one character for use inside a regex character class."""
    if ch in _CONTROL:
        return _CONTROL[ch]
    if ord(ch) < 0x20:
        return "\\x%02x" % ord(ch)
    return "\\" + ch if ch in "\\^]-" else ch


def _esc_literal(text: str) -> str:
    """Escape a literal for use in a regex, control characters included."""
    return "".join(_CONTROL.get(c, re.escape(c)) for c in text)


def _for_lark(regex: str) -> str:
    """Fence a regex for Lark's `/…/` delimiters.

    Purely a matter of Lark's own syntax: a `/` inside the pattern would close
    it. Backslash pairs are stepped over so an escape is never split.
    """
    out = []
    i = 0
    while i < len(regex):
        ch = regex[i]
        if ch == "\\" and i + 1 < len(regex):
            out.append(regex[i:i + 2])
            i += 2
            continue
        out.append("\\/" if ch == "/" else ch)
        i += 1
    return "".join(out)


class LarkGrammar:
    """One translated grammar: the Lark source, plus what it was built from."""

    def __init__(self, source: str, start: str, terminals: Dict[str, str]) -> None:
        self.source = source
        self.start = start
        self.terminals = terminals


class Translator:
    """§D.1 notation in, Lark out."""

    def __init__(
        self,
        grammar: ebnf.Grammar,
        scanner_order: Dict[str, int],
        lead_patterns: Optional[Tuple[Sequence[str], Sequence[str]]] = None,
    ) -> None:
        self.g = grammar
        self.order = dict(scanner_order)
        self.rows = self.order.pop("#rows")
        self.injected: Dict[str, str] = {}
        self._regex_cache: Dict[str, str] = {}
        self.ident = self._identifier_terminal()
        if lead_patterns is not None:
            self._inject_lead_lookahead(*lead_patterns)

    # -- T9 -------------------------------------------------------------
    def priority(self, name: str) -> int:
        """Scanner row -> Lark priority. Lower row, higher priority."""
        if name in self.order:
            return 10 * (self.rows + 1 - self.order[name])
        base = 10 * (self.rows + 1 - self.order[self.ident]) if self.ident else 0
        return base + (1 if name in self.injected else 2)

    # -- terminal shapes -------------------------------------------------
    def _identifier_terminal(self) -> Optional[str]:
        """The open, maximal-munch identifier terminal of this grammar.

        T7 and T8 both anchor on it: it is the terminal a closed vocabulary is
        drawn from, and the one a set difference subtracts from. It is the
        lowest-priority terminal in the scanner-order table shaped
        `HEAD { TAIL }` — for both VSON grammars, the last row but one.
        """
        best = None
        for name, row in sorted(self.order.items(), key=lambda kv: -kv[1]):
            if self._head_tail(name) is not None:
                best = name
                break
        return best

    def _head_tail(self, name: str) -> Optional[Tuple[ebnf.Expr, ebnf.Expr]]:
        """`HEAD { TAIL }` if the terminal has that shape, else None."""
        expr = self.g.rules.get(name)
        if not isinstance(expr, ebnf.Seq) or len(expr.items) != 2:
            return None
        head, tail = expr.items
        if not isinstance(tail, ebnf.Rep):
            return None
        try:
            self._class_body(head)
            self._class_body(tail.item)
        except TranslationError:
            return None
        return head, tail.item

    def _literal_alternatives(self, name: str) -> Optional[List[str]]:
        """The members, if the terminal is a plain alternation of literals."""
        expr = self.g.rules.get(name)
        if isinstance(expr, ebnf.Lit):
            return [expr.text]
        if not isinstance(expr, ebnf.Alt):
            return None
        if not all(isinstance(i, ebnf.Lit) for i in expr.items):
            return None
        return [i.text for i in expr.items]

    def is_closed_vocabulary(self, name: str) -> bool:
        """T8: a literal alternation whose members are whole identifiers."""
        members = self._literal_alternatives(name)
        if not members or self.ident is None or name == self.ident:
            return False
        ident_rx = re.compile(self._regex_of(self.ident, guarded=False))
        return all(ident_rx.fullmatch(m) for m in members)

    # -- character classes (T5, T6) --------------------------------------
    def _class_body(self, expr: ebnf.Expr) -> str:
        """The body of a regex character class, or UNIVERSAL."""
        if isinstance(expr, ebnf.Lit):
            if len(expr.text) != 1:
                raise TranslationError("a character class needs one-character literals")
            return _esc_class(expr.text)
        if isinstance(expr, ebnf.Range):
            return "%s-%s" % (_esc_class(expr.lo), _esc_class(expr.hi))
        if isinstance(expr, ebnf.Special):
            value = SPECIALS.get(expr.text)
            if value is None:
                raise TranslationError("no rule for the character set ? %s ?" % expr.text)
            return UNIVERSAL if value is UNIVERSAL else _esc_class(value)
        if isinstance(expr, ebnf.Ref):
            if not self.g.is_terminal(expr.name):
                raise TranslationError("a character class cannot reference %r" % expr.name)
            return self._class_body(self.g.rules[expr.name])
        if isinstance(expr, ebnf.Alt):
            parts = [self._class_body(i) for i in expr.items]
            if UNIVERSAL in parts:
                raise TranslationError("the universal set cannot join a class union")
            return "".join(parts)
        raise TranslationError("not a character class: %r" % (expr,))

    # -- regexes (T4) -----------------------------------------------------
    def _regex_of(self, name: str, guarded: bool = True) -> str:
        """The regular expression of one terminal, references inlined."""
        key = "%s/%s" % (name, guarded)
        if key in self._regex_cache:
            return self._regex_cache[key]
        if name in self.injected:
            self._regex_cache[key] = self.injected[name]
            return self.injected[name]
        if name not in self.g.rules:
            raise TranslationError("terminal %r is used but never declared" % name)
        rx = self._regex(self.g.rules[name])
        if guarded and self.is_closed_vocabulary(name):
            rx = "%s(?![%s])" % (rx, self._continuation_class())
        self._regex_cache[key] = rx
        return rx

    def _continuation_class(self) -> str:
        """T8's anchor: the characters that may continue an identifier."""
        shape = self._head_tail(self.ident) if self.ident else None
        if shape is None:
            raise TranslationError("this grammar has no identifier terminal to anchor on")
        return self._class_body(shape[1])

    def _regex(self, expr: ebnf.Expr) -> str:
        if isinstance(expr, ebnf.Lit):
            return _esc_literal(expr.text)
        if isinstance(expr, ebnf.Range):
            return "[%s]" % self._class_body(expr)
        if isinstance(expr, ebnf.Special):
            body = self._class_body(expr)
            return "[\\s\\S]" if body is UNIVERSAL else "[%s]" % body
        if isinstance(expr, ebnf.Ref):
            if not self.g.is_terminal(expr.name):
                raise TranslationError(
                    "terminal expression references the production %r" % expr.name
                )
            return "(?:%s)" % self._regex_of(expr.name)
        if isinstance(expr, ebnf.Seq):
            return "".join(self._regex(i) for i in expr.items)
        if isinstance(expr, ebnf.Alt):
            try:
                body = self._class_body(expr)
            except TranslationError:
                return "(?:%s)" % "|".join(self._regex(i) for i in expr.items)
            return "[%s]" % body
        if isinstance(expr, ebnf.Opt):
            return "(?:%s)?" % self._regex(expr.item)
        if isinstance(expr, ebnf.Rep):
            return "(?:%s)*" % self._regex(expr.item)
        if isinstance(expr, ebnf.Diff):
            return self._regex_diff(expr)
        raise TranslationError("no rule for %r" % (expr,))

    def _regex_diff(self, expr: ebnf.Diff) -> str:
        # T6 — a character set minus a character set.
        try:
            left = self._class_body(expr.left)
            right = self._class_body(expr.right)
        except TranslationError:
            left = right = None
        if left is not None and right is not None:
            if left is not UNIVERSAL:
                raise TranslationError(
                    "only the universal character set can be subtracted from"
                )
            return "[^%s]" % right
        # T7 — an identifier terminal minus a closed vocabulary.
        if not isinstance(expr.left, ebnf.Ref) or not isinstance(expr.right, ebnf.Ref):
            raise TranslationError("no rule for the difference %r" % (expr,))
        members = self._literal_alternatives(expr.right.name)
        if members is None or self._head_tail(expr.left.name) is None:
            raise TranslationError("no rule for the difference %r" % (expr,))
        tail = self._class_body(self._head_tail(expr.left.name)[1])
        excluded = "|".join(_esc_literal(m) for m in members)
        return "(?!(?:%s)(?![%s]))%s" % (excluded, tail, self._regex_of(expr.left.name))

    # -- T11 --------------------------------------------------------------
    def _inject_lead_lookahead(
        self, sigils: Sequence[str], items: Sequence[str]
    ) -> None:
        wanted = set(items)
        target = None
        for name in self.g.productions():
            expr = self.g.rules[name]
            if not isinstance(expr, ebnf.Seq) or len(expr.items) != 2:
                continue
            lead, rest = expr.items
            if not isinstance(lead, ebnf.Ref) or not isinstance(rest, ebnf.Alt):
                continue
            if all(isinstance(i, ebnf.Ref) for i in rest.items) and {
                i.name for i in rest.items
            } == wanted:
                target = lead.name
                break
        if target is None:
            raise TranslationError(
                "no production leads with one symbol and then exactly %s — the "
                "item-boundary table and the productions disagree" % sorted(wanted)
            )
        shape = self.g.rules[target]
        if (
            not isinstance(shape, ebnf.Seq)
            or len(shape.items) != 2
            or not isinstance(shape.items[0], ebnf.Opt)
            or not isinstance(shape.items[0].item, ebnf.Lit)
            or not isinstance(shape.items[1], ebnf.Ref)
        ):
            raise TranslationError(
                "%r is not the `[ prefix ] IDENT` the lookahead rule expects" % target
            )
        users = [n for n in self.g.productions() if target in self.g.refs(self.g.rules[n])]
        if len(users) != 1:
            raise TranslationError(
                "%r is used by %d productions; the lookahead rule assumes one"
                % (target, len(users))
            )
        prefix = shape.items[0].item.text
        ident = shape.items[1].name
        ident_rx = self._regex_of(ident)
        skip = self._skip_regex()
        follow = "(?:%s)" % "|".join(
            _esc_literal(s) for s in sorted(sigils, key=len, reverse=True)
        )
        bare = "%s_HANDLE" % ident
        prefixed = "%s_HANDLE_PREFIX" % ident
        self.injected[bare] = "%s(?=%s%s)" % (ident_rx, skip, follow)
        self.injected[prefixed] = "%s(?=%s%s%s%s)" % (
            _esc_literal(prefix), skip, ident_rx, skip, follow
        )
        for name in (bare, prefixed):
            self.g.add(name, ebnf.Special("injected by the item-boundary rule"))
        self.g.replace(target, ebnf.Seq([ebnf.Opt(ebnf.Ref(prefixed)), ebnf.Ref(bare)]))

    def _skip_regex(self) -> str:
        """What may sit between a handle and the sigil that identifies it.

        Whitespace, and anything T10 discards — a comment between an item's
        handle and its sigil does not end the item, because the parser never
        sees the comment at all.

        Each discarded terminal is matched MAXIMALLY, which a lookahead does
        not get for free: a regex backtracks, so a plain `#[^\\n]*` inside the
        lookahead would happily give back half of `# note / here` and report
        the `/` in the comment as the handle's sigil. `_maximal_guard` forbids
        that, and the reason it has to is that §D.2 discards a comment whole:
        a sigil the parser never sees cannot end an item.
        """
        parts = ["\\s"] + [
            "(?:%s%s)" % (self._regex_of(t), self._maximal_guard(t))
            for t in self.ignored_terminals()
        ]
        return "(?:%s)*" % "|".join(parts)

    def _maximal_guard(self, name: str) -> str:
        """A lookahead asserting the terminal could not have matched further.

        For a terminal shaped `HEAD { TAIL }` that is "no further `TAIL`".
        A terminal of any other shape gets no guard, and the caller has to be
        able to live with a shorter match.
        """
        expr = self.g.rules.get(name)
        if isinstance(expr, ebnf.Seq) and isinstance(expr.items[-1], ebnf.Rep):
            return "(?!%s)" % self._regex(expr.items[-1].item)
        return ""

    # -- T10 --------------------------------------------------------------
    def referenced_terminals(self) -> List[str]:
        """Terminals a syntactic production names.

        A terminal only another terminal mentions — `ALPHA_`, `INT`, the two
        halves of `REL` — is a piece of a regular expression, not a token the
        parser ever sees, so rule T4 has already inlined it and nothing is
        emitted for it.
        """
        names: List[str] = []
        for name in self.g.reachable():
            if self.g.is_terminal(name):
                continue
            for ref in self.g.refs(self.g.rules[name]):
                if self.g.is_terminal(ref) and ref not in names:
                    names.append(ref)
        return names

    def ignored_terminals(self) -> List[str]:
        referenced = set(self.referenced_terminals())
        return [t for t in self.order if t not in referenced]

    # -- emission ---------------------------------------------------------
    def _rule_body(self, expr: ebnf.Expr) -> str:
        if isinstance(expr, ebnf.Lit):
            return '"%s"' % expr.text.replace("\\", "\\\\").replace('"', '\\"')
        if isinstance(expr, ebnf.Ref):
            return expr.name
        if isinstance(expr, ebnf.Seq):
            return " ".join(self._rule_body(i) for i in expr.items)
        if isinstance(expr, ebnf.Alt):
            return "(%s)" % " | ".join(self._rule_body(i) for i in expr.items)
        if isinstance(expr, ebnf.Opt):
            return "(%s)?" % self._rule_body(expr.item)
        if isinstance(expr, ebnf.Rep):
            return "(%s)*" % self._rule_body(expr.item)
        raise TranslationError("no rule for %r in a syntactic production" % (expr,))

    def emit(self) -> LarkGrammar:
        lines = [
            "// Generated from docs/vson.md by tools/grammar/lark_backend.py.",
            "// Do not edit: edit the spec. See docs/vson.md §D.10.",
            "",
        ]
        start = self.g.start()
        reachable = self.g.reachable(start)
        for name in reachable:
            if self.g.is_terminal(name):
                continue
            lines.append("%-14s : %s" % (name, self._rule_body(self.g.rules[name])))
        lines.append("")
        terminals: Dict[str, str] = {}
        for name in self.referenced_terminals() + self.ignored_terminals():
            if name in terminals:
                continue
            terminals[name] = self._regex_of(name)
            lines.append(
                "%s.%d : /%s/"
                % (name, self.priority(name), _for_lark(terminals[name]))
            )
        lines.append("")
        lines.append("WHITESPACE : /\\s+/")
        lines.append("%ignore WHITESPACE")
        for name in self.ignored_terminals():
            lines.append("%%ignore %s" % name)
        return LarkGrammar("\n".join(lines) + "\n", start, terminals)


def translate(
    grammar: ebnf.Grammar,
    scanner_order: Dict[str, int],
    lead_patterns: Optional[Tuple[Sequence[str], Sequence[str]]] = None,
) -> LarkGrammar:
    """Translate one §D.1 grammar into Lark source."""
    return Translator(grammar, scanner_order, lead_patterns).emit()
