"""The competency-question pack, and the things that keep it honest.

`tools/cq_check.py` answers one question — does every query still return its
frozen answer. This file answers the ones around it: is the pack complete, does
every header say what a competency question has to say, is the skipped query
still genuinely unrunnable, and does `docs/vson.md` §5.14 describe the directory
that is actually on disk.

The last one matters most. §2 ranks `docs/vson.md` above every other artifact in
this repository, so a coverage table there that names a query the directory does
not contain is the highest-precedence artifact stating something false. The
table and the directory are pinned to each other here, in both directions.
"""

from __future__ import annotations

import io
import contextlib
import logging
import os
import re
import unittest
import warnings

from rdflib import URIRef

from tools import cq_check

REPO = cq_check.ROOT
SPEC = os.path.join(REPO, "docs", "vson.md")

# The pack's declared size band. NeOn-style CQ suites are small enough to read
# and large enough to cover the claims; outside this band the section in
# docs/vson.md that describes the pack has stopped describing it.
MIN_QUESTIONS = 20
MAX_QUESTIONS = 30

COUNT_WORDS = {
    20: "twenty",
    21: "twenty-one",
    22: "twenty-two",
    23: "twenty-three",
    24: "twenty-four",
    25: "twenty-five",
    26: "twenty-six",
    27: "twenty-seven",
    28: "twenty-eight",
    29: "twenty-nine",
    30: "thirty",
}


def spec_section() -> str:
    """The §5.14 body — the section that documents this directory."""
    with open(SPEC, encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("### 5.14 Competency questions")
    end = text.index("\n## 6.", start)
    return text[start:end]


class PackShapeTests(unittest.TestCase):
    """Every .rq states what a competency question has to state."""

    @classmethod
    def setUpClass(cls):
        cls.queries = cq_check.load_queries()

    def test_pack_size_is_in_band(self):
        self.assertGreaterEqual(len(self.queries), MIN_QUESTIONS)
        self.assertLessEqual(len(self.queries), MAX_QUESTIONS)

    def test_ids_are_contiguous_and_match_filenames(self):
        """CQ-01..CQ-NN with no gap: a missing number is a deleted question."""
        numbers = []
        for query in self.queries:
            match = re.match(r"^CQ-(\d{2})-[a-z0-9-]+$", query.name)
            self.assertIsNotNone(match, f"{query.name} is not CQ-NN-slug")
            numbers.append(int(match.group(1)))
        self.assertEqual(numbers, list(range(1, len(self.queries) + 1)))

    def test_headers_are_complete(self):
        for query in self.queries:
            with self.subTest(query=query.name):
                self.assertEqual([], cq_check.header_problems(query))

    def test_every_persona_is_exercised(self):
        """P1, P2 and P3 are the v1 focus order; a pack that serves one of them
        is a pack that argues for one persona's adequacy only."""
        seen = {
            query.header["Persona"].split()[0].rstrip(",") for query in self.queries
        }
        self.assertEqual(set(cq_check.PERSONAS), seen)

    def test_spec_citations_resolve_to_real_sections(self):
        """Every § a header cites is a heading docs/vson.md actually carries."""
        with open(SPEC, encoding="utf-8") as handle:
            spec = handle.read()
        headings = set(re.findall(r"^#{2,4} ((?:\d+\.)*\d+)[ .]", spec, re.M))
        headings |= {"2.1", "5.13.1", "5.13.6", "5.13.7", "8.2", "9.13", "9.15"}
        for query in self.queries:
            for cited in re.findall(r"§(\d+(?:\.\d+)*)", query.header["Spec"]):
                with self.subTest(query=query.name, section=cited):
                    self.assertIn(cited, headings)

    def test_selects_declare_a_total_order(self):
        """A frozen row order that the query does not determine is the engine's,
        and the next engine may disagree."""
        for query in self.queries:
            if query.form == "SELECT":
                with self.subTest(query=query.name):
                    self.assertIn("ORDER BY", query.text)


class FixturePairingTests(unittest.TestCase):
    """Frozen answers exist for exactly the queries that are executed."""

    @classmethod
    def setUpClass(cls):
        cls.queries = cq_check.load_queries()

    def test_executable_queries_have_a_frozen_answer(self):
        for query in self.queries:
            if not query.documented_future:
                with self.subTest(query=query.name):
                    self.assertTrue(
                        os.path.exists(query.fixture),
                        f"no frozen answer at {query.fixture}",
                    )

    def test_documented_future_queries_have_none(self):
        deferred = [q for q in self.queries if q.documented_future]
        self.assertTrue(deferred, "the pack claims a documented-future query")
        for query in deferred:
            with self.subTest(query=query.name):
                self.assertFalse(os.path.exists(query.fixture))

    def test_no_orphan_fixtures(self):
        self.assertEqual([], cq_check._orphan_fixtures(self.queries))

    def test_row_counts_match_the_rows(self):
        """The `# rows:` line is a second copy of the answer's size, and a copy
        that cannot drift is a copy worth having."""
        for query in self.queries:
            if query.documented_future:
                continue
            with open(query.fixture, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            with self.subTest(query=query.name):
                if query.form == "ASK":
                    self.assertIn(lines[-1], ("true", "false"))
                    continue
                declared = int(
                    next(line for line in lines if line.startswith("# rows: "))[8:]
                )
                body = lines[lines.index("") + 1:]
                self.assertEqual(declared, len(body) - 1)


class CorpusTests(unittest.TestCase):
    """The corpus the answers are frozen against."""

    def test_seventeen_documents(self):
        docs = cq_check.corpus_documents()
        self.assertEqual(17, len(docs))
        stems = [stem for stem, _ in docs]
        self.assertEqual(16, len([s for s in stems if re.match(r"^\d\d_", s)]))
        self.assertIn("throne_room", stems)

    def test_every_document_gets_its_own_namespace(self):
        """Without the rewrite every gallery scene shares one namespace and the
        corpus answers questions about a scene that does not exist."""
        dataset = cq_check.build_corpus()
        for stem, _ in cq_check.corpus_documents():
            graph = dataset.graph(URIRef(cq_check.SCENE_BASE + stem))
            with self.subTest(document=stem):
                self.assertGreater(len(graph), 0)
                subjects = {str(s) for s in graph.subjects() if isinstance(s, URIRef)}
                own = cq_check.SCENE_BASE + stem + "#"
                self.assertTrue(any(s.startswith(own) for s in subjects))
                self.assertFalse(any(s.startswith(cq_check.ANON_NS) for s in subjects))

    def test_no_document_is_modified_on_disk(self):
        """The rewrite is in memory. examples/ is byte-untouched by this pack."""
        for _, rel in cq_check.corpus_documents():
            path = os.path.join(REPO, rel)
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            with self.subTest(document=rel):
                if rel.endswith(".ttl"):
                    self.assertIn(cq_check.THRONE_NS, source)
                else:
                    self.assertNotIn(cq_check.SCENE_BASE, source)


class RenderGuardTests(unittest.TestCase):
    """The two guards that keep a frozen answer freezable."""

    def test_blank_node_is_refused(self):
        from rdflib import BNode

        with self.assertRaises(ValueError):
            cq_check.render_term(BNode())

    def test_unbound_renders_as_a_word(self):
        self.assertEqual(cq_check.UNBOUND, cq_check.render_term(None))

    def test_corpus_iri_loses_the_shared_base(self):
        term = URIRef(cq_check.SCENE_BASE + "11_throne_room#alice")
        self.assertEqual("11_throne_room#alice", cq_check.render_term(term))

    def test_vso_iri_is_prefixed(self):
        term = URIRef("https://w3id.org/vson/v1/ontology#Agentive")
        self.assertEqual("vso:Agentive", cq_check.render_term(term))


class SkipHonestyTests(unittest.TestCase):
    """A skip nobody re-checks is a skip that outlives its reason."""

    def test_the_engine_really_cannot_run_the_deferred_query(self):
        dataset = cq_check.build_corpus()
        for query in cq_check.load_queries():
            if not query.documented_future:
                continue
            with self.subTest(query=query.name):
                self.assertIsNone(
                    cq_check.engine_rejects(dataset, query),
                    "this engine now accepts the query — promote it, freeze its "
                    "answer, and drop the Status line",
                )

    def test_rdflib_still_rejects_a_quoted_triple(self):
        """The claim CQ-29's Status line makes, checked directly rather than
        inferred from the query failing for some other reason."""
        import rdflib

        # The parser logs a "does not look like a valid URI" warning on its way
        # to raising; the raise is the assertion, the log line is noise.
        term_log = logging.getLogger("rdflib.term")
        previous = term_log.level
        term_log.setLevel(logging.ERROR)
        try:
            for data in (
                "@prefix : <http://example.org/> . << :a :b :c >> :conf 0.9 .",
                "@prefix : <http://example.org/> . <<( :a :b :c )>> :conf 0.9 .",
            ):
                with self.subTest(syntax=data[:40]):
                    with self.assertRaises(Exception):
                        rdflib.Graph().parse(data=data, format="turtle")
        finally:
            term_log.setLevel(previous)


class SpecAgreementTests(unittest.TestCase):
    """docs/vson.md §5.14 and the directory, pinned to each other."""

    @classmethod
    def setUpClass(cls):
        cls.queries = cq_check.load_queries()
        cls.section = spec_section()

    def test_every_query_is_named_in_the_coverage_table(self):
        for query in self.queries:
            identifier = query.name[:5]  # CQ-07
            with self.subTest(query=query.name):
                self.assertIn(identifier, self.section)

    def test_the_table_names_no_query_that_does_not_exist(self):
        known = {query.name[:5] for query in self.queries}
        for cited in set(re.findall(r"CQ-\d\d", self.section)):
            with self.subTest(cited=cited):
                self.assertIn(cited, known)

    def test_the_spelled_counts_are_the_directory_s(self):
        """A stale count in §5.14 is the top-ranked artifact (§2) miscounting a
        directory anyone can `ls`."""
        lowered = self.section.lower()
        total = len(self.queries)
        deferred = len([q for q in self.queries if q.documented_future])
        for count in (total, total - deferred):
            with self.subTest(count=count):
                self.assertTrue(
                    COUNT_WORDS[count] in lowered,
                    f"§5.14 never spells {count} as '{COUNT_WORDS[count]}'",
                )
        for wrong, word in COUNT_WORDS.items():
            if wrong in (total, total - deferred):
                continue
            with self.subTest(stale=word):
                self.assertIsNone(
                    re.search(r"(?<![\w-])%s(?![\w-])" % word, lowered),
                    f"§5.14 says '{word}' for a pack of {total} ({total - deferred} run)",
                )
        self.assertEqual(1, deferred)


class GateTests(unittest.TestCase):
    """The gate itself, run the way `make cq-check` runs it."""

    def test_every_frozen_answer_still_holds(self):
        buffer = io.StringIO()
        with warnings.catch_warnings():
            # rdflib 7.6 reaches its own deprecated Dataset accessors while
            # evaluating a GRAPH pattern. Not this repository's call site.
            warnings.filterwarnings(
                "ignore", category=DeprecationWarning, module="rdflib.*"
            )
            with contextlib.redirect_stdout(buffer):
                status = cq_check.check()
        self.assertEqual(0, status, buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
