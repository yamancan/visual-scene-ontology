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
  (`pip install --user -e .`, ranges live in `pyproject.toml`). CI tests 3.11.
- **Rust** (stable toolchain) for the `cli/` crate.
- **pnpm 10** and **Node 22** for `web/`.

## Verification gates

Run these before opening a pull request. CI runs the same set.

```bash
make check           # ontology parse, Penman→Turtle round-trip, SHACL, OWL RL, ruff lint, unittests, spec gallery
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
  `make check` green, including the OWL 2 RL disjointness pass.
- **Parser or emitter changes**: the Rust CLI and the Python reference must emit
  isomorphic graphs — `make cli-check` checks this with `rdflib.to_isomorphic`
  over `throne_room` plus the gallery. Change both or neither.
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
