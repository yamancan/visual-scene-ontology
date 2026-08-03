"""GQA scene graphs -> VSON.

Input format
------------
``sceneGraphs.json`` (``train_sceneGraphs.json`` / ``val_sceneGraphs.json``),
documented on the GQA download page under "Scene_graphs.json": a dictionary
from image id to a scene graph with ``width``, ``height``, optional
``location`` and ``weather``, and ``objects`` — a dictionary from object id to
``{name, x, y, w, h, attributes, relations}`` where each relation is
``{name, object}`` and ``object`` is the target object's id.

One divergence between the documentation and the distributed file, and this
importer accepts both. The published table types ``relations`` as a dictionary
keyed by relation id; every record in the released ``sceneGraphs.zip`` writes a
**list** instead. Reading only the documented shape would import nothing from
the real file, and reading only the real shape would reject the documented one.

What GQA gives VSON that the others do not: ``location`` and ``weather`` are
scene-level facts, so they become a ``vso:SceneContext`` (§5.3.1) rather than
being flattened onto an object. That is the Frame layer of §3.1 carrying
exactly what it exists to carry.
"""

from __future__ import annotations

import json

from . import VERSION
from .common import SceneBuilder
from .mapping import load_table
from .report import LossinessReport

DATASET = "gqa"

#: GQA's two scene-level fields, and the vso:SceneContext roles they are.
#: ``weather`` is §5.3.1's own role name; ``location`` is a venue.
CONTEXT_FIELDS = (("location", "venue"), ("weather", "weather"))


def read(path, directional_policy="camera", **_unused):
    """Return ``(scenes, report)`` for one GQA scene-graph file."""
    table = load_table(DATASET)
    report = LossinessReport(
        DATASET, path, table.rel_path, VERSION,
        {"directional": directional_policy},
    )
    report.note(
        "GQA carries no viewer and no camera; every vso:CameraView in this "
        "output is minted by the importer (docs/vson.md C5)."
    )
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    builder = SceneBuilder(table, report, directional_policy)

    scenes = []
    for image_id in sorted(raw):
        record = _record(image_id, raw[image_id])
        scene = builder.build(record)
        if scene is not None:
            scenes.append(scene)
    return scenes, report


def _record(image_id, graph):
    objects = graph.get("objects") or {}
    context = {}
    for field, role in CONTEXT_FIELDS:
        value = graph.get(field)
        if value:
            context[role] = value

    neutral_objects = []
    relations = []
    for object_id in sorted(objects):
        source = objects[object_id]
        neutral_objects.append({
            "id": object_id,
            "name": source.get("name"),
            "attributes": source.get("attributes") or [],
            "bbox": _bbox(source),
        })
        for relation in _relations(source):
            relations.append({
                "subject": object_id,
                "predicate": relation.get("name"),
                "object": relation.get("object"),
            })

    return {
        "doc_id": "gqa-%s" % image_id,
        "image_size": (graph.get("width"), graph.get("height")),
        "context": context,
        "objects": neutral_objects,
        "relations": relations,
        "comments": [
            "Imported from GQA by `python3 -m tools.importers gqa` "
            "(tools/importers, v%s)." % VERSION,
            "Source record: image %s. Mapping table: "
            "tools/importers/mappings/gqa.json." % image_id,
            "The CameraView is minted by the importer, not annotated by GQA "
            "(docs/vson.md C5). Nothing here was read off the image.",
        ],
    }


def _relations(source):
    relations = source.get("relations") or []
    if isinstance(relations, dict):
        return [relations[key] for key in sorted(relations)]
    return relations


def _bbox(source):
    for key in ("x", "y", "w", "h"):
        if source.get(key) is None:
            return None
    return (source["x"], source["y"], source["w"], source["h"])
