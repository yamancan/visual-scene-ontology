"""
VSON caption renderer — deterministic graph -> natural-language text.

Phase A of the v1.1 plan. Pure function: same graph -> same caption byte-for-byte.
Consumes RDF graph (post Penman/X transpilation) so the renderer is syntax-
independent.

Acceptance:
- CI determinism test compares output to ground-truth fixtures in
  tests/fixtures/captions/{01..11}.txt for the 11 gallery scenes.
- Generation faithfulness is evaluated separately (Phase A 30-image gate).
"""

from __future__ import annotations

import json
import os
from typing import Optional

import rdflib
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.namespace import Namespace

VSO = Namespace("https://vson.dev/v1/ontology#")

_HERE = os.path.dirname(__file__)
with open(os.path.join(_HERE, "verbs.json"), encoding="utf-8") as _vf:
    VERBS = json.load(_vf)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render(g: Graph) -> str:
    """Render a VSON RDF graph to a deterministic English caption.

    The caption is a 1-6 sentence summary suitable for downstream image-gen
    models. Output is stable: the same graph always produces the same string.
    """
    composition = _find_composition(g)
    if composition is None:
        return ""

    disc = _disambiguators(g, composition)

    sentences: list[str] = []

    frame = _frame_sentence(g, composition)
    if frame:
        sentences.append(frame)

    subjects = _subjects_sentence(g, composition, disc)
    if subjects:
        sentences.append(subjects)

    actions = _actions_sentences(g, composition, disc)
    sentences.extend(actions)

    spatial = _spatial_sentences(g, composition, disc)
    sentences.extend(spatial)

    return " ".join(sentences).strip()


# ---------------------------------------------------------------------------
# Composition discovery
# ---------------------------------------------------------------------------


def _find_composition(g: Graph) -> Optional[URIRef]:
    nodes = sorted(
        (s for s in g.subjects(RDF.type, VSO.Composition) if isinstance(s, URIRef)),
        key=str,
    )
    return nodes[0] if nodes else None


# ---------------------------------------------------------------------------
# Frame sentence (style + camera + scene context)
# ---------------------------------------------------------------------------


def _frame_sentence(g: Graph, scene: URIRef) -> str:
    style = _first_framedby(g, scene, VSO.VisualStyle)
    cam = _first_framedby(g, scene, VSO.CameraView)
    ctx = _first_framedby(g, scene, VSO.SceneContext)

    bits: list[str] = []

    if style is not None:
        aesthetic = _humanize(_str_prop(g, style, VSO.aesthetic))
        medium = _humanize(_str_prop(g, style, VSO.medium))
        palette = _humanize(_str_prop(g, style, VSO.palette))
        if aesthetic and medium:
            bits.append(f"{aesthetic} on {medium}")
        elif aesthetic:
            bits.append(aesthetic)
        if palette:
            bits.append(f"{palette} palette")

    if cam is not None:
        cam_bits: list[str] = []
        angle = _humanize(_str_prop(g, cam, VSO.angle))
        framing = _humanize(_str_prop(g, cam, VSO.framing))
        focal = _str_prop(g, cam, VSO.focalLength)
        if angle and framing:
            cam_bits.append(f"{angle} {framing}")
        elif framing:
            cam_bits.append(framing)
        elif angle:
            cam_bits.append(f"{angle} shot")
        if focal:
            cam_bits.append(f"{focal} lens")
        if cam_bits:
            bits.append(", ".join(cam_bits))

    if ctx is not None:
        ctx_bits: list[str] = []
        venue = _humanize(_str_prop(g, ctx, VSO.venue))
        atmosphere = _humanize(_str_prop(g, ctx, VSO.atmosphere))
        time_of_day = _humanize(_str_prop(g, ctx, VSO.timeOfDay))
        weather = _humanize(_str_prop(g, ctx, VSO.weather))
        if venue:
            ctx_bits.append(f"in a {venue}")
        if atmosphere:
            ctx_bits.append(f"{atmosphere} atmosphere")
        if time_of_day:
            ctx_bits.append(f"at {time_of_day}")
        if weather and weather != "indoor":
            ctx_bits.append(f"{weather} weather")
        if ctx_bits:
            bits.append(", ".join(ctx_bits))

    if not bits:
        return ""
    return _capitalize(", ".join(bits)) + "."


# ---------------------------------------------------------------------------
# Same-class disambiguation
# ---------------------------------------------------------------------------


_LAYOUT_RANK = {
    "left": 0,
    "center_left": 1,
    "center": 2,
    "center_right": 3,
    "right": 4,
}


Disc = tuple[str, str]  # (pre-head adjective, post-head phrase)


def _disambiguators(g: Graph, scene: URIRef) -> dict[URIRef, Disc]:
    """Return positional discriminators for Generic same-class entities.

    When a scene depicts multiple entities sharing both `vso:class` and
    `Role`, none Named, the renderer would otherwise produce 'the person is
    left of the person' four times. We inspect the group, order it by
    Layout dimension (left/center_left/center/center_right/right), then by
    bbox2d x-coordinate, then by IRI; we emit a (pre, post) tuple per
    entity such that the noun phrase becomes 'the {pre} {head} {post}',
    e.g. 'the leftmost person' or 'the second person from the left'.
    Entities with unique noun phrases get no entry.
    """
    entities = _depicted_entities(g, scene)
    if len(entities) <= 1:
        return {}

    groups: dict[tuple, list[URIRef]] = {}
    for e in entities:
        ind = _str_prop(g, e, VSO.individuation) or ""
        if ind.endswith("Named"):
            continue
        cls = _class_label(g, e)
        if not cls:
            continue
        quals = _qualities_by_dimension(g, e)
        role = (quals.get("Role") or [""])[0]
        groups.setdefault((cls, role), []).append(e)

    out: dict[URIRef, Disc] = {}
    for group in groups.values():
        if len(group) <= 1:
            continue

        def sort_key(e: URIRef):
            quals = _qualities_by_dimension(g, e)
            layout = (quals.get("Layout") or [""])[0]
            if layout in _LAYOUT_RANK:
                return (0, _LAYOUT_RANK[layout], str(e))
            bbox = _str_prop(g, e, VSO.bbox2d)
            if bbox:
                try:
                    return (1, float(bbox.split(",")[0]), str(e))
                except (ValueError, IndexError):
                    pass
            return (2, 0, str(e))

        ordered = sorted(group, key=sort_key)
        n = len(ordered)
        # Pre-head adjective ("leftmost") plus optional post-head phrase
        # ("from the left") so word order stays English-natural.
        if n == 2:
            labels: list[Disc] = [("leftmost", ""), ("rightmost", "")]
        elif n == 3:
            labels = [("leftmost", ""), ("middle", ""), ("rightmost", "")]
        elif n == 4:
            labels = [
                ("leftmost", ""),
                ("second", "from the left"),
                ("third", "from the left"),
                ("rightmost", ""),
            ]
        elif n == 5:
            labels = [
                ("leftmost", ""),
                ("second", "from the left"),
                ("middle", ""),
                ("fourth", "from the left"),
                ("rightmost", ""),
            ]
        else:
            labels = [("leftmost", "")]
            labels.extend((_ordinal(i + 1), "from the left") for i in range(1, n - 1))
            labels.append(("rightmost", ""))
        for e, label in zip(ordered, labels):
            out[e] = label
    return out


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ---------------------------------------------------------------------------
# Subject inventory
# ---------------------------------------------------------------------------


def _subjects_sentence(g: Graph, scene: URIRef, disc: dict[URIRef, str]) -> str:
    entities = _depicted_entities(g, scene)
    if not entities:
        return ""
    phrases = [_entity_noun_phrase(g, e, disc.get(e)) for e in entities]
    phrases = [p for p in phrases if p]
    if not phrases:
        return ""
    if len(phrases) == 1:
        return _capitalize(phrases[0]) + "."
    return _capitalize(", ".join(phrases[:-1]) + ", and " + phrases[-1]) + "."


def _depicted_entities(g: Graph, scene: URIRef) -> list[URIRef]:
    """Return depicts-targets that are ENTITIES (not perdurants/spatialfacts).

    Sorted by IRI string for determinism.
    """
    targets = list(g.objects(scene, VSO.depicts))
    out: list[URIRef] = []
    for t in targets:
        if not isinstance(t, URIRef):
            continue
        types = set(g.objects(t, RDF.type))
        # Skip reified perdurants and spatial facts; keep PhysicalObject /
        # Aggregate / Substance and any subclass of vso:Entity not already
        # classified as a perdurant or SpatialFact.
        if VSO.Event in types or VSO.Process in types or VSO.Stative in types:
            continue
        if VSO.SpatialFact in types:
            continue
        if VSO.Quality in types:
            continue
        out.append(t)
    return sorted(out, key=str)


def _all_perdurant_targets(g: Graph, scene: URIRef) -> list[URIRef]:
    """Walk depicts + occurs to collect Event / Process / Stative targets."""
    seen: set[URIRef] = set()
    out: list[URIRef] = []
    for pred in (VSO.depicts, VSO.occurs):
        for t in g.objects(scene, pred):
            if not isinstance(t, URIRef) or t in seen:
                continue
            types = set(g.objects(t, RDF.type))
            if (VSO.Event in types) or (VSO.Process in types) or (VSO.Stative in types):
                seen.add(t)
                out.append(t)
    return sorted(out, key=str)


def _all_spatial_targets(g: Graph, scene: URIRef) -> list[URIRef]:
    """Walk depicts + hasFact to collect SpatialFact targets."""
    seen: set[URIRef] = set()
    out: list[URIRef] = []
    for pred in (VSO.depicts, VSO.hasFact):
        for t in g.objects(scene, pred):
            if not isinstance(t, URIRef) or t in seen:
                continue
            types = set(g.objects(t, RDF.type))
            if VSO.SpatialFact in types:
                seen.add(t)
                out.append(t)
    return sorted(out, key=str)


def _entity_noun_phrase(g: Graph, entity: URIRef, discriminator: Optional[str] = None) -> str:
    """Build 'a red apple' / 'Alice, a joyful queen' / 'a heavy gold crown with lightning enchantment'.

    `discriminator`, when supplied, prepends a positional adjective ('leftmost',
    'second from left', ...) so that multiple Generic same-class entities in
    the same scene get distinguishable noun phrases.
    """
    individuation = _str_prop(g, entity, VSO.individuation)
    cls_label = _class_label(g, entity)
    qualities = _qualities_by_dimension(g, entity)

    # Adjectives from selected dimensions, in fixed order. Skip Age (numeric;
    # would render as "30 joyful queen" — awkward). Render Age separately if
    # present.
    adj_dimensions = [
        "Affect",
        "Color",
        "Material",
        "Size",
        "Weight",
        "Fit",
        "Hair",
        "Skin",
        "ActionState",
    ]
    adjectives: list[str] = []
    for dim in adj_dimensions:
        vals = qualities.get(dim) or []
        if not vals:
            continue
        # Color and Material may legitimately stack (multi-color outfit, mixed
        # textile). Slash-join so image-gen models read them as alternates
        # instead of a flat first-write-wins; other dimensions stay scalar.
        if dim in ("Color", "Material") and len(vals) > 1:
            adjectives.append("/".join(_humanize(v).lower() for v in vals))
        else:
            adjectives.append(_humanize(vals[0]).lower())

    role = (qualities.get("Role") or [None])[0]
    age = (qualities.get("Age") or [None])[0]
    enchantment = (qualities.get("Enchantment") or [None])[0]

    head_noun = _humanize(cls_label).lower() if cls_label else "thing"

    is_named = individuation and individuation.endswith("Named")
    proper_name = _proper_name(entity) if is_named else None

    # If the proper name local-name equals the role (e.g. variable "queen"
    # with role=queen), drop the redundant proper name — it was just a
    # Penman var, not a real character name.
    if proper_name and role and proper_name.lower() == _humanize(role).lower():
        proper_name = None
        is_named = False

    head = head_noun
    if role:
        head = f"{_humanize(role).lower()} {head_noun}"

    adj_str = " ".join(adjectives)
    article = _indefinite_article((adj_str + " " + head).strip())

    if is_named and proper_name:
        if adj_str:
            base = f"{proper_name}, {article} {adj_str} {head}"
        else:
            base = f"{proper_name}, {article} {head}"
    else:
        if adj_str:
            base = f"{article} {adj_str} {head}"
        else:
            base = f"{article} {head}"
    base = " ".join(base.split())  # collapse whitespace

    extras: list[str] = []
    if enchantment:
        extras.append(f"with {_humanize(enchantment).lower()} enchantment")
    if age:
        extras.append(f"age {_humanize(age)}")

    if discriminator:
        # Splice before extras so 'from the left' attaches to the head noun
        # rather than to a trailing 'age adult' / 'with glowing enchantment'.
        base = _splice_discriminator(base, discriminator)
    if extras:
        # When a post-head discriminator is present, the head noun has already
        # consumed a trailing phrase; separate the extras with a comma to
        # avoid 'person from the left age adult' running together.
        sep = ", " if discriminator and discriminator[1] else " "
        base = base + sep + " ".join(extras)
    return base


def _splice_discriminator(noun_phrase: str, disc: Disc) -> str:
    """Insert (pre, post) discriminator into a noun phrase and definite-ize."""
    pre, post = disc
    parts = noun_phrase.split(" ", 1)
    if not parts:
        return noun_phrase
    head, *rest = parts
    body = rest[0] if rest else ""
    if head.lower() in ("a", "an", "the"):
        prefix = f"the {pre} {body}".strip() if pre else f"the {body}".strip()
        return f"{prefix} {post}".strip() if post else prefix
    # Proper-name path — name already disambiguates.
    return noun_phrase


def _proper_name(entity: URIRef) -> str:
    # Default-namespace IRI: '...#alice' -> 'Alice'
    iri = str(entity)
    local = iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return local.capitalize() if local else local


# ---------------------------------------------------------------------------
# Actions (Event / Process / Stative)
# ---------------------------------------------------------------------------


def _actions_sentences(g: Graph, scene: URIRef, disc: dict[URIRef, str]) -> list[str]:
    out: list[str] = []
    for t in _all_perdurant_targets(g, scene):
        types = set(g.objects(t, RDF.type))
        if VSO.Event in types:
            s = _event_sentence(g, t, disc)
        elif VSO.Process in types:
            s = _process_sentence(g, t, disc)
        elif VSO.Stative in types:
            s = _stative_sentence(g, t, disc)
        else:
            continue
        if s:
            out.append(s)
    return out


def _event_sentence(g: Graph, ev: URIRef, disc: dict[URIRef, str]) -> str:
    lemma = _str_prop(g, ev, VSO.lemma) or ""
    agent = _ref_phrase(g, ev, VSO.agent, disc)
    patient = _ref_phrase(g, ev, VSO.patient, disc)
    instrument = _ref_phrase(g, ev, VSO.instrument, disc)
    theme = _ref_phrase(g, ev, VSO.theme, disc)
    recipient = _ref_phrase(g, ev, VSO.recipient, disc)
    goal = _ref_phrase(g, ev, VSO.goal, disc)
    manner = _str_prop(g, ev, VSO.manner)

    verb_forms = VERBS["event"].get(lemma, {})
    verb = verb_forms.get("present") or lemma

    subject = agent or theme or "Something"
    bits: list[str] = [_capitalize(subject), verb]
    if patient:
        bits.append(patient)
    elif theme and recipient:
        bits.extend([theme, "to", recipient])
    elif theme:
        bits.append(theme)
    if instrument:
        bits.extend(["with", instrument])
    if recipient and "to" not in bits:
        bits.extend(["to", recipient])
    if goal and not patient:
        bits.extend(["at", goal])
    if manner:
        bits.append(_humanize(manner) + "ly" if not _humanize(manner).endswith("ly") else _humanize(manner))

    return " ".join(bits) + "."


def _process_sentence(g: Graph, proc: URIRef, disc: dict[URIRef, str]) -> str:
    lemma = _str_prop(g, proc, VSO.lemma) or ""
    agent = _ref_phrase(g, proc, VSO.agent, disc)
    patient = _ref_phrase(g, proc, VSO.patient, disc)
    theme = _ref_phrase(g, proc, VSO.theme, disc)
    goal = _ref_phrase(g, proc, VSO.goal, disc)
    manner = _str_prop(g, proc, VSO.manner)

    forms = VERBS["process"].get(lemma, {})
    participle = forms.get("participle") or (lemma + "ing")

    subject = agent or theme or patient or "Something"
    bits: list[str] = [_capitalize(subject), "is", participle]
    if patient and not agent:
        # already used as subject
        pass
    elif patient:
        bits.append(patient)
    elif theme and not agent:
        pass
    if goal:
        bits.extend(["toward", goal])
    if manner:
        bits.append(_humanize(manner))
    return " ".join(bits) + "."


def _stative_sentence(g: Graph, st: URIRef, disc: dict[URIRef, str]) -> str:
    lemma = _str_prop(g, st, VSO.lemma) or ""
    holder = _ref_phrase(g, st, VSO.holder, disc)
    theme = _ref_phrase(g, st, VSO.theme, disc)
    experiencer = _ref_phrase(g, st, VSO.experiencer, disc)
    stimulus = _ref_phrase(g, st, VSO.stimulus, disc)
    manner = _str_prop(g, st, VSO.manner)

    forms = VERBS["stative"].get(lemma, {})
    verb = forms.get("present") or lemma

    subject = holder or experiencer or theme or "Something"
    obj = theme or stimulus

    bits: list[str] = [_capitalize(subject), verb]
    if obj and obj != subject:
        bits.append(obj)
    if manner:
        bits.append(_humanize(manner))
    # For intransitive postures (stand/sit/lie/lean), no object
    return " ".join(bits) + "."


# ---------------------------------------------------------------------------
# Spatial facts
# ---------------------------------------------------------------------------


# RCC-8 verbs ship in third-person-singular; we need plural forms for the
# collapsed-figure case. Maps singular -> plural verb-phrase verbatim.
_RCC_PLURAL = {
    "is disconnected from": "are disconnected from",
    "touches": "touch",
    "partially overlaps": "partially overlap",
    "equals": "equal",
    "is a tangential part of": "are tangential parts of",
    "is contained inside": "are contained inside",
    "tangentially contains": "tangentially contain",
    "fully contains": "fully contain",
}


def _spatial_sentences(g: Graph, scene: URIRef, disc: dict[URIRef, "Disc"]) -> list[str]:
    """Collapse runs of (predicate, ground)-equivalent facts into one sentence.

    A scene may legitimately assert the same spatial relation between many
    figures and one ground (five people all 'in front of' a wall). Rather
    than emit five identical-shape sentences, group them by their predicate
    signature and ground IRI, then English-list the figures with a plural
    verb form. Single-fact groups stay singular.
    """
    rows: list[tuple[str, str, URIRef, URIRef, URIRef]] = []
    seen_pairs: set[tuple[str, str, str]] = set()

    for fact in _all_spatial_targets(g, scene):
        figure_iri = next(iter(g.objects(fact, VSO.figure)), None)
        ground_iri = next(iter(g.objects(fact, VSO.ground)), None)
        if figure_iri is None or ground_iri is None:
            continue
        directional = _local_name(next(iter(g.objects(fact, VSO.directional)), None))
        proximal = _local_name(next(iter(g.objects(fact, VSO.proximal)), None))
        rcc = _local_name(next(iter(g.objects(fact, VSO.rcc)), None))

        if proximal in {"near", "far", "adjacent"}:
            a, b = sorted([str(figure_iri), str(ground_iri)])
            key = (a, b, proximal)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            if str(figure_iri) != a:
                figure_iri, ground_iri = ground_iri, figure_iri
            phrase = VERBS["proximal_phrase"].get(proximal, proximal)
            rows.append(("proximal", phrase, ground_iri, figure_iri, fact))
        elif directional:
            phrase = VERBS["directional_phrase"].get(directional, _humanize(directional))
            rows.append(("dir", phrase, ground_iri, figure_iri, fact))
        elif rcc:
            phrase = VERBS["rcc_phrase"].get(rcc, rcc)
            rows.append(("rcc", phrase, ground_iri, figure_iri, fact))

    out: list[str] = []
    i = 0
    while i < len(rows):
        kind, verb, gnd, fig, _ = rows[i]
        j = i + 1
        figures: list[URIRef] = [fig]
        while j < len(rows) and rows[j][0] == kind and rows[j][1] == verb and rows[j][2] == gnd:
            figures.append(rows[j][3])
            j += 1
        ground_phrase = _entity_short_phrase(g, gnd, disc)
        figure_phrases = [_entity_short_phrase(g, f, disc) for f in figures]
        joined = _english_join(figure_phrases)
        if len(figures) == 1:
            if kind == "rcc":
                out.append(f"{_capitalize(joined)} {verb} {ground_phrase}.")
            else:
                out.append(f"{_capitalize(joined)} is {verb} {ground_phrase}.")
        else:
            if kind == "rcc":
                plural = _RCC_PLURAL.get(verb, verb)
                out.append(f"{_capitalize(joined)} {plural} {ground_phrase}.")
            else:
                out.append(f"{_capitalize(joined)} are {verb} {ground_phrase}.")
        i = j
    return out


def _english_join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_framedby(g: Graph, scene: URIRef, kind: URIRef) -> Optional[URIRef]:
    candidates = sorted(
        (
            f
            for f in g.objects(scene, VSO.framedBy)
            if isinstance(f, URIRef) and (f, RDF.type, kind) in g
        ),
        key=str,
    )
    return candidates[0] if candidates else None


def _str_prop(g: Graph, subj: URIRef, pred: URIRef) -> str:
    for o in g.objects(subj, pred):
        if isinstance(o, Literal):
            return str(o)
        if isinstance(o, URIRef):
            return _local_name(o)
    return ""


def _class_label(g: Graph, entity: URIRef) -> str:
    """Return the open class string (e.g., 'Knight', 'Crown', 'Apple')."""
    for o in g.objects(entity, VSO["class"]):
        if isinstance(o, Literal):
            return str(o)
        if isinstance(o, URIRef):
            return _local_name(o)
    # Fallback: derive from rdf:type if no class property
    types = sorted(
        (
            t
            for t in g.objects(entity, RDF.type)
            if isinstance(t, URIRef)
            and t not in {VSO.PhysicalObject, VSO.Aggregate, VSO.Substance, VSO.Entity, VSO.Endurant}
        ),
        key=str,
    )
    if types:
        return _local_name(types[0])
    return ""


def _qualities_by_dimension(g: Graph, entity: URIRef) -> dict[str, list[str]]:
    """Map dimension local-name -> ordered list of value local-names.

    Multiple Quality nodes can share a dimension (e.g., a striped outfit with
    Color=blue + Color=white). Order is the IRI sort of the Quality nodes,
    which is stable across re-parses. Empty list never appears in the dict.
    """
    out: dict[str, list[str]] = {}
    quality_nodes = sorted(
        (q for q in g.objects(entity, VSO.hasQuality)),
        key=str,
    )
    for q in quality_nodes:
        dim = _local_name(next(iter(g.objects(q, VSO.dimension)), None))
        val = _local_name(next(iter(g.objects(q, VSO.value)), None))
        if dim and val:
            out.setdefault(dim, []).append(val)
    return out


def _ref_phrase(g: Graph, subj: URIRef, pred: URIRef, disc: Optional[dict[URIRef, str]] = None) -> str:
    """For thematic role refs: produce 'Alice' / 'the apple' / 'a sword'."""
    for o in g.objects(subj, pred):
        if isinstance(o, URIRef):
            return _entity_short_phrase(g, o, disc)
        if isinstance(o, Literal):
            return str(o)
    return ""


def _entity_short_phrase(
    g: Graph, entity: URIRef, disc: Optional[dict[URIRef, "Disc"]] = None
) -> str:
    """Short reference: proper name if Named, else 'the <discriminator?> <class>'."""
    individuation = _str_prop(g, entity, VSO.individuation)
    cls_label = _class_label(g, entity)
    if individuation and individuation.endswith("Named"):
        return _proper_name(entity)
    if cls_label:
        head = _humanize(cls_label).lower()
        if disc and entity in disc:
            pre, post = disc[entity]
            prefix = f"the {pre} {head}".strip() if pre else f"the {head}"
            return f"{prefix} {post}".strip() if post else prefix
        return f"the {head}"
    return "the entity"


def _humanize(snake_or_camel: str) -> str:
    if not snake_or_camel:
        return ""
    s = snake_or_camel.replace("_", " ")
    # Don't lowercase if it's a proper name token; we expect inputs to be
    # snake_case or camelCase enum values (lowercase by convention).
    return s


def _capitalize(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


def _indefinite_article(noun_phrase: str) -> str:
    if not noun_phrase:
        return "a"
    first_word = noun_phrase.strip().split()[0]
    return "an" if first_word and first_word[0].lower() in "aeiou" else "a"


def _local_name(value) -> str:
    if value is None:
        return ""
    if isinstance(value, URIRef):
        s = str(value)
        return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    if isinstance(value, Literal):
        return str(value)
    return ""


# ---------------------------------------------------------------------------
# CLI shim (for `python -m tools.render.caption <file.ttl>`)
# ---------------------------------------------------------------------------


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m tools.render.caption <file.vson|file.ttl>", flush=True)
        return 2
    path = argv[1]
    g = Graph()

    # Auto-detect by extension; for .vson, use the Penman transpiler.
    if path.endswith(".vson"):
        # Lazy import to avoid pulling penman tools into tests that only
        # exercise the renderer with pre-parsed graphs.
        import sys as _sys

        _here = os.path.dirname(os.path.dirname(_HERE))
        if _here not in _sys.path:
            _sys.path.insert(0, _here)
        from tools.penman import vson_penman as vp  # type: ignore

        with open(path, encoding="utf-8") as f:
            penman_src = f.read()
        turtle_src = vp.to_turtle(penman_src)
        g.parse(data=turtle_src, format="turtle")
    else:
        g.parse(path, format="turtle")

    print(render(g))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
