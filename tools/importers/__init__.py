"""Vision-dataset importers: dataset scene graphs -> conformant VSON.

Three datasets, one shape. Each importer reads a published annotation file in
its own format, consults a **checked-in mapping table** under
``tools/importers/mappings/`` — data, not code — and emits VSON-P text plus a
**lossiness report** saying, per source construct, what mapped exactly, what
was approximated, and what was dropped and why.

    python3 -m tools.importers gqa <sceneGraphs.json> --out-dir out/

The three tables are the whole of the dataset-specific knowledge. The code
below decides nothing about what ``on`` means; ``mappings/gqa.json`` does, and
a reader who disagrees edits a JSON file rather than a parser.

What an importer does **not** claim. §2.1 of docs/vson.md governs: a conformant
VSON document is one the schema accepts, not one that is true of a picture. An
imported document inherits its source annotation's errors exactly, and the
mapping table adds its own approximations on top — every one of which is
counted in the report rather than smoothed over.
"""

from .mapping import MappingTable, load_table  # noqa: F401
from .model import Scene  # noqa: F401
from .report import LossinessReport  # noqa: F401

#: Importer release. Independent of the spec and vocabulary versions (§8.1) —
#: it names a build of these readers and nothing about the namespace.
VERSION = "1.0.0"

#: dataset key -> module attribute path, resolved lazily so importing this
#: package does not import three readers to run one.
DATASETS = ("gqa", "psg", "vg")


def read(dataset, path, **options):
    """Read one annotation file and return ``(scenes, report)``.

    ``dataset`` is one of :data:`DATASETS`; ``options`` are the per-importer
    policy switches documented in :mod:`tools.importers.__main__`.
    """
    if dataset not in DATASETS:
        raise ValueError(
            "unknown dataset %r; known: %s" % (dataset, ", ".join(DATASETS))
        )
    if dataset == "gqa":
        from . import gqa as reader
    elif dataset == "psg":
        from . import psg as reader
    else:
        from . import vg as reader
    return reader.read(path, **options)
