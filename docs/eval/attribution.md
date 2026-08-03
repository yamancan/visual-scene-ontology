# Attribution and licence — the staged dataset material

**Status: DRAFT, held for maintainer review. Nothing derived from these
datasets is published from this repository until this file has been reviewed
and this line has been changed by a person.**

This file exists because the coverage study in
[`coverage.md`](./coverage.md) is derived from three third-party annotation
releases. It states exactly what was taken, what was written from it, and what
the licence position is — including where that position could **not** be
established, which is more of it than one would like.

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
