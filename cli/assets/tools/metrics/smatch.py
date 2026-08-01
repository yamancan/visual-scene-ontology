#!/usr/bin/env python3
"""Smatch — triple-level agreement between two VSON documents.

docs/vson.md §5.15. Two extraction runs over one image produce two graphs whose
node names have nothing to do with each other: `:cat` in one run and `_:e3` in
the other may be the same animal, and no string comparison can tell. Smatch
(Cai & Knight 2013, for AMR) is the standard answer — search for the variable
alignment that maximizes the number of triples the two graphs share, then report
precision, recall and F1 over triples under that alignment. This module is that
metric, defined over VSON's materialized VSON-T graph so it works from any
surface syntax, and reporting the per-layer sub-scores a layered scheme owes its
readers.

**It is agreement, not correctness.** F1 = 1.0 says the two documents assert the
same graph up to variable renaming. It says nothing about whether either one
describes the picture: two runs of the same model agreeing on the same
hallucination score 1.0, and §2.1 is unchanged by every number here. No image is
read. This is the same posture as `vson verify --geometry` — claims compared
against claims — with the second set of claims coming from another document
rather than from the same one.

What a triple is
----------------
Every term is either a **variable** or a **constant** (§5.15.1):

  * variable — a blank node, or an IRI outside the VSON and W3C vocabulary
    namespaces that the document asserts at least one triple *about* (it appears
    in subject position). These are the nodes whose names are arbitrary, and the
    alignment is a partial injection from one document's variables to the
    other's.
  * constant — a literal (matched on lexical form *and* datatype/language), a
    vocabulary IRI (matched on the full IRI), or a document-local IRI that only
    ever appears in object position (matched on its **local name**, because the
    document base is arbitrary per run: `:Human` and `:Human` under two
    different bases are the same class designation).

A triple `(s, p, o)` of document A matches a triple of B when the predicates are
equal, and each of `s`/`o` either is the same constant on both sides or is a
variable on both sides with the alignment mapping one to the other. Predicates
are always compared as constants; a document-local predicate would be a C2
violation, and `vson validate` is where that is reported.

The alignment
-------------
Finding the alignment that maximizes matches is NP-hard in general (Cai & Knight
prove it by reduction), so this is the same hill-climbing search the reference
smatch uses: start from an initialization, repeatedly take the single best
improving move (re-point one variable, or swap two), stop at a local optimum,
and keep the best result over several restarts.

Seed policy — the part that has to be written down
--------------------------------------------------
A metric whose number moves between runs is not a metric. Three things pin this
one (§5.15.4):

  1. **The restarts are enumerated, not sampled.** Restart 0 is the
     colour-refinement alignment (a 1-WL refinement of both graphs, paired by
     colour); restart 1 is the greedy constant-anchored alignment (classic
     smatch "smart initialization"); restarts 2..R-1 are pseudo-random. The
     default R is 5.
  2. **The pseudo-random source is specified here, not imported.**
     `random.Random` is only guaranteed reproducible for `random()` itself, and
     any reimplementation in another language could not match it at all. The
     generator below is a 64-bit LCG with the constants of Knuth's MMIX, seeded
     `seed + restart_index`, driving a Fisher-Yates shuffle written out in this
     file. A third party gets byte-identical restarts from the same seed.
  3. **No ordering decision consults a name.** Variables are ordered by their
     refinement colour, and residual ties (variables the refinement cannot tell
     apart) by first appearance. Blank-node labels are minted per parse by
     rdflib and differ between runs, so a sort that touched them would make the
     score depend on the parser's mood.

The default seed is **0**, and CI runs the default. `--seed` exists for a study
that wants to report a spread over seeds; a reported VSON agreement number
should state the seed and the restart count beside it, exactly as an AMR Smatch
number states its restart count.

Per-layer sub-scores
--------------------
A scheme whose thesis is that structure comes in layers has to report per layer:
one F1 hides which layer moved. Every triple is assigned to exactly one of
**objects, attributes, spatial, frames, events, other** by the tables in
§5.15.3, and the sub-scores are computed **under the single global alignment** —
never by re-optimizing per layer, which would report a number no single reading
of the two documents achieves. `spatial` is additionally reported
**viewer-blind**: the same layer with `vso:viewer` triples dropped from both
sides, which separates "the two runs disagree about the relation" from "the two
runs disagree about which camera anchors it".

Precision counts matched triples on A's side of a layer; recall on B's side.
The two are equal overall (matching is a bijection between the matched subsets)
and can differ inside a layer, when the layer tables put a matched pair in
different layers on the two sides — a `vso:depicts` edge to a node one document
types and the other does not. F1 is the harmonic mean of the two, and reduces to
`2m / (|A| + |B|)` whenever they agree, which is why the overall F1 is symmetric
in its arguments.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.metrics.smatch a.vson b.ttl
    python3 -m tools.metrics.smatch --format json a.x.vson b.vson
Accepted inputs: `.ttl` / `.turtle` (VSON-T), `.vson` (VSON-P), `.x.vson`
(VSON-X). The two need not be in the same syntax.

Exit 0 — the documents are identical at triple level (F1 = 1.0).
Exit 1 — they differ.
Exit 2 — no verdict: unreadable input, unknown syntax, bad flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from rdflib import BNode, Graph, Literal, URIRef

VSO = "https://w3id.org/vson/v1/ontology#"
RCC = "https://w3id.org/vson/v1/rcc8#"
ALLEN = "https://w3id.org/vson/v1/allen#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

# The namespaces whose IRIs are vocabulary, never document identity. An IRI
# outside this list is the document's own name for something, and the whole
# point of an alignment is that such names carry no information across runs.
VOCABULARY_NAMESPACES = (
    VSO,
    RCC,
    ALLEN,
    RDF_NS,
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2002/07/owl#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/ns/shacl#",
    "http://www.w3.org/2004/02/skos/core#",
    "https://w3id.org/vson/v1/shapes#",
)

RDF_TYPE = URIRef(RDF_NS + "type")

# --------------------------------------------------------------------------
# The layer partition (§5.15.3)
# --------------------------------------------------------------------------

LAYER_OBJECTS = "objects"
LAYER_ATTRIBUTES = "attributes"
LAYER_SPATIAL = "spatial"
LAYER_FRAMES = "frames"
LAYER_EVENTS = "events"
LAYER_OTHER = "other"

#: Report order. `spatial` is followed by its viewer-blind variant, which is a
#: second reading of the same triples rather than a seventh layer.
LAYERS = (
    LAYER_OBJECTS,
    LAYER_ATTRIBUTES,
    LAYER_SPATIAL,
    LAYER_FRAMES,
    LAYER_EVENTS,
    LAYER_OTHER,
)

SPATIAL_VIEWER_BLIND = "spatial_viewer_blind"


def _vso(names: str) -> Set[str]:
    return {VSO + n for n in names.split()}


CLASS_LAYER: Dict[str, str] = {}
for _cls, _layer in (
    ("Frame SceneContext VisualStyle CameraView Composition Persona", LAYER_FRAMES),
    ("Perdurant Event Process Stative", LAYER_EVENTS),
    ("SpatialFact", LAYER_SPATIAL),
    ("Quality", LAYER_ATTRIBUTES),
    ("Entity Endurant PhysicalObject Aggregate Substance Region", LAYER_OBJECTS),
    ("Annotation Negation BeliefState Quantification", LAYER_OTHER),
):
    for _name in _vso(_cls):
        CLASS_LAYER[_name] = _layer

#: The three interchangeable Composition membership edges (§5.2). They are
#: normalized to `vso:depicts` before scoring, so a scene written with
#: `:hasFact` in VSON-P and `:depicts` in VSON-X is not reported as a
#: disagreement — the spec says the two say the same thing.
COMPOSITION_EDGES = _vso("depicts hasFact occurs")
CANONICAL_COMPOSITION_EDGE = VSO + "depicts"

FRAME_PROPERTIES = _vso(
    "framedBy viewedBy rendersAs angle focalLength framing lookAt cameraPosition "
    "aesthetic palette medium venue atmosphere timeOfDay weather embodies hasInvariant"
)
SPATIAL_PROPERTIES = _vso(
    "figure ground rcc directional proximal viewer occludes visibleFraction"
)
EVENT_PROPERTIES = _vso(
    "lemma agent patient theme instrument recipient source goal beneficiary "
    "experiencer stimulus location cause result holder manner time "
    "causes enables prevents triggers holds wears owns carries"
)
ATTRIBUTE_PROPERTIES = _vso(
    "individuation animacy countability affordance class hasQuality dimension "
    "value modifier bbox2d position3d scale3d rotation"
)
#: Named for the reader, not for the algorithm: anything unlisted lands in
#: `other` anyway, and the partition stays total by construction.
OTHER_PROPERTIES = _vso(
    "partOf hasPart properPartOf overlaps disjoint believes intends perceives "
    "proposition negatedStatement quantifier variable scope qDomain "
    "annotatedSubject annotatedPredicate annotatedObject probability confidence"
)

VIEWER = VSO + "viewer"

# --------------------------------------------------------------------------
# A deterministic pseudo-random generator (§5.15.4)
# --------------------------------------------------------------------------


class Lcg:
    """A 64-bit linear congruential generator, Knuth's MMIX constants.

    Written out rather than imported so the restart sequence is reproducible by
    anything that can multiply 64-bit integers — another Python version, another
    language, a reviewer with a calculator and patience. `random.Random`
    guarantees reproducibility for `random()` alone, and none at all for
    `shuffle`, which is exactly the call a restart needs.
    """

    MULT = 6364136223846793005
    INC = 1442695040888963407
    MASK = (1 << 64) - 1

    def __init__(self, seed: int) -> None:
        self.state = seed & self.MASK

    def next_u32(self) -> int:
        self.state = (self.state * self.MULT + self.INC) & self.MASK
        # The high bits of an LCG are the well-behaved ones; the low bit of a
        # power-of-two-modulus LCG alternates.
        return (self.state >> 32) & 0xFFFFFFFF

    def below(self, bound: int) -> int:
        """A value in `[0, bound)`. Modulo bias is accepted and irrelevant: this
        picks a starting point for a hill climb, not a statistic."""
        return self.next_u32() % bound if bound > 0 else 0

    def shuffled(self, items: Sequence) -> List:
        """Fisher-Yates, written out so a reimplementation can match it."""
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.below(i + 1)
            out[i], out[j] = out[j], out[i]
        return out


def _digest(payload: str) -> str:
    """A stable content hash. `hash()` is salted per process (PYTHONHASHSEED),
    so it can never order anything this module prints."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# Loading a document into the scored form
# --------------------------------------------------------------------------


class LoadError(Exception):
    """The document could not be read. Never a verdict — exit 2."""


def _local_name(iri: str) -> str:
    for sep in ("#", "/"):
        if sep in iri:
            head, _, tail = iri.rpartition(sep)
            if tail:
                return tail
    return iri


def _is_vocabulary(term: URIRef) -> bool:
    return str(term).startswith(VOCABULARY_NAMESPACES)


def constant_key(term) -> str:
    """The key a constant is matched on. Prefixed by kind so a literal whose
    lexical form happens to spell an IRI cannot collide with that IRI."""
    if isinstance(term, Literal):
        return "L" + term.n3()
    if isinstance(term, URIRef):
        if _is_vocabulary(term):
            return "I" + str(term)
        return "N" + _local_name(str(term))
    raise TypeError("blank nodes are always variables: {!r}".format(term))


def parse_graph(path: str) -> Graph:
    """Materialize the VSON-T graph of a document in any of the three syntaxes.

    The transpilers are imported lazily so a Turtle-only run does not pay for
    them, and so this module keeps working in a checkout whose optional pieces
    are missing.
    """
    lower = path.lower()
    graph = Graph()
    try:
        if lower.endswith(".x.vson"):
            from tools.vson_x import to_turtle as x_to_turtle

            with open(path, encoding="utf-8") as handle:
                graph.parse(data=x_to_turtle(handle.read()), format="turtle")
        elif lower.endswith(".vson"):
            from tools.penman import vson_penman as vp

            with open(path, encoding="utf-8") as handle:
                graph.parse(data=vp.to_turtle(handle.read()), format="turtle")
        elif lower.endswith((".ttl", ".turtle")):
            graph.parse(path, format="turtle")
        else:
            raise LoadError(
                "{}: unknown syntax. Expected .ttl / .turtle (VSON-T), .vson "
                "(VSON-P) or .x.vson (VSON-X).".format(path)
            )
    except LoadError:
        raise
    except OSError as exc:
        raise LoadError("{}: {}".format(path, exc.strerror or exc)) from exc
    except Exception as exc:  # parse / transpile failure
        raise LoadError("{}: {}: {}".format(path, type(exc).__name__, exc)) from exc
    return graph


@dataclass
class Document:
    """One document, in the only form the metric looks at.

    `triples` are canonical: predicates are strings, endpoints are slots — a
    slot is `("v", index)` for a variable and `("c", key)` for a constant — and
    the list is deduplicated and ordered by the deterministic key of §5.15.4.
    `layers[i]` is the layer of `triples[i]`.
    """

    path: str
    triples: List[Tuple[str, Tuple[str, object], Tuple[str, object]]]
    layers: List[str]
    n_vars: int

    def __len__(self) -> int:
        return len(self.triples)


def _normalized_triples(graph: Graph) -> List[Tuple[object, str, object]]:
    """Every triple with the three interchangeable Composition edges collapsed."""
    out = []
    for subj, pred, obj in graph:
        key = str(pred)
        if key in COMPOSITION_EDGES:
            key = CANONICAL_COMPOSITION_EDGE
        out.append((subj, key, obj))
    return out


def _variable_terms(triples) -> Set[object]:
    """Blank nodes, plus every document-local IRI the document describes.

    The subject-position rule is what keeps `:Human` in `:alice a :Human` a
    constant: the document names the class and says nothing about it, so its
    name is all the identity it has, and two runs that write different class
    names must not be credited with agreeing. A node the document *does*
    describe is an entity, and its name is arbitrary.
    """
    described = {s for s, _, _ in triples if isinstance(s, URIRef) and not _is_vocabulary(s)}
    variables: Set[object] = set(described)
    for subj, _, obj in triples:
        for term in (subj, obj):
            if isinstance(term, BNode):
                variables.add(term)
    return variables


def _node_family(type_objects: Dict[object, Set[str]], node) -> Optional[str]:
    """The layer a node's asserted VSO classes put it in, or None."""
    for cls in sorted(type_objects.get(node, ())):
        layer = CLASS_LAYER.get(cls)
        if layer is not None:
            return layer
    return None


def _layer_of(type_objects, subj, pred: str, obj) -> str:
    """The layer of one triple. The rules of §5.15.3, in order."""
    if pred == str(RDF_TYPE):
        if isinstance(obj, URIRef) and str(obj) in CLASS_LAYER:
            return CLASS_LAYER[str(obj)]
        if isinstance(obj, URIRef) and _is_vocabulary(obj):
            return LAYER_OTHER
        # A document-local class designation (`:alice a :Human`) is a claim
        # about the same node the VSO class typed, so it lands in that layer.
        return _node_family(type_objects, subj) or LAYER_OBJECTS
    subject_family = _node_family(type_objects, subj)
    if subject_family == LAYER_OTHER:
        # Annotation / Negation / BeliefState / Quantification: the reification
        # layers the five named layers do not cover, whichever property is used
        # (`vso:source` is a thematic role on a Perdurant and a provenance
        # string on an Annotation — the subject decides).
        return LAYER_OTHER
    if pred == CANONICAL_COMPOSITION_EDGE:
        return _node_family(type_objects, obj) or LAYER_OBJECTS
    if pred in FRAME_PROPERTIES:
        return LAYER_FRAMES
    if pred in SPATIAL_PROPERTIES:
        return LAYER_SPATIAL
    if pred in EVENT_PROPERTIES or pred.startswith(ALLEN):
        return LAYER_EVENTS
    if pred in ATTRIBUTE_PROPERTIES:
        return LAYER_ATTRIBUTES
    return LAYER_OTHER


def _refined_colors(triples, variables) -> Dict[object, str]:
    """1-WL colour refinement over the variables, anchored on the constants.

    The initial colour of a variable is the multiset of its constant-anchored
    edges; each round folds in the colours of its variable neighbours. Two
    variables the refinement separates can never be confused by the orderings
    below, and two it does not separate are interchangeable enough that the
    order between them cannot be read off any name.
    """
    out_const: Dict[object, List[str]] = {v: [] for v in variables}
    out_var: Dict[object, List[Tuple[str, object]]] = {v: [] for v in variables}
    in_var: Dict[object, List[Tuple[str, object]]] = {v: [] for v in variables}
    for subj, pred, obj in triples:
        s_var, o_var = subj in variables, obj in variables
        if s_var and o_var:
            out_var[subj].append((pred, obj))
            in_var[obj].append((pred, subj))
        elif s_var:
            out_const[subj].append(pred + " " + constant_key(obj))
        elif o_var:
            out_const[obj].append("^" + pred + " " + constant_key(subj))

    color = {v: _digest("|".join(sorted(out_const[v]))) for v in variables}
    previous = -1
    for _ in range(len(variables) + 1):
        distinct = len(set(color.values()))
        if distinct == previous or distinct == len(variables):
            break
        previous = distinct
        color = {
            v: _digest(
                color[v]
                + "|>"
                + "|".join(sorted(p + " " + color[n] for p, n in out_var[v]))
                + "|<"
                + "|".join(sorted(p + " " + color[n] for p, n in in_var[v]))
            )
            for v in variables
        }
    return color


def build_document(graph: Graph, path: str = "<graph>") -> Document:
    """Turn a parsed graph into the canonical scored form."""
    triples = _normalized_triples(graph)
    variables = _variable_terms(triples)

    type_objects: Dict[object, Set[str]] = {}
    for subj, pred, obj in triples:
        if pred == str(RDF_TYPE) and isinstance(obj, URIRef):
            type_objects.setdefault(subj, set()).add(str(obj))

    colors = _refined_colors(triples, variables)
    # First appearance breaks the ties the refinement cannot: rdflib's in-memory
    # store iterates in insertion (parse) order, so this is stable for a given
    # input text, and it is only ever consulted between variables the refinement
    # has already declared indistinguishable.
    first_seen: Dict[object, int] = {}
    for index, (subj, _, obj) in enumerate(triples):
        for term in (subj, obj):
            if term in variables and term not in first_seen:
                first_seen[term] = index
    ordered = sorted(variables, key=lambda v: (colors[v], first_seen.get(v, 0)))
    var_id = {v: i for i, v in enumerate(ordered)}

    def slot(term):
        if term in variables:
            return ("v", var_id[term])
        return ("c", constant_key(term))

    canonical = {}
    for subj, pred, obj in triples:
        canonical[(pred, slot(subj), slot(obj))] = _layer_of(
            type_objects, subj, pred, obj
        )
    keyed = sorted(canonical.items(), key=lambda item: repr(item[0]))
    return Document(
        path=path,
        triples=[t for t, _ in keyed],
        layers=[layer for _, layer in keyed],
        n_vars=len(ordered),
    )


def load_document(path: str) -> Document:
    """Parse and canonicalize one document from disk."""
    return build_document(parse_graph(path), path)


# --------------------------------------------------------------------------
# The search
# --------------------------------------------------------------------------


class _Weights:
    """The two tables the incremental scorer runs on.

    `w1[(a, b)]` counts the triples that match as soon as A-variable `a` is
    aligned to B-variable `b`, whatever else the alignment does: the ones with a
    constant in the other position, and the self-loops. `w2[(a, b), (a2, b2)]`
    counts the triples that need *both* pairs. `base` is the triples with no
    variable at all, which every alignment matches.
    """

    def __init__(self, doc_a: Document, doc_b: Document) -> None:
        b_index = set(doc_b.triples)
        self.base = 0
        # a -> {const-anchored triple signature}
        a_anchored: Dict[int, List[Tuple[str, str, str]]] = {}
        a_rel: List[Tuple[str, int, int]] = []
        for pred, s, o in doc_a.triples:
            if s[0] == "v" and o[0] == "v":
                if s[1] == o[1]:
                    a_anchored.setdefault(s[1], []).append(("self", pred, ""))
                else:
                    a_rel.append((pred, s[1], o[1]))
            elif s[0] == "v":
                a_anchored.setdefault(s[1], []).append(("out", pred, o[1]))
            elif o[0] == "v":
                a_anchored.setdefault(o[1], []).append(("in", pred, s[1]))
            elif (pred, s, o) in b_index:
                self.base += 1

        self.w1: Dict[Tuple[int, int], int] = {}
        for a, entries in a_anchored.items():
            for b in range(doc_b.n_vars):
                hits = 0
                for kind, pred, key in entries:
                    if kind == "out":
                        probe = (pred, ("v", b), ("c", key))
                    elif kind == "in":
                        probe = (pred, ("c", key), ("v", b))
                    else:
                        probe = (pred, ("v", b), ("v", b))
                    if probe in b_index:
                        hits += 1
                if hits:
                    self.w1[(a, b)] = hits

        self.w2: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = {}
        b_rel: Dict[str, List[Tuple[int, int]]] = {}
        for pred, s, o in doc_b.triples:
            if s[0] == "v" and o[0] == "v" and s[1] != o[1]:
                b_rel.setdefault(pred, []).append((s[1], o[1]))
        for pred, a, a2 in a_rel:
            for b, b2 in b_rel.get(pred, ()):
                key = ((a, b), (a2, b2))
                self.w2[key] = self.w2.get(key, 0) + 1

        # Candidate targets for each A-variable: the B-variables it could ever
        # gain anything from. Anything outside this set is a move that cannot
        # raise the score, so the search never considers it.
        pools: Dict[int, Set[int]] = {a: set() for a in range(doc_a.n_vars)}
        for (a, b) in self.w1:
            pools[a].add(b)
        for ((a, b), (a2, b2)) in self.w2:
            pools[a].add(b)
            pools[a2].add(b2)
        self.candidates: Dict[int, List[int]] = {
            a: sorted(bs) for a, bs in pools.items()
        }

    def unit(self, a: int, b: Optional[int]) -> int:
        if b is None:
            return 0
        return self.w1.get((a, b), 0)

    def pair(self, a: int, b: Optional[int], a2: int, b2: Optional[int]) -> int:
        if b is None or b2 is None:
            return 0
        return self.w2.get(((a, b), (a2, b2)), 0) + self.w2.get(((a2, b2), (a, b)), 0)

    def score(self, mapping: Dict[int, Optional[int]]) -> int:
        total = self.base
        items = [(a, b) for a, b in sorted(mapping.items()) if b is not None]
        for i, (a, b) in enumerate(items):
            total += self.w1.get((a, b), 0)
            for a2, b2 in items[i + 1:]:
                total += self.pair(a, b, a2, b2)
        return total


def _move_delta(w: _Weights, mapping, a: int, new_b: Optional[int]) -> int:
    """Score change from re-pointing `a`, with `new_b` currently unused."""
    old_b = mapping[a]
    delta = w.unit(a, new_b) - w.unit(a, old_b)
    for a2, b2 in mapping.items():
        if a2 == a or b2 is None:
            continue
        delta += w.pair(a, new_b, a2, b2) - w.pair(a, old_b, a2, b2)
    return delta


def _swap_delta(w: _Weights, mapping, a1: int, a2: int) -> int:
    """Score change from exchanging the targets of `a1` and `a2`."""
    b1, b2 = mapping[a1], mapping[a2]
    delta = (
        w.unit(a1, b2) - w.unit(a1, b1) + w.unit(a2, b1) - w.unit(a2, b2)
    )
    for a3, b3 in mapping.items():
        if a3 in (a1, a2) or b3 is None:
            continue
        delta += w.pair(a1, b2, a3, b3) - w.pair(a1, b1, a3, b3)
        delta += w.pair(a2, b1, a3, b3) - w.pair(a2, b2, a3, b3)
    delta += w.pair(a1, b2, a2, b1) - w.pair(a1, b1, a2, b2)
    return delta


_MAX_STEPS = 500


def _hill_climb(w: _Weights, mapping: Dict[int, Optional[int]]) -> Tuple[Dict, int]:
    """Steepest-ascent hill climbing to a local optimum.

    Two move kinds, both from the reference smatch: re-point one variable at a
    free target, and swap two variables' targets. Ties keep the incumbent, and
    every enumeration order below is over integer ids assigned by §5.15.4 — so
    the local optimum reached is a function of the two documents alone.
    """
    score = w.score(mapping)
    used = {b: a for a, b in mapping.items() if b is not None}
    for _ in range(_MAX_STEPS):
        best_delta = 0
        best_move = None
        for a in sorted(mapping):
            for b in w.candidates.get(a, ()):
                if b == mapping[a]:
                    continue
                if b in used:
                    other = used[b]
                    delta = _swap_delta(w, mapping, a, other)
                    move = ("swap", a, other)
                else:
                    delta = _move_delta(w, mapping, a, b)
                    move = ("move", a, b)
                if delta > best_delta:
                    best_delta, best_move = delta, move
            # Unmapping is a legal move: a variable with no counterpart costs
            # nothing to leave unmapped, and holding a bad target blocks a swap.
            if mapping[a] is not None:
                delta = _move_delta(w, mapping, a, None)
                if delta > best_delta:
                    best_delta, best_move = delta, ("move", a, None)
        if best_move is None:
            break
        if best_move[0] == "move":
            _, a, b = best_move
            old = mapping[a]
            if old is not None:
                del used[old]
            mapping[a] = b
            if b is not None:
                used[b] = a
        else:
            _, a1, a2 = best_move
            b1, b2 = mapping[a1], mapping[a2]
            mapping[a1], mapping[a2] = b2, b1
            for b, a in ((b1, a2), (b2, a1)):
                if b is not None:
                    used[b] = a
        score += best_delta
    return mapping, score


def _color_init(doc_a: Document, doc_b: Document, w: _Weights) -> Dict[int, Optional[int]]:
    """Pair variables by refinement colour: equal rank first, then any candidate.

    Variable ids are assigned in colour order (§5.15.4), so rank *i* on one side
    and rank *i* on the other are the two graphs' variables at the same position
    of the same ordering. For two documents that assert the same graph that is
    the identity alignment, and the climb starts already at the optimum — which
    is what makes `vson diff x x` report 1.0 by construction rather than by luck.
    """
    mapping: Dict[int, Optional[int]] = {a: None for a in range(doc_a.n_vars)}
    used: Set[int] = set()
    for a in range(doc_a.n_vars):
        options = w.candidates.get(a, ())
        pick = a if (a in options and a not in used) else None
        if pick is None:
            for b in options:
                if b not in used:
                    pick = b
                    break
        if pick is not None:
            mapping[a] = pick
            used.add(pick)
    return mapping


def _greedy_init(doc_a: Document, doc_b: Document, w: _Weights) -> Dict[int, Optional[int]]:
    """Classic smatch smart initialization: strongest constant anchor first."""
    mapping: Dict[int, Optional[int]] = {a: None for a in range(doc_a.n_vars)}
    used: Set[int] = set()
    ranked = sorted(w.w1.items(), key=lambda kv: (-kv[1], kv[0]))
    for (a, b), _weight in ranked:
        if mapping[a] is None and b not in used:
            mapping[a] = b
            used.add(b)
    return mapping


def _random_init(
    doc_a: Document, doc_b: Document, w: _Weights, rng: Lcg
) -> Dict[int, Optional[int]]:
    mapping: Dict[int, Optional[int]] = {a: None for a in range(doc_a.n_vars)}
    used: Set[int] = set()
    for a in rng.shuffled(range(doc_a.n_vars)):
        options = [b for b in w.candidates.get(a, ()) if b not in used]
        if options:
            b = options[rng.below(len(options))]
            mapping[a] = b
            used.add(b)
    return mapping


DEFAULT_SEED = 0
DEFAULT_RESTARTS = 5


def best_alignment(
    doc_a: Document, doc_b: Document, seed: int = DEFAULT_SEED, restarts: int = DEFAULT_RESTARTS
) -> Tuple[Dict[int, Optional[int]], int]:
    """The alignment with the most matched triples this search found.

    Not provably the maximum — the problem is NP-hard and this is hill climbing
    — which is why the restart count and seed are reported beside every number.
    """
    w = _Weights(doc_a, doc_b)
    best_map: Dict[int, Optional[int]] = {}
    best_score = -1
    for index in range(max(1, restarts)):
        if index == 0:
            start = _color_init(doc_a, doc_b, w)
        elif index == 1:
            start = _greedy_init(doc_a, doc_b, w)
        else:
            start = _random_init(doc_a, doc_b, w, Lcg(seed + index))
        mapping, score = _hill_climb(w, start)
        if score > best_score:
            best_map, best_score = dict(mapping), score
    return best_map, best_score


# --------------------------------------------------------------------------
# Scoring under an alignment
# --------------------------------------------------------------------------


@dataclass
class LayerScore:
    """One row of the report. `matched_a` and `matched_b` differ only when a
    matched pair falls in different layers on the two sides."""

    layer: str
    matched_a: int
    matched_b: int
    total_a: int
    total_b: int

    @property
    def precision(self) -> Optional[float]:
        return None if self.total_a == 0 else self.matched_a / self.total_a

    @property
    def recall(self) -> Optional[float]:
        return None if self.total_b == 0 else self.matched_b / self.total_b

    @property
    def f1(self) -> Optional[float]:
        p, r = self.precision, self.recall
        if p is None and r is None:
            return None  # nothing on either side: no agreement to report
        if not p or not r:
            return 0.0
        return 2 * p * r / (p + r)

    def as_json(self) -> Dict[str, object]:
        def rounded(value):
            return None if value is None else round(value, 6)

        return {
            "matched_a": self.matched_a,
            "matched_b": self.matched_b,
            "triples_a": self.total_a,
            "triples_b": self.total_b,
            "precision": rounded(self.precision),
            "recall": rounded(self.recall),
            "f1": rounded(self.f1),
        }


@dataclass
class Report:
    """Everything one comparison produced."""

    doc_a: Document
    doc_b: Document
    seed: int
    restarts: int
    overall: LayerScore
    layers: Dict[str, LayerScore]

    @property
    def identical(self) -> bool:
        """True when the two documents assert the same graph up to variable
        renaming — every triple on both sides matched."""
        return (
            self.overall.matched_a == self.overall.total_a
            and self.overall.matched_b == self.overall.total_b
        )

    @property
    def f1(self) -> float:
        value = self.overall.f1
        if value is None:
            # Two documents that assert nothing agree, vacuously and exactly.
            return 1.0
        return value


def _image(triple, mapping):
    """A triple of A rewritten into B's variables, or None if it cannot be."""
    pred, s, o = triple
    out = []
    for slot in (s, o):
        if slot[0] == "c":
            out.append(slot)
            continue
        target = mapping.get(slot[1])
        if target is None:
            return None
        out.append(("v", target))
    return (pred, out[0], out[1])


def _viewer_blind(doc: Document) -> Set[int]:
    """Indices of the layer's triples once `vso:viewer` is dropped."""
    return {
        i
        for i, (pred, _, _) in enumerate(doc.triples)
        if doc.layers[i] == LAYER_SPATIAL and pred != VIEWER
    }


def compare(
    doc_a: Document,
    doc_b: Document,
    seed: int = DEFAULT_SEED,
    restarts: int = DEFAULT_RESTARTS,
) -> Report:
    """Align the two documents and score them, overall and per layer."""
    mapping, _search_score = best_alignment(doc_a, doc_b, seed=seed, restarts=restarts)
    inverse = {b: a for a, b in mapping.items() if b is not None}

    b_index = set(doc_b.triples)
    a_index = set(doc_a.triples)
    matched_a = {
        i for i, t in enumerate(doc_a.triples) if (_image(t, mapping) in b_index)
    }
    matched_b = {
        i for i, t in enumerate(doc_b.triples) if (_image(t, inverse) in a_index)
    }

    def score_for(name: str, keep_a: Set[int], keep_b: Set[int]) -> LayerScore:
        return LayerScore(
            layer=name,
            matched_a=len(matched_a & keep_a),
            matched_b=len(matched_b & keep_b),
            total_a=len(keep_a),
            total_b=len(keep_b),
        )

    layers: Dict[str, LayerScore] = {}
    for layer in LAYERS:
        layers[layer] = score_for(
            layer,
            {i for i, lay in enumerate(doc_a.layers) if lay == layer},
            {i for i, lay in enumerate(doc_b.layers) if lay == layer},
        )
    layers[SPATIAL_VIEWER_BLIND] = score_for(
        SPATIAL_VIEWER_BLIND, _viewer_blind(doc_a), _viewer_blind(doc_b)
    )

    overall = LayerScore(
        layer="overall",
        matched_a=len(matched_a),
        matched_b=len(matched_b),
        total_a=len(doc_a),
        total_b=len(doc_b),
    )
    return Report(
        doc_a=doc_a,
        doc_b=doc_b,
        seed=seed,
        restarts=restarts,
        overall=overall,
        layers=layers,
    )


def compare_paths(
    path_a: str,
    path_b: str,
    seed: int = DEFAULT_SEED,
    restarts: int = DEFAULT_RESTARTS,
) -> Report:
    """Load two documents from disk and compare them. The eval-loop entry point."""
    return compare(
        load_document(path_a), load_document(path_b), seed=seed, restarts=restarts
    )


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

_ROW_ORDER = (
    (LAYER_OBJECTS, "objects"),
    (LAYER_ATTRIBUTES, "attributes"),
    (LAYER_SPATIAL, "spatial"),
    (SPATIAL_VIEWER_BLIND, "  viewer-blind"),
    (LAYER_FRAMES, "frames"),
    (LAYER_EVENTS, "events"),
    (LAYER_OTHER, "other"),
)


def _cell(value: Optional[float]) -> str:
    return "     —" if value is None else "{:.4f}".format(value)


def _matched_cell(score: LayerScore) -> str:
    if score.matched_a == score.matched_b:
        return str(score.matched_a)
    return "{}/{}".format(score.matched_a, score.matched_b)


def render_text(report: Report) -> str:
    """The human-readable report. One row per layer, plus the overall line."""
    lines = [
        "vson diff — Smatch graph agreement (docs/vson.md §5.15)",
        "  a  {}  ({} triples)".format(report.doc_a.path, len(report.doc_a)),
        "  b  {}  ({} triples)".format(report.doc_b.path, len(report.doc_b)),
        "  alignment: seed {}, {} restarts".format(report.seed, report.restarts),
        "",
        "  {:<16}{:>8}{:>7}{:>7}{:>11}{:>9}{:>9}".format(
            "layer", "match", "a", "b", "precision", "recall", "F1"
        ),
    ]
    for key, label in _ROW_ORDER:
        score = report.layers[key]
        lines.append(
            "  {:<16}{:>8}{:>7}{:>7}{:>11}{:>9}{:>9}".format(
                label,
                _matched_cell(score),
                score.total_a,
                score.total_b,
                _cell(score.precision),
                _cell(score.recall),
                _cell(score.f1),
            )
        )
    overall = report.overall
    lines.append(
        "  {:<16}{:>8}{:>7}{:>7}{:>11}{:>9}{:>9}".format(
            "overall",
            _matched_cell(overall),
            overall.total_a,
            overall.total_b,
            _cell(overall.precision),
            _cell(overall.recall),
            _cell(report.f1),
        )
    )
    lines.append("")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    payload = {
        "metric": "vson-smatch",
        "spec": "docs/vson.md §5.15",
        "seed": report.seed,
        "restarts": report.restarts,
        "a": {"path": report.doc_a.path, "triples": len(report.doc_a)},
        "b": {"path": report.doc_b.path, "triples": len(report.doc_b)},
        "identical": report.identical,
        "summary": summary_line(report),
        "overall": report.overall.as_json(),
        "layers": {
            key: report.layers[key].as_json() for key, _label in _ROW_ORDER
        },
    }
    payload["overall"]["f1"] = round(report.f1, 6)
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# The summary line cli/src/commands/diff.rs looks for, to tell "these two
# documents differ" (exit 1) from "this tool never reached a verdict" (exit 2).
TELL = "smatch:"


def summary_line(report: Report) -> str:
    if report.identical:
        return (
            "{} the two documents assert the same graph up to variable renaming "
            "(F1 1.0000). No image was read.".format(TELL)
        )
    return (
        "{} the two documents differ (F1 {:.4f}). Agreement between two "
        "documents, not evidence about the image.".format(TELL, report.f1)
    )


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.metrics.smatch",
        description=(
            "Smatch graph agreement between two VSON documents (docs/vson.md "
            "§5.15). Reads no image."
        ),
    )
    ap.add_argument("a", help="first document (.ttl / .vson / .x.vson)")
    ap.add_argument("b", help="second document (.ttl / .vson / .x.vson)")
    ap.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="report shape (default: text)",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="restart seed (default: {}) — see the seed policy in §5.15.4".format(
            DEFAULT_SEED
        ),
    )
    ap.add_argument(
        "--restarts",
        type=int,
        default=DEFAULT_RESTARTS,
        help="hill-climb restarts (default: {})".format(DEFAULT_RESTARTS),
    )
    ap.add_argument(
        "--label-a",
        help="report the first input under this name (for a caller that copied it)",
    )
    ap.add_argument("--label-b", help="likewise for the second input")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.restarts < 1:
        print("error: --restarts must be at least 1", file=sys.stderr)
        return 2
    try:
        doc_a = load_document(args.a)
        doc_b = load_document(args.b)
    except LoadError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    if args.label_a:
        doc_a.path = args.label_a
    if args.label_b:
        doc_b.path = args.label_b

    report = compare(doc_a, doc_b, seed=args.seed, restarts=args.restarts)
    if args.format == "json":
        # stdout stays parseable: in JSON mode the summary line — which the
        # caller needs to tell "they differ" from "this never ran" — goes to
        # stderr, and the same sentence is in the payload's `summary` key.
        sys.stdout.write(render_json(report))
        print(summary_line(report), file=sys.stderr)
    else:
        sys.stdout.write(render_text(report))
        print(summary_line(report))
    return 0 if report.identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
