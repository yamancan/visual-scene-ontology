"""The scene the importers build, and the VSON-P text they write from it.

One intermediate representation for three datasets. A reader's whole job is to
turn its own file format into :class:`Scene`; everything from there — variable
naming, VSON-P layout, bounding-box normalization — happens once, here, so the
three importers cannot drift in how they spell the same construct.

Geometry. ``vso:bbox2d`` is ``"x,y,w,h"`` as fractions of the image with the
origin at the top-left (docs/vson.md §5.4, §5.13.1); every dataset here stores
pixels. :func:`normalize_bbox` converts, clamps into the unit square, and
formats to a string the ``vss:GeometryShape`` pattern accepts. The arithmetic
is :class:`decimal.Decimal`, not float, for the reason §5.13.3 gives: the
boundary cases of the geometry check turn on equality of coordinates, and a
float would decide those by rounding error.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

#: Four decimal places on a normalized coordinate is ~1/10000 of the frame —
#: finer than any annotation here is accurate to, and short enough that a
#: golden file stays readable.
_QUANTUM = Decimal("0.0001")


def _fmt_component(value):
    """Format one clamped Decimal as the §5.4 value grammar spells it."""
    q = value.quantize(_QUANTUM, rounding=ROUND_HALF_UP)
    if q <= 0:
        return "0"
    if q >= 1:
        return "1"
    text = format(q, "f").rstrip("0")
    return text if not text.endswith(".") else text[:-1]


def normalize_bbox(x, y, w, h, width, height):
    """Pixel box + image size -> a ``vso:bbox2d`` string, or ``None``.

    Returns ``(text, clamped)``: ``clamped`` is true when the source box left
    the image, which several of these datasets' boxes do. A box is clipped to
    the frame rather than dropped, because the entity is still there; the flag
    is what the lossiness report counts.

    ``None`` when the image size is unknown or non-positive — the conversion
    §5.4 requires cannot be done, and inventing a denominator would be
    inventing geometry.
    """
    if not width or not height or width <= 0 or height <= 0:
        return None, False
    px, py = Decimal(str(x)), Decimal(str(y))
    pw, ph = Decimal(str(w)), Decimal(str(h))
    iw, ih = Decimal(str(width)), Decimal(str(height))

    x1, y1 = px / iw, py / ih
    x2, y2 = (px + pw) / iw, (py + ph) / ih
    clamped = x1 < 0 or y1 < 0 or x2 > 1 or y2 > 1
    x1 = min(max(x1, Decimal(0)), Decimal(1))
    y1 = min(max(y1, Decimal(0)), Decimal(1))
    x2 = min(max(x2, Decimal(0)), Decimal(1))
    y2 = min(max(y2, Decimal(0)), Decimal(1))
    parts = [
        _fmt_component(x1),
        _fmt_component(y1),
        _fmt_component(x2 - x1),
        _fmt_component(y2 - y1),
    ]
    return ",".join(parts), clamped


def escape(text):
    """Encode a dataset string as a VSON-P double-quoted literal body."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


class Quality(object):
    """One reified ``vso:Quality`` — a registry dimension and a value."""

    def __init__(self, var, dimension, value):
        self.var = var
        self.dimension = dimension
        self.value = value


class Entity(object):
    """One depicted ``vso:PhysicalObject`` and its traits."""

    def __init__(self, var, cls):
        self.var = var
        self.cls = cls
        self.individuation = None
        self.animacy = None
        self.countability = None
        self.affordances = []
        self.bbox2d = None
        self.edges = []          # [(mereology predicate, entity var)]
        self.qualities = []


class SpatialFact(object):
    """One reified ``vso:SpatialFact``. ``viewer`` is required with a
    ``directional`` value (C5) and permitted without one."""

    def __init__(self, var, figure, ground):
        self.var = var
        self.figure = figure
        self.ground = ground
        self.rcc = None
        self.directional = None
        self.proximal = None
        self.viewer = None


class Perdurant(object):
    """One reified ``vso:Event`` / ``vso:Process`` / ``vso:Stative``."""

    def __init__(self, var, cls, lemma):
        self.var = var
        self.cls = cls
        self.lemma = lemma
        self.roles = []          # [(role, entity_var)], emission order

    def add(self, role, target):
        self.roles.append((role, target))


class Scene(object):
    """A single image's worth of VSON, in emission order."""

    def __init__(self, doc_id, camera_var="cam"):
        self.doc_id = doc_id
        self.camera_var = camera_var
        self.comments = []
        self.context = {}        # vso:SceneContext role -> string value
        self.entities = []
        self.facts = []
        self.perdurants = []

    # -- emission ---------------------------------------------------------

    def to_vson_p(self):
        """Render VSON-P (docs/vson.md Appendix B)."""
        out = []
        for line in self.comments:
            out.append("# " + line if line else "#")
        out.append("(scene / Composition")
        if self.context:
            fields = " ".join(
                ':%s "%s"' % (role, escape(value))
                for role, value in sorted(self.context.items())
            )
            out.append("   :framedBy (ctx / SceneContext %s)" % fields)
        out.append("   :framedBy (%s / CameraView)" % self.camera_var)
        out.append("   :viewedBy %s" % self.camera_var)
        for entity in self.entities:
            out.extend(self._entity_lines(entity))
        for fact in self.facts:
            out.extend(self._fact_lines(fact))
        for perdurant in self.perdurants:
            out.extend(self._perdurant_lines(perdurant))
        out[-1] = out[-1] + ")"
        return "\n".join(out) + "\n"

    def _entity_lines(self, entity):
        lines = ["   :depicts (%s / PhysicalObject" % entity.var]
        traits = []
        if entity.individuation:
            traits.append(":individuation %s" % entity.individuation)
        if entity.animacy:
            traits.append(":animacy %s" % entity.animacy)
        if entity.countability:
            traits.append(":countability %s" % entity.countability)
        if traits:
            lines.append("               " + " ".join(traits))
        for affordance in entity.affordances:
            lines.append("               :affordance %s" % affordance)
        lines.append('               :class "%s"' % escape(entity.cls))
        if entity.bbox2d:
            lines.append('               :bbox2d "%s"' % entity.bbox2d)
        for predicate, target in entity.edges:
            lines.append("               :%s %s" % (predicate, target))
        for quality in entity.qualities:
            lines.append(
                '               :hasQuality (%s / Quality :dimension %s :value "%s")'
                % (quality.var, quality.dimension, escape(quality.value))
            )
        lines[-1] = lines[-1] + ")"
        return lines

    def _fact_lines(self, fact):
        lines = [
            "   :depicts (%s / SpatialFact" % fact.var,
            "               :figure %s :ground %s" % (fact.figure, fact.ground),
        ]
        values = []
        if fact.rcc:
            values.append(":rcc %s" % fact.rcc)
        if fact.directional:
            values.append(":directional %s" % fact.directional)
        if fact.proximal:
            values.append(":proximal %s" % fact.proximal)
        if fact.viewer:
            values.append(":viewer %s" % fact.viewer)
        lines.append("               " + " ".join(values))
        lines[-1] = lines[-1] + ")"
        return lines

    def _perdurant_lines(self, perdurant):
        roles = " ".join(":%s %s" % pair for pair in perdurant.roles)
        line = "   :depicts (%s / %s :lemma %s" % (
            perdurant.var, perdurant.cls, perdurant.lemma,
        )
        if roles:
            return [line, "               " + roles + ")"]
        return [line + ")"]
