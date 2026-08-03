"""PSG (Panoptic Scene Graph) -> VSON.

Input format
------------
``psg.json``: one object with ``data`` (the per-image records),
``thing_classes``, ``stuff_classes``, ``predicate_classes`` and
``test_image_ids``. A record carries ``image_id``, ``file_name``, ``width``,
``height``, ``segments_info``, ``annotations`` — which parallels
``segments_info`` element for element and holds the ``bbox`` — and
``relations``: triplets of integers, two indices into ``segments_info`` and a
**0-based** index into ``predicate_classes``.

The class id of a segment indexes ``thing_classes + stuff_classes``
concatenated, and ``segments_info[i]["isthing"]`` says which half it came from.
That distinction is worth more to VSON than it looks: COCO *stuff* is where
``vso:countability`` is not ``Count`` — sky, grass, water and road are read by
amount, not by count (§5.4) — so this is the one importer here that can decide
that axis from the source rather than defaulting it.

**The subject/object order of a relation triplet.** ``get_ann_info`` in
``openpsg/datasets/psg.py`` passes the triplets through as ``(o0, o1, r)``
without naming them, while the frequency-matrix helper further down the same
file reads index 0 as the object and index 1 as the subject. The two readings
are not reconcilable from the code alone, so this importer does not pretend to
settle it: ``--psg-relation-order`` defaults to ``subject_object``, which is
the ordering the predicate names imply (a *person* ``walking on`` a
*pavement*), and ``object_subject`` is one flag away for a reader who
establishes otherwise.
"""

from __future__ import annotations

import json

from . import VERSION
from .common import SceneBuilder
from .mapping import load_table
from .report import LossinessReport

DATASET = "psg"

RELATION_ORDERS = ("subject_object", "object_subject")


def read(path, directional_policy="camera", relation_order="subject_object",
         **_unused):
    """Return ``(scenes, report)`` for one PSG annotation file."""
    if relation_order not in RELATION_ORDERS:
        raise ValueError(
            "unknown --psg-relation-order %r; known: %s"
            % (relation_order, ", ".join(RELATION_ORDERS))
        )
    table = load_table(DATASET)
    report = LossinessReport(
        DATASET, path, table.rel_path, VERSION,
        {"directional": directional_policy, "relation_order": relation_order},
    )
    report.note(
        "PSG carries no viewer and no camera; every vso:CameraView in this "
        "output is minted by the importer (docs/vson.md C5)."
    )
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    classes = list(raw.get("thing_classes") or []) + list(
        raw.get("stuff_classes") or []
    )
    predicates = list(raw.get("predicate_classes") or [])
    if not classes or not predicates:
        raise ValueError(
            "%s carries no thing_classes/stuff_classes/predicate_classes; "
            "PSG's own class and predicate names live in the annotation file, "
            "and nothing here invents them" % path
        )
    builder = SceneBuilder(table, report, directional_policy)

    scenes = []
    for record in raw.get("data") or []:
        scene = builder.build(
            _record(record, classes, predicates, relation_order, report)
        )
        if scene is not None:
            scenes.append(scene)
    return scenes, report


def _record(record, classes, predicates, relation_order, report):
    segments = record.get("segments_info") or []
    annotations = record.get("annotations") or []
    objects = []
    for index, segment in enumerate(segments):
        annotation = annotations[index] if index < len(annotations) else {}
        objects.append({
            "id": index,
            "name": _class_name(segment.get("category_id"), classes),
            "attributes": [],
            "bbox": _bbox(annotation),
            # COCO's thing/stuff split is a countability signal the other two
            # datasets do not carry (§5.4).
            "countability": "Count" if segment.get("isthing") else "Mass",
        })

    relations = []
    for triplet in record.get("relations") or []:
        if len(triplet) != 3:
            report.predicates.record(
                "(malformed)", "dropped", "relation triplet is not three ints"
            )
            continue
        first, second, predicate_index = triplet
        subject, obj = (first, second)
        if relation_order == "object_subject":
            subject, obj = (second, first)
        relations.append({
            "subject": subject,
            "predicate": _predicate_name(predicate_index, predicates),
            "object": obj,
        })

    return {
        "doc_id": "psg-%s" % record.get("image_id"),
        "image_size": (record.get("width"), record.get("height")),
        "context": {},
        "objects": objects,
        "relations": relations,
        "comments": [
            "Imported from PSG by `python3 -m tools.importers psg` "
            "(tools/importers, v%s)." % VERSION,
            "Source record: image %s (%s). Mapping table: "
            "tools/importers/mappings/psg.json."
            % (record.get("image_id"), record.get("file_name")),
            "The CameraView is minted by the importer, not annotated by PSG "
            "(docs/vson.md C5). Nothing here was read off the image.",
        ],
    }


def _class_name(category_id, classes):
    if category_id is None or category_id < 0 or category_id >= len(classes):
        return None
    return classes[category_id]


def _predicate_name(index, predicates):
    if index is None or index < 0 or index >= len(predicates):
        return "(out of range: %s)" % index
    return predicates[index]


#: detectron2 BoxMode: 0 is XYXY_ABS, 1 is XYWH_ABS.
_XYXY, _XYWH = 0, 1


def _bbox(annotation):
    """PSG boxes are ``[x1, y1, x2, y2]`` in pixels, returned as ``x,y,w,h``.

    Not a guess: ``openpsg/datasets/psg.py`` rewrites each ``annotations``
    entry with the comment *"Convert from xyxy to xywh"* and the arithmetic to
    match, and ``bbox_mode`` is written as detectron2's ``0`` (``XYXY_ABS``)
    where PSG's preprocessing emits it. A record that declares ``XYWH_ABS`` is
    honoured as such rather than converted twice.
    """
    bbox = (annotation or {}).get("bbox")
    if not bbox or len(bbox) != 4:
        return None
    mode = (annotation or {}).get("bbox_mode", _XYXY)
    if mode == _XYWH or str(mode).lower() in ("xywh", "xywh_abs"):
        return (bbox[0], bbox[1], bbox[2], bbox[3])
    return (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
