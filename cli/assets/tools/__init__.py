"""Where the reference implementation reads its data files from.

The modules under `tools/` load four things they do not contain: the three
ontology files, the two shapes files, `cli/src/penman/routing-tables.json` and
the two `SKILL.md` bodies. Every one of those paths is anchored to `__file__`
rather than to the working directory, so it resolves the same under `python3 -m
tools.validate_report` from anywhere, under `unittest discover`, and under an
editable install.

Two trees satisfy those paths as written: a checkout, and the home the release
binary materializes (`cli/src/commands/embed.rs`, which extracts every embedded
asset at its repository-relative path). A non-editable `pip install` is the
third case and satisfies neither — setuptools cannot ship a file from outside a
package directory at its original path, so the wheel carries those trees under
`tools/_data/` instead, at the same repository-relative paths beneath it
(`pyproject.toml`'s `[tool.setuptools.package-dir]` is the mapping).

`resource()` is the only place that knows both layouts, and it tries the
checkout first — so for a contributor, for CI and for the release binary
nothing about resolution changes, and `tools/_data/` is a directory that only
ever exists inside a wheel.
"""

from __future__ import annotations

import os

_PACKAGE = os.path.dirname(os.path.abspath(__file__))

# The tree this package sits in: the checkout root, or the materialized home.
_ROOT = os.path.dirname(_PACKAGE)

# Where a non-editable install carries the same files.
_INSTALLED = os.path.join(_PACKAGE, "_data")


def resource(*parts: str) -> str:
    """An absolute path to a repository-relative data file.

    The checkout path wins whenever it exists, and is also what comes back when
    neither layout has the file — so a caller that goes on to open it raises an
    error naming the place a reader would look, not a `_data` path that exists
    in no checkout.
    """
    checkout = os.path.join(_ROOT, *parts)
    if os.path.exists(checkout):
        return checkout
    installed = os.path.join(_INSTALLED, *parts)
    if os.path.exists(installed):
        return installed
    return checkout
