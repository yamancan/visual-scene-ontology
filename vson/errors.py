"""The three exceptions this package raises, and the line between them.

A library that raises whatever its dependencies raise makes its caller import
`rdflib`, `pyshacl` and the transpilers to write an `except` clause. These three
are what `vson` promises instead, and the promise is narrow on purpose: every
failure that is *about a document* is a `VsonSyntaxError`, every failure that is
about *this checkout* is a `VsonResourceError`, and both are `VsonError`.

A failing **verdict** is none of them. `validate()` returns a `Verdict` whose
`conforms` is `False`; a document that breaks a shape is an answer, not an
error, and raising on it would make the normal case exceptional
(docs/vson.md §5.16).
"""

from __future__ import annotations


class VsonError(Exception):
    """Base class for everything this package raises on purpose."""


class VsonSyntaxError(VsonError):
    """A document could not be read as the syntax it was taken to be.

    Raised by `to_turtle`, `from_x` and anything built on them — including the
    repair loop, where "the chat function returned a reply with no document in
    it" lands here too: a reply that carries no document is a reply this
    package cannot parse.
    """


class VsonResourceError(VsonError):
    """A canonical file this package reads is missing or unreadable.

    The package resolves `skills/`, `tools/schema/` and `pyproject.toml` out of
    the tree it lives in — a checkout, or the `tools/_data/` a wheel carries
    (see `vson/_resources.py`). This is what a caller sees when neither has the
    file: an incomplete install, or a checkout with a file renamed out from
    under it.
    """
