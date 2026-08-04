<!--
One person reviews these, so the checklist is not ceremony: it is the set of
things that would otherwise be found by the reviewer running your branch, one
at a time, over several days. A box you cannot tick honestly is fine — say so
under "Anything you could not tick" and the review starts from there.
-->

## What this changes

<!-- One paragraph. What the tree does after this that it did not do before. -->

## Why

<!-- The problem, not the patch. If it fixes an issue, link it. -->

## How it was verified

<!-- The command you ran and what it printed. "Tests pass" is not a receipt;
     `make check` with its output is. -->

```
```

## Checklist

- [ ] **`make check` is green** on this branch, and I ran it after the last commit rather than before it.
- [ ] The gates for what I touched are green too: `make cli-check` (Rust or `cli/assets/`), `make x-check` and `make x-skill-check` (VSON-X), `make envelope-check` (studio envelopes), `make iri-check`, `make site` (publish surface), and `cd web && pnpm check && pnpm lint && pnpm test && pnpm build` (anything under `web/`).
- [ ] **No `.md` in a code commit.** Documentation moves in its own commit with a `docs:` prefix — see [CONTRIBUTING.md](../CONTRIBUTING.md). A new Markdown file also needs an explicit negation in `.gitignore`, because `*.md` is ignored repo-wide.
- [ ] **No baked envelope bytes were edited or regenerated.** The corpus under `web/static/` is frozen: `make envelope-check` proves the committed bytes still conform, and re-baking them would replace the evidence rather than check it. Withdrawing a file is a separate, deliberate change with its own reason in the commit message.
- [ ] **Every number I wrote is one the tree computes.** `make check` runs the counts gate; if it told me a claim had drifted, I changed the claim rather than the pattern that caught it.
- [ ] **A new named shape has a negative conformance entry** (`tests/conformance/manifest.ttl`), or a stated exemption — `make conformance` fails without one.
- [ ] **A mirrored file was re-synced**: `python3 scripts/check_embedded_assets.py --sync` after editing anything under `ontology/`, `shapes/`, `tools/` or `vson/`, with both copies committed.
- [ ] Commits are English, conventional-prefixed, and one logical change each.

## Anything you could not tick

<!-- Unticked boxes with reasons are more useful than ticked boxes without.
     A gate you could not run — no Rust toolchain, no pnpm — belongs here. -->
