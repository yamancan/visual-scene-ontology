"""``python3 -m tools.importers <dataset> <file>`` — the importer entry point.

    python3 -m tools.importers gqa sceneGraphs.json --out-dir out/
    python3 -m tools.importers vg  scene_graphs.json --image-data image_data.json
    python3 -m tools.importers psg psg.json --report psg-lossiness.json

**Why this is not a `vson` subcommand.** The Rust binary carries a byte-
identical mirror of every Python module and every data file it runs
(`cli/src/commands/embed.rs`, `scripts/check_embedded_assets.py`), so a
`vson import` would put three dataset mapping tables inside the released
binary. Those tables are *dataset* artifacts — they change when a dataset's
vocabulary changes, and they assert nothing about VSON — whereas everything the
binary embeds today is a spec artifact: the ontology, the shapes, the
transpilers, the gates. Importing is also a corpus-preparation step, run once
per dump, rather than a check anyone runs per document. So the importers stay
Python-only and the CLI surface stays the conformance surface. Reversing this
costs one clap arm and one `python_bridge` probe if the trade ever changes.

Exit codes: 0 wrote something, 1 the input produced no conformant scene,
2 the input or the mapping table could not be read.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import DATASETS, VERSION, read
from .common import DIRECTIONAL_POLICIES
from .mapping import TableError
from .psg import RELATION_ORDERS


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.importers",
        description="Convert a vision-dataset scene graph to VSON-P, with a "
                    "lossiness report.",
    )
    parser.add_argument("dataset", choices=list(DATASETS))
    parser.add_argument("file", help="the dataset annotation file")
    parser.add_argument(
        "--out-dir",
        help="write one .vson file per scene here (default: stdout)",
    )
    parser.add_argument(
        "--report",
        help="write the lossiness report here (default: stderr summary only)",
    )
    parser.add_argument(
        "--directional-policy", choices=list(DIRECTIONAL_POLICIES),
        default="camera",
        help="what to do with a directional predicate in a source that has no "
             "viewer (C5): 'camera' mints one vso:CameraView per image and "
             "anchors the fact to it; 'skip' drops the fact and counts it.",
    )
    parser.add_argument(
        "--image-data",
        help="VG only: path to image_data.json, which carries the image "
             "dimensions vso:bbox2d normalization needs",
    )
    parser.add_argument(
        "--psg-relation-order", choices=list(RELATION_ORDERS),
        default="subject_object",
        help="PSG only: how to read a relation triplet's first two indices",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        scenes, report = read(
            args.dataset,
            args.file,
            directional_policy=args.directional_policy,
            image_data=args.image_data,
            relation_order=args.psg_relation_order,
        )
    except (OSError, ValueError, TableError) as error:
        sys.stderr.write("error: %s\n" % error)
        return 2

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        for scene in scenes:
            path = os.path.join(args.out_dir, "%s.vson" % scene.doc_id)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(scene.to_vson_p())
    else:
        for scene in scenes:
            sys.stdout.write(scene.to_vson_p())
            sys.stdout.write("\n")

    payload = report.to_dict()
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    predicates = payload["predicates"]
    sys.stderr.write(
        "%s: %d record(s) read, %d scene(s) emitted; predicates "
        "%d exact / %d approximate / %d dropped / %d unmapped\n"
        % (args.dataset, payload["records_read"], payload["scenes_emitted"],
           predicates["exact"], predicates["approximate"],
           predicates["dropped"], predicates["unmapped"])
    )
    return 0 if scenes else 1


if __name__ == "__main__":
    sys.exit(main())
