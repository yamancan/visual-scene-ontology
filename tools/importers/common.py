"""The conversion every importer shares, once.

A reader's output is a *neutral record* — one image, its objects, its
relations, its size — and this module turns that into a :class:`Scene` under a
:class:`~tools.importers.mapping.MappingTable`, counting every source construct
into a :class:`~tools.importers.report.LossinessReport` on the way.

Two policies live here because they are decisions about VSON, not about any one
dataset:

**Directionals and the missing viewer (docs/vson.md C5, §3.3).** None of these
datasets has a viewer concept. Their annotations were nevertheless made by a
person looking at *the* image, so ``to the left of`` means left in the image
frame — which is exactly what a ``vso:CameraView`` denotes, and exactly the
frame ``vso:bbox2d`` is normalized against (§5.13.1). The default policy
therefore mints one ``vso:CameraView`` per image, anchors every directional
fact to it, and counts each one under ``directionals.viewer_inferred``: the
camera is **inferred by this importer, not annotated by the dataset**, and the
count is what keeps that visible. ``--directional-policy skip`` drops the facts
instead and counts them; nothing emits a directional without a viewer, because
that document would not be VSON (C5).

**Unmapped attributes are dropped, not minted.** §5.5.1 permits a dimension
outside the registry when it is minted in the producer's own namespace — but
VSON-P routes every ``:dimension`` bareword into the ``vso:`` namespace
(``role_value_to_vso`` in ``cli/src/penman/routing-tables.json``), so that
escape hatch is not reachable from the syntax these importers write. An
attribute with no registry dimension is therefore counted as ``unmapped`` and
left out, never spelled as a ``vso:`` term the registry does not carry — which
would be a C2 violation (§5.5.1).
"""

from __future__ import annotations

import re

from .model import Entity, Perdurant, Quality, Scene, SpatialFact, normalize_bbox

#: Penman bare identifiers are ``[A-Za-z_][\w-]*`` (Appendix B). Dataset ids
#: are numeric strings or arbitrary tokens, so they are prefixed and scrubbed.
_UNSAFE = re.compile(r"[^A-Za-z0-9_]")

DIRECTIONAL_POLICIES = ("camera", "skip")


def entity_var(object_id):
    return "o" + _UNSAFE.sub("_", str(object_id))


class SceneBuilder(object):
    """Neutral record -> :class:`Scene`, under one mapping table."""

    def __init__(self, table, report, directional_policy="camera"):
        if directional_policy not in DIRECTIONAL_POLICIES:
            raise ValueError(
                "unknown --directional-policy %r; known: %s"
                % (directional_policy, ", ".join(DIRECTIONAL_POLICIES))
            )
        self.table = table
        self.report = report
        self.directional_policy = directional_policy

    # -- entry point ------------------------------------------------------

    def build(self, record):
        """Return a :class:`Scene`, or ``None`` when the record cannot make
        a conformant document (C4: a Composition must depict something)."""
        self.report.records += 1
        scene = Scene(record["doc_id"])
        scene.comments = list(record.get("comments", []))
        scene.context = dict(record.get("context") or {})

        by_id = {}
        for source in record.get("objects") or []:
            entity = self._entity(source, record.get("image_size"))
            if entity is None:
                continue
            by_id[str(source["id"])] = entity
            scene.entities.append(entity)

        if not scene.entities:
            self.report.skipped_records["no entity survived (C4)"] += 1
            return None

        self._relations(record, scene, by_id)
        self.report.scenes += 1
        return scene

    # -- entities ---------------------------------------------------------

    def _entity(self, source, image_size):
        name = source.get("name")
        if not name:
            self.report.entities["dropped: no class label"] += 1
            return None
        entity = Entity(entity_var(source["id"]), name)
        self.report.entities["emitted"] += 1

        traits = self.table.object_class(name)
        individuation = self.table.policy.get("individuation")
        if individuation:
            entity.individuation = individuation
            self.report.traits["individuation"] += 1
        animacy = traits.get("animacy")
        if animacy:
            entity.animacy = animacy
            self.report.traits["animacy"] += 1
        else:
            self.report.traits["animacy_undetermined"] += 1
        countability = traits.get("countability") or source.get("countability")
        if countability:
            entity.countability = countability
            self.report.traits["countability"] += 1
        elif self.table.policy.get("countability_default"):
            entity.countability = self.table.policy["countability_default"]
            self.report.traits["countability_defaulted"] += 1
        else:
            self.report.traits["countability_undetermined"] += 1
        for affordance in traits.get("affordance", []):
            entity.affordances.append(affordance)
            self.report.traits["affordance"] += 1

        self._geometry(entity, source, image_size)
        self._attributes(entity, source)
        return entity

    def _geometry(self, entity, source, image_size):
        box = source.get("bbox")
        if not box:
            self.report.geometry["absent in source"] += 1
            return
        if not image_size:
            self.report.geometry["dropped: image size unknown"] += 1
            return
        text, clamped = normalize_bbox(
            box[0], box[1], box[2], box[3], image_size[0], image_size[1]
        )
        if text is None:
            self.report.geometry["dropped: image size unknown"] += 1
            return
        entity.bbox2d = text
        self.report.geometry["normalized"] += 1
        if clamped:
            self.report.geometry["clamped to frame"] += 1

    def _attributes(self, entity, source):
        for raw in source.get("attributes") or []:
            name = normalize_label(raw)
            entry = self.table.attribute(name)
            if entry is None:
                self.report.attributes.record_unmapped(name)
                continue
            if entry["kind"] == "drop":
                self.report.attributes.record(name, "dropped", entry["reason"])
                continue
            quality = Quality(
                "%s_q%d" % (entity.var, len(entity.qualities) + 1),
                entry["dimension"],
                entry["value"],
            )
            entity.qualities.append(quality)
            self.report.attributes.record(name, entry["fidelity"])

    # -- relations --------------------------------------------------------

    def _relations(self, record, scene, by_id):
        for relation in record.get("relations") or []:
            name = normalize_label(relation["predicate"])
            subject = by_id.get(str(relation["subject"]))
            obj = by_id.get(str(relation["object"]))
            if subject is None or obj is None:
                self.report.predicates.record(
                    name, "dropped", "endpoint absent from the record's objects"
                )
                continue
            if subject is obj:
                self.report.predicates.record(
                    name, "dropped", "reflexive: figure and ground are one object"
                )
                continue
            entry = self.table.predicate(name)
            if entry is None:
                self.report.predicates.record_unmapped(name)
                continue
            if entry["kind"] == "drop":
                self.report.predicates.record(name, "dropped", entry["reason"])
                continue
            if entry.get("swap"):
                subject, obj = obj, subject
            builder = getattr(self, "_build_" + entry["kind"])
            builder(scene, entry, subject, obj, name)

    def _build_spatial(self, scene, entry, subject, obj, name):
        if entry.get("directional") and self.directional_policy == "skip":
            self.report.predicates.record(
                name, "dropped",
                "directional without a viewer in the source (C5); "
                "--directional-policy skip",
            )
            self.report.directionals["skipped"] += 1
            return
        fact = SpatialFact(
            "sf%d" % (len(scene.facts) + 1), subject.var, obj.var
        )
        fact.rcc = entry.get("rcc")
        fact.directional = entry.get("directional")
        fact.proximal = entry.get("proximal")
        if fact.directional:
            # C5 is not optional: a directional fact carries its viewer or it
            # is not emitted at all.
            fact.viewer = scene.camera_var
            self.report.directionals["viewer_inferred"] += 1
        scene.facts.append(fact)
        self.report.predicates.record(name, entry["fidelity"])

    def _build_perdurant(self, scene, entry, subject, obj, name):
        perdurant = Perdurant(
            "e%d" % (len(scene.perdurants) + 1), entry["class"], entry["lemma"]
        )
        perdurant.add(entry["subject_role"], subject.var)
        if entry.get("object_role"):
            perdurant.add(entry["object_role"], obj.var)
        scene.perdurants.append(perdurant)
        self.report.predicates.record(name, entry["fidelity"])

    def _build_edge(self, scene, entry, subject, obj, name):
        subject.edges.append((entry["predicate"], obj.var))
        self.report.predicates.record(name, entry["fidelity"])


def normalize_label(text):
    """Lower-case and collapse whitespace — the only normalization applied to
    a source string before it is looked up.

    Visual Genome writes ``ON``, ``on`` and ``on  a`` for one predicate, so a
    table keyed on raw strings would need three entries and would still miss
    the fourth. Nothing else is done: no stemming, no alias resolution, no
    stop-word stripping, because each of those would be a mapping decision
    made in code instead of in the table.
    """
    return " ".join(str(text).lower().split())
