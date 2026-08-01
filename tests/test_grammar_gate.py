"""The executable-grammar gate — docs/vson.md §D.10.

`make grammar-check` runs the spec's own grammars against the corpus, so the
one thing it cannot establish about itself is that it would notice. These tests
establish that, and the three claims underneath it:

  (a) **The extractor reads the spec, not a copy.** Doctoring the Markdown —
      dropping a member from §D.3's `CONCEPT` production, moving a §D.7 row's
      `Decided by` column — changes what the generated parser accepts. If the
      pipeline carried a transcription of the grammar anywhere, none of these
      would move.
  (b) **The translation rules do what their names say.** Rule T8's guard makes
      a closed vocabulary match only a whole identifier; rule T7's difference
      excludes exactly the trait keywords and nothing that merely starts with
      one; rule T11's lookahead is what tells a handle from a positional ref.
  (c) **The gate goes red.** Every claim `check.py` makes is checked here
      against a spec that violates it, because a check nobody has watched fail
      is a check nobody should trust.

The extraction and EBNF tests run everywhere. The ones that build a parser need
lark, which is the `dev` extra (`pip install -e ".[dev]"`); `make grammar-check`
exits 2 without it rather than skipping, and these skip, because a skipped test
inside `make test` would be the only quiet failure in the chain.
"""

from __future__ import annotations

import os
import unittest

from tools.grammar import build, ebnf, extract_grammar, gbnf_backend, lark_backend

try:  # the dev extra
    import lark  # noqa: F401

    HAVE_LARK = True
except ImportError:  # pragma: no cover - exercised only on a runtime-only install
    HAVE_LARK = False

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
needs_lark = unittest.skipUnless(HAVE_LARK, "lark is the `dev` extra")


def _spec() -> str:
    return extract_grammar.spec_text()


def _scene(name: str) -> str:
    with open(os.path.join(REPO, "examples", "gallery-x", name), encoding="utf-8") as fh:
        return fh.read()


def _accepts(parser, text: str) -> bool:
    try:
        parser.parse(text)
        return True
    except Exception:
        return False


class Extraction(unittest.TestCase):
    """What the spec has to carry for any of this to run."""

    def test_both_grammars_are_found_and_are_ebnf(self):
        for name in ("penman", "vson-x"):
            source = extract_grammar.grammar_source(name)
            grammar = ebnf.parse(source)
            self.assertEqual("document", grammar.start(), name)
            self.assertTrue(grammar.terminals(), name)

    def test_a_missing_block_is_an_error_not_an_empty_grammar(self):
        doctored = _spec().replace("## Appendix B — Penman EBNF", "## Gone —")
        with self.assertRaises(extract_grammar.ExtractionError):
            extract_grammar.grammar_source("penman", doctored)

    def test_the_scanner_order_comes_from_the_table(self):
        order = extract_grammar.scanner_order("vson-x")
        self.assertLess(order["UNIT"], order["NUM"], "§D.2 tries UNIT before NUM")
        self.assertLess(order["NUM"], order["IDENT"])

    def test_the_handle_sigils_come_from_the_lead_pattern_table(self):
        sigils, items = extract_grammar.handle_lead_patterns()
        self.assertEqual({"/", ">", ">>", "!", "&"}, set(sigils))
        self.assertIn("entity_tail", items)

    def test_every_error_row_carries_an_identifier_and_a_verdict(self):
        rows = extract_grammar.error_rows()
        self.assertEqual(18, len(rows))
        self.assertEqual({"grammar", "parser"}, {decided for _, decided in rows})


class Notation(unittest.TestCase):
    """§D.1's dialect, including the two details it leaves implicit."""

    def test_literals_do_not_escape(self):
        grammar = ebnf.parse('X = \'"\' | "\\" ;')
        self.assertEqual(ebnf.Alt([ebnf.Lit('"'), ebnf.Lit("\\")]), grammar.rules["X"])

    def test_difference_binds_tighter_than_concatenation(self):
        grammar = ebnf.parse("X = A - B C ;")
        self.assertEqual(
            ebnf.Seq([ebnf.Diff(ebnf.Ref("A"), ebnf.Ref("B")), ebnf.Ref("C")]),
            grammar.rules["X"],
        )

    def test_garbage_is_rejected(self):
        with self.assertRaises(ebnf.EbnfError):
            ebnf.parse("X = A ;;")


@needs_lark
class TranslationRules(unittest.TestCase):
    """The rules `lark_backend` documents, exercised one at a time."""

    @classmethod
    def setUpClass(cls):
        cls.spec = build.load("vson-x")
        cls.parser = cls.spec.parser()

    def test_t8_a_keyword_matches_only_a_whole_identifier(self):
        # §D.3: the spellings are closed. `Named` is a trait, `Namedly` is not,
        # and a lexer that stopped after `Named` would silently split the token.
        self.assertTrue(_accepts(self.parser, "~s\n a /PhysicalObject Named\n"))
        self.assertFalse(_accepts(self.parser, "~s\n a /PhysicalObject Namedly\n"))

    def test_t7_a_modifier_may_start_with_a_trait_spelling(self):
        # MOD = IDENT - TRAIT_KEYWORD subtracts the tokens, not the prefixes.
        self.assertFalse(_accepts(self.parser, "~s *layout tri ~Named\n"))
        self.assertTrue(_accepts(self.parser, "~s *layout tri ~Namedly\n"))

    def test_t11_the_same_ident_is_a_handle_or_a_ref_by_lookahead(self):
        # §D.4: `boar` heads an item when a sigil follows it, and is a
        # positional ref when one does not.
        both = "~s\n a /PhysicalObject\n boar /PhysicalObject\n a >> strike boar\n"
        self.assertTrue(_accepts(self.parser, both))
        self.assertTrue(
            _accepts(self.parser, "~s\n a /PhysicalObject\n a >> strike @b b /PhysicalObject\n")
        )

    def test_t11_a_sigil_inside_a_comment_is_not_a_sigil(self):
        # The lookahead T11 injects is a regex, and a regex backtracks: without
        # the maximal-match guard it would give back half of the comment and
        # read the `/` in it as the sigil that makes `b` a handle. §D.2
        # discards a comment whole, so `b` stays a positional ref.
        text = "~s\n a /PhysicalObject\n b /PhysicalObject\n a >> strike b # x / y"
        self.assertTrue(_accepts(self.parser, text))

    def test_t12_a_trait_spelling_outside_entity_tail_is_an_ordinary_ident(self):
        self.assertTrue(_accepts(self.parser, "~s\n Named /PhysicalObject\n"))

    def test_an_untranslatable_construct_is_an_error_not_a_guess(self):
        grammar = ebnf.parse("document = X ;\nX = ? something nobody wrote a rule for ? ;")
        with self.assertRaises(lark_backend.TranslationError):
            lark_backend.translate(grammar, {"X": 1, "#rows": 1})


@needs_lark
class ItReadsTheSpec(unittest.TestCase):
    """Doctor the Markdown; the generated parser has to change with it."""

    def test_dropping_a_concept_breaks_the_scene_that_uses_it(self):
        scene = _scene("01_minimal.x.vson")
        self.assertTrue(_accepts(build.load("vson-x").parser(), scene))
        doctored = _spec().replace(
            'CONCEPT       = "PhysicalObject" | "Aggregate" | "Substance"',
            'CONCEPT       = "Aggregate" | "Substance"',
        )
        self.assertNotEqual(doctored, _spec())
        self.assertFalse(_accepts(build.load("vson-x", doctored).parser(), scene))

    def test_a_lead_pattern_table_the_productions_do_not_match_is_refused(self):
        # §D.4's rows and §D.5's `handle_item` are two statements of one fact.
        # Drop a row and the translator has no way to know which production the
        # lookahead belongs to — so it refuses, rather than generating a parser
        # for a language nobody specified.
        doctored = _spec().replace('| `[ "@" ] IDENT ">>"` | `event` |', "")
        self.assertNotEqual(doctored, _spec())
        with self.assertRaises(lark_backend.TranslationError):
            build.load("vson-x", doctored)

    def test_the_arglist_restriction_is_the_production_not_the_error_table(self):
        # §D.5 note 6: `arg_kv` drops `kv`'s `[ "~" MOD ]` tail, which is what
        # moves §D.7 E10 into the grammar's half of the `Decided by` column.
        bad = "~s\n a /PhysicalObject\n b /PhysicalObject\n a >> strike b *manner gently ~soft\n"
        self.assertFalse(_accepts(build.load("vson-x").parser(), bad))
        doctored = _spec().replace(
            'arglist        = { ref | arg_kv } ;',
            'arglist        = { ref | kv } ;',
        )
        self.assertTrue(_accepts(build.load("vson-x", doctored).parser(), bad))


@needs_lark
class TheGateGoesRed(unittest.TestCase):
    """Every claim check.py prints, against a spec that breaks it."""

    def test_a_wrong_spelled_count_fails_the_vocabulary_check(self):
        from tools.grammar import check

        doctored = _spec().replace(
            "**`SYM_LEMMA`** — 3 tokens", "**`SYM_LEMMA`** — 4 tokens"
        )
        with self.assertRaises(check.Failure):
            check.check_vocabularies(build.load("vson-x", doctored), [])

    def test_a_vocabulary_the_lexer_does_not_share_fails(self):
        from tools.grammar import check

        doctored = _spec().replace('| "adjacent" ;', '| "beside" ;')
        with self.assertRaises(check.Failure):
            check.check_vocabularies(build.load("vson-x", doctored), [])

    def test_a_row_that_claims_the_grammar_decides_it_must_prove_it(self):
        from tools.grammar import check

        doctored = _spec().replace(
            "| `~MOD` on the Composition's `*rendersAs` | parser |",
            "| `~MOD` on the Composition's `*rendersAs` | grammar |",
        )
        self.assertNotEqual(doctored, _spec())
        with self.assertRaises(check.Failure):
            check.check_error_rows(build.load("vson-x", doctored), [])

    def test_the_committed_gbnf_is_what_the_spec_generates(self):
        from tools.grammar import check

        spec = build.load("vson-x")
        with open(check.GBNF_PATH, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), check.generate_gbnf(spec))

    def test_the_gbnf_is_readable_gbnf_and_a_broken_one_is_not(self):
        rules = gbnf_backend.read(check_gbnf_text())
        self.assertIn(gbnf_backend.ROOT_RULE, rules.bodies)
        with self.assertRaises(gbnf_backend.GbnfError):
            gbnf_backend.read("root ::= missing-rule\n")


def check_gbnf_text() -> str:
    from tools.grammar import check

    with open(check.GBNF_PATH, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    unittest.main()
