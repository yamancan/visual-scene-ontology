# Contributing

## Heads up: `*.md` is gitignored

`.gitignore` blocks `*.md` repo-wide. This is deliberate. If you add a new
markdown file, `git status` will not show it and `git add` will refuse it.

To ship a markdown file that genuinely has to be in the repo, add an explicit
negation next to the existing ones in `.gitignore`:

```gitignore
!path/to/your-file.md
```

Then confirm with `git check-ignore path/to/your-file.md` — no output (exit 1)
means it is now trackable. The negation must name the exact path; directory
globs will not resurrect a file that `*.md` already matched.

## Prerequisites

CI is the source of truth for versions (`.github/workflows/ci.yml`):

- **Python 3.9+** — `make deps` installs the pinned dependencies
  (`pip install --user -e ".[dev]"`, ranges live in `pyproject.toml`). The `dev`
  extra is `lark`, which `make grammar-check` generates its parsers with; the
  runtime dependencies stay free of it. CI tests 3.11.
- **Rust** (stable toolchain) for the `cli/` crate.
- **pnpm 10** and **Node 22** for `web/`.

## Verification gates

Run these before opening a pull request. CI runs the same set.

```bash
make check           # ontology parse, Penman→Turtle round-trip, SHACL, OWL RL, ruff lint, unittests, spec gallery, executable grammars, conformance suite
make cli-check       # Rust build + tests + graph-isomorphism parity against the Python reference
make x-check         # VSON-X round-trip parity
make x-skill-check   # VSON-X skill conformance over examples/gallery-x
make envelope-check  # every committed studio envelope must SHACL-conform
```

`make check-all` runs all five in one go.

For the web studio:

```bash
cd web
pnpm install --frozen-lockfile
pnpm check   # svelte-check
pnpm lint    # prettier --check + eslint
pnpm test    # vitest
pnpm build
```

## Changes that need extra care

- **Ontology / shapes** (`ontology/`, `shapes/`): any change must keep
  `make check` green, including the OWL 2 RL disjointness pass. A **new named
  shape needs a negative entry** in `tests/conformance/manifest.ttl` — a
  document that trips it, with the source shape, focus node, path and severity
  pinned. `make conformance` fails on a shape that has neither an entry nor a
  stated exemption, because the coverage table `docs/vson.md` §2.2 publishes is
  generated from that manifest and must not claim what the suite lacks.
- **Conformance suite** (`tests/conformance/`): the manifest is maintained by
  hand and there is no `--freeze`. A pinned expectation that moves is a question
  to answer — which of the document, the shape or the engine changed — not a
  fixture to rewrite. After adding or removing an entry, regenerate §2.2's table
  with `python3 -m tools.conformance_runner --coverage-table` and paste it
  between the `conformance-coverage` markers.
- **Parser or emitter changes**: the Rust CLI and the Python reference must emit
  isomorphic graphs — `make cli-check` checks this with `rdflib.to_isomorphic`
  over `throne_room` plus the gallery. Change both or neither.
- **Grammar changes**: `docs/vson.md` Appendix B and Appendix D are the source.
  `tools/grammar/` carries no copy of a production, so edit the spec and run
  `make grammar-check`; `make grammar-gbnf` regenerates the committed GBNF after
  a deliberate change, and is never the fix for a red gate (`docs/vson.md`
  §D.10).
- **Spec changes**: update `docs/vson.md` (the canonical spec — see its
  precedence clause in section 2) and add an entry to `spec/CHANGELOG.md` in
  the same change. `spec/vson-spec-v1.md` is a superseded historical record.

## Commit style

- English only.
- Code and config only. No `.md` files, no notes, no scratch output, no
  unrelated formatting churn in the same commit.
- Conventional-commit prefixes matching the existing history (`feat`, `fix`,
  `refactor`, `docs`, `ci`, `style`, `lint`), scoped where it helps:
  `fix(cli): ...`.
- One logical change per commit.

## Reporting bugs

Open an issue with the input that reproduces it — a `.vson`, `.x.vson`, or
`.ttl` snippet is worth more than a description. For security issues, see
[SECURITY.md](SECURITY.md) instead.
