"""Offline tests for the merged distribution (`site/v1/vson-full.ttl`).

`scripts/build_site.py` derives one file rather than copying it: the three
ontology documents concatenated, which is the import closure of the canonical
name in a single fetch. `make site` checks it on every run — but `make site`
runs the merge and the check together, so a check that could never fail would
look exactly like a check that passes. These establish, from the checkout and
with no network:

  * the merge is the closure it claims to be — every IRI it names in the two
    companion namespaces is declared inside it, and both documents its header
    imports are present as documents. That is the property the file exists for:
    a consumer parsing this one file resolves every `vso:rcc` and Allen value,
    which a consumer parsing `ontology/vso.ttl` alone does not;

  * the arithmetic assertion in `build_site.check_merged` goes red when the
    merge stops stating the union of its sources. Turtle concatenation fails
    quietly — a re-declared prefix rebinds, a truncated source swallows the
    file after it — and both produce something that still parses.

Run: python3 -m unittest tests.test_merged_distribution

Skipped automatically if rdflib is not installed.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")


def _script(name):
    """Import a module from scripts/ by path — the same loader
    tests/test_live_claims.py uses, including the sys.path entry that lets
    build_site import check_legacy_iri by bare name."""
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(SCRIPTS, name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


try:
    import rdflib

    build_site = _script("build_site")
except ImportError:  # pragma: no cover — dependency probe for the skip guard
    rdflib = None
    build_site = None


def _quiet(callable_, *args):
    """Run a check without letting its report into the test output."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = callable_(*args)
    return result, buffer.getvalue()


@contextlib.contextmanager
def _site():
    """`build_site` writing into a temporary directory instead of `site/`.

    The checkout's own `site/` is left alone: it is git-ignored and rebuilt by
    `make site`, and a test that clobbered it while a build was reading it
    would be a test with a side effect on another gate.
    """
    original = build_site.SITE
    tmp = tempfile.mkdtemp(prefix="vson-site-")
    build_site.SITE = tmp
    try:
        yield tmp
    finally:
        build_site.SITE = original
        shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(rdflib, "rdflib required")
class MergeIsTheImportClosure(unittest.TestCase):
    """One fetch resolves what three did."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = rdflib.Graph()
        cls.graph.parse(data=build_site.merged_text(), format="turtle")
        cls.core = rdflib.Graph()
        cls.core.parse(
            os.path.join(REPO, build_site.MERGE_SOURCES[0][0]), format="turtle"
        )

    def _companion_namespaces(self) -> "list[str]":
        return [
            iri + "#"
            for _, iri in build_site.MERGE_SOURCES[1:]
        ]

    def test_every_document_the_core_imports_is_in_the_merge(self) -> None:
        core_iri = rdflib.URIRef(build_site.MERGE_SOURCES[0][1])
        imported = sorted(
            str(o) for o in self.core.objects(core_iri, rdflib.OWL.imports)
        )
        self.assertEqual(len(imported), 2)
        for iri in imported:
            with self.subTest(imported=iri):
                self.assertIn(
                    (rdflib.URIRef(iri), rdflib.RDF.type, rdflib.OWL.Ontology),
                    self.graph,
                )

    def test_every_companion_iri_the_merge_names_is_declared_in_it(
        self,
    ) -> None:
        # The property the file exists for. An IRI that appears only as an
        # object is a name the consumer cannot follow any further; in the
        # merged graph there are none.
        subjects = {
            str(s)
            for s in self.graph.subjects()
            if isinstance(s, rdflib.URIRef)
        }
        undefined = set()
        for namespace in self._companion_namespaces():
            for triple in self.graph:
                for node in triple:
                    if not isinstance(node, rdflib.URIRef):
                        continue
                    name = str(node)
                    if name.startswith(namespace) and name not in subjects:
                        undefined.add(name)
        self.assertEqual(undefined, set())

    def test_the_core_document_alone_would_not_have_resolved_them(self) -> None:
        # The measurement the merge exists for, restated against the merge:
        # the same IRIs that are declared above are absent from the core
        # document. Without this the previous test would pass on an empty set.
        declared = set()
        for namespace in self._companion_namespaces():
            declared |= {
                str(s)
                for s in self.graph.subjects()
                if isinstance(s, rdflib.URIRef) and str(s).startswith(namespace)
            }
        self.assertGreater(len(declared), 20)
        in_core = {
            str(node)
            for triple in self.core
            for node in triple
            if isinstance(node, rdflib.URIRef) and str(node) in declared
        }
        self.assertEqual(in_core, set())

    def test_the_merge_states_the_union_and_nothing_more(self) -> None:
        total = 0
        for rel, _ in build_site.MERGE_SOURCES:
            g = rdflib.Graph()
            g.parse(os.path.join(REPO, rel), format="turtle")
            total += len(g)
        self.assertEqual(len(self.graph), total)

    def test_the_merge_is_reproducible(self) -> None:
        # Nothing in the preamble may carry a build date or a host: the file
        # has to be byte-identical across two runs of the same checkout.
        self.assertEqual(build_site.merged_text(), build_site.merged_text())


@unittest.skipUnless(rdflib, "rdflib required")
class MergeCheckGoesRed(unittest.TestCase):
    """A gate nobody has seen fail is a gate nobody should trust."""

    def _write(self, site: str, text: str) -> None:
        target = os.path.join(site, build_site.MERGED)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_the_real_merge_passes(self) -> None:
        with _site() as site:
            self._write(site, build_site.merged_text())
            failures: "list[str]" = []
            _quiet(build_site.check_merged, failures)
            self.assertEqual(failures, [])

    def test_a_dropped_statement_is_caught(self) -> None:
        # The shape of a truncated source: the bytes still parse, the file
        # still carries triples, and it states one triple fewer than the union.
        text = build_site.merged_text()
        # Any single complete statement will do; this one is matched by shape
        # rather than by spelling, because the generated block's column widths
        # move when a term is added.
        dropped = re.search(
            r"^rcc:DC\s+rdfs:isDefinedBy[^\n]*\n", text, re.M
        )
        self.assertIsNotNone(dropped)
        with _site() as site:
            self._write(site, text[: dropped.start()] + text[dropped.end():])
            failures: "list[str]" = []
            _quiet(build_site.check_merged, failures)
            self.assertEqual(len(failures), 1)
            self.assertIn(build_site.MERGED, failures[0])

    def test_an_unparseable_merge_is_caught(self) -> None:
        with _site() as site:
            self._write(site, "@prefix ex: <http://e.org/> .\nex:a ex:b")
            failures: "list[str]" = []
            _quiet(build_site.check_merged, failures)
            self.assertEqual(len(failures), 1)
            self.assertIn("does not parse", failures[0])


@unittest.skipUnless(rdflib, "rdflib required")
class ContentTypeMatrixIsClosed(unittest.TestCase):
    """Every published RDF/JSON document is typed, and every rule is used."""

    def test_the_merged_path_is_typed(self) -> None:
        with open(
            os.path.join(REPO, "publish", "_headers"), encoding="utf-8"
        ) as fh:
            headers = fh.read()
        self.assertIn("/%s\n" % build_site.MERGED, headers)

    def test_an_untyped_published_document_is_caught(self) -> None:
        # The reverse direction of the _headers check, which is the one a
        # static host punishes silently: an untyped .ttl goes out as
        # text/plain and a content-negotiating client refuses it.
        with _site() as site:
            os.makedirs(site, exist_ok=True)
            shutil.copyfile(
                os.path.join(REPO, "publish", "_headers"),
                os.path.join(site, "_headers"),
            )
            failures: "list[str]" = []
            paths = [dst for _, dst in build_site.COPY]
            paths += [build_site.MERGED, "v1/untyped.ttl"]
            _quiet(build_site.check_headers, paths, failures)
            self.assertEqual(len(failures), 1)
            self.assertIn("v1/untyped.ttl", failures[0])


if __name__ == "__main__":
    unittest.main()
