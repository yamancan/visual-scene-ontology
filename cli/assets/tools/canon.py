#!/usr/bin/env python3
"""Canonical form and denotation equality — docs/vson.md §4.6.

"VSON-T and VSON-P are graph-equivalent" is the claim this specification
repeats most often, and until v1.3 the only thing standing behind it was a
test helper whose own docstring called itself "a test-only utility"
(`tools/vson_x/equiv.py`). A helper can decide a case; it cannot say what the
case *is*. §4.6 says it: two documents denote the same scene iff, after the
two normalizations that section states, their **RDFC-1.0 canonical N-Quads
are byte-identical**. This module is that section, executable.

The algorithm
-------------
**RDFC-1.0** — *RDF Dataset Canonicalization*, W3C Recommendation 2024-05-21
([Appendix E](../docs/vson.md#appendix-e--related-work-and-bibliography)),
the standard that assigns every blank node a deterministic label (`_:c14n0`,
`_:c14n1`, …) computed from the graph's own shape, so that two isomorphic
datasets serialize to the same bytes and two non-isomorphic ones do not.
Default hash algorithm SHA-256, canonical N-Quads per Appendix A of that
Recommendation.

**Why this file carries its own implementation.** rdflib 7.6 has no RDFC-1.0.
What `rdflib.compare` implements is **RGDA1** (McCusker 2015) — a different
digest algorithm, which decides isomorphism correctly but issues different
labels and produces no canonical N-Quads document, so nothing frozen against
it would be reproducible by a second implementer working from the
Recommendation. URDNA2015, the algorithm most JSON-LD toolchains ship, *is*
RDFC-1.0 up to the canonical N-Quads escaping clarification (Appendix B of
the Recommendation), so a URDNA2015 implementation should agree with this one
on every VSON document — none of which contain the control characters where
the two forms differ. The core below (`rdfc10`) is vocabulary-blind: it takes
quads and returns bytes, and `tests/test_canon.py` checks it against the
worked examples published *in* the Recommendation, not against itself.

The VSON layer
--------------
Two normalizations run before canonicalization, both stated normatively in
§4.6 and both promoted from `tools/vson_x/equiv.py`, where they were first
worked out empirically:

  * **N1 — anonymization.** Every IRI in the document namespace that the
    document types as one of `ANONYMOUS_CLASSES` is replaced by a fresh blank
    node, one per IRI. Those classes are the reified relations and the frames
    a document attaches only by `vso:framedBy`: nodes for which no surface
    ever offered the author a name to choose, so the name a transpiler
    invented for one (`:q1`) and the blank node another minted (`_:_q1`)
    cannot be a disagreement about the scene.
  * **N2 — composition edges.** `vso:hasFact` and `vso:occurs` are rewritten
    to `vso:depicts`, which §5.2 declares interchangeable for the same target
    and §5.15.1 already normalizes the same way for the same reason.

Everything else is left exactly as written. In particular the canonical form
is **not** independent of the document namespace: two documents that name the
same queen `:alice` under different bases denote different scenes here, and
that is the intended reading — an IRI is a name, and §5.15's metric is the
instrument for the graded question this all-or-nothing one cannot answer.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.canon examples/throne_room.ttl        # sha256 per file
    python3 -m tools.canon --nquads examples/gallery/01_minimal.vson
    python3 -m tools.canon --corpus                        # the frozen table
    python3 -m tools.canon --freeze                        # rewrite fixtures

Exit 0 — every requested document canonicalized (and, with `--check`, matched
         its frozen hash).
Exit 1 — a document could not be loaded, or a frozen hash moved.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from itertools import permutations
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import rdflib
from rdflib import RDF, BNode, Graph, Literal, URIRef

# The VSO namespace is minted once, in cli/src/penman/routing-tables.json.
# Reading it from the transpiler rather than restating the IRI keeps a stale
# copy from silently switching N1 off: every class test below would fall
# through, nothing would be anonymized, and the oracle would go on answering
# — wrongly, and without a word.
from tools.penman.vson_penman import VSO as VSO_IRI

VSO = rdflib.Namespace(VSO_IRI)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

XSD_STRING = URIRef("http://www.w3.org/2001/XMLSchema#string")

# ---------------------------------------------------------------------------
# §4.6 — the two normalizations
# ---------------------------------------------------------------------------

# The closed list of §4.6. `vso:CameraView` and `vso:Persona` are deliberately
# absent: both are referents. A CameraView is what `vso:viewedBy` and
# `vso:viewer` point at (C5, §3.3), a Persona is the cross-document identity
# carrier of §9.12, and every surface makes the author name them (`^cam`,
# `@alice_persona`). A name the author chose is a name the comparison must
# keep. Entities are absent for the same reason, one step stronger: `:alice`
# is what the document is *about*.
ANONYMOUS_CLASSES: Tuple[URIRef, ...] = (
    VSO.Quality,
    VSO.Stative,
    VSO.Event,
    VSO.Process,
    VSO.SpatialFact,
    VSO.Annotation,
    VSO.Negation,
    VSO.BeliefState,
    VSO.Quantification,
    VSO.SceneContext,
    VSO.VisualStyle,
)

# §5.2 declares the three interchangeable for the same target; the VSON-X
# parser emits only the first (§4.4). Same rule, same rationale, as §5.15.1.
COMPOSITION_EDGES: Tuple[URIRef, ...] = (VSO.depicts, VSO.hasFact, VSO.occurs)
CANONICAL_COMPOSITION_EDGE: URIRef = VSO.depicts


class CanonicalizationError(Exception):
    """The dataset could not be canonicalized within the configured budget."""


# ---------------------------------------------------------------------------
# Canonical N-Quads — Appendix A of the Recommendation
# ---------------------------------------------------------------------------

# Characters the canonical form requires ECHAR for. Everything not listed here
# and not requiring UCHAR is written as itself, in UTF-8.
_ECHAR = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}

# IRIREF forbids these outright, so a canonical serializer must escape them
# rather than emit an unparseable document.
_IRI_FORBIDDEN = set('<>"{}|^`\\')


def _is_xml_char(code: int) -> bool:
    """The XML 1.1 `Char` production, which Appendix A defers to."""
    return (
        0x1 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF
    )


def _uchar(code: int) -> str:
    # "a lowercase \u with 4 HEXes", uppercase hex digits. Code points above
    # the BMP are all Char and never reach this branch, but a lone surrogate
    # in a hostile input would, and \U keeps the output parseable.
    if code <= 0xFFFF:
        return "\\u{:04X}".format(code)
    return "\\U{:08X}".format(code)


def _escape_literal(lexical: str) -> str:
    out: List[str] = []
    for char in lexical:
        code = ord(char)
        if code in _ECHAR:
            out.append(_ECHAR[code])
        elif code <= 0x07 or code == 0x0B or 0x0E <= code <= 0x1F or code == 0x7F:
            out.append(_uchar(code))
        elif not _is_xml_char(code):
            out.append(_uchar(code))
        else:
            out.append(char)
    return "".join(out)


def _escape_iri(iri: str) -> str:
    out: List[str] = []
    for char in iri:
        code = ord(char)
        if char in _IRI_FORBIDDEN or code <= 0x20 or not _is_xml_char(code):
            out.append(_uchar(code))
        else:
            out.append(char)
    return "".join(out)


def _term_to_nquads(term, label: Callable[[BNode], str]) -> str:
    """One term in canonical n-quads form. `label` names blank nodes."""
    if isinstance(term, URIRef):
        return "<{}>".format(_escape_iri(str(term)))
    if isinstance(term, BNode):
        return "_:{}".format(label(term))
    if isinstance(term, Literal):
        text = '"{}"'.format(_escape_literal(str(term)))
        if term.language:
            return "{}@{}".format(text, term.language)
        datatype = term.datatype
        # Appendix A: a literal typed xsd:string MUST NOT write its datatype.
        if datatype is None or datatype == XSD_STRING:
            return text
        return "{}^^<{}>".format(text, _escape_iri(str(datatype)))
    raise CanonicalizationError("not an RDF term: {!r}".format(term))


Quad = Tuple[object, object, object, Optional[object]]


def quad_to_nquads(quad: Quad, label: Callable[[BNode], str]) -> str:
    """A quad in canonical n-quads form, terminated by a single LF."""
    subject, predicate, obj, graph = quad
    parts = [
        _term_to_nquads(subject, label),
        _term_to_nquads(predicate, label),
        _term_to_nquads(obj, label),
    ]
    if graph is not None:
        parts.append(_term_to_nquads(graph, label))
    return " ".join(parts) + " .\n"


def quads_of(graph: Graph) -> List[Quad]:
    """The dataset of a VSON document: its triples, in the default graph.

    A VSON document is one RDF graph, which is the dataset whose default graph
    it is and which has no named graphs — so the graph-name slot is empty in
    every quad, and RDFC-1.0's `g` position never carries a blank node here.
    """
    return [(s, p, o, None) for s, p, o in graph]


# ---------------------------------------------------------------------------
# RDFC-1.0 — §4 of the Recommendation
# ---------------------------------------------------------------------------

# §7.1 of the Recommendation: an implementation MUST defend against datasets
# built to make this algorithm run forever. The budget is on calls to Hash
# N-Degree Quads, which is where the exponential lives. No VSON document in
# this repository spends any of it — the gallery's blank nodes all separate at
# first degree — so the number only has to be large enough that a real
# document never trips it and small enough that a poisoned one fails fast.
DEFAULT_CALL_LIMIT = 10000


class _IdentifierIssuer:
    """§4.3 / §4.5 — issues `<prefix><n>` labels, remembering what it issued."""

    __slots__ = ("prefix", "counter", "issued")

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.counter = 0
        self.issued: Dict[str, str] = {}

    def issue(self, existing: str) -> str:
        if existing in self.issued:
            return self.issued[existing]
        identifier = "{}{}".format(self.prefix, self.counter)
        self.issued[existing] = identifier
        self.counter += 1
        return identifier

    def get(self, existing: str) -> Optional[str]:
        return self.issued.get(existing)

    def copy(self) -> "_IdentifierIssuer":
        clone = _IdentifierIssuer(self.prefix)
        clone.counter = self.counter
        # dict preserves insertion order, which is the order §4.4.3 step 5.3
        # replays when it turns temporary identifiers into canonical ones.
        clone.issued = dict(self.issued)
        return clone


class _Canonicalizer:
    """The canonicalization state of §4.2, plus the algorithms that read it."""

    def __init__(
        self,
        quads: Sequence[Quad],
        hash_algorithm: str = "sha256",
        call_limit: int = DEFAULT_CALL_LIMIT,
    ) -> None:
        self.quads = list(dict.fromkeys(quads))  # a dataset is a set of quads
        self.hash_algorithm = hash_algorithm
        self.call_limit = call_limit
        self.calls = 0
        self.canonical = _IdentifierIssuer("c14n")
        self.bnode_to_quads: Dict[str, List[Quad]] = {}
        self._first_degree: Dict[str, str] = {}

    # -- helpers ------------------------------------------------------------

    def _hash(self, payload: str) -> str:
        digest = hashlib.new(self.hash_algorithm)
        digest.update(payload.encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _bnodes_of(quad: Quad) -> List[Tuple[str, str]]:
        """(position, identifier) for each blank node component of a quad."""
        found = []
        for position, component in (("s", quad[0]), ("o", quad[2]), ("g", quad[3])):
            if isinstance(component, BNode):
                found.append((position, str(component)))
        return found

    # -- §4.6 Hash First Degree Quads ---------------------------------------

    def hash_first_degree(self, reference: str) -> str:
        cached = self._first_degree.get(reference)
        if cached is not None:
            return cached
        lines = [
            quad_to_nquads(
                quad, lambda b: "a" if str(b) == reference else "z"
            )
            for quad in self.bnode_to_quads[reference]
        ]
        lines.sort()  # Python compares str by code point, which is the rule
        result = self._hash("".join(lines))
        self._first_degree[reference] = result
        return result

    # -- §4.7 Hash Related Blank Node ---------------------------------------

    def hash_related(
        self, related: str, quad: Quad, issuer: _IdentifierIssuer, position: str
    ) -> str:
        payload = position
        if position != "g":
            payload += "<{}>".format(_escape_iri(str(quad[1])))
        identifier = self.canonical.get(related) or issuer.get(related)
        if identifier is not None:
            payload += "_:{}".format(identifier)
        else:
            payload += self.hash_first_degree(related)
        return self._hash(payload)

    # -- §4.8 Hash N-Degree Quads -------------------------------------------

    def hash_n_degree(
        self, identifier: str, issuer: _IdentifierIssuer
    ) -> Tuple[str, _IdentifierIssuer]:
        self.calls += 1
        if self.calls > self.call_limit:
            raise CanonicalizationError(
                "RDFC-1.0 exceeded {} calls to Hash N-Degree Quads; the input "
                "is degenerate or adversarial (Recommendation §7.1)".format(
                    self.call_limit
                )
            )

        # Step 3 — group every blank node this one is related to by the hash
        # of *how* it is related (position, predicate, and either the label
        # already issued to it or its first-degree hash).
        related_hashes: Dict[str, List[str]] = {}
        for quad in self.bnode_to_quads[identifier]:
            for position, component in self._bnodes_of(quad):
                if component == identifier:
                    continue
                key = self.hash_related(component, quad, issuer, position)
                related_hashes.setdefault(key, []).append(component)

        data_to_hash = ""
        for related_hash in sorted(related_hashes):
            data_to_hash += related_hash
            chosen_path = ""
            chosen_issuer: Optional[_IdentifierIssuer] = None

            # Step 5.4 — every ordering of the tied nodes is a candidate
            # "gossip path"; the lexicographically smallest one wins, which is
            # what makes the result independent of the input's labels.
            for permutation in permutations(related_hashes[related_hash]):
                issuer_copy = issuer.copy()
                path = ""
                recursion: List[str] = []
                abandoned = False

                for related in permutation:
                    canonical = self.canonical.get(related)
                    if canonical is not None:
                        path += "_:{}".format(canonical)
                    else:
                        if issuer_copy.get(related) is None:
                            recursion.append(related)
                        path += "_:{}".format(issuer_copy.issue(related))
                    if (
                        chosen_path
                        and len(path) >= len(chosen_path)
                        and path > chosen_path
                    ):
                        abandoned = True
                        break
                if abandoned:
                    continue

                for related in recursion:
                    result, issuer_copy = self.hash_n_degree(related, issuer_copy)
                    path += "_:{}".format(issuer_copy.issue(related))
                    path += "<{}>".format(result)
                    if (
                        chosen_path
                        and len(path) >= len(chosen_path)
                        and path > chosen_path
                    ):
                        abandoned = True
                        break
                if abandoned:
                    continue

                if not chosen_path or path < chosen_path:
                    chosen_path = path
                    chosen_issuer = issuer_copy

            data_to_hash += chosen_path
            if chosen_issuer is not None:
                issuer = chosen_issuer

        return self._hash(data_to_hash), issuer

    # -- §4.4 Canonicalization Algorithm ------------------------------------

    def run(self) -> str:
        # Step 2 — the blank node to quads map.
        for quad in self.quads:
            for _position, identifier in self._bnodes_of(quad):
                bucket = self.bnode_to_quads.setdefault(identifier, [])
                if quad not in bucket:
                    bucket.append(quad)

        # Step 3 — first-degree hashes.
        hash_to_bnodes: Dict[str, List[str]] = {}
        for identifier in self.bnode_to_quads:
            hash_to_bnodes.setdefault(self.hash_first_degree(identifier), []).append(
                identifier
            )

        # Step 4 — a hash reached by exactly one node names that node.
        for key in sorted(hash_to_bnodes):
            identifiers = hash_to_bnodes[key]
            if len(identifiers) > 1:
                continue
            self.canonical.issue(identifiers[0])
            del hash_to_bnodes[key]

        # Step 5 — the rest are tied at first degree and are separated by the
        # n-degree hash of the paths leading out of them.
        for key in sorted(hash_to_bnodes):
            hash_path_list: List[Tuple[str, _IdentifierIssuer]] = []
            for identifier in hash_to_bnodes[key]:
                if self.canonical.get(identifier) is not None:
                    continue
                temporary = _IdentifierIssuer("b")
                temporary.issue(identifier)
                hash_path_list.append(self.hash_n_degree(identifier, temporary))
            # sorted() is stable, so nodes an automorphism leaves genuinely
            # indistinguishable keep the order they were reached in.
            for _result_hash, temporary in sorted(hash_path_list, key=lambda r: r[0]):
                for existing in temporary.issued:
                    self.canonical.issue(existing)

        # Steps 6 and 7 — relabel, serialize, sort, concatenate.
        missing = [b for b in self.bnode_to_quads if self.canonical.get(b) is None]
        if missing:  # pragma: no cover — defensive; step 5 labels everything
            raise CanonicalizationError(
                "no canonical identifier issued for {}".format(sorted(missing))
            )

        def label(node: BNode) -> str:
            issued = self.canonical.get(str(node))
            if issued is None:  # pragma: no cover — same invariant as above
                raise CanonicalizationError("unlabelled blank node {!r}".format(node))
            return issued

        lines = [quad_to_nquads(quad, label) for quad in self.quads]
        lines.sort()
        return "".join(lines)


def rdfc10(
    quads: Iterable[Quad],
    hash_algorithm: str = "sha256",
    call_limit: int = DEFAULT_CALL_LIMIT,
) -> str:
    """The serialized canonical form of a dataset, per RDFC-1.0.

    Vocabulary-blind on purpose: this is the Recommendation and nothing else,
    which is what lets `tests/test_canon.py` check it against the worked
    examples published in the Recommendation itself.
    """
    return _Canonicalizer(list(quads), hash_algorithm, call_limit).run()


# ---------------------------------------------------------------------------
# The VSON canonical form — §4.6
# ---------------------------------------------------------------------------


def document_namespace(graph: Graph) -> Optional[str]:
    """The document namespace: what `:` resolves to, else the base, else none.

    N1 rewrites names, so the set of names it may touch has to be decidable
    from the document alone. It is the namespace bound to the empty prefix —
    every VSON surface emits one — falling back to the document base. A
    document with neither has no document namespace, and N1 anonymizes
    nothing: no IRI in it was invented by a transpiler.
    """
    for prefix, namespace in graph.namespaces():
        if prefix == "":
            return str(namespace)
    base = getattr(graph, "base", None)
    return str(base) if base else None


def _anonymizable(graph: Graph, subject, namespace: Optional[str]) -> bool:
    if namespace is None or not isinstance(subject, URIRef):
        return False
    if not str(subject).startswith(namespace):
        return False
    for cls in graph.objects(subject, RDF.type):
        if cls in ANONYMOUS_CLASSES:
            return True
    return False


def canonical_graph(graph: Graph) -> Graph:
    """Apply N1 and N2. The result is what §4.6 canonicalizes."""
    namespace = document_namespace(graph)
    rewrite: Dict[URIRef, BNode] = {}
    for subject in set(graph.subjects()):
        if _anonymizable(graph, subject, namespace):
            # One fresh blank node per IRI: the map is injective, so N1 can
            # never merge two nodes the document distinguished.
            rewrite[subject] = BNode()

    out = Graph()
    for prefix, namespace_iri in graph.namespaces():
        out.bind(prefix, namespace_iri)
    for subject, predicate, obj in graph:
        edge = CANONICAL_COMPOSITION_EDGE if predicate in COMPOSITION_EDGES else predicate
        out.add(
            (
                rewrite.get(subject, subject),
                edge,
                rewrite.get(obj, obj) if isinstance(obj, URIRef) else obj,
            )
        )
    return out


def canonical_nquads(graph: Graph) -> str:
    """The canonical form of a VSON document: N1, N2, then RDFC-1.0."""
    return rdfc10(quads_of(canonical_graph(graph)))


def canonical_hash(graph: Graph) -> str:
    """SHA-256 of the canonical N-Quads, lowercase hex — the document's name.

    The hash is a convenience over the bytes, not a second definition: §4.6
    decides equality on the canonical N-Quads themselves. It is what a fixture
    can freeze and a report can print.
    """
    return hashlib.sha256(canonical_nquads(graph).encode("utf-8")).hexdigest()


def denotes_same(left: Graph, right: Graph) -> bool:
    """The §4.6 test. True iff the two documents denote the same scene."""
    return canonical_nquads(left) == canonical_nquads(right)


def load_graph(path: str) -> Graph:
    """Materialize the VSON-T graph of a document in any of the three syntaxes.

    Written once, in `tools/metrics/smatch.parse_graph` (§5.15). §4.6 and
    §5.15 have to agree about what "the materialized VSON-T graph" is, and two
    loaders is exactly how they would stop agreeing.
    """
    from tools.metrics.smatch import parse_graph

    return parse_graph(path)


def hash_of_path(path: str) -> str:
    return canonical_hash(load_graph(path))


# ---------------------------------------------------------------------------
# The frozen corpus — tests/fixtures/canonical/
# ---------------------------------------------------------------------------

FIXTURES = os.path.join(REPO, "tests", "fixtures", "canonical")
MANIFEST = os.path.join(FIXTURES, "hashes.txt")
# The one canonical form frozen as bytes rather than as a hash. It is the
# richest scene in the gallery and it is one of the twelve that exists in two
# surfaces, so this single file is what the cross-syntax claim *is*: VSON-P
# and VSON-X both canonicalize to these bytes.
WITNESS_STEM = "11_throne_room"
WITNESS = os.path.join(FIXTURES, WITNESS_STEM + ".nq")

MANIFEST_HEADER = """\
# VSON canonical hashes — docs/vson.md §4.6.
#
# SHA-256 of the RDFC-1.0 canonical N-Quads of each shipped document, after
# the §4.6 normalizations (N1 anonymization, N2 composition edges). Two rows
# with one hash are two documents that denote the same scene; the twelve
# VSON-P / VSON-X pairs below are the cross-syntax proof, and every one of
# them is a pair of equal hashes.
#
# Frozen. Regenerate with `python3 -m tools.canon --freeze`, which is an
# authoring step and never a fix: a moved hash means a document, a transpiler
# or an emitter changed what a scene denotes, and which one it was is the
# thing to establish before the fixture moves.
#
# <sha256>  <surface>  <path>
"""

SURFACES = (("VSON-T", ".ttl"), ("VSON-X", ".x.vson"), ("VSON-P", ".vson"))


def surface_of(path: str) -> str:
    for name, suffix in SURFACES:
        if path.endswith(suffix):
            return name
    return "unknown"


def corpus_paths() -> List[str]:
    """Every document the manifest covers, repo-relative and sorted."""
    paths = ["examples/throne_room.ttl"]
    for directory in ("examples/gallery", "examples/gallery-x"):
        absolute = os.path.join(REPO, directory)
        paths.extend(
            "{}/{}".format(directory, name)
            for name in sorted(os.listdir(absolute))
            if name.endswith(".vson")
        )
    return paths


def corpus_rows() -> List[Tuple[str, str, str]]:
    """(hash, surface, path) for the whole corpus, in manifest order."""
    return [
        (hash_of_path(os.path.join(REPO, path)), surface_of(path), path)
        for path in corpus_paths()
    ]


def render_manifest(rows: Sequence[Tuple[str, str, str]]) -> str:
    return MANIFEST_HEADER + "".join(
        "{}  {:<6}  {}\n".format(digest, surface, path)
        for digest, surface, path in rows
    )


def parse_manifest(text: str) -> List[Tuple[str, str, str]]:
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, surface, path = line.split()
        rows.append((digest, surface, path))
    return rows


def frozen_rows() -> List[Tuple[str, str, str]]:
    with open(MANIFEST, encoding="utf-8") as handle:
        return parse_manifest(handle.read())


def freeze() -> List[str]:
    """Rewrite both fixtures from the corpus. Returns the paths written."""
    rows = corpus_rows()
    if not os.path.isdir(FIXTURES):
        os.makedirs(FIXTURES)
    with open(MANIFEST, "w", encoding="utf-8") as handle:
        handle.write(render_manifest(rows))
    witness = canonical_nquads(
        load_graph(os.path.join(REPO, "examples/gallery", WITNESS_STEM + ".vson"))
    )
    with open(WITNESS, "w", encoding="utf-8") as handle:
        handle.write(witness)
    return [MANIFEST, WITNESS]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.canon",
        description=(
            "RDFC-1.0 canonical form and SHA-256 of a VSON document "
            "(docs/vson.md §4.6)."
        ),
    )
    ap.add_argument("paths", nargs="*", help=".ttl (VSON-T), .vson (VSON-P), .x.vson")
    ap.add_argument(
        "--nquads",
        action="store_true",
        help="print the canonical N-Quads instead of the hash",
    )
    ap.add_argument(
        "--corpus", action="store_true", help="print the manifest for the shipped corpus"
    )
    ap.add_argument(
        "--check", action="store_true", help="compare the corpus against the fixtures"
    )
    ap.add_argument("--freeze", action="store_true", help="rewrite the fixtures")
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)

    if args.freeze:
        for path in freeze():
            print("  froze {}".format(os.path.relpath(path, REPO)))
        return 0

    if args.check:
        expected = {(surface, path): digest for digest, surface, path in frozen_rows()}
        moved = []
        for digest, surface, path in corpus_rows():
            was = expected.get((surface, path))
            if was != digest:
                moved.append((path, was, digest))
        for path, was, digest in moved:
            print("  MOVED {}\n    frozen {}\n    now    {}".format(path, was, digest))
        print(
            "  {} document(s), {} moved".format(len(corpus_paths()), len(moved))
        )
        return 1 if moved else 0

    if args.corpus:
        sys.stdout.write(render_manifest(corpus_rows()))
        return 0

    if not args.paths:
        _parser().print_help()
        return 1

    status = 0
    for path in args.paths:
        try:
            graph = load_graph(path)
        except Exception as exc:  # load / transpile failure
            print("  ERROR {}: {}".format(path, exc), file=sys.stderr)
            status = 1
            continue
        if args.nquads:
            sys.stdout.write(canonical_nquads(graph))
        else:
            print("{}  {}".format(canonical_hash(graph), path))
    return status


if __name__ == "__main__":
    sys.exit(main())
