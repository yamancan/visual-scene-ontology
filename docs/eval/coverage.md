# Vocabulary coverage of the vision-dataset importers

**What this is.** A measurement of how much of three published scene-graph
vocabularies the checked-in mapping tables
([`tools/importers/mappings/`](../../tools/importers/mappings)) decide, and how
much of the annotation volume those decisions account for. It is the first
measurement in this repository taken against something other than this
repository's own corpus.

**What it is not.** It is **not** an accuracy figure and **not** an evaluation
of VSON against ground truth. It says nothing about whether a converted document
is true of its picture; [`docs/vson.md`](../vson.md) §2.1 governs, and no
annotation here was checked against an image. A mapping the tables call
`approximate` counts as covered, and the note beside it is what says what was
lost. There is no ground truth in this repository and no evaluation number is
claimed anywhere below.

---

## 1. Method

Two inputs, both checked in, so every number below is recomputable offline:

- **The measured vocabularies**, [`docs/eval/vocab/*.tsv`](./vocab) — one row
  per source string with its occurrence count. Each file's header carries the
  URL, the archive sha256, the retrieval date, the image count and the counting
  rule.
- **The mapping tables**, `tools/importers/mappings/*.json` — the same data the
  importers run on, not a summary of it.

[`scripts/coverage_report.py`](../../scripts/coverage_report.py) joins them.
`make importer-check` runs it with `--check`, so this document cannot drift from
the tables it describes: change a mapping and this file goes stale and the build
says so.

**How the vocabularies were counted.**

| Dataset | Source | Retrieved | Counted |
|---|---|---|---|
| GQA | `sceneGraphs.zip` (`train` + `val`), sha256 `59f6a3f6…c51989` | 2026-08-03 | 85,638 images; every `relations[*].name`, `attributes[*]` and object `name`, once per occurrence |
| VG | `relationships.json.zip` (sha256 `e648867b…79182f`) and `attributes.json.zip` (sha256 `7f71c80f…3de3f38c`) | 2026-08-03 | 108,077 images; every `predicate` and every attribute string, once per occurrence |
| PSG | the predicate table published in the OpenPSG README | 2026-08-03 | 56 predicates, in seven groups (6+5+31+4+4+3+3). **No token counts** — `psg.json` is not fetchable from a stable public URL, so PSG has vocabulary-level coverage only, and its token columns read `—` rather than a guess |

Strings are lower-cased and their whitespace collapsed before lookup, and
nothing else: no stemming, no alias resolution, no stop-word stripping. Each of
those would be a mapping decision taken in code instead of in the table.

**Two numbers, not one.** *Type* coverage is how many distinct source strings a
table decides; *token* coverage is what share of the corpus's occurrences those
strings account for. For a curated vocabulary the two are close. For an open one
they are three orders of magnitude apart, and that gap is the finding.

---

## 2. The measurement

<!-- coverage:begin -->

| Dataset | Axis | Vocabulary (types) | Expressed | Dropped with a reason | Not yet decided |
|---|---|---|---|---|---|
| GQA | relation predicates | 310 | 291 (93.87%) | 19 (6.13%) | 0 (0.00%) |
| GQA | object attributes | 617 | 286 (46.35%) | 257 (41.65%) | 74 (11.99%) |
| VG | relation predicates | 36383 | 385 (1.06%) | 55 (0.15%) | 35943 (98.79%) |
| VG | object attributes | 65314 | 294 (0.45%) | 283 (0.43%) | 64737 (99.12%) |
| PSG | relation predicates | 56 | 55 (98.21%) | 1 (1.79%) | 0 (0.00%) |

| Dataset | Axis | Occurrences (tokens) | Expressed | Dropped with a reason | Not yet decided |
|---|---|---|---|---|---|
| GQA | relation predicates | 4330796 | 4321099 (99.78%) | 9697 (0.22%) | 0 (0.00%) |
| GQA | object attributes | 771327 | 678389 (87.95%) | 74533 (9.66%) | 18405 (2.39%) |
| VG | relation predicates | 2316104 | 2049229 (88.48%) | 106924 (4.62%) | 159951 (6.91%) |
| VG | object attributes | 2342898 | 1676718 (71.57%) | 194073 (8.28%) | 472107 (20.15%) |
| PSG | relation predicates | — | — | — | — |

**Exact and approximate, separately.** An `approximate` mapping is one the table itself marks as losing or adding something, with a note beside it saying what.

| Dataset | Axis | Exact (types) | Approximate (types) | Exact (tokens) | Approximate (tokens) |
|---|---|---|---|---|---|
| GQA | relation predicates | 101 | 190 | 3.20% | 96.57% |
| GQA | object attributes | 211 | 75 | 82.88% | 5.07% |
| VG | relation predicates | 130 | 255 | 13.34% | 75.13% |
| VG | object attributes | 219 | 75 | 67.95% | 3.61% |
| PSG | relation predicates | 34 | 21 | — | — |

**Why a drop is a drop.** Every dropped entry carries a reason, so the residual is grouped rather than lumped. Reasons are shown abbreviated; the tables carry them in full.

| Dataset | Axis | Reason | Types | Tokens |
|---|---|---|---|---|
| GQA | relation predicates | the source predicate is a bare preposition with no determinat… | 1 | 8639 |
| GQA | relation predicates | a depiction/reflection relation between two entities | 6 | 715 |
| GQA | relation predicates | the relation is not binary ('between' needs two grounds), and… | 2 | 148 |
| GQA | relation predicates | prospective aspect ('about to'): asserting the perdurant woul… | 2 | 67 |
| GQA | relation predicates | 'the other side of' is a relation to a reference frame the an… | 1 | 64 |
| GQA | relation predicates | comparative between two entities | 7 | 64 |
| GQA | object attributes | no registry dimension for physical condition or state of repa… | 54 | 19354 |
| GQA | object attributes | no registry dimension for geometric shape: the twenty-one dim… | 33 | 15539 |
| GQA | object attributes | an object-type, sport or brand modifier rather than a value o… | 65 | 11050 |
| GQA | object attributes | no registry dimension for surface pattern (striped, plaid, fl… | 25 | 9447 |
| GQA | object attributes | a scene-level property attached to an object | 28 | 8640 |
| GQA | object attributes | no registry dimension for surface texture or finish (shiny, r… | 30 | 7320 |
| GQA | object attributes | an evaluative judgement of the annotator (beautiful, pretty,… | 20 | 2685 |
| GQA | object attributes | a sex or gender label | 2 | 498 |
| VG | relation predicates | the source predicate is a bare preposition with no determinat… | 21 | 90442 |
| VG | relation predicates | the relation is not binary ('between' needs two grounds), and… | 2 | 3597 |
| VG | relation predicates | a text/label-bearing relation | 3 | 3561 |
| VG | relation predicates | the object is a material, and vso:Material is a value on the… | 1 | 2332 |
| VG | relation predicates | a depiction/reflection relation between two entities | 7 | 1801 |
| VG | relation predicates | an attribute string in the predicate slot — a Visual Genome a… | 5 | 1390 |
| VG | relation predicates | a bare past participle with no second argument reading | 1 | 735 |
| VG | relation predicates | protrusion: the figure is partly inside and partly outside th… | 1 | 670 |
| VG | relation predicates | a bare participle with no stimulus reading | 1 | 554 |
| VG | relation predicates | a path/route relation between two places | 1 | 521 |
| VG | relation predicates | an evaluative stance verb | 1 | 362 |
| VG | relation predicates | 'taking' is ambiguous between removal and photography here, a… | 1 | 359 |
| VG | relation predicates | an intrinsic part-of-extent relation ('the end of') | 1 | 339 |
| VG | relation predicates | prospective aspect ('about to'): asserting the perdurant woul… | 2 | 143 |
| VG | relation predicates | comparative between two entities | 7 | 118 |
| VG | object attributes | no registry dimension for physical condition or state of repa… | 54 | 39243 |
| VG | object attributes | no registry dimension for geometric shape: the twenty-one dim… | 35 | 36215 |
| VG | object attributes | an object-type, sport or brand modifier rather than a value o… | 68 | 31450 |
| VG | object attributes | a determiner, possessive or deictic in the attribute slot — a… | 16 | 23861 |
| VG | object attributes | no registry dimension for surface pattern (striped, plaid, fl… | 27 | 20130 |
| VG | object attributes | a scene-level property attached to an object | 30 | 19078 |
| VG | object attributes | no registry dimension for surface texture or finish (shiny, r… | 31 | 16516 |
| VG | object attributes | an evaluative judgement of the annotator (beautiful, pretty,… | 20 | 5966 |
| VG | object attributes | a sex or gender label | 2 | 1614 |
| PSG | relation predicates | prospective aspect ('about to'): asserting the perdurant woul… | 1 | — |

**The viewer that is not there (C5).** A source predicate that becomes a `vso:directional` value cannot be written without a `vso:viewer`, and none of these datasets has one. This is how much of each corpus that clause reaches.

| Dataset | Axis | Directional types | Directional tokens | Share of all tokens |
|---|---|---|---|---|
| GQA | relation predicates | 16 | 3938292 | 90.94% |
| VG | relation predicates | 30 | 143970 | 6.22% |
| PSG | relation predicates | 2 | — | — |

**The ranked residual** — the most frequent source strings the tables do not decide, which is where the next mapping work is and what the scope boundary looks like from inside.

- **GQA relation predicates** — none: every measured type is decided.
- **GQA object attributes** — `clear` (7263), `painted` (1122), `covered` (916), `up` (747), `down` (603), `lush` (457), `grouped` (365), `dried` (336), `double decker` (293), `overhead` (275), `filled` (273), `tinted` (271)
- **VG relation predicates** — `shining on` (415), `colored` (329), `are near` (327), `topping` (327), `reflecting on` (323), `hold` (320), `out of` (313), `are above` (309), `inside a` (307), `having` (305), `standing with` (305), `has on a` (304)
- **VG object attributes** — `clear` (14065), `painted` (3403), `distant` (2778), `looking` (2712), `wearing` (2435), `pictured` (2258), `dead` (2211), `back` (2083), `dirt` (2020), `watching` (2001), `colored` (1974), `circular` (1953)

<!-- coverage:end -->

---

## 3. What the numbers say

**1. C5 is the largest single mismatch, and it is now a number.** 90.94% of
GQA's 4,330,796 relation occurrences map to a `vso:directional` value — almost
entirely `to the left of` and `to the right of`, which GQA emits in matched
pairs. Every one of them requires a `vso:viewer` that no annotation supplies.
The importer's policy and its justification are in
[`docs/importers.md`](../importers.md) §4.1: one `vso:CameraView` is minted per
image, anchored to, and counted, and `--directional-policy skip` costs nine
relation occurrences in ten on this corpus. VG's directional load is far lower
(6.22%) because VG's relation vocabulary is dominated by `on`, `has`, `in` and
`of`; PSG's is two predicates out of 56.

This is not an argument against C5. It is the measurement of what C5 costs an
importer, which is what the clause's critics and its defenders were both
missing.

**2. A closed source vocabulary is nearly wholly expressible; an open one is
not — by type.** Every one of GQA's 310 relation types and 55 of PSG's 56
predicates get a VSON construct or a stated reason for not getting one. Visual
Genome's 36,383 predicate types are 1.06% covered. By *token* the same tables
reach 99.78% of GQA and 88.48% of VG. Both facts are true at once, and quoting
either alone misdescribes the situation: VG's tail is 35,943 strings, most of
them spelling variants, determiner-suffixed forms and outright annotation noise
(`white` and `black` appear in VG's *predicate* slot 1,390 times between the
five colour words the table drops for that reason).

**3. The dropped attributes are mostly four axes the registry does not have.**
Not noise: geometric shape (`round`, `rectangular`, `octagonal`), surface
pattern (`striped`, `plaid`, `floral`), physical condition (`wet`, `rusty`,
`broken`) and surface texture (`shiny`, `rough`, `glossy`). The drop-reason
table above carries the type and token counts for each, on both corpora — so the
question "what would a twenty-second dimension buy" has an answer derived from
data rather than from taste. §5.5.1 keeps the registry closed under `vso:` and
§8.2 keeps it closed inside v1.x; this is evidence for a v2 conversation, not a
change.

**4. Four kinds of drop are structural, and no dimension would fix them.**
Comparatives (`taller than`) — a `vso:Quality` is a value on one entity's
dimension and VSON has no binary comparison. Ternary relations (`between`) — a
`vso:SpatialFact` carries exactly one figure and one ground (§5.7). Prospective
aspect (`about to hit`, PSG's one dropped predicate) — asserting the perdurant
would assert an event the annotation says has not happened. Object-intrinsic
orientation (`on the back of`) — VSON's directionals are viewer-anchored by
construction, so "the back of the truck" has no spelling and only the contact
survives.

**5. Approximation is the normal case, not the exception.** On GQA relations,
96.57% of tokens are carried by `approximate` mappings and 3.20% by `exact`
ones. The dominant approximations are the directionals (viewer inferred) and
`on` → `rcc:EC` (support read as topological contact). Anyone building a corpus
from these tables is building a corpus of defensible readings, each with a note
saying what it lost — which is the honest version of what every scene-graph
conversion in the literature does silently.

---

## 4. Limits, stated plainly

- **No ground truth, so no accuracy.** Nothing here was compared against a
  human judgement of an image. §2.1 stands: *verified* still means verified
  against the schema.
- **PSG has no token coverage.** Its annotation file was not read. The 56
  predicates come from the published table; the counts columns are `—`.
- **Coverage is of a table, not of a language.** A different mapping table over
  the same vocabulary would produce different numbers. What is pinned is *this*
  table's decisions, which is why the tables are checked in and the numbers are
  regenerated from them.
- **Round-trip retention is not measured.** Import → export → compare, per
  dataset, needs an exporter in the same direction, and §7 ships none for these
  formats. The graph-agreement metric that would score it exists
  (`tools/metrics/smatch.py`, §5.15); the exporters do not.
- **The vocabularies are frozen measurements.** Re-deriving them needs the
  dumps (about 1.5 GB unpacked), which is why the counts are checked in with
  their archive hashes rather than recomputed in CI. The counting rule is in
  §1 above and the file headers; the join is CI-run on every build.

---

## 5. Reproducing this

```bash
# offline, from the checkout: recompute every number above
python3 scripts/coverage_report.py

# fail if this document no longer matches the tables
python3 scripts/coverage_report.py --check      # make importer-check runs this

# rewrite the measurement block after a mapping-table change
python3 scripts/coverage_report.py --write
```

Re-deriving `docs/eval/vocab/*.tsv` from the dumps needs the archives named in
§1 and their sha256s; the counting rule is one pass per file, one increment per
occurrence, lower-cased with whitespace collapsed.

Licence and attribution for the derived vocabulary counts:
[`docs/eval/attribution.md`](./attribution.md). **Nothing derived from these
datasets is published from this repository** until that file has been reviewed.
