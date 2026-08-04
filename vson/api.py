"""The stable calls: read a document, get a verdict, get a rendering.

Every function here is a thin, named front for a reference implementation that
already exists under `tools/`. Nothing is re-implemented — `validate()` runs
`tools.validate_report.report_for`, the same three gates in the same order that
`vson validate` runs (docs/vson.md §2, §5.16); `to_turtle` is
`tools.penman.vson_penman.to_turtle`; `diff` is `tools.metrics.smatch.compare`;
`canon` is `tools.canon`. What this module adds is a surface a consumer can
depend on: one import path, one input convention, typed results, and three
exceptions instead of whatever the dependencies raise.

Input convention
----------------
Every entry point takes `text_or_path` and accepts either:

  * a path to `.ttl`/`.turtle` (VSON-T), `.vson` (VSON-P) or `.x.vson`
    (VSON-X) — dispatched by `tools.metrics.smatch.parse_graph`, which
    docs/vson.md §4.6 and §5.15 both already defer to for "the materialized
    VSON-T graph";
  * the document text itself.

A value is treated as a path when `os.path.isfile` says so, and as text
otherwise; `syntax=` overrides the guess in either direction.

**`is_path=` settles that first guess, and a caller who already knows the answer
should pass it.** `True` reads the argument as a path, `False` reads it as the
document text whatever it looks like, and the default `None` keeps the
convention above. Guessing is a convenience for a person naming their own files;
for a program relaying input from somewhere else it is a hazard, because
`os.path.isfile` answers about the directory *this process* stands in — so a
document whose entire text is `scene.vson`, which is a plausible thing for a
language model to emit, would otherwise be read as whatever file happens to sit
beside the caller. `vson/mcp.py` names its two arguments `document` and `path`
and passes that answer down here rather than letting it be re-derived.

`validate`, `load`, `turtle_of`, `caption` and `fol` take it. `diff`,
`denotes_same`, `canon` and `canonical_hash` do not: a caller that needs it
there resolves with `load(..., is_path=...)` first and hands the graph to
`tools.canon` or `tools.metrics.smatch`, which is what `load` is the escape
hatch for.

**Sniffing text follows §5.16.5, with one documented extension.** §5.16.5 fixes
how `vson validate -` decides the syntax of a stream: the first token that is
neither whitespace nor a comment, `(` for VSON-P and anything else for VSON-T.
This module adds `~` for VSON-X (§4.3), which that clause does not admit,
because the CLI's `-` does not accept VSON-X at all and a VSON-X document is not
valid Turtle — reading one as VSON-T yields a parse error, never a different
verdict. Pass `syntax="t"` to get the CLI's exact behaviour.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .errors import VsonSyntaxError
from ._resources import path_to

# The strict profile. docs/vson.md §5.16.6: only `strict` decides C3 and
# therefore conformance, and the relaxed shapes file ships but no shipped
# command selects it.
DEFAULT_SHAPES = path_to("shapes", "vson-shapes.ttl")

# The three surface syntaxes, by the letters this package names them with.
SYNTAXES = ("t", "p", "x")


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One violation, with the fields docs/vson.md §5.16.1 lists.

    `location` is not among them. §5.16.3 is explicit that a position may only
    be reported when it was *established*, and establishing one needs the
    Penman source and its variable positions — which `cli/src/commands/
    sourcemap.rs` has and this package does not. A null field would be honest;
    an absent field is honester, and a caller that wants line numbers wants the
    CLI's `--format json`.
    """

    gate: str
    rule: str
    severity: str
    message: str
    shape: Optional[str] = None
    constraint: Optional[str] = None
    focus_node: Optional[str] = None
    result_path: Optional[str] = None
    value: Optional[str] = None

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "Finding":
        """One record as `tools.validate_report` emits it."""
        return cls(
            gate=record["gate"],
            rule=record["rule"],
            severity=record["severity"],
            message=record["message"],
            shape=record.get("shape"),
            constraint=record.get("constraint"),
            focus_node=record.get("focus_node"),
            result_path=record.get("result_path"),
            value=record.get("value"),
        )

    def as_record(self) -> Dict[str, Any]:
        """Back to the record shape, in §5.16.1's field order."""
        return {
            "gate": self.gate,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "shape": self.shape,
            "constraint": self.constraint,
            "focus_node": self.focus_node,
            "result_path": self.result_path,
            "value": self.value,
        }


@dataclass
class Verdict:
    """What the three gates decided about one document.

    `conforms` is the verdict; `gate` names the first gate that failed, or is
    `None`; `findings` are that gate's findings and only that gate's, because
    the gates short-circuit in §2's order and at most one of them ever speaks.
    A conformant document produces a `Verdict` with an empty `findings` list —
    §5.16 requires a clean run to still produce a report, so that a caller can
    tell "nothing was wrong" from "the tool never ran".

    What it establishes is what §2.1 says a verdict establishes and nothing
    further: no image is read anywhere in this package, so `conforms=True`
    is never evidence that the document describes a picture.
    """

    conforms: bool
    gate: Optional[str]
    findings: List[Finding] = field(default_factory=list)
    source: str = "<text>"
    #: The record-format identifier this verdict was built from (§5.16.6).
    report: str = "vson-validate-records/1"

    @property
    def messages(self) -> List[str]:
        """The finding messages, in the order the findings are in.

        For a SHACL failure these are the `sh:message` strings — the text the
        repair loop feeds back to the model.
        """
        return [f.message for f in self.findings]

    def report_text(self) -> str:
        """The findings as one block of text, for a prompt or a log.

        This is *not* `pyshacl`'s own text rendering, which is what the studio
        puts in its repair prompt (`web/src/lib/extract/orchestrator.ts`). It is
        the same violations rendered from the structured records instead, one
        per line, in the order §5.16.1 freezes — so it is stable across runs,
        and it is not byte-identical to the studio's and is not claimed to be.
        """
        lines = []
        for found in self.findings:
            where = found.focus_node or found.value or ""
            path = " {}".format(found.result_path) if found.result_path else ""
            lines.append(
                "{} [{}]{}{}".format(
                    found.message,
                    found.rule,
                    " on <{}>".format(where) if where else "",
                    path,
                )
            )
        return "\n".join(lines)

    def as_record(self) -> Dict[str, Any]:
        """The document `python3 -m tools.validate_report` prints."""
        return {
            "report": self.report,
            "path": self.source,
            "conforms": self.conforms,
            "gate": self.gate,
            "findings": [f.as_record() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Reading a document
# ---------------------------------------------------------------------------


def _is_path(value: str) -> bool:
    try:
        return os.path.isfile(value)
    except (OSError, ValueError):  # embedded NUL, absurd length — it is text
        return False


def _syntax_of_path(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".x.vson"):
        return "x"
    if lower.endswith(".vson"):
        return "p"
    if lower.endswith((".ttl", ".turtle")):
        return "t"
    raise VsonSyntaxError(
        "{}: unknown syntax. Expected .ttl / .turtle (VSON-T), .vson (VSON-P) "
        "or .x.vson (VSON-X).".format(path)
    )


def sniff(text: str) -> str:
    """The syntax of a document given as text — `"t"`, `"p"` or `"x"`.

    docs/vson.md §5.16.5 plus the `~` extension this module's docstring
    records. Empty input is VSON-T, which parses to a graph of no triples
    rather than to a parse error nobody asked for.
    """
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char == "#":
            newline = text.find("\n", index)
            if newline < 0:
                return "t"
            index = newline + 1
            continue
        if char == "(":
            return "p"
        if char == "~":
            return "x"
        return "t"
    return "t"


@dataclass(frozen=True)
class _Document:
    """One input, resolved: its VSON-T text, what to call it, where it was."""

    turtle: str
    label: str
    syntax: str
    path: Optional[str] = None


def _resolve(
    text_or_path: str,
    syntax: Optional[str] = None,
    label: Optional[str] = None,
    is_path: Optional[bool] = None,
) -> _Document:
    if not isinstance(text_or_path, str):
        raise TypeError(
            "expected a document or a path to one, got {}".format(
                type(text_or_path).__name__
            )
        )
    if syntax is not None and syntax not in SYNTAXES:
        raise ValueError(
            "syntax must be one of {}, got {!r}".format(SYNTAXES, syntax)
        )

    # The caller's answer when there is one; `os.path.isfile` only when there
    # is not. A `False` here is the difference between reading the document a
    # caller sent and reading a file it merely named.
    if is_path is None:
        is_path = _is_path(text_or_path)
    path = text_or_path if is_path else None
    if path is not None:
        actual = syntax or _syntax_of_path(path)
        try:
            with open(path, encoding="utf-8") as handle:
                body = handle.read()
        except OSError as exc:
            raise VsonSyntaxError(
                "{}: {}".format(path, exc.strerror or exc)
            ) from exc
    else:
        actual = syntax or sniff(text_or_path)
        body = text_or_path

    turtle = body if actual == "t" else _transpile(body, actual)
    return _Document(
        turtle=turtle,
        label=label or path or "<text>",
        syntax=actual,
        path=path if actual == "t" else None,
    )


def _transpile(body: str, syntax: str) -> str:
    return to_turtle(body) if syntax == "p" else from_x(body)


def _materialize(document: _Document):
    """A resolved document's graph — or the honest reason it has none.

    Every parse this module performs goes through here, so that "this is not
    Turtle" reaches a caller as `VsonSyntaxError` under the document's own
    label, rather than as whatever `rdflib` raised wherever the text was read.
    """
    import rdflib

    graph = rdflib.Graph()
    try:
        graph.parse(data=document.turtle, format="turtle")
    except Exception as exc:
        raise VsonSyntaxError(
            "{}: VSON-T parse error: {}: {}".format(
                document.label, type(exc).__name__, exc
            )
        ) from exc
    return graph


def to_turtle(penman: str) -> str:
    """VSON-P (Penman, §4.2) -> VSON-T (Turtle-star, §4.1). The `p2t` direction.

    `tools.penman.vson_penman.to_turtle`, which `vson convert p2t` and the Rust
    CLI's own transpiler are held byte-identical to by `make cli-check`.
    """
    from tools.penman import vson_penman

    try:
        return vson_penman.to_turtle(penman)
    except Exception as exc:
        raise VsonSyntaxError(
            "VSON-P parse error: {}: {}".format(type(exc).__name__, exc)
        ) from exc


def from_x(vson_x: str) -> str:
    """VSON-X (compact, §4.3) -> VSON-T. The `x2t` direction.

    `tools.vson_x.to_turtle`. There is no `t2x` and no `t2p`: back-conversion to
    an authoring surface is deferred (§6.1), which is why an envelope produced
    in VSON-X mode carries `vson_p = ""`.
    """
    from tools.vson_x import to_turtle as x_to_turtle

    try:
        return x_to_turtle(vson_x)
    except Exception as exc:
        raise VsonSyntaxError(
            "VSON-X parse error: {}: {}".format(type(exc).__name__, exc)
        ) from exc


def turtle_of(
    text_or_path: str,
    syntax: Optional[str] = None,
    is_path: Optional[bool] = None,
) -> str:
    """The VSON-T text of any input, transpiling if the surface is P or X."""
    return _resolve(text_or_path, syntax, is_path=is_path).turtle


def load(
    text_or_path: str,
    syntax: Optional[str] = None,
    is_path: Optional[bool] = None,
):
    """The materialized VSON-T graph of any input, as an `rdflib.Graph`.

    The escape hatch. Everything below is defined over this graph, and a caller
    who wants to SPARQL it, serialize it or hand it to `pyshacl` directly should
    take it from here rather than re-deriving it — including a caller who needs
    `is_path` on one of the calls that does not take it.
    """
    return _materialize(_resolve(text_or_path, syntax, is_path=is_path))


# ---------------------------------------------------------------------------
# The three gates
# ---------------------------------------------------------------------------


def _gates(document: _Document, path: str, shapes_path: str) -> Dict[str, Any]:
    """`tools.validate_report.report_for`, with the parse failure named as one.

    The gates read the document off disk and parse it themselves, three frames
    down, and `rdflib`'s parse error is not one of this package's three. Which
    is why the reparse below is on the failure path only: a document that will
    not parse is the caller's to fix and comes back as `VsonSyntaxError`, a gate
    that broke on a document that parses is this repository's and keeps its own
    traceback, and a conformant document pays nothing for the distinction.
    """
    from tools import validate_report

    try:
        return validate_report.report_for(path, shapes_path, document.label)
    except Exception:
        _materialize(document)
        raise


def validate(
    text_or_path: str,
    syntax: Optional[str] = None,
    shapes: Optional[str] = None,
    label: Optional[str] = None,
    is_path: Optional[bool] = None,
) -> Verdict:
    """Run the three gates over one document and return a structured verdict.

    SHACL over the strict profile, then OWL 2 RL disjointness, then C2
    vocabulary closure — §2's order, short-circuiting at the first that fails,
    which is why at most one gate is ever named in the result.

    `shapes` selects a shapes file. §5.16.6: a verifier asked for the relaxed
    profile **MUST** either validate against that file or refuse, never validate
    against the strict shapes and label the result relaxed — so pointing this at
    `shapes/vson-shapes-relaxed.ttl` really does validate against it, and the
    resulting verdict is not a conformance verdict (§6.1).

    `is_path` settles whether `text_or_path` is a file or the document itself,
    for a caller that already knows — see the module docstring.

    Reads no image. §2.1 governs what the answer establishes.
    """
    document = _resolve(text_or_path, syntax, label, is_path)
    shapes_path = shapes or DEFAULT_SHAPES

    if document.path is not None:
        record = _gates(document, document.path, shapes_path)
    else:
        # `report_for` reads a file, the same way the CLI hands it transpiled
        # Turtle in a temp file. Writing the *transpiled text* rather than a
        # re-serialization of a parsed graph keeps the bytes the gate sees the
        # bytes the transpiler produced.
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ttl", encoding="utf-8", delete=False
        )
        try:
            handle.write(document.turtle)
            handle.close()
            record = _gates(document, handle.name, shapes_path)
        finally:
            os.unlink(handle.name)

    return Verdict(
        conforms=record["conforms"],
        gate=record["gate"],
        findings=[Finding.from_record(f) for f in record["findings"]],
        source=record["path"],
        report=record["report"],
    )


# ---------------------------------------------------------------------------
# Renderings
# ---------------------------------------------------------------------------


def caption(
    text_or_path: str,
    syntax: Optional[str] = None,
    is_path: Optional[bool] = None,
) -> str:
    """Graph -> English, deterministically and with no model in the loop.

    `tools.render.caption.render` (v1.0.5, §7). The same renderer
    `vson export caption` runs.
    """
    from tools.render import render as render_caption

    return render_caption(load(text_or_path, syntax, is_path))


def fol(
    text_or_path: str,
    syntax: Optional[str] = None,
    is_path: Optional[bool] = None,
) -> str:
    """Graph -> Prolog-style first-order-logic facts.

    `tools.render.fol.render`, behind `vson export fol`. Reified Events,
    Processes, Statives and SpatialFacts are collapsed back into single n-ary
    facts, which is the point: §3.4's reification is how VSON writes n-ary
    relations in a binary-relation language, and this undoes the encoding.
    """
    from tools.render.fol import render as render_fol

    return render_fol(load(text_or_path, syntax, is_path))


# ---------------------------------------------------------------------------
# Agreement and canonical form
# ---------------------------------------------------------------------------


def diff(
    left: str,
    right: str,
    left_syntax: Optional[str] = None,
    right_syntax: Optional[str] = None,
    seed: Optional[int] = None,
    restarts: Optional[int] = None,
):
    """Triple-level agreement between two documents — `vson diff` (§5.15).

    Returns `tools.metrics.smatch.Report`: overall and per-layer precision,
    recall and F1 under the variable alignment that maximizes matched triples,
    plus `.identical` for "these two assert the same graph up to renaming".

    **It is agreement, not correctness.** F1 = 1.0 says the two documents say
    the same thing; two runs of one model agreeing on one hallucination score
    1.0 as well. No image is read.
    """
    from tools.metrics import smatch

    kwargs = {}
    if seed is not None:
        kwargs["seed"] = seed
    if restarts is not None:
        kwargs["restarts"] = restarts
    return smatch.compare(
        smatch.build_document(load(left, left_syntax), _name(left)),
        smatch.build_document(load(right, right_syntax), _name(right)),
        **kwargs
    )


def _name(text_or_path: str) -> str:
    return text_or_path if _is_path(text_or_path) else "<text>"


def canon(text_or_path: str, syntax: Optional[str] = None) -> str:
    """The canonical N-Quads form of a document — RDFC-1.0 (§4.6).

    `tools.canon.canonical_nquads`. Two documents denote the same scene exactly
    when these two strings are equal, which is what `denotes_same` is.
    """
    from tools import canon as canon_module

    return canon_module.canonical_nquads(load(text_or_path, syntax))


def canonical_hash(text_or_path: str, syntax: Optional[str] = None) -> str:
    """The SHA-256 of the canonical form — the frozen-corpus identifier."""
    from tools import canon as canon_module

    return canon_module.canonical_hash(load(text_or_path, syntax))


def denotes_same(
    left: str,
    right: str,
    left_syntax: Optional[str] = None,
    right_syntax: Optional[str] = None,
) -> bool:
    """The §4.6 test: do these two documents denote the same scene?

    True across syntaxes — the VSON-P and VSON-X forms of one scene canonicalize
    to the same bytes, which is what `tests/fixtures/canonical/` freezes.
    """
    from tools import canon as canon_module

    return canon_module.denotes_same(
        load(left, left_syntax), load(right, right_syntax)
    )
