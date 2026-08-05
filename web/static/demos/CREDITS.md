# Demo image credits

The six photographs in this directory are the studio's demo strip — the
thumbnails under the dropzone, and the images the 16-scene gallery sits beside.
They are **third-party work**. The repository's Apache-2.0 grant covers the code
and the ontology; it does not cover these pixels, and this file is where that is
said. The same six rows are in the repository's root [`NOTICE`](../../../NOTICE)
and, per entry, in [`manifest.json`](./manifest.json) beside this file.

## The six

| File | Photographer | Licence | Unsplash photo | sha256 of the bytes served here |
|---|---|---|---|---|
| `kitchen.jpg` | Karl Fredrickson | Unsplash License | <https://unsplash.com/photos/TYIzeCiZ_60> | `4b73c6163fb862eca7e0045234386a6098d3e0377d9fc8fc00381d6101f50a5b` |
| `cat.jpg` | Jason Leung | Unsplash License | <https://unsplash.com/photos/bEHmVywPcjE> | `5aff60f1810fde510cf4bc4f9f2616442997a72c599a0f3852731e3c4f0159cd` |
| `chess.jpg` | Felix Mittermeier | Unsplash License | <https://unsplash.com/photos/nAjil1z3eLk> | `888ed92f8a6e1e26e034c64e6c915c34b176e62ee273853848443160c3233364` |
| `blocks.jpg` | Karl Abuid | Unsplash License | <https://unsplash.com/photos/7ezVb0oTQ6M> | `382e1366b5b1522a0cda49681f105c28ac2af14a698d1fd76f211b78d135a004` |
| `table.jpg` | Chris Reyem | Unsplash License | <https://unsplash.com/photos/wH8y3nslmyo> | `b9e5850002ed40834b67f4a2d1ed686d73c779558a1a469ec5c97c52a42d64e0` |
| `bicycle.jpg` | Abhishek Ravi | Unsplash License | <https://unsplash.com/photos/czNXupVwHdU> | `af711930c3867f07d7cb1f5bfeb3e0d4f83c16b1752ced57f1ec19b4b87a4ccb` |

The labels the studio shows (`Coffee Pour`, `Cat on a Rug`, `Fallen King`,
`Block Tower`, `Garden Table`, `Bicycle & Wall`) are this project's captions,
not the photographers' titles. On 2026-08-05 the set changed shape: two
landscape demos (`books.jpg`, a mountain range; `forest.jpg`, a fjord) and one
figure demo (`lamp.jpg`) were withdrawn as editorially weak — a scene-graph
demo earns its place with distinct entities and visible relations, and a
landscape has neither — and five scenes chosen on that criterion replaced
them. That withdrawal was editorial, not a rights issue; the earlier
person-standard withdrawals are documented below.

## The licence, stated exactly

**Unsplash License** — <https://unsplash.com/license>.

It is **not CC0** and **not a public-domain dedication**. Unsplash published
under CC0 until 2017 and stopped; anything in this repository's history that
called these images CC0 was wrong. The Unsplash License grants an irrevocable,
nonexclusive, worldwide copyright licence to use the photographs free of charge,
including commercially, without permission from or attribution to the
photographer — the credits above are given because the photographers earned
them, not because the licence compels them.

Two things it does not grant, and they are the reason this file exists:

- **No model release.** A photograph of an identifiable person is licensed by
  its photographer, not by the person in it. On 2026-08-04 a fifth image was
  withdrawn from this set for that reason — its subject was an identifiable
  woman and the baked envelope beside it published a machine-readable inference
  about her face (`vso:dimension vso:Affect ; vso:value :thoughtful`), which no
  copyright licence authorizes. See [`spec/CHANGELOG.md`](../../../spec/CHANGELOG.md),
  annotation 2026-08-04, and the earlier lookbook withdrawal, which set the standard.
- **No property release**, and no licence over trademarks or logos that happen
  to appear in a frame.

## How the provenance was established, so it can be re-walked

Nothing here rests on memory. Each step is reproducible from the bytes in this
directory. Two chains exist, because the set was assembled in two eras:

**`kitchen.jpg` (2026-08-04, via Lorem Picsum):**

1. **The file says where it came from.** The JPEG carries a comment segment
   reading `Picsum ID: 1060`, written by Lorem Picsum when it served the image.
   `grep -a 'Picsum ID' web/static/demos/kitchen.jpg` prints it.
2. **Lorem Picsum says who took it.** `curl -s https://picsum.photos/id/1060/info`
   returns `{"id":"1060","author":"Karl Fredrickson", …,"url":"https://unsplash.com/photos/TYIzeCiZ_60", …}`.
3. **The Unsplash page is the primary record**, verified in a browser
   (`unsplash.com` returns 401 to command-line clients).

**The five 2026-08-05 scenes (direct from Unsplash):**

1. **The file says where it came from.** Each JPEG carries a comment segment
   reading `Unsplash <photo-id>`, written at import:
   `grep -a 'Unsplash' web/static/demos/cat.jpg` → `Unsplash bEHmVywPcjE`.
2. **The bytes came from the photo's own download endpoint**
   (`https://unsplash.com/photos/<photo-id>/download`), then a centre-region
   crop to the strip's 640×480 frame. The sha256 column above is of the bytes
   served here, not of Unsplash's original.
3. **The photo page is the primary record.** Each page was retrieved on
   2026-08-05 and its licence line read: "Free to use under the Unsplash
   License" on all five — none is an Unsplash+ (paid-tier) photograph, whose
   licence is different and whose download endpoint refuses anonymous clients.

## What the studio asserts about these photographs

Each image ships with a baked envelope under [`envelopes/`](./envelopes) — a
scene graph a vision-language model produced from it once, frozen and never
regenerated, which is what makes a demo click cost nothing. Those graphs are
**model output about a photograph**, not statements the photographer made and
not statements this project verified: `docs/vson.md` §2.1 says what a green
validation establishes, and it is never that the document describes the image.

Two bakes produced the corpus. `kitchen.json` is a server-era bake
(`google/gemini-2.5-flash` through the retired `/api/extract` route). The five
2026-08-05 envelopes were authored by `claude-fable-5` in a Claude Code
session against the same extractor skill (`skill@1.0.0`), validated by the
CLI's own three gates plus `vson verify --geometry` until conforming, and
assembled by [`web/scripts/bake-session-demos.ts`](../../scripts/bake-session-demos.ts)
through the studio's own `buildPenmanEnvelope` — same walker, same wire
format as a live extraction. A session is not per-image metered, so those
envelopes carry `latency_ms`, `input_tokens` and `output_tokens` as `0`; the
zeros are sentinels meaning "not measured", never measurements. Their
`shacl_retries` counts are real.

## The rule going forward

An entry in `manifest.json` must carry `credit`, `license` and `source_url`.
[`web/tests/demo-credits.test.ts`](../../tests/demo-credits.test.ts) fails
`pnpm test` — which CI runs before the build — on any entry that omits one, on
any entry whose image is absent, on a `CREDITS.md` or `NOTICE` that does not
cover every entry, and on the strings `CC0` or `public domain` wherever a licence
is named. An uncredited image cannot reach a deploy.
