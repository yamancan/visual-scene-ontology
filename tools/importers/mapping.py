"""Loading and checking the per-dataset mapping tables.

The tables under ``mappings/`` are **data**: one JSON file per dataset, one
entry per source predicate and per source attribute value, each saying which
VSON construct it becomes and how faithfully. Nothing here decides a mapping;
this module only reads the file and refuses one that is malformed, so a bad
table fails at load rather than half-way through a corpus.

File shape
----------

    {
      "dataset": "gqa",
      "_provenance": { ... where the vocabulary came from ... },
      "policy":    { "individuation": "Skolem", ... },
      "object_classes": { "man": {"animacy": "Agentive"}, ... },
      "predicates": { "<source predicate>": <entry>, ... },
      "attributes": { "<source attribute>": <entry>, ... }
    }

Every entry carries ``kind`` and ``fidelity``:

``kind``
    ``spatial`` — a ``vso:SpatialFact`` with any of ``rcc`` / ``directional`` /
    ``proximal``; ``perdurant`` — a reified ``vso:Event`` / ``vso:Process`` /
    ``vso:Stative`` with thematic roles; ``edge`` — one property asserted
    directly between the two entities (the §5.8 mereology set, or
    ``vso:occludes``); ``quality`` — a reified
    ``vso:Quality`` on a registry dimension (attributes only); ``drop`` — no
    VSON construct, with a ``reason``.

``fidelity``
    ``exact`` — the VSON construct denotes what the source construct denotes.
    ``approximate`` — a defensible reading that loses or adds something, and
    ``note`` says what. ``dropped`` — for ``kind: drop``.

An entry may set ``"swap": true``, which exchanges subject and object before
the construct is built (``worn by`` is ``wearing`` read backwards).
"""

from __future__ import annotations

import json
import os
import re

#: docs/vson.md §5.6, byte-identical to the pattern vss:LemmaShape enforces.
LEMMA_RE = re.compile(r"^[a-z][a-z0-9_]*$")

HERE = os.path.dirname(os.path.abspath(__file__))
MAPPINGS_DIR = os.path.join(HERE, "mappings")

KINDS = ("spatial", "perdurant", "edge", "quality", "drop")
FIDELITIES = ("exact", "approximate", "dropped")

#: The closed value sets an entry may name, transcribed from docs/vson.md
#: §5.12 and §5.8. tests/test_importers.py checks each of these against
#: ontology/vso.ttl and ontology/rcc8.ttl, so this is a fail-fast copy rather
#: than a second registry.
RCC_VALUES = ("DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPi", "NTPPi")
DIRECTIONAL_VALUES = (
    "above", "below", "left_of", "right_of", "in_front_of", "behind",
)
PROXIMAL_VALUES = ("near", "far", "adjacent", "next_to", "facing")
#: The properties an ``edge`` entry may assert directly between the two
#: entities: the five of §5.8 plus vso:occludes (§5.10), which is the other
#: binary entity-to-entity property in the vocabulary.
EDGE_PREDICATES = (
    "partOf", "hasPart", "properPartOf", "overlaps", "disjoint", "occludes",
)
PERDURANT_CLASSES = ("Event", "Process", "Stative")
ROLES = (
    "agent", "patient", "theme", "instrument", "recipient", "source", "goal",
    "beneficiary", "experiencer", "stimulus", "holder", "manner", "cause",
    "result", "location", "time",
)
AFFORDANCES = ("Holdable", "Wearable", "Mountable", "Container", "Edible")
ANIMACY = ("Agentive", "Inert")
COUNTABILITY = ("Count", "Mass", "Collective")
INDIVIDUATION = ("Generic", "Named", "Kind", "Skolem")


class TableError(ValueError):
    """A mapping table that cannot be trusted to convert anything."""


class MappingTable(object):
    """One dataset's table, checked at construction."""

    def __init__(self, data, path):
        self.path = path
        # The report names the table, and a report is a frozen artifact: an
        # absolute path would make it machine-specific.
        self.rel_path = os.path.relpath(
            path, os.path.dirname(os.path.dirname(HERE))
        )
        self.data = data
        self.dataset = data.get("dataset")
        self.provenance = data.get("_provenance", {})
        self.policy = data.get("policy", {})
        self.object_classes = data.get("object_classes", {})
        self.predicates = data.get("predicates", {})
        self.attributes = data.get("attributes", {})
        self._check()

    # -- lookups ----------------------------------------------------------

    def predicate(self, name):
        return self.predicates.get(name)

    def attribute(self, name):
        return self.attributes.get(name)

    def object_class(self, name):
        return self.object_classes.get(name, {})

    # -- validation -------------------------------------------------------

    def _fail(self, message):
        raise TableError("%s: %s" % (self.path, message))

    def _check(self):
        if not self.dataset:
            self._fail("no 'dataset' key")
        individuation = self.policy.get("individuation")
        if individuation is not None and individuation not in INDIVIDUATION:
            self._fail("policy.individuation %r is not a §5.12 value" % individuation)
        for name, entry in sorted(self.object_classes.items()):
            self._check_object_class(name, entry)
        for name, entry in sorted(self.predicates.items()):
            self._check_entry("predicate", name, entry, ("spatial", "perdurant",
                                                          "edge", "drop"))
        for name, entry in sorted(self.attributes.items()):
            self._check_entry("attribute", name, entry, ("quality", "drop"))

    def _check_object_class(self, name, entry):
        where = "object_classes[%r]" % name
        if not isinstance(entry, dict):
            self._fail("%s is not an object" % where)
        for key, allowed in (("animacy", ANIMACY),
                             ("countability", COUNTABILITY)):
            value = entry.get(key)
            if value is not None and value not in allowed:
                self._fail("%s.%s %r is not a §5.12 value" % (where, key, value))
        for affordance in entry.get("affordance", []):
            if affordance not in AFFORDANCES:
                self._fail("%s.affordance %r is not a §5.12 value"
                           % (where, affordance))

    def _check_entry(self, what, name, entry, allowed_kinds):
        where = "%ss[%r]" % (what, name)
        if not isinstance(entry, dict):
            self._fail("%s is not an object" % where)
        kind = entry.get("kind")
        if kind not in allowed_kinds:
            self._fail("%s.kind %r is not one of %s"
                       % (where, kind, ", ".join(allowed_kinds)))
        fidelity = entry.get("fidelity")
        if fidelity not in FIDELITIES:
            self._fail("%s.fidelity %r is not one of %s"
                       % (where, fidelity, ", ".join(FIDELITIES)))
        if kind == "drop":
            if fidelity != "dropped":
                self._fail("%s is a drop but its fidelity is %r" % (where, fidelity))
            if not entry.get("reason"):
                self._fail("%s is a drop with no reason" % where)
            return
        if fidelity == "dropped":
            self._fail("%s has fidelity 'dropped' but kind %r" % (where, kind))
        if fidelity == "approximate" and not entry.get("note"):
            self._fail("%s is approximate with no note saying what is lost" % where)
        getattr(self, "_check_" + kind)(where, entry)

    def _check_spatial(self, where, entry):
        values = [k for k in ("rcc", "directional", "proximal") if k in entry]
        if not values:
            self._fail("%s: a spatial entry needs rcc, directional or proximal"
                       % where)
        for key, allowed in (("rcc", RCC_VALUES),
                             ("directional", DIRECTIONAL_VALUES),
                             ("proximal", PROXIMAL_VALUES)):
            value = entry.get(key)
            if value is not None and value not in allowed:
                self._fail("%s.%s %r is not a §5.12 value" % (where, key, value))

    def _check_perdurant(self, where, entry):
        if entry.get("class") not in PERDURANT_CLASSES:
            self._fail("%s.class %r is not Event/Process/Stative"
                       % (where, entry.get("class")))
        lemma = entry.get("lemma", "")
        if not isinstance(lemma, str) or not LEMMA_RE.match(lemma):
            self._fail("%s.lemma %r is not ^[a-z][a-z0-9_]*$ (§5.6)"
                       % (where, lemma))
        for key in ("subject_role", "object_role"):
            role = entry.get(key)
            if role is not None and role not in ROLES:
                self._fail("%s.%s %r is not a §5.6 role" % (where, key, role))
        if entry.get("subject_role") is None:
            self._fail("%s has no subject_role" % where)

    def _check_edge(self, where, entry):
        predicate = entry.get("predicate")
        if predicate not in EDGE_PREDICATES:
            self._fail("%s.predicate %r is not a §5.8 / §5.10 entity property"
                       % (where, predicate))

    def _check_quality(self, where, entry):
        if not entry.get("dimension"):
            self._fail("%s has no dimension" % where)
        if not entry.get("value"):
            self._fail("%s has no value" % where)


def table_path(dataset):
    return os.path.join(MAPPINGS_DIR, "%s.json" % dataset)


def load_table(dataset):
    """Read and check one dataset's mapping table."""
    path = table_path(dataset)
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return MappingTable(data, path)
