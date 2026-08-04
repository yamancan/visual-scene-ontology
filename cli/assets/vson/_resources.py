"""Where the canonical text and schema this package exposes are read from.

`SKILL_PROMPT`, `SKILL_X_PROMPT`, the two repair templates and
`ENVELOPE_SCHEMA` are not restated here — they are read, at import time, from
the very files the rest of the repository ships:

    skills/vson-extractor/SKILL.md            SKILL_PROMPT
    skills/vson-extractor-x/SKILL.md          SKILL_X_PROMPT
    tools/extractor/prompts/specialized/*.md  the repair templates
    tools/schema/vson-output.schema.json      ENVELOPE_SCHEMA

That is the same single-sourcing `web/src/lib/prompts/bodies.ts` gets from its
Vite `?raw` imports of the same four paths: edit the file and the next import
ships it, rename one and this module fails loudly in the same checkout. A
constant retyped here would be a fifth copy of a string this repository already
spells in four places, and the copy-drift gates (`make fragment-check`,
`make registry-check`) exist because that is exactly how this project has drifted
before.

**Checkout first, then the installed layout.** `tools.resource` is the single
resolver both packages share, and it is deliberately not re-implemented here:
`tools/*.py` read the ontology, the shapes and the routing tables through it
too, and one resolver is the only way those two sets of paths cannot disagree
about where a wheel put them. It tries the checkout — which is also the tree an
editable install and the release binary's materialized home present — and falls
back to `tools/_data/`, where a non-editable `pip install` carries every file
that lives outside a package directory in the source tree. `pyproject.toml`'s
`[tool.setuptools.package-dir]` is the build-time half of that arrangement.

Importing `tools` from here is the sanctioned direction: this package is a
facade over `tools` and `pyproject.toml` ships the two together for exactly
that reason, so a `vson` that can import at all can import `tools`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from tools import resource

from .errors import VsonResourceError


def path_to(*parts: str) -> str:
    """An absolute path to a repository-relative file. No existence check."""
    return resource(*parts)


def read_text(*parts: str) -> str:
    """The UTF-8 text of a repository-relative file, or `VsonResourceError`."""
    target = path_to(*parts)
    try:
        with open(target, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise VsonResourceError(
            "vson: cannot read {}: {}. This package resolves the canonical "
            "skills/, prompt and schema files out of the tree it lives in — a "
            "checkout, or the data an installed vson-tools carries under "
            "tools/_data/. Neither has this file, so the install is incomplete: "
            "reinstall vson-tools, or install it editable (pip install -e .) "
            "from a full checkout.".format(target, exc.strerror or exc)
        ) from exc


def read_json(*parts: str) -> Dict[str, Any]:
    """A repository-relative JSON document, parsed."""
    text = read_text(*parts)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise VsonResourceError(
            "vson: {} is not valid JSON: {}".format(path_to(*parts), exc)
        ) from exc


# The `version` line of pyproject.toml's `[project]` table. Anchored to that
# table so a version pinned inside a dependency specifier can never match.
_PROJECT_VERSION = re.compile(
    r"^\[project\]$.*?^version\s*=\s*[\"']([^\"']+)[\"']",
    re.MULTILINE | re.DOTALL,
)


def project_version() -> str:
    """The distribution version, read from `pyproject.toml` in the checkout.

    The checkout is the source of truth here for the same reason it is for the
    skills and the schema: an installed distribution's metadata is a *copy*, and
    a stale editable install would otherwise let `vson.__version__` disagree with
    the `pyproject.toml` a reader is looking at. `importlib.metadata` is the
    fallback for the case where there is no checkout to read.
    """
    try:
        text = read_text("pyproject.toml")
    except VsonResourceError:
        text = ""
    match = _PROJECT_VERSION.search(text)
    if match:
        return match.group(1)
    try:
        from importlib.metadata import version

        return version("vson-tools")
    except Exception as exc:  # pragma: no cover — no checkout and no metadata
        raise VsonResourceError(
            "vson: cannot determine the package version — neither {} nor "
            "installed distribution metadata for 'vson-tools' is readable"
            .format(path_to("pyproject.toml"))
        ) from exc
