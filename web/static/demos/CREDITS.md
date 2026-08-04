# Demo image credits

The four photographs in this directory are the studio's demo strip — the
thumbnails under the dropzone, and the images the 16-scene gallery sits beside.
They are **third-party work**. The repository's Apache-2.0 grant covers the code
and the ontology; it does not cover these pixels, and this file is where that is
said. The same four rows are in the repository's root [`NOTICE`](../../../NOTICE)
and, per entry, in [`manifest.json`](./manifest.json) beside this file.

## The four

| File | Photographer | Licence | Unsplash photo | Picsum ID | sha256 of the bytes served here |
|---|---|---|---|---|---|
| `kitchen.jpg` | Karl Fredrickson | Unsplash License | <https://unsplash.com/photos/TYIzeCiZ_60> | 1060 | `4b73c6163fb862eca7e0045234386a6098d3e0377d9fc8fc00381d6101f50a5b` |
| `forest.jpg` | Alexey Topolyanskiy | Unsplash License | <https://unsplash.com/photos/-oWyJoSqBRM> | 1015 | `1024478f7c40b7ebdea4a95689c0f6cddd74fddf4f3d7d4ca8ba8641027d0de8` |
| `books.jpg` | Lee Roylland | Unsplash License | <https://unsplash.com/photos/dfZbts6B4yw> | 684 | `34ecf96f7c897aaf48f01f962e6ff6dce1c457afdcc0c9008aeca6e9d47d7da8` |
| `lamp.jpg` | Dominik Martin | Unsplash License | <https://unsplash.com/photos/vf29T22259I> | 325 | `3b27cf51a3fe87ac13a3d8ef34a0369f91b57d24b7fdf94ca9f4a1b416806c77` |

The labels the studio shows (`Coffee Pour`, `Fjord Overlook`, `Snow Traverse`,
`Forest Figure`) are this project's captions, not the photographers' titles, and
two of them do not describe their file's name. The file names are historical and
are not renamed here, because the sha256 index that makes a demo click cost $0
([`envelopes/index.json`](./envelopes/index.json)) is keyed on bytes and the
manifest is keyed on paths.

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
  annotation 2026-08-04, and commit `fb446ea`, which set the standard.
- **No property release**, and no licence over trademarks or logos that happen
  to appear in a frame.

## How the provenance was established, so it can be re-walked

Nothing here rests on memory. Each step is reproducible from the bytes in this
directory:

1. **The file says where it came from.** Every JPEG carries a comment segment
   reading `Picsum ID: N`, written by Lorem Picsum when it served the image.
   `exiftool -Comment web/static/demos/kitchen.jpg` prints it; so does
   `grep -a 'Picsum ID' web/static/demos/kitchen.jpg`.
2. **Lorem Picsum says who took it.** `curl -s https://picsum.photos/id/1060/info`
   returns `{"id":"1060","author":"Karl Fredrickson", …,"url":"https://unsplash.com/photos/TYIzeCiZ_60", …}`.
   The four rows above are that endpoint's `author` and `url` fields, retrieved
   2026-08-04, one request per ID.
3. **The Unsplash page is the primary record.** Lorem Picsum is a re-server; the
   photo page it points at is the first-party one. `unsplash.com` returns 401 to
   command-line clients, so this step is a browser step and the maintainer's, not
   a script's.

## What the studio asserts about these photographs

Each image ships with a baked envelope under [`envelopes/`](./envelopes) — a
scene graph a vision-language model produced from it once, frozen and never
regenerated, which is what makes a demo click cost nothing. Those graphs are
**model output about a photograph**, not statements the photographer made and
not statements this project verified: `docs/vson.md` §2.1 says what a green
validation establishes, and it is never that the document describes the image.

## The rule going forward

An entry in `manifest.json` must carry `credit`, `license` and `source_url`.
[`web/tests/demo-credits.test.ts`](../../tests/demo-credits.test.ts) fails
`pnpm test` — which CI runs before the build — on any entry that omits one, on
any entry whose image is absent, on a `CREDITS.md` or `NOTICE` that does not
cover every entry, and on the strings `CC0` or `public domain` wherever a licence
is named. An uncredited image cannot reach a deploy.
