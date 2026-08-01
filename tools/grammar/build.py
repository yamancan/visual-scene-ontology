#!/usr/bin/env python3
"""Assemble a runnable parser from the spec. docs/vson.md §D.10.

Extraction (`extract_grammar`) reads the productions out of `docs/vson.md`;
`ebnf` turns them into a tree; `lark_backend` rewrites the tree into Lark and
`gbnf_backend` into a constrained-decoding grammar. This module is the seam
that runs those four in order and hands back something callable.

Nothing here is cached to disk. A generated parser that lives in the checkout
is a copy of the grammar, and a copy can be stale; regenerating on every run
costs a few milliseconds and cannot be. The one generated file this repository
does commit is `tools/grammar/vson-x.gbnf`, because a decoding grammar is only
useful to somebody who is not running this code — and `make grammar-check`
regenerates it and compares byte for byte (§D.10).
"""

from __future__ import annotations

from typing import Dict, Optional

from tools.grammar import ebnf, extract_grammar, lark_backend


class SpecGrammar:
    """One grammar of the spec, in every form the gate needs."""

    def __init__(self, name: str, text: Optional[str] = None) -> None:
        spec = extract_grammar.spec_text() if text is None else text
        self.name = name
        # Kept so every later question is answered from the same reading of the
        # spec this grammar was built from, and not from whatever is on disk.
        self.spec_text = spec
        self.ebnf_source = extract_grammar.grammar_source(name, spec)
        self.grammar = ebnf.parse(self.ebnf_source)
        self.scanner_order = extract_grammar.scanner_order(name, spec)
        lead_heading = extract_grammar.GRAMMARS[name]["lead_patterns"]
        self.lead_patterns = (
            extract_grammar.handle_lead_patterns(lead_heading, spec)
            if lead_heading
            else None
        )
        # The translator mutates the tree (rule T11 respells one production),
        # so it gets its own copy of it.
        self._translator = lark_backend.Translator(
            ebnf.parse(self.ebnf_source), self.scanner_order, self.lead_patterns
        )
        self.lark = self._translator.emit()

    def closed_vocabularies(self) -> Dict[str, list]:
        """The §D.3 sets, as the productions declare them (T8's test)."""
        out = {}
        for name in self.grammar.terminals():
            members = self._translator._literal_alternatives(name)
            if members and self._translator.is_closed_vocabulary(name):
                out[name] = members
        return out

    def parser(self):
        """A Lark LALR(1) parser with a contextual lexer (rule T12)."""
        import lark  # imported here so extraction works without the dev extra

        return lark.Lark(self.lark.source, start=self.lark.start, parser="lalr")


def load(name: str, text: Optional[str] = None) -> SpecGrammar:
    return SpecGrammar(name, text)
