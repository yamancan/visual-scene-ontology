# Vision-dataset importers

`tools/importers/` converts published scene-graph annotations into conformant
VSON, with a per-dataset **lossiness report** that counts every source
construct exactly once. Three datasets ship: **GQA**, **Visual Genome (VG)** and
**PSG**.

```
python3 -m tools.importers gqa sceneGraphs.json      --out-dir out/ --report gqa.json
python3 -m tools.importers vg  scene_graphs.json     --image-data image_data.json
python3 -m tools.importers psg psg.json              --out-dir out/
```

What the numbers came out at is [`docs/eval/coverage.md`](./eval/coverage.md).
What an imported document establishes is nothing beyond what its source
annotation established: [`docs/vson.md`](./vson.md) §2.1 governs, an importer
reads no image, and every approximation the tables make is counted rather than
smoothed over.

---

## 1. Why `python -m` and not `vson import`

The Rust binary carries a byte-identical mirror of every Python module and data
file it runs ([`cli/src/commands/embed.rs`](../cli/src/commands/embed.rs),
gated by [`scripts/check_embedded_assets.py`](../scripts/check_embedded_assets.py)),
so a `vson import` subcommand would put three dataset mapping tables inside the
released binary. Those tables are **dataset** artifacts: they change when a
dataset's vocabulary changes and they assert nothing about VSON. Everything the
binary embeds today is a **spec** artifact — the ontology, the shapes, the
transpilers, the gates. Importing is also a corpus-preparation step run once per
dump, not a check run per document.

So the importers are Python-only and the CLI surface stays the conformance
surface. The reversal costs one `clap` arm and one `python_bridge` probe if the
trade ever changes.

---

## 2. Input formats

Each reader documents its format in its own module docstring; this is the
summary and the provenance.

| Dataset | File | Shape | Where the format is documented |
|---|---|---|---|
| GQA | `sceneGraphs.json` (`train_` / `val_`) | `{imageId: {width, height, location?, weather?, objects: {objectId: {name, x, y, w, h, attributes, relations}}}}` | the GQA download page's "Scene_graphs.json" table (retrieved 2026-08-03) |
| VG | `scene_graphs.json` | `[{image_id, objects: [{object_id, names, x, y, w, h, attributes, synsets}], relationships: [{relationship_id, predicate, subject_id, object_id}]}]` | the released file itself; the `relationships.json` variant inlines the endpoints as `subject` / `object` objects and is also accepted |
| PSG | `psg.json` | `{data: [{image_id, width, height, segments_info, annotations, relations}], thing_classes, stuff_classes, predicate_classes}` | `openpsg/datasets/psg.py` in the OpenPSG repository (retrieved 2026-08-03) |

Three things learned by reading the real files rather than only the
documentation, each of which the readers handle:

- **GQA's `relations` is a list, not a dictionary.** The published table types
  it as a dictionary keyed by relation id; every record in the released
  `sceneGraphs.zip` writes a list. The reader accepts both.
- **VG's scene graphs carry pixels and no image size.** `vso:bbox2d` is a
  fraction of the image (§5.4), and the width and height live in a different
  file (`image_data.json`). Without `--image-data`, every box is dropped and
  counted; inventing a denominator is not an option.
- **PSG's boxes are `xyxy`, not COCO's `xywh`.** `openpsg/datasets/psg.py`
  rewrites each `annotations` entry with the comment *"Convert from xyxy to
  xywh"* and the arithmetic to match, and writes detectron2's `bbox_mode` `0`
  (`XYXY_ABS`). A record that declares `XYWH_ABS` is honoured as such.

One thing that could **not** be settled from the sources: PSG's relation
triplets are `[i, j, predicate]` into `segments_info`, but `get_ann_info` passes
them through unnamed while the frequency-matrix helper in the same file reads
index 0 as the *object*. `--psg-relation-order` defaults to `subject_object`,
which is what the predicate names imply (a *person* `walking on` a *pavement*),
and the flag is there because the code does not decide it.

---

## 3. The mapping tables are data

One JSON file per dataset under `tools/importers/mappings/`. The code decides
nothing about what `on` means; the table does, and a reader who disagrees edits
JSON rather than a parser.

```json
"on":            { "kind": "spatial",   "fidelity": "approximate",
                   "rcc": "EC", "note": "support read as topological contact…" },
"wearing":       { "kind": "perdurant", "fidelity": "exact", "class": "Stative",
                   "lemma": "wear", "subject_role": "holder", "object_role": "theme" },
"of":            { "kind": "edge",      "fidelity": "approximate",
                   "predicate": "partOf", "note": "…" },
"taller than":   { "kind": "drop",      "fidelity": "dropped",
                   "reason": "comparative between two entities; …" }
```

| `kind` | Becomes |
|---|---|
| `spatial` | a `vso:SpatialFact` with any of `rcc` / `directional` / `proximal` (§5.7) |
| `perdurant` | a reified `vso:Event` / `vso:Process` / `vso:Stative` with thematic roles (§5.6) |
| `edge` | one property asserted between the two entities: the five of §5.8, or `vso:occludes` (§5.10) |
| `quality` | a reified `vso:Quality` on one of the twenty-one registry dimensions (§5.5.1) — attributes only |
| `drop` | nothing, plus a `reason` |

| `fidelity` | Means |
|---|---|
| `exact` | the VSON construct denotes what the source construct denotes |
| `approximate` | a defensible reading that loses or adds something; `note` is **required** and says what |
| `dropped` | for `kind: drop`; `reason` is required |

`"swap": true` exchanges subject and object first (`worn by` is `wearing` read
backwards). `"variant_of"` marks a spelling variant of another key — VG writes
`on`, `ON`, `on a` and `is on` for one relation, and PSG's published table gives
parenthesised alternates for four of its predicates.

[`tools/importers/mapping.py`](../tools/importers/mapping.py) refuses a table
that names a value outside §5.12, a role outside §5.6, a lemma outside
`^[a-z][a-z0-9_]*$`, an approximation with no note, or a drop with no reason —
at load time, not half-way through a corpus.
[`tests/test_importers.py`](../tests/test_importers.py) then reads every term
the tables mention back out of `ontology/vso.ttl` and `ontology/rcc8.ttl`, so a
typo in the data cannot ship documents that fail C2.

---

## 4. The two policies

### 4.1 The viewer that is not there (C5)

**None of these datasets has a viewer, and VSON requires one.** C5 (§2, §3.3)
says a `vso:directional` fact **MUST** carry a `vso:viewer`; GQA, VG and PSG all
annotate `to the left of` with no camera, no observer and no frame node at all.
This is the single largest structural mismatch between VSON and the corpora it
would be trained or evaluated on — and it is not small:
**90.94% of GQA's 4,330,796 relation occurrences** map to a directional value
([coverage.md](./eval/coverage.md)).

The default policy is `--directional-policy camera`:

- mint **one `vso:CameraView` per image**, and anchor every directional fact to
  it;
- count each one under `directionals.viewer_inferred` in the report;
- say so in the emitted document's comment header, in every case.

The justification is that the annotation was made by a person looking at *the*
image, so `to the left of` means left in the image frame — which is what a
`vso:CameraView` denotes, and the same frame `vso:bbox2d` is normalized against
(§5.13.1). The camera is nevertheless **inferred by the importer and not
annotated by the dataset**, which is why it is counted rather than assumed.

`--directional-policy skip` drops those facts and counts them under
`directionals.skipped` instead. What it costs is measured: on GQA it discards
nine relation occurrences in ten. Nothing emits a directional without a viewer,
because that document would not be VSON.

**What the datasets cannot express either way.** `on the back of`, `on the side
of` and `on the front of` are *object-intrinsic* orientations — the back of the
truck, not the back as seen from anywhere. VSON's directionals are
viewer-anchored by construction (C5), so those readings are lost and only the
contact survives; every such entry carries that note.

### 4.2 Unmapped attributes are dropped, never minted

§5.5.1 permits a dimension outside the registry **when it is minted in the
producer's own namespace**. That escape hatch is not reachable from VSON-P:
`role_value_to_vso` in
[`cli/src/penman/routing-tables.json`](../cli/src/penman/routing-tables.json)
routes every `:dimension` bareword into the `vso:` namespace, so a VSON-P
producer cannot write `:dimension :Reflectance`. An importer that wanted the
document-namespace dimension would have to emit Turtle directly.

So an attribute with no registry dimension is counted as `unmapped` and left
out. It is never spelled as a `vso:` term the registry does not carry — that
document would fail C2.

The measured consequence is in [coverage.md](./eval/coverage.md): the largest
groups of *dropped* attributes are not noise but **axes the twenty-one
dimensions do not carry** — geometric shape (`round`, `rectangular`), surface
pattern (`striped`, `plaid`), physical condition (`wet`, `rusty`, `broken`) and
surface texture (`shiny`, `rough`). Each is dropped with that reason spelled
out, so the count of what a new dimension would buy is derivable from the table
rather than guessed.

---

## 5. What every import decides for you

| Axis | Decision | Why |
|---|---|---|
| `vso:individuation` | `Skolem`, always | `ontology/vso.ttl` reads `vso:Skolem` as "a particular but unnamed individual, tracked within the document by a minted handle" — an annotated region with an object id, exactly |
| `vso:class` | the source label, as a **string literal** | these datasets ship label lists, not IRIs ([§5.17.3](./vson.md#5173-the-four-gaps-and-why-each-is-a-sentence-rather-than-a-triple)); a bareword would mint a document IRI per label and imply an alignment that does not exist |
| `vso:value` | the source string, as a string literal | same reason |
| `vso:animacy` | only where the table's `object_classes` decides it; otherwise **omitted and counted** | no shape and no clause requires an Entity to carry a trait (§5.4's Enforcement paragraph); guessing `Inert` for every unlisted animal would be asserting something |
| `vso:countability` | `Count` by default; `Mass` / `Collective` from `object_classes`; from COCO's thing/stuff split for PSG | a bounded annotated region is a countable individual unless the label says otherwise, and PSG is the one source that says so |
| `vso:bbox2d` | pixels ÷ image size, exact decimal arithmetic, clamped into the unit square | §5.4, §5.13.1; a box outside the frame is clipped and counted, never dropped |
| variable names | `o<object id>`, `sf<n>`, `e<n>` | traceable back to the source annotation, which is what a corpus needs |

---

## 6. The lossiness report

`--report <file>` writes JSON with one rule: **every source construct is counted
exactly once**, under `exact`, `approximate`, `dropped` or `unmapped`, and a
dropped one carries the reason. It is the same discipline §5.13.6 imposes on the
geometry check's verdicts — nothing is silently skipped.

```json
"predicates": {
  "read": 10, "exact": 3, "approximate": 5, "dropped": 2, "unmapped": 0,
  "by_name":       { "approximate": { "on": 1, "to the left of": 1 }, … },
  "unmapped_names":{ },
  "drop_reasons":  { "comparative between two entities; …": 1 }
},
"directionals": { "viewer_inferred": 2 },
"geometry":     { "normalized": 4, "clamped to frame": 1 },
"traits":       { "individuation": 4, "animacy_undetermined": 2, … }
```

Frozen examples: [`tests/fixtures/importers/*/golden/report.json`](../tests/fixtures/importers).

---

## 7. Fixtures and gates

`tests/fixtures/importers/<dataset>/` holds a **hand-written** sample in the
dataset's real format — three records each, written from the format
documentation and from reading the released files, never copied out of a dump —
and a `golden/` directory with the emitted VSON-P and the report, frozen byte
for byte.

`make importer-check` (inside `make check`) establishes, on every golden:

1. the emitted text and the report have not moved;
2. every document passes the three gates `vson validate` runs — SHACL, OWL 2 RL,
   C2 vocabulary closure;
3. no document contradicts its own rectangles (`verify --geometry`, §5.13);
4. **every `vso:directional` fact carries exactly one `vso:CameraView` viewer** —
   C5 checked on the graph, not trusted from the code;
5. every VSO term in the three mapping tables is declared in the ontology, every
   dimension is one of the twenty-one, every lemma matches §5.6's pattern;
6. `docs/eval/coverage.md` still matches what the measured vocabularies and the
   shipped tables produce.

Regenerate the goldens with
`VSON_FREEZE_IMPORTERS=1 python3 -m unittest tests.test_importers`. That is an
authoring step, not a fix for a red build: establish what moved first.
