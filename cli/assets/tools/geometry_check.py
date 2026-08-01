#!/usr/bin/env python3
"""Geometry consistency gate — what two rectangles decide about an asserted relation.

docs/vson.md §5.13. When a `vso:SpatialFact`'s figure and ground both carry a
`vso:bbox2d`, the document has stated two things that can disagree with each
other: the relation, and the rectangles. This gate reports the disagreements.

**It reads no pixels.** Nothing here opens an image, and a clean run establishes
nothing about the picture (§2.1). It compares one set of the document's claims
against another set of the document's claims — geometry-vs-assertion coherence,
never claim-vs-image. A document whose boxes and relations agree can still
describe a photograph that contains neither object.

**It refutes; it does not confirm.** `vso:bbox2d` is a *bounding* box: the
tightest axis-aligned rectangle containing the entity's projection, so the
rectangle contains the region and is not the region. Two facts follow, and they
are the whole engine (§5.13):

    X ⊆ bbox(X)                        (extensive)
    X ⊆ Y  ⟹  bbox(X) ⊆ bbox(Y)        (monotone)

A relation asserted between two *regions* therefore entails something about
their rectangles, and when the rectangles falsify that entailment the assertion
is refuted. The converse never holds: a cat sitting on a mat is `rcc:EC` while
its rectangle overlaps the mat's, so "the rectangles stand in PO" is not
evidence for `rcc:PO`. Measured on the 21 baked studio envelopes: of the 13
`vso:rcc` facts they state over two rectangles, a gate that computed the
rectangles' own relation and demanded a match would reject 11. This one rejects
4, and each of the 4 is refuted by an entailment (§5.13.3).

**Never guess.** Every relation is either decided or reported undecidable with a
reason: `no-geometry`, `malformed-geometry`, `ambiguous-geometry`,
`ambiguous-endpoints`, `degenerate-geometry`, `viewer-not-image-frame`,
`relation-out-of-scope`, `unrecognized-value`. `vso:proximal`, `in_front_of` /
`behind` and `vso:visibleFraction` are out of scope for rectangles and say so on
every run; they are not silently skipped.

**Not a conformance clause.** C1–C9 (§2) are unchanged: a geometry-inconsistent
document is still a conformant VSON document, and §8.2 forbids making it
otherwise inside v1.x. This is a fourth construct beside the three in §2.1's
table, in the same position as the OWL 2 RL gate — worth running, required by
nothing. That is why `vson validate` does not run it and `vson verify
--geometry` does.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.geometry_check [--verbose] [files...]
With no files, checks examples/throne_room.ttl + every examples/gallery/*.vson.

Exit 0 — no asserted relation is contradicted by the asserted geometry.
Exit 1 — at least one is.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Dict, List, Optional, Tuple

import rdflib
from rdflib import RDF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VSO = rdflib.Namespace("https://w3id.org/vson/v1/ontology#")
RCC = rdflib.Namespace("https://w3id.org/vson/v1/rcc8#")

# The §5.4 value space, one component at a time. The language is the one
# vss:GeometryShape's sh:pattern accepts; tests/test_geometry_check.py pins the
# two against each other rather than duplicating the string, so a document this
# gate calls malformed is exactly a document SHACL rejects.
_COMPONENT = r"(?:0|0\.\d+|1|1\.0+)"
BBOX2D_RE = re.compile(r"^{c},{c},{c},{c}$".format(c=_COMPONENT))

# The three verdicts (§5.13). `inconsistent` is the only one that fails the gate.
CONSISTENT = "consistent"
INCONSISTENT = "inconsistent"
UNDECIDABLE = "undecidable"

# The undecidable taxonomy (§5.13). Reported, never guessed at.
NO_GEOMETRY = "no-geometry"
MALFORMED = "malformed-geometry"
AMBIGUOUS = "ambiguous-geometry"
AMBIGUOUS_ENDPOINTS = "ambiguous-endpoints"
DEGENERATE = "degenerate-geometry"
NO_IMAGE_FRAME = "viewer-not-image-frame"
OUT_OF_SCOPE = "relation-out-of-scope"
UNRECOGNIZED = "unrecognized-value"

RCC8 = ("DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPi", "NTPPi")


# --------------------------------------------------------------------------
# Rectangles
# --------------------------------------------------------------------------


def _exact_sum(a: Decimal, b: Decimal) -> Decimal:
    """`a + b`, never rounded.

    `Decimal` addition rounds to the active context's 28 significant digits, and
    §5.4 bounds a `vso:bbox2d` component's *value* to `[0,1]` but says nothing
    about its *length*. The context is widened here to the exact result's own
    size — every digit from the larger operand's leading one down to the smaller
    operand's last — so the sum this gate compares is the sum the document
    states, at any length.
    """
    with localcontext() as ctx:
        ctx.prec = (
            max(a.adjusted(), b.adjusted())
            - min(a.as_tuple().exponent, b.as_tuple().exponent)
            + 3
        )
        return a + b


def _exact_half(value: Decimal) -> Decimal:
    """`value / 2`, never rounded — halving a decimal costs one digit."""
    with localcontext() as ctx:
        ctx.prec = len(value.as_tuple().digits) + 2
        return value / 2


@dataclass(frozen=True)
class Rect:
    """A closed axis-aligned rectangle in normalized image coordinates.

    Image coordinates are the viewer's: origin at the top-left of the frame, x
    increasing to the right, y increasing *downward* (§5.13). That is the
    convention the layout consumers §5.4 names use and the one the shipped
    corpus was written in — `examples/gallery/10_geometry_bbox.vson` puts the
    apple at y=0.55 and the table it rests on at y=0.60.

    Components are `Decimal`, so every comparison below is exact. Boundary
    relations (EC, EQ, the TPP/NTPP cut) turn on equality of coordinates, and
    binary floats would decide them by rounding error.
    """

    x1: Decimal
    y1: Decimal
    x2: Decimal
    y2: Decimal

    @classmethod
    def from_xywh(cls, x: Decimal, y: Decimal, w: Decimal, h: Decimal) -> "Rect":
        return cls(x, y, _exact_sum(x, w), _exact_sum(y, h))

    @property
    def degenerate(self) -> bool:
        """No interior — a zero-width or zero-height box. RCC-8 is defined over
        regions with non-empty interior, so these are not decided, only reported.
        The directional rule is unaffected: a centroid needs no interior."""
        return self.x1 == self.x2 or self.y1 == self.y2

    # The doubled centroid. Every ordering comparison uses these rather than the
    # centroid, because x̄(a) < x̄(b) ⟺ 2x̄(a) < 2x̄(b) and the doubled form needs
    # no division: `left_of` is decided by the document's own numbers, never by
    # a rounding step between them.
    @property
    def cx2(self) -> Decimal:
        return _exact_sum(self.x1, self.x2)

    @property
    def cy2(self) -> Decimal:
        return _exact_sum(self.y1, self.y2)

    # The centroid itself, for reports only — never for a decision.
    @property
    def cx(self) -> Decimal:
        return _exact_half(self.cx2)

    @property
    def cy(self) -> Decimal:
        return _exact_half(self.cy2)

    def meets(self, other: "Rect") -> bool:
        """The closed rectangles share at least a point."""
        return (
            self.x1 <= other.x2
            and other.x1 <= self.x2
            and self.y1 <= other.y2
            and other.y1 <= self.y2
        )

    def interiors_meet(self, other: "Rect") -> bool:
        """The open rectangles share a point — overlap with positive area."""
        return (
            self.x1 < other.x2
            and other.x1 < self.x2
            and self.y1 < other.y2
            and other.y1 < self.y2
        )

    def contains(self, other: "Rect") -> bool:
        """`other` ⊆ `self`, boundaries allowed to touch."""
        return (
            self.x1 <= other.x1
            and other.x2 <= self.x2
            and self.y1 <= other.y1
            and other.y2 <= self.y2
        )

    def strictly_contains(self, other: "Rect") -> bool:
        """`other` ⊆ interior(`self`) — strict on all four sides."""
        return (
            self.x1 < other.x1
            and other.x2 < self.x2
            and self.y1 < other.y1
            and other.y2 < self.y2
        )


def parse_bbox2d(text: str) -> Optional[Rect]:
    """A `vso:bbox2d` literal as a rectangle, or None if it is not one.

    None means "outside the §5.4 value space", which is a SHACL violation
    (`vss:GeometryShape`) and this gate's `malformed-geometry` — the shape is
    the right reporter, so nothing here is decided from it.
    """
    if not BBOX2D_RE.match(text):
        return None
    try:
        x, y, w, h = (Decimal(part) for part in text.split(","))
    except InvalidOperation:  # pragma: no cover — the regex already excludes it
        return None
    return Rect.from_xywh(x, y, w, h)


def rect_rcc8(a: Rect, b: Rect) -> str:
    """The RCC-8 relation between the two *rectangles*, as rectangles.

    Exact and jointly-exhaustive on non-degenerate axis-aligned rectangles.
    Diagnostic only: it is what the boxes say about the boxes, never a verdict
    about the entities they bound (see the module docstring).
    """
    if not a.meets(b):
        return "DC"
    if not a.interiors_meet(b):
        return "EC"
    if a == b:
        return "EQ"
    if b.contains(a):
        return "NTPP" if b.strictly_contains(a) else "TPP"
    if a.contains(b):
        return "NTPPi" if a.strictly_contains(b) else "TPPi"
    return "PO"


def _escapes(inner: Rect, outer: Rect, strict: bool) -> str:
    """Which sides `inner` crosses on its way out of `outer`, as prose."""
    ok = (lambda a, b: a < b) if strict else (lambda a, b: a <= b)
    sides = []
    if not ok(outer.x1, inner.x1):
        sides.append("left ({} vs {})".format(inner.x1, outer.x1))
    if not ok(inner.x2, outer.x2):
        sides.append("right ({} vs {})".format(inner.x2, outer.x2))
    if not ok(outer.y1, inner.y1):
        sides.append("top ({} vs {})".format(inner.y1, outer.y1))
    if not ok(inner.y2, outer.y2):
        sides.append("bottom ({} vs {})".format(inner.y2, outer.y2))
    return ", ".join(sides)


# --------------------------------------------------------------------------
# The RCC-8 refutation table (§5.13)
# --------------------------------------------------------------------------


def rcc_refutation(name: str, fig: Rect, gnd: Rect) -> str:
    """Why the rectangles refute `rcc:name` between figure and ground, or "".

    One line per relation, each of them an entailment of monotonicity:

        DC    — never refutable. Disjoint regions may have any boxes at all
                (two interleaved combs share a bounding box).
        EC/PO — both entail the regions meet, so both entail the boxes meet.
        EQ    — entails equal regions, hence equal boxes.
        TPP   — entails figure ⊆ ground, hence bbox(figure) ⊆ bbox(ground).
        NTPP  — entails figure ⊆ interior(ground); a compact region inside an
                open set attains its extremes strictly inside it, so the
                containment of boxes is strict on all four sides.
        TPPi / NTPPi — the same two, with the roles swapped.
    """
    if name == "DC":
        return ""
    if name in ("EC", "PO"):
        if not fig.meets(gnd):
            return (
                "{} entails the two regions share a point, so their rectangles "
                "must meet; these are disjoint.".format(name)
            )
        return ""
    if name == "EQ":
        if fig != gnd:
            return (
                "EQ entails one region, so the two rectangles must be identical; "
                "they differ."
            )
        return ""
    if name == "TPP":
        if not gnd.contains(fig):
            return (
                "TPP entails figure ⊆ ground, so the figure's rectangle must lie "
                "inside the ground's; it escapes on the {}.".format(
                    _escapes(fig, gnd, strict=False)
                )
            )
        return ""
    if name == "NTPP":
        if not gnd.strictly_contains(fig):
            return (
                "NTPP entails figure ⊆ interior(ground), so the figure's rectangle "
                "must lie strictly inside the ground's; it reaches the boundary or "
                "beyond on the {}.".format(_escapes(fig, gnd, strict=True))
            )
        return ""
    if name == "TPPi":
        if not fig.contains(gnd):
            return (
                "TPPi entails ground ⊆ figure, so the ground's rectangle must lie "
                "inside the figure's; it escapes on the {}.".format(
                    _escapes(gnd, fig, strict=False)
                )
            )
        return ""
    if name == "NTPPi":
        if not fig.strictly_contains(gnd):
            return (
                "NTPPi entails ground ⊆ interior(figure), so the ground's rectangle "
                "must lie strictly inside the figure's; it reaches the boundary or "
                "beyond on the {}.".format(_escapes(gnd, fig, strict=True))
            )
        return ""
    return ""  # pragma: no cover — callers filter to the eight names above


# --------------------------------------------------------------------------
# The directional decision rule (§5.13)
# --------------------------------------------------------------------------

# Unlike the RCC-8 table above, this is a *stipulation*, not an entailment:
# nothing about two regions forces an ordering of their bounding-box centres.
# §5.13 fixes it as the reading of the four viewer-relative values, because a
# rule the gate can state is worth more than a relation nobody can check.
# in_front_of / behind are absent: depth is not a function of the image plane.
DIRECTIONAL_RULE = {
    "above": ("cy", "<", "sits higher in the frame (smaller y)"),
    "below": ("cy", ">", "sits lower in the frame (larger y)"),
    "left_of": ("cx", "<", "sits further left (smaller x)"),
    "right_of": ("cx", ">", "sits further right (larger x)"),
}


def directional_refutation(name: str, fig: Rect, gnd: Rect) -> str:
    """Why the centroids refute `vso:name`, or "" if they do not."""
    axis, op, prose = DIRECTIONAL_RULE[name]
    doubled = axis + "2"
    f = getattr(fig, doubled)
    g = getattr(gnd, doubled)
    holds = f < g if op == "<" else f > g
    if holds:
        return ""
    return (
        "{} holds exactly when the figure's centroid {} than the ground's; here "
        "the figure's is {} and the ground's is {}.".format(
            name, prose, getattr(fig, axis), getattr(gnd, axis)
        )
    )


# --------------------------------------------------------------------------
# Reading a document
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Geometry:
    """One entity's `vso:bbox2d`, or the reason there is nothing usable."""

    rect: Optional[Rect]
    text: str
    problem: str


def geometry_index(g: rdflib.Graph) -> Dict[rdflib.term.Node, Geometry]:
    """Every node carrying `vso:bbox2d`, mapped to its rectangle or its problem."""
    raw: Dict[rdflib.term.Node, List[str]] = {}
    for s, _, o in g.triples((None, VSO.bbox2d, None)):
        raw.setdefault(s, []).append(str(o))
    index = {}
    for node, values in raw.items():
        if len(values) > 1:
            index[node] = Geometry(None, ", ".join(sorted(values)), AMBIGUOUS)
            continue
        text = values[0]
        rect = parse_bbox2d(text)
        index[node] = Geometry(rect, text, "" if rect else MALFORMED)
    return index


NOTHING = Geometry(None, "", NO_GEOMETRY)


def image_frame_camera(g: rdflib.Graph) -> Tuple[Optional[rdflib.term.Node], str]:
    """The CameraView whose image the rectangles are normalized against.

    `vso:bbox2d` is a fraction of *the* image (§5.4), and the image is the one
    the composition is viewed through (§5.2, `vso:viewedBy`, at most one). A
    directional value is anchored to its own `vso:viewer` (C5), so the gate can
    read the rectangles as that viewer's left and right only when the two
    cameras are the same one. This is what the mandatory viewer buys: without
    C5 there would be no anchor to compare against.

    Falls back to the sole `vso:CameraView` in a document that declares no
    `vso:viewedBy`; returns (None, why) when the frame is ambiguous.
    """
    viewed = set(g.objects(None, VSO.viewedBy))
    if len(viewed) == 1:
        return next(iter(viewed)), ""
    if len(viewed) > 1:
        return None, "the document declares {} vso:viewedBy cameras".format(len(viewed))
    cameras = set(g.subjects(RDF.type, VSO.CameraView))
    if len(cameras) == 1:
        return next(iter(cameras)), ""
    return None, "the document declares no vso:viewedBy camera"


def short(term: rdflib.term.Node) -> str:
    """A readable name: the fragment, or the last path segment."""
    text = str(term)
    for sep in ("#", "/"):
        if sep in text:
            text = text.rsplit(sep, 1)[1] or text
    return text


@dataclass(frozen=True)
class Finding:
    """One asserted relation, and what the rectangles had to say about it."""

    subject: str
    slot: str
    value: str
    figure: str
    ground: str
    fig_box: str
    gnd_box: str
    verdict: str
    tag: str
    detail: str

    def headline(self) -> str:
        where = "{} {} {}".format(self.subject, self.slot, self.value)
        if self.figure:
            where += "  figure {}{}  ground {}{}".format(
                self.figure,
                ' "{}"'.format(self.fig_box) if self.fig_box else "",
                self.ground,
                ' "{}"'.format(self.gnd_box) if self.gnd_box else "",
            )
        return where


def _pair(
    index: Dict[rdflib.term.Node, Geometry],
    figure: rdflib.term.Node,
    ground: rdflib.term.Node,
) -> Tuple[Geometry, Geometry, str, str]:
    """Both endpoints' geometry, plus the first problem that blocks a decision."""
    fig = index.get(figure, NOTHING)
    gnd = index.get(ground, NOTHING)
    if fig.problem == NO_GEOMETRY and gnd.problem == NO_GEOMETRY:
        return fig, gnd, NO_GEOMETRY, "neither endpoint carries a vso:bbox2d."
    for role, geom in (("figure", fig), ("ground", gnd)):
        if geom.problem == NO_GEOMETRY:
            return fig, gnd, NO_GEOMETRY, "the {} carries no vso:bbox2d.".format(role)
        if geom.problem == MALFORMED:
            return (
                fig,
                gnd,
                MALFORMED,
                'the {}\'s vso:bbox2d "{}" is outside the §5.4 value space; SHACL '
                "reports that, this gate decides nothing from it.".format(
                    role, geom.text
                ),
            )
        if geom.problem == AMBIGUOUS:
            return (
                fig,
                gnd,
                AMBIGUOUS,
                "the {} carries more than one vso:bbox2d.".format(role),
            )
    return fig, gnd, "", ""


def _relation_endpoints(
    g: rdflib.Graph, fact: rdflib.term.Node
) -> Tuple[Optional[rdflib.term.Node], Optional[rdflib.term.Node], str]:
    """The fact's figure and ground, or the reason it has no single pair."""
    figures = list(g.objects(fact, VSO.figure))
    grounds = list(g.objects(fact, VSO.ground))
    if len(figures) != 1 or len(grounds) != 1:
        return (
            None,
            None,
            "the fact carries {} figure(s) and {} ground(s)".format(
                len(figures), len(grounds)
            ),
        )
    return figures[0], grounds[0], ""


def findings_for(g: rdflib.Graph) -> List[Finding]:
    """Every geometry-checkable claim in the graph, with its verdict."""
    index = geometry_index(g)
    camera, camera_problem = image_frame_camera(g)
    out: List[Finding] = []

    facts = set(g.subjects(RDF.type, VSO.SpatialFact)) | set(g.subjects(VSO.figure, None))
    for fact in sorted(facts, key=str):
        figure, ground, endpoint_problem = _relation_endpoints(g, fact)
        slots = (
            [("vso:rcc", v) for v in g.objects(fact, VSO.rcc)]
            + [("vso:directional", v) for v in g.objects(fact, VSO.directional)]
            + [("vso:proximal", v) for v in g.objects(fact, VSO.proximal)]
        )
        for slot, value in sorted(slots, key=lambda sv: (sv[0], str(sv[1]))):
            out.append(
                _spatial_finding(
                    g,
                    index,
                    camera,
                    camera_problem,
                    fact,
                    figure,
                    ground,
                    endpoint_problem,
                    slot,
                    value,
                )
            )

    for subject, _, target in sorted(g.triples((None, VSO.occludes, None)), key=str):
        out.append(_occlusion_finding(index, subject, target))

    for subject, _, value in sorted(g.triples((None, VSO.visibleFraction, None)), key=str):
        out.append(
            Finding(
                subject=short(subject),
                slot="vso:visibleFraction",
                value=str(value),
                figure="",
                ground="",
                fig_box="",
                gnd_box="",
                verdict=UNDECIDABLE,
                tag=OUT_OF_SCOPE,
                detail=(
                    "a rectangle over-approximates a region's area, so the visible "
                    "fraction of an entity is not a function of its box; and VSON "
                    "makes no closed-world commitment about vso:occludes, so a value "
                    "below 1 is always explicable by an occluder the document does "
                    "not declare, or by the frame edge (§5.13)."
                ),
            )
        )
    return out


def _spatial_finding(
    g: rdflib.Graph,
    index: Dict[rdflib.term.Node, Geometry],
    camera: Optional[rdflib.term.Node],
    camera_problem: str,
    fact: rdflib.term.Node,
    figure: Optional[rdflib.term.Node],
    ground: Optional[rdflib.term.Node],
    endpoint_problem: str,
    slot: str,
    value: rdflib.term.Node,
) -> Finding:
    name = short(value)
    label = "{}:{}".format("rcc" if slot == "vso:rcc" else "vso", name)

    def finding(verdict, tag, detail, fig_box="", gnd_box=""):
        return Finding(
            subject=short(fact),
            slot=slot,
            value=label,
            figure=short(figure) if figure is not None else "",
            ground=short(ground) if ground is not None else "",
            fig_box=fig_box,
            gnd_box=gnd_box,
            verdict=verdict,
            tag=tag,
            detail=detail,
        )

    if slot == "vso:proximal":
        return finding(
            UNDECIDABLE,
            OUT_OF_SCOPE,
            "VSON fixes no distance threshold for near / far / adjacent / next_to "
            "and no orientation for facing, so no rectangle pair decides them (§5.13).",
        )
    if slot == "vso:directional" and name in ("in_front_of", "behind"):
        return finding(
            UNDECIDABLE,
            OUT_OF_SCOPE,
            "depth is not a function of the image plane; two rectangles decide no "
            "front/behind ordering (§5.13).",
        )
    if slot == "vso:rcc" and name not in RCC8:
        return finding(
            UNDECIDABLE,
            UNRECOGNIZED,
            "not one of the eight RCC-8 values C8 closes; SHACL reports that, this "
            "gate decides nothing from it.",
        )
    if slot == "vso:directional" and name not in DIRECTIONAL_RULE:
        return finding(
            UNDECIDABLE,
            UNRECOGNIZED,
            "not one of the six vso:directional values §5.12 closes; SHACL reports "
            "that, this gate decides nothing from it.",
        )
    if endpoint_problem:
        return finding(UNDECIDABLE, AMBIGUOUS_ENDPOINTS, endpoint_problem)

    fig, gnd, tag, detail = _pair(index, figure, ground)
    if tag:
        return finding(UNDECIDABLE, tag, detail, fig.text, gnd.text)

    if slot == "vso:directional":
        viewers = list(g.objects(fact, VSO.viewer))
        if len(viewers) != 1:
            return finding(
                UNDECIDABLE,
                NO_IMAGE_FRAME,
                "a directional fact carries exactly one vso:viewer (C5); this one "
                "carries {}, so there is no frame to read the rectangles in.".format(
                    len(viewers)
                ),
                fig.text,
                gnd.text,
            )
        if camera is None:
            return finding(
                UNDECIDABLE,
                NO_IMAGE_FRAME,
                "the rectangles are fractions of one image and {}, so which "
                "camera's left is meant is undetermined.".format(camera_problem),
                fig.text,
                gnd.text,
            )
        if viewers[0] != camera:
            return finding(
                UNDECIDABLE,
                NO_IMAGE_FRAME,
                "the fact is anchored to {} while the rectangles are normalized "
                "against the image of {}.".format(short(viewers[0]), short(camera)),
                fig.text,
                gnd.text,
            )
        why = directional_refutation(name, fig.rect, gnd.rect)
        return finding(
            INCONSISTENT if why else CONSISTENT,
            "",
            why or "the centroid ordering agrees with the asserted direction.",
            fig.text,
            gnd.text,
        )

    # vso:rcc, both boxes in hand.
    if fig.rect.degenerate or gnd.rect.degenerate:
        return finding(
            UNDECIDABLE,
            DEGENERATE,
            "a zero-area rectangle bounds a region with no interior, and RCC-8 is "
            "defined over regions that have one.",
            fig.text,
            gnd.text,
        )
    why = rcc_refutation(name, fig.rect, gnd.rect)
    if why:
        why += " The two rectangles stand in {}.".format(rect_rcc8(fig.rect, gnd.rect))
    return finding(
        INCONSISTENT if why else CONSISTENT,
        "",
        why or "the rectangles are compatible with the asserted relation.",
        fig.text,
        gnd.text,
    )


def _occlusion_finding(
    index: Dict[rdflib.term.Node, Geometry],
    subject: rdflib.term.Node,
    target: rdflib.term.Node,
) -> Finding:
    """`X vso:occludes Y` — the one non-SpatialFact claim rectangles can refute.

    An occluder hides part of what it occludes, so the two projections share
    image points and the two rectangles meet. Only the *closed* test is used:
    "hides part of" is not defined in §5.10 as hiding positive area, and
    demanding overlapping interiors would refute a document the specification
    permits.
    """
    fig, gnd, tag, detail = _pair(index, subject, target)
    if tag:
        verdict = UNDECIDABLE
    elif not fig.rect.meets(gnd.rect):
        verdict, tag = INCONSISTENT, ""
        detail = (
            "an occluder hides part of what it occludes, so the two regions overlap "
            "in the image and their rectangles must meet; these are disjoint."
        )
    else:
        verdict, tag = CONSISTENT, ""
        detail = "the rectangles meet, which is all occlusion requires of them."
    return Finding(
        subject=short(subject),
        slot="vso:occludes",
        value=short(target),
        figure=short(subject),
        ground=short(target),
        fig_box=fig.text,
        gnd_box=gnd.text,
        verdict=verdict,
        tag=tag,
        detail=detail,
    )


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def _tally(findings: List[Finding]) -> str:
    if not findings:
        return "no relation to decide"
    parts = []
    for verdict in (CONSISTENT, INCONSISTENT):
        n = sum(1 for f in findings if f.verdict == verdict)
        if n:
            parts.append("{} {}".format(n, verdict))
    tags: Dict[str, int] = {}
    for f in findings:
        if f.verdict == UNDECIDABLE:
            tags[f.tag] = tags.get(f.tag, 0) + 1
    if tags:
        parts.append(
            "{} undecidable ({})".format(
                sum(tags.values()),
                ", ".join("{} {}".format(v, k) for k, v in sorted(tags.items())),
            )
        )
    return "{} relation(s): {}".format(len(findings), "; ".join(parts))


def _load(path: str) -> rdflib.Graph:
    g = rdflib.Graph()
    if path.endswith(".vson"):
        # Imported lazily: Turtle-only runs should not pay for the transpiler.
        from tools.penman import vson_penman as vp

        with open(path, encoding="utf-8") as fh:
            g.parse(data=vp.to_turtle(fh.read()), format="turtle")
    else:
        g.parse(path, format="turtle")
    return g


def _report(display: str, findings: List[Finding], verbose: bool) -> None:
    bad = [f for f in findings if f.verdict == INCONSISTENT]
    print(
        "  {} {}  [{}]".format("INCONSISTENT" if bad else "OK", display, _tally(findings))
    )
    for f in findings:
        if not verbose and f.verdict != INCONSISTENT:
            continue
        marker = (
            f.verdict
            if f.verdict != UNDECIDABLE
            else "{}: {}".format(UNDECIDABLE, f.tag)
        )
        print("      {}  {}".format(marker, f.headline()))
        print("          {}".format(f.detail))


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.geometry_check",
        description=(
            "Check asserted spatial relations against asserted vso:bbox2d "
            "rectangles (docs/vson.md §5.13). Reads no image."
        ),
    )
    ap.add_argument("files", nargs="*", help=".ttl or .vson documents")
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="print every relation's verdict, not only the inconsistent ones",
    )
    ap.add_argument(
        "--label",
        help=(
            "report the input under this name instead of its own path. For a "
            "caller that transpiled a .vson to a temp .ttl and wants the report "
            "to name the source the user typed — which is what `vson verify "
            "--geometry` does. One input only."
        ),
    )
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point. `argv` is the argument list without the program name — this
    gate takes a flag, unlike its two siblings, so it parses rather than slicing.
    """
    parser = _parser()
    args = parser.parse_args(argv)
    files = args.files or (
        [os.path.join(ROOT, "examples/throne_room.ttl")]
        + sorted(glob.glob(os.path.join(ROOT, "examples/gallery/*.vson")))
    )
    if args.label and len(files) != 1:
        parser.error("--label renames one input; {} were given".format(len(files)))
    bad = 0
    for path in files:
        findings = findings_for(_load(path))
        bad += sum(1 for f in findings if f.verdict == INCONSISTENT)
        _report(args.label or os.path.relpath(path, ROOT), findings, args.verbose)
    # The summary line is the tell cli/src/commands/verify.rs looks for to tell
    # "this document contradicts itself" from "this checker never ran". Both
    # spellings name the construct — geometry against assertion, never against
    # the image (§2.1).
    if bad:
        print(
            "geometry-consistency: {} asserted relation(s) contradicted by the "
            "document's own geometry. No image was read.".format(bad)
        )
        return 1
    print(
        "geometry-consistency: no asserted relation is contradicted by the "
        "document's own geometry. No image was read."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
