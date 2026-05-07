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

    sentences: list[str] = []

    frame = _frame_sentence(g, composition)
    if frame:
        sentences.append(frame)

    subjects = _subjects_sentence(g, composition)
    if subjects:
        sentences.append(subjects)

    actions = _actions_sentences(g, composition)
    sentences.extend(actions)

    spatial = _spatial_sentences(g, composition)
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
# Subject inventory
# ---------------------------------------------------------------------------


def _subjects_sentence(g: Graph, scene: URIRef) -> str:
    entities = _depicted_entities(g, scene)
    if not entities:
        return ""
    phrases = [_entity_noun_phrase(g, e) for e in entities]
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


def _entity_noun_phrase(g: Graph, entity: URIRef) -> str:
    """Build 'a red apple' / 'Alice, a joyful queen' / 'a heavy gold crown with lightning enchantment'."""
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
        val = qualities.get(dim)
        if val:
            adjectives.append(_humanize(val).lower())

    role = qualities.get("Role")
    age = qualities.get("Age")
    enchantment = qualities.get("Enchantment")

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

    if extras:
        return base + " " + " ".join(extras)
    return base


def _proper_name(entity: URIRef) -> str:
    # Default-namespace IRI: '...#alice' -> 'Alice'
    iri = str(entity)
    local = iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return local.capitalize() if local else local


# ---------------------------------------------------------------------------
# Actions (Event / Process / Stative)
# ---------------------------------------------------------------------------


def _actions_sentences(g: Graph, scene: URIRef) -> list[str]:
    out: list[str] = []
    for t in _all_perdurant_targets(g, scene):
        types = set(g.objects(t, RDF.type))
        if VSO.Event in types:
            s = _event_sentence(g, t)
        elif VSO.Process in types:
            s = _process_sentence(g, t)
        elif VSO.Stative in types:
            s = _stative_sentence(g, t)
        else:
            continue
        if s:
            out.append(s)
    return out


def _event_sentence(g: Graph, ev: URIRef) -> str:
    lemma = _str_prop(g, ev, VSO.lemma) or ""
    agent = _ref_phrase(g, ev, VSO.agent)
    patient = _ref_phrase(g, ev, VSO.patient)
    instrument = _ref_phrase(g, ev, VSO.instrument)
    theme = _ref_phrase(g, ev, VSO.theme)
    recipient = _ref_phrase(g, ev, VSO.recipient)
    goal = _ref_phrase(g, ev, VSO.goal)
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


def _process_sentence(g: Graph, proc: URIRef) -> str:
    lemma = _str_prop(g, proc, VSO.lemma) or ""
    agent = _ref_phrase(g, proc, VSO.agent)
    patient = _ref_phrase(g, proc, VSO.patient)
    theme = _ref_phrase(g, proc, VSO.theme)
    goal = _ref_phrase(g, proc, VSO.goal)
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


def _stative_sentence(g: Graph, st: URIRef) -> str:
    lemma = _str_prop(g, st, VSO.lemma) or ""
    holder = _ref_phrase(g, st, VSO.holder)
    theme = _ref_phrase(g, st, VSO.theme)
    experiencer = _ref_phrase(g, st, VSO.experiencer)
    stimulus = _ref_phrase(g, st, VSO.stimulus)
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


def _spatial_sentences(g: Graph, scene: URIRef) -> list[str]:
    out: list[str] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for t in _all_spatial_targets(g, scene):
        s = _spatial_sentence(g, t, seen_pairs)
        if s:
            out.append(s)
    return out


def _spatial_sentence(g: Graph, fact: URIRef, seen_pairs: set) -> str:
    figure_iri = next(iter(g.objects(fact, VSO.figure)), None)
    ground_iri = next(iter(g.objects(fact, VSO.ground)), None)
    if figure_iri is None or ground_iri is None:
        return ""

    figure = _entity_short_phrase(g, figure_iri)
    ground = _entity_short_phrase(g, ground_iri)

    directional = _local_name(next(iter(g.objects(fact, VSO.directional)), None))
    proximal = _local_name(next(iter(g.objects(fact, VSO.proximal)), None))
    rcc = _local_name(next(iter(g.objects(fact, VSO.rcc)), None))

    # For symmetric facts (proximal in {near, far, adjacent}), de-duplicate
    # the reverse pair: collapse (a,b,proximal) and (b,a,proximal) into one
    # sentence about the alphabetically-first ordered pair.
    if proximal in {"near", "far", "adjacent"}:
        a, b = sorted([str(figure_iri), str(ground_iri)])
        key = (a, b, proximal)
        if key in seen_pairs:
            return ""
        seen_pairs.add(key)
        # Re-pick figure/ground in the canonical order so output is stable
        if str(figure_iri) != a:
            figure, ground = ground, figure
        phrase = VERBS["proximal_phrase"].get(proximal, proximal)
        return f"{_capitalize(figure)} is {phrase} {ground}."

    if directional:
        phrase = VERBS["directional_phrase"].get(directional, _humanize(directional))
        return f"{_capitalize(figure)} is {phrase} {ground}."

    if rcc:
        phrase = VERBS["rcc_phrase"].get(rcc, rcc)
        return f"{_capitalize(figure)} {phrase} {ground}."

    return ""


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


def _qualities_by_dimension(g: Graph, entity: URIRef) -> dict[str, str]:
    """Map dimension local-name -> value local-name. Deterministic by sort."""
    out: dict[str, str] = {}
    quality_nodes = sorted(
        (q for q in g.objects(entity, VSO.hasQuality)),
        key=str,
    )
    for q in quality_nodes:
        dim = _local_name(next(iter(g.objects(q, VSO.dimension)), None))
        val = _local_name(next(iter(g.objects(q, VSO.value)), None))
        if dim and val and dim not in out:
            out[dim] = val
    return out


def _ref_phrase(g: Graph, subj: URIRef, pred: URIRef) -> str:
    """For thematic role refs: produce 'Alice' / 'the apple' / 'a sword'."""
    for o in g.objects(subj, pred):
        if isinstance(o, URIRef):
            return _entity_short_phrase(g, o)
        if isinstance(o, Literal):
            return str(o)
    return ""


def _entity_short_phrase(g: Graph, entity: URIRef) -> str:
    """Short reference: proper name if Named, else 'the <class>'."""
    individuation = _str_prop(g, entity, VSO.individuation)
    cls_label = _class_label(g, entity)
    if individuation and individuation.endswith("Named"):
        return _proper_name(entity)
    if cls_label:
        return f"the {_humanize(cls_label).lower()}"
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
