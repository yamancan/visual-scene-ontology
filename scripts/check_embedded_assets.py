#!/usr/bin/env python3
"""Keep the files embedded in the `vson` binary a mirror, not a fork.

The release binary carries the ontology, the shapes, the Python package the
Python-backed subcommands run, and `routing-tables.json`, so that a binary
copied out of a checkout still works (`cli/src/commands/embed.rs`). `include_str!`
may not reach outside the crate root — a path that escapes it compiles inside a
checkout but fails the isolated verify build `cargo package` runs — so the crate
keeps a byte-identical mirror under `cli/assets/`.

A mirror is only worth having while it is still a mirror. This gate establishes
five things, and the middle three are the ones a person cannot hold in their
head:

  1. **Byte equality.** Every mirrored file equals the repository original,
     byte for byte. Edit `shapes/vson-shapes.ttl` and forget the mirror, and the
     binary would validate against last month's shapes while CI — which runs
     from the checkout — stays green.
  2. **Import closure.** Every `tools.…` and `vson.…` module the embedded
     Python imports is itself embedded. One new `from tools.canon import …`
     inside `smatch.py` is enough to break `vson diff` for everyone outside a
     checkout, and no test that runs from the checkout can see it.
  3. **Resource closure.** Every file the embedded Python *reads* rather than
     imports is embedded too. `vson/_resources.py` resolves the two `SKILL.md`
     bodies, the two repair templates, the envelope schema and `pyproject.toml`
     out of the tree the package lives in, and no import statement mentions any
     of them — so nothing above would notice their absence, and `vson mcp`
     would fail on the first line of `vson/repair.py`.
  4. **Path coverage.** Every repository-relative path `cli/src/` names — each
     `PyGate::script`, each `python_bridge` probe, each `mcp` probe, each
     ontology and shapes file `validate` reads — is embedded. This is what makes
     a *new* Python-backed subcommand fail here instead of in a user's terminal.
  5. **No orphans.** Every file under `cli/assets/` is listed in `ASSETS`. An
     unlisted mirror is a file nobody updates and the binary never carries.

The manifest is read out of `cli/src/commands/embed.rs`, so this gate and the
binary cannot disagree about what is embedded.

Exit codes
----------
  0  the mirror is current, closed under imports and reads, and covers every
     named path.
  1  it has drifted; every difference is printed.

Usage
-----
  python3 scripts/check_embedded_assets.py
  python3 scripts/check_embedded_assets.py --sync   # refresh cli/assets/ then re-check
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EMBED_RS = "cli/src/commands/embed.rs"
CRATE = "cli"
MIRROR = "cli/assets"

# `("<path under the materialized home>", include_str!("<path from embed.rs>"))`,
# tolerant of the line breaks rustfmt inserts once an entry passes 100 columns.
ENTRY = re.compile(
    r"\(\s*\"([^\"]+)\"\s*,\s*include_str!\(\s*\"([^\"]+)\"\s*,?\s*\)\s*,?\s*\)",
    re.S,
)

# Repository-relative paths named as string literals anywhere in cli/src/. The
# four prefixes are the only trees the binary reads out of a home.
NAMED_PATH = re.compile(
    r"\"((?:tools|ontology|shapes|vson)/[A-Za-z0-9_./-]+\.(?:py|ttl|json))\""
)

# The packages whose modules must be embedded when embedded Python imports them.
# `tools` is the reference implementation the spawned modules live in; `vson` is
# the client library `vson mcp` runs as a server.
EMBEDDED_PACKAGES = ("tools", "vson")

# `read_text("skills", "vson-extractor", "SKILL.md")` and its `read_json` twin,
# in `vson/_resources.py`'s call convention: one string literal per path
# segment. Only all-literal calls are resolvable, which is the whole set today
# and is asserted below — a computed path would silently pass this gate, so a
# call this cannot resolve is reported rather than skipped.
RESOURCE_READERS = ("read_text", "read_json")


def read(path: str) -> str:
    with open(os.path.join(REPO, path), encoding="utf-8") as fh:
        return fh.read()


def manifest() -> "list[tuple[str, str]]":
    """`(home-relative path, repo-relative path of the included file)` pairs.

    The second element is resolved from `embed.rs`'s own directory, exactly as
    `include_str!` resolves it.
    """
    src = read(EMBED_RS)
    start = src.index("pub const ASSETS")
    body = src[start : src.index("];", start)]
    here = os.path.dirname(EMBED_RS)
    return [
        (rel, os.path.normpath(os.path.join(here, inc)).replace(os.sep, "/"))
        for rel, inc in ENTRY.findall(body)
    ]


def original(rel: str, included: str) -> str:
    """The repository file a mirrored asset must equal, byte for byte.

    An asset included from under `cli/assets/` is a mirror, and the file it
    mirrors is the one at the same home-relative path in the repository root.
    Anything included from elsewhere in the crate — `routing-tables.json` —
    already lives there and is its own original, so it returns itself and the
    byte comparison is skipped.
    """
    return rel if included.startswith(MIRROR + "/") else included


def sync(pairs: "list[tuple[str, str]]") -> "list[str]":
    copied = []
    for rel, included in pairs:
        src = original(rel, included)
        if src == included:
            continue
        dst = os.path.join(REPO, included)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(REPO, src), dst)
        copied.append(f"{src} -> {included}")
    return copied


def mirrored_files() -> "list[str]":
    out = []
    for dirpath, _dirs, names in os.walk(os.path.join(REPO, MIRROR)):
        for name in names:
            full = os.path.join(dirpath, name)
            out.append(os.path.relpath(full, REPO).replace(os.sep, "/"))
    return sorted(out)


def module_files(module: str) -> "list[str]":
    """The file(s) `import <module>` would load, as home-relative paths."""
    stem = module.replace(".", "/")
    return [f"{stem}.py", f"{stem}/__init__.py"]


def read_resources(rel: str, tree: ast.AST) -> "tuple[list[str], list[str]]":
    """`(resolved home-relative paths, unresolvable call sites)`.

    Reads `read_text(...)` / `read_json(...)` calls whose arguments are all
    string literals and joins the segments the way `vson/_resources.py` does.
    A call with a non-literal argument is returned in the second list rather
    than dropped: this gate cannot follow it, and a resource the gate cannot
    follow is a resource that can go missing from the binary unnoticed. The one
    exception is a splat — `read_text(*parts)`, which is how `read_json`
    forwards to `read_text` inside `_resources.py` itself. A splat carries no
    path of its own; the literals it will receive are at the call sites, which
    this gate reads anyway.
    """
    paths: "list[str]" = []
    unresolved: "list[str]" = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name not in RESOURCE_READERS or not node.args:
            continue
        if any(isinstance(a, ast.Starred) for a in node.args):
            continue
        segments = [
            a.value
            for a in node.args
            if isinstance(a, ast.Constant) and isinstance(a.value, str)
        ]
        if len(segments) != len(node.args) or node.keywords:
            unresolved.append(f"{rel}:{node.lineno} {name}(…) is not all literals")
            continue
        paths.append("/".join(segments))
    return paths, unresolved


def imported_modules(rel: str, tree: ast.AST) -> "tuple[set[str], set[str]]":
    """The `tools.…` and `vson.…` modules one embedded Python file imports.

    Two sets, because `from X import Y` cannot be read off the syntax alone:
    `X` is certainly a module (strict), while `Y` may be a submodule or an
    ordinary function (lenient — required only if `X` itself is not embedded,
    which would make `Y` unreachable either way). Relative imports resolve
    against the file's own package.
    """
    package = os.path.dirname(rel).replace("/", ".")
    strict: "set[str]" = set()
    lenient: "set[str]" = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            strict.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                module = ".".join(parts[: len(parts) - node.level + 1])
                if node.module:
                    module = f"{module}.{node.module}"
            else:
                module = node.module or ""
            strict.add(module)
            lenient.update(f"{module}.{alias.name}" for alias in node.names)
    def is_embedded_package(module: str) -> bool:
        return any(
            module == pkg or module.startswith(pkg + ".")
            for pkg in EMBEDDED_PACKAGES
        )

    return (
        {m for m in strict if is_embedded_package(m)},
        {m for m in lenient if is_embedded_package(m)},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sync",
        action="store_true",
        help="refresh cli/assets/ from the repository originals, then re-check",
    )
    args = parser.parse_args()

    pairs = manifest()
    print(f"embed-check: {len(pairs)} asset(s) declared in {EMBED_RS}")

    if args.sync:
        for line in sync(pairs):
            print(f"  synced {line}")

    failures: "list[str]" = []
    embedded = {rel for rel, _ in pairs}

    # 1. byte equality with the repository original
    for rel, included in pairs:
        src = original(rel, included)
        if not os.path.exists(os.path.join(REPO, included)):
            failures.append(f"{included} is included by {EMBED_RS} but does not exist")
            continue
        if src == included:
            continue
        if not os.path.exists(os.path.join(REPO, src)):
            failures.append(f"{src} does not exist, but {included} mirrors it")
            continue
        with open(os.path.join(REPO, src), "rb") as a, open(os.path.join(REPO, included), "rb") as b:
            if a.read() != b.read():
                failures.append(f"{included} has drifted from {src} (run --sync)")

    # 2/3. every module an embedded module imports, and every file one reads
    for rel, included in pairs:
        if not rel.endswith(".py"):
            continue
        tree = ast.parse(read(included), filename=rel)
        strict, lenient = imported_modules(rel, tree)
        for module in sorted(strict):
            if not any(c in embedded for c in module_files(module)):
                failures.append(f"{rel} imports {module}, which is not embedded")
        for module in sorted(lenient):
            parent = module.rsplit(".", 1)[0]
            resolves = any(c in embedded for c in module_files(module))
            if not resolves and not any(c in embedded for c in module_files(parent)):
                failures.append(f"{rel} imports {module}, which is not embedded")
        resources, unresolved = read_resources(rel, tree)
        for path in sorted(set(resources)):
            if path not in embedded:
                failures.append(f"{rel} reads {path}, which is not embedded")
        failures.extend(unresolved)

    # 4. every repo-relative path cli/src/ names is embedded
    for dirpath, _dirs, names in os.walk(os.path.join(REPO, CRATE, "src")):
        for name in sorted(names):
            if not name.endswith(".rs"):
                continue
            rs = os.path.relpath(os.path.join(dirpath, name), REPO).replace(os.sep, "/")
            for path in sorted(set(NAMED_PATH.findall(read(rs)))):
                if path not in embedded:
                    failures.append(f"{rs} names {path}, which is not embedded")

    # 5. no orphan under the mirror
    included_paths = {included for _, included in pairs}
    for path in mirrored_files():
        if path not in included_paths:
            failures.append(f"{path} is mirrored but not listed in ASSETS")

    if failures:
        print("\nembed-check: FAIL")
        for line in failures:
            print(f"  - {line}")
        print(
            "\nThe binary carries these files so it works outside a checkout.\n"
            "Refresh the mirror with `python3 scripts/check_embedded_assets.py --sync`,\n"
            "or add the missing entry to ASSETS in " + EMBED_RS + "."
        )
        return 1

    total = sum(os.path.getsize(os.path.join(REPO, inc)) for _, inc in pairs)
    print(f"  OK {len(pairs)} asset(s), {total // 1024} KiB, mirror byte-identical and closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
