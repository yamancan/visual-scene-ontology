"""
VSON FOL (first-order logic) renderer — deterministic graph -> Prolog-style
predicate-logic facts.

VSON's RDF-star core IS first-order logic: every triple `s p o` is a binary
predicate `p(s, o)`. Reified Events / Processes / Statives / SpatialFacts
encode n-ary relations as conjunctions of binary triples that share a
Skolem-like blank node; this renderer collapses those clusters back into
single n-ary facts so the logical content is visible at a glance.

Output groups:

  1. Unary class predicates                     -- e.g. PhysicalObject(p1).
  2. Collapsed n-ary reified facts              -- e.g. strike(agent=bob,
                                                          patient=boar,
                                                          instrument=sword).
  3. Binary predicates over non-reified nodes   -- e.g. depicts(c, p1).

Determinism: every list is sorted by node IRI / predicate IRI; the output
is byte-identical across runs and across rdflib parses.

Acceptance:
- CI determinism test compares output to ground-truth fixtures in
  tests/fixtures/fol/ for the 16-scene gallery.
"""

from __future__ import annotations

from typing import Optional

from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.namespace import Namespace

VSO = Namespace("https://vson.dev/v1/ontology#")

# Reified n-ary classes — each instance bundles 2-N role triples that we
# collapse into one functional-style fact.
_REIFIED_CLASSES: tuple[URIRef, ...] = (
    VSO.Event,
    VSO.Process,
    VSO.Stative,
    VSO.SpatialFact,
)

# Predicate -> argument label, used when collapsing reified clusters.
_ROLE_LABELS: dict[URIRef, str] = {
    VSO.agent: "agent",
    VSO.patient: "patient",
    VSO.theme: "theme",
    VSO.instrument: "instrument",
    VSO.recipient: "recipient",
    VSO.goal: "goal",
    VSO.source: "source",
    VSO.holder: "holder",
    VSO.experiencer: "experiencer",
    VSO.stimulus: "stimulus",
    VSO.figure: "figure",
    VSO.ground: "ground",
    VSO.directional: "dir",
    VSO.proximal: "prox",
    VSO.rcc: "rcc",
    VSO.allen: "allen",
    VSO.viewer: "viewer",
    VSO.manner: "manner",
    VSO.dimension: "dim",
    VSO.value: "value",
}


def render(g: Graph) -> str:
    """Render a VSON RDF graph to deterministic Prolog-style FOL facts.

    Pure function: same graph -> same string byte-for-byte. Output ends
    with a single trailing newline so concatenation is well-defined.
    """
    # Discover reified n-ary nodes once; their binary triples are folded
    # into the collapsed-fact section and skipped in the binary-predicate
    # pass to avoid double-emission.
    reified: dict[URIRef | BNode, URIRef] = {}
    for s, _, t in g.triples((None, RDF.type, None)):
        if t in _REIFIED_CLASSES and s not in reified:
            reified[s] = t

    sections: list[str] = []

    unary = _unary_section(g, reified)
    if unary:
        sections.append(unary)

    nary = _nary_section(g, reified)
    if nary:
        sections.append(nary)

    binary = _binary_section(g, reified)
    if binary:
        sections.append(binary)

    return "\n\n".join(sections) + "\n" if sections else ""


# ---------------------------------------------------------------------------
# Section 1 — unary class predicates
# ---------------------------------------------------------------------------


def _unary_section(g: Graph, reified: dict) -> str:
    rows: list[tuple[str, str]] = []
    for s, _, t in g.triples((None, RDF.type, None)):
        # Collapsed reified nodes are emitted as n-ary facts in section 2;
        # don't also list them as unary class facts.
        if s in reified and t in _REIFIED_CLASSES:
            continue
        if not isinstance(t, URIRef):
            continue
        rows.append((_term(t), _term(s)))
    if not rows:
        return ""
    rows.sort()
    body = "\n".join(f"{cls}({arg})." for cls, arg in rows)
    return f"% unary class predicates\n{body}"


# ---------------------------------------------------------------------------
# Section 2 — collapsed n-ary reified facts
# ---------------------------------------------------------------------------


def _nary_section(g: Graph, reified: dict) -> str:
    if not reified:
        return ""
    entries: list[tuple[str, str, str]] = []
    for node, kind in reified.items():
        head, args, comment = _collapse(g, node, kind)
        if not head:
            continue
        body = ", ".join(f"{k}={v}" for k, v in args) if args else ""
        entries.append((_term(node), f"{head}({body}).", f"  % {comment} {_term(node)}"))
    if not entries:
        return ""
    entries.sort(key=lambda e: e[0])
    body = "\n".join(fact + tail for _, fact, tail in entries)
    return f"% n-ary reified facts (collapsed from binary triples)\n{body}"


def _collapse(g: Graph, node, kind: URIRef) -> tuple[str, list[tuple[str, str]], str]:
    """Collapse a reified n-ary node into (head, args, type-comment).

    For Event/Process/Stative the head is the lemma when present; for
    SpatialFact the head is `spatialfact` (the relation kind shows up as
    the `dir` / `prox` / `rcc` argument so the output is uniform).
    """
    type_label = _term(kind)
    lemma: Optional[str] = None
    args: list[tuple[str, str]] = []
    for p, o in g.predicate_objects(node):
        if p == RDF.type:
            continue
        if p == VSO.lemma and isinstance(o, Literal):
            lemma = str(o)
            continue
        label = _ROLE_LABELS.get(p)
        if label is None:
            # Unknown reified property — fall through to binary section
            # rather than swallowing it silently.
            continue
        args.append((label, _term(o)))
    args.sort()
    head = lemma if lemma else type_label.lower()
    return head, args, type_label


# ---------------------------------------------------------------------------
# Section 3 — binary predicates over non-reified subjects
# ---------------------------------------------------------------------------


def _binary_section(g: Graph, reified: dict) -> str:
    rows: list[tuple[str, str, str]] = []
    for s, p, o in g:
        if p == RDF.type:
            continue
        if s in reified and p in _ROLE_LABELS:
            # Already emitted as a positional argument of a collapsed fact.
            continue
        if s in reified and p == VSO.lemma:
            continue
        rows.append((_term(p), _term(s), _term(o)))
    if not rows:
        return ""
    rows.sort()
    body = "\n".join(f"{pred}({subj}, {obj})." for pred, subj, obj in rows)
    return f"% binary predicates\n{body}"


# ---------------------------------------------------------------------------
# Term serialization
# ---------------------------------------------------------------------------


def _term(node) -> str:
    if isinstance(node, Literal):
        s = str(node)
        if '"' in s or "\\" in s:
            s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'
    if isinstance(node, BNode):
        return f"_:{node}"
    if isinstance(node, URIRef):
        s = str(node)
        local = s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        return local if local else s
    return str(node)


# ---------------------------------------------------------------------------
# CLI shim (for `python -m tools.render.fol <file>`)
# ---------------------------------------------------------------------------


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m tools.render.fol <file.vson|file.ttl>", flush=True)
        return 2
    path = argv[1]
    g = Graph()

    if path.endswith(".vson"):
        # Lazy import: Turtle input does not need the Penman transpiler.
        from tools.penman import vson_penman as vp

        with open(path, encoding="utf-8") as f:
            penman_src = f.read()
        turtle_src = vp.to_turtle(penman_src)
        g.parse(data=turtle_src, format="turtle")
    else:
        g.parse(path, format="turtle")

    print(render(g), end="")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
