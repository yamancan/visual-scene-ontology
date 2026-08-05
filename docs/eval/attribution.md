# Attribution and licence — the staged dataset material, and the shipped pixels

**Status of §1–§4 (the datasets): DRAFT, held for maintainer review. Nothing
derived from these datasets is published from this repository until this file
has been reviewed and this line has been changed by a person.** §5 is not
draft and is not held: it covers images this repository already ships.

This file exists because the coverage study in
[`coverage.md`](./coverage.md) is derived from three third-party annotation
releases. It states exactly what was taken, what was written from it, and what
the licence position is — including where that position could **not** be
established, which is more of it than one would like.

It grew a fifth section for an uncomfortable reason. §1–§4 held a review gate
over word-frequency tables — `on`, `to the left of`, `striped` with counts —
while four actual photographs shipped live in the web studio with no recorded
source at all. The stricter standard was applied to the lesser exposure. §5 is
the correction.

---

## 1. What is checked in, and what is not

| In this repository | Derived from | Form |
|---|---|---|
| [`docs/eval/vocab/gqa-*.tsv`](./vocab) | GQA `sceneGraphs.zip` | a frequency table: one row per distinct predicate/attribute string with its occurrence count |
| [`docs/eval/vocab/vg-*.tsv`](./vocab) | Visual Genome `relationships.json` / `attributes.json` | the same, plus a ranked residual head |
| [`docs/eval/vocab/psg-predicates.tsv`](./vocab) | the predicate table published in the OpenPSG README | 56 predicate names, no counts |
| `tools/importers/mappings/*.json` | the vocabularies above | this project's own mapping decisions, keyed on source strings |
| `tests/fixtures/importers/*` | **nothing** | hand-written samples in each dataset's format, written from the format documentation; no record is copied from any dump |

**Not in this repository, and not planned:** no images, no image identifiers, no
image URLs, no annotation records, no converted corpus. The `url` fields in the
VG fixture point at `example.org` precisely so that no real image is referenced.

The only third-party *content* carried here is **source vocabulary strings**
(`on`, `to the left of`, `striped`) with counts. A mapping table cannot be
written or checked without them, and a coverage number cannot be re-derived
without them offline.

---

## 2. Licence position, per source

### GQA (Hudson & Manning 2019)

- Distributed from `downloads.cs.stanford.edu/nlp/data/gqa/sceneGraphs.zip`;
  the archive's own `readme.txt` points to `gqadataset.org` for "all
  information about the dataset".
- **Licence not established.** The GQA pages retrieved on 2026-08-03
  (`cs.stanford.edu/people/dorarad/gqa/index.html`, `.../about.html`,
  `.../download.html`) contain no licence statement, no Creative Commons mark
  and no terms-of-use link that a script could find. This file does not assert
  a licence it did not read.
- **Action for review:** confirm the licence from `gqadataset.org` or from the
  authors before anything derived from GQA is published.

### Visual Genome (Krishna et al. 2017)

- Annotation dumps retrieved from
  `homes.cs.washington.edu/~ranjay/visualgenome/data/dataset/`.
- **The canonical domain is gone.** `visualgenome.org`, retrieved 2026-08-03,
  serves unrelated commercial content — online-casino review copy — and no
  longer serves the dataset, its documentation or any licence statement. The
  dataset's own paper states a CC BY 4.0 release, and that is the commonly
  cited position, but **this file records only what was retrieved**: the
  licence text was not read from a first-party page on that date.
- **Images are separate and are not touched.** Visual Genome's images come from
  Flickr under Flickr's terms, not the dataset's licence. Nothing here
  references an image.
- **Action for review:** establish the annotation licence from the paper, from
  the current mirror, or from the authors; decide whether the derived frequency
  tables may be published, and under what attribution line.

### PSG (Yang et al. 2022) / OpenPSG

- The 56 predicate names are transcribed from the predicate table published in
  the OpenPSG repository README (`github.com/Jingkang50/OpenPSG`), retrieved
  2026-08-03.
- **The repository's `LICENSE` is MIT** (retrieved 2026-08-03, same
  repository). That covers the code. The PSG *annotations* — which build on
  COCO panoptic segmentations and Visual Genome images — carry no licence
  statement in that file.
- No PSG annotation file was downloaded or read.
- **Action for review:** confirm the annotation licence before any PSG-derived
  material is published.

---

## 3. Attribution lines, drafted

To be used verbatim if and when the derived tables are published, once §2's
open questions are closed:

> Vocabulary frequency tables derived from the **GQA** dataset scene graphs.
> Hudson, D. A. & Manning, C. D. (2019). *GQA: A New Dataset for Real-World
> Visual Reasoning and Compositional Question Answering.* CVPR 2019.
> Counts computed from `sceneGraphs.zip` (sha256 `59f6a3f6…c51989`, retrieved
> 2026-08-03). No images and no annotation records are redistributed.

> Vocabulary frequency tables derived from **Visual Genome**. Krishna, R.,
> Zhu, Y., Groth, O., Johnson, J., Hata, K., Kravitz, J., Chen, S.,
> Kalantidis, Y., Li, L.-J., Shamma, D. A., Bernstein, M. S. & Fei-Fei, L.
> (2017). *Visual Genome: Connecting Language and Vision Using Crowdsourced
> Dense Image Annotations.* IJCV 123(1). Counts computed from
> `relationships.json` and `attributes.json` (archive sha256s in
> [`vocab/`](./vocab), retrieved 2026-08-03). No images, image identifiers or
> annotation records are redistributed.

> Predicate names quoted from the **PSG** predicate table published in the
> OpenPSG repository. Yang, J., Ang, Y. Z., Guo, Z., Zhou, K., Zhang, W. &
> Liu, Z. (2022). *Panoptic Scene Graph Generation.* ECCV 2022.

---

## 4. Why publication is held

The programme this work belongs to states the rule directly: derived graphs are
staged in-repo and their publication waits for a maintainer's licence review.
That is the state of this file. Concretely:

- the derived vocabulary tables are committed **locally**, so the coverage
  numbers are re-derivable and CI-checkable offline;
- nothing here is pushed to a registry, a dataset host, an archive or a DOI
  service by any automated process;
- the seed corpus that the importers *could* produce — converted graphs over
  real image sets — **does not exist in this repository** and is not created
  until §2's licence questions are answered.

When they are answered, the corpus is staged as image-ID lists plus derived
graphs, never pixels, with the attribution lines of §3 beside it.

---

## 5. The demo photographs — pixels this repository does ship

Everything above is about material that is *not* published. This section is
about material that is: four JPEGs under
[`web/static/demos/`](../../web/static/demos), served from the studio as the
clickable demo strip, and committed to this repository.

### 5.1 What they are

Photographs published on Unsplash, retrieved through **Lorem Picsum**
(`picsum.photos`), which re-serves Unsplash photographs and writes a
`Picsum ID: N` comment into the JPEG it returns.

| File | Photographer | Licence | Unsplash photo | Picsum ID |
|---|---|---|---|---|
| `kitchen.jpg` | Karl Fredrickson | Unsplash License | <https://unsplash.com/photos/TYIzeCiZ_60> | 1060 |
| `forest.jpg` | Oleksii Topolianskyi | Unsplash License | <https://unsplash.com/photos/-oWyJoSqBRM> | 1015 |
| `books.jpg` | Lee Roylland | Unsplash License | <https://unsplash.com/photos/dfZbts6B4yw> | 684 |
| `lamp.jpg` | Dominik Martin | Unsplash License | <https://unsplash.com/photos/vf29T22259I> | 325 |

The sha256 of each file as served is in
[`web/static/demos/CREDITS.md`](../../web/static/demos/CREDITS.md), which is the
canonical copy of this table; the root [`NOTICE`](../../NOTICE) carries it too,
and [`manifest.json`](../../web/static/demos/manifest.json) carries the same
three facts per entry so the studio can render them.

### 5.2 The licence position, and it is established

Unlike §2, this one is not open. The licence is the **Unsplash License**
(<https://unsplash.com/license>): an irrevocable, nonexclusive, worldwide
copyright licence to use the photographs free of charge, including
commercially, without permission or attribution.

- **Never "CC0", never "public domain".** Unsplash published under CC0 until
  2017 and stopped. Any statement in this repository's history calling these
  images CC0 was false, and the string is now rejected by a test wherever a
  licence is named.
- **It conveys no model release and no property release.** The photographer
  licenses the photograph. Nobody depicted in it has licensed anything.

### 5.3 How it was established, and the one step a script cannot take

1. `grep -a 'Picsum ID' web/static/demos/kitchen.jpg` — the file names its own
   re-server and ID.
2. `curl -s https://picsum.photos/id/1060/info` — returns the `author` and the
   `url` of the Unsplash photo page. The table in §5.1 is those two fields for
   each of the four IDs, retrieved 2026-08-04.
3. The Unsplash photo page itself is the first-party record. `unsplash.com`
   answers command-line clients with 401, so confirming each page shows the
   photographer named above is a **browser step, performed by the maintainer**,
   not something CI can do or this file can claim on its own.

### 5.4 One image was withdrawn rather than credited

A fifth demo shipped until 2026-08-04. Its subject was an identifiable woman,
and the byte-frozen envelope beside it published a machine-readable inference
about her face (`vso:dimension vso:Affect ; vso:value :thoughtful`). No
copyright licence authorizes that, and the Unsplash License in particular
conveys no model release. It was removed — image, envelope, index entry and
manifest entry — on the standard the earlier `lookbook.jpg` withdrawal had
already set. It was not replaced: a replacement would require re-baking an
envelope, and the four that remain are byte-untouched. See
[`spec/CHANGELOG.md`](../../spec/CHANGELOG.md), annotation 2026-08-04.

### 5.5 What the envelopes beside them assert

Each demo ships with a frozen envelope — a scene graph a vision-language model
produced from that photograph once. Those are **model claims about a
photograph**, not the photographer's statements and not verified facts about
the picture; [`docs/vson.md`](../vson.md) §2.1 states what a green validation
does and does not establish, and it never establishes that a document describes
its image. Nothing in the demo set should be read as an assertion by anyone
depicted or by the person who took the photograph.

### 5.6 The gate

[`web/tests/demo-credits.test.ts`](../../web/tests/demo-credits.test.ts) fails
`pnpm test` — which CI runs before `pnpm build` — when a manifest entry lacks a
`credit`, a `license` or a `source_url`, when the credited image is missing,
when `CREDITS.md` or `NOTICE` does not cover every entry, or when a licence is
named `CC0` or `public domain`. §1–§4 rest on a review gate a person performs;
§5 rests on a gate that runs.
