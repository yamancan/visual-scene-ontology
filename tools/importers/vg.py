"""Visual Genome scene graphs -> VSON.

Input format
------------
``scene_graphs.json``: a JSON **array** of per-image records, each
``{"image_id": int, "objects": [...], "relationships": [...]}``. An object is
``{"object_id", "names": [str], "x", "y", "w", "h", "attributes": [str],
"synsets": [str]}``; a relationship is ``{"relationship_id", "predicate",
"subject_id", "object_id", "synsets"}``. The ``relationships.json`` variant
inlines the two endpoints as ``"subject"`` / ``"object"`` objects instead of
naming their ids, and this reader accepts that spelling too.

Two things this file does not have, and they are the two most consequential
facts about importing it.

**No image dimensions.** ``vso:bbox2d`` is a fraction of the image (§5.4) and
``scene_graphs.json`` stores pixels without a width or a height; those live in
``image_data.json``. Without ``--image-data`` every box is dropped and counted,
because the alternative is inventing a denominator.

**No predicate vocabulary.** VG relationship predicates are free text — the
published dump carries 36,383 distinct predicate strings after case and
whitespace normalization (docs/eval/coverage.md). A mapping table over an open
vocabulary is necessarily a head, not a cover, and the residual is measured
rather than assumed away.
"""

from __future__ import annotations

import json

from . import VERSION
from .common import SceneBuilder
from .mapping import load_table
from .report import LossinessReport

DATASET = "vg"


def read(path, directional_policy="camera", image_data=None, **_unused):
    """Return ``(scenes, report)`` for one VG scene-graph file.

    ``image_data`` is an optional path to VG's ``image_data.json``, which is
    what supplies the width and height §5.4 normalization needs.
    """
    table = load_table(DATASET)
    report = LossinessReport(
        DATASET, path, table.rel_path, VERSION,
        {"directional": directional_policy,
         "image_data": image_data or "(none)"},
    )
    report.note(
        "Visual Genome carries no viewer and no camera; every vso:CameraView "
        "in this output is minted by the importer (docs/vson.md C5)."
    )
    sizes = _image_sizes(image_data)
    if not sizes:
        report.note(
            "No image_data.json was given, so no vso:bbox2d could be written: "
            "scene_graphs.json stores pixel boxes and no image dimensions."
        )
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    builder = SceneBuilder(table, report, directional_policy)

    scenes = []
    for graph in raw:
        scene = builder.build(_record(graph, sizes))
        if scene is not None:
            scenes.append(scene)
    return scenes, report


def _image_sizes(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as handle:
        entries = json.load(handle)
    return {
        str(entry["image_id"]): (entry.get("width"), entry.get("height"))
        for entry in entries
    }


def _record(graph, sizes):
    image_id = graph.get("image_id")
    objects = []
    for source in graph.get("objects") or []:
        objects.append(_object(source))

    relations = []
    for relationship in graph.get("relationships") or []:
        subject_id, object_id = _endpoints(relationship, objects)
        relations.append({
            "subject": subject_id,
            "predicate": relationship.get("predicate"),
            "object": object_id,
        })

    return {
        "doc_id": "vg-%s" % image_id,
        "image_size": sizes.get(str(image_id)),
        "context": {},
        "objects": objects,
        "relations": relations,
        "comments": [
            "Imported from Visual Genome by `python3 -m tools.importers vg` "
            "(tools/importers, v%s)." % VERSION,
            "Source record: image %s. Mapping table: "
            "tools/importers/mappings/vg.json." % image_id,
            "The CameraView is minted by the importer, not annotated by VG "
            "(docs/vson.md C5). Nothing here was read off the image.",
        ],
    }


def _object(source):
    names = source.get("names") or ([source["name"]] if "name" in source else [])
    return {
        "id": source.get("object_id"),
        # VG stores a list of names per object and the released dump writes one
        # entry in all but a handful; the first is taken and any others are not
        # silently merged into the class string.
        "name": names[0] if names else None,
        "attributes": source.get("attributes") or [],
        "bbox": _bbox(source),
    }


def _endpoints(relationship, objects):
    """Ids of the two endpoints, adding inline endpoint objects if needed."""
    if "subject_id" in relationship and "object_id" in relationship:
        return relationship["subject_id"], relationship["object_id"]
    known = {entry["id"] for entry in objects}
    ids = []
    for key in ("subject", "object"):
        inline = relationship.get(key) or {}
        object_id = inline.get("object_id")
        if object_id is not None and object_id not in known:
            objects.append(_object(inline))
            known.add(object_id)
        ids.append(object_id)
    return ids[0], ids[1]


def _bbox(source):
    for key in ("x", "y", "w", "h"):
        if source.get(key) is None:
            return None
    return (source["x"], source["y"], source["w"], source["h"])
