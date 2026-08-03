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

**This resolves paths in the checkout, not package data.** `pyproject.toml` says
why in its `[tool.setuptools.package-data]` comment: `setuptools` cannot reach
outside a package directory, so a non-editable `pip install .` cannot carry
`cli/src/penman/routing-tables.json` either — and `tools/penman/vson_penman.py`
has read that from the checkout since v1.0. Every gate in this repository
installs editable (`make deps` and CI both run `pip install -e .`), which keeps
these paths live. Nothing here makes the non-editable install work; it does not
make it worse.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from .errors import VsonResourceError

# vson/_resources.py -> vson/ -> the checkout root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def path_to(*parts: str) -> str:
    """An absolute path to a repository-relative file. No existence check."""
    return os.path.join(REPO_ROOT, *parts)


def read_text(*parts: str) -> str:
    """The UTF-8 text of a repository-relative file, or `VsonResourceError`."""
    target = path_to(*parts)
    try:
        with open(target, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise VsonResourceError(
            "vson: cannot read {}: {}. This package resolves the canonical "
            "skills/, prompt and schema files out of the checkout it lives in; "
            "install it editable (pip install -e .) from a full checkout."
            .format(target, exc.strerror or exc)
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
