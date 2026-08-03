"""VSON for Python — one import, a stable surface, and no re-implementations.

    import vson

    verdict = vson.validate("examples/throne_room.vson")
    print(verdict.conforms, verdict.gate, verdict.messages)

Why this package exists, and what it is not
-------------------------------------------
Everything VSON can do already existed under `tools/`, as the reference
implementations `docs/vson.md` §10 lists and the gate matrix runs. What did not
exist was a **surface**: a consumer had to import `tools.validate_report`,
`tools.penman.vson_penman`, `tools.vson_x`, `tools.render.fol`,
`tools.metrics.smatch` and `tools.canon` by their internal paths, read a JSON
record to get a verdict, and catch whatever `rdflib` and `pyshacl` happened to
raise. Every one of those paths is an implementation detail this repository
reserves the right to move.

So this package is a **facade over `tools/`, not a promotion of it.** `tools/`
stays exactly where the Makefile, the CI workflow, `scripts/`, the Pyodide
worker and §10 already point at it — renaming 22 modules to gain an import path
would have broken every one of those for no verification benefit. What `vson`
adds is a name a consumer can depend on, typed results in place of dicts, one
input convention across every call, and three exceptions of its own. What it
adds nothing of is behaviour: `validate` runs the same three gates in the same
order as `vson validate`, and if the two ever disagree, the CLI and §2 are
right.

The surface
-----------
Reading and verifying (`vson.api`):

    validate(text_or_path) -> Verdict     the three gates, structured (§5.16)
    Verdict, Finding                      the verdict and its records
    to_turtle(penman) -> str              VSON-P -> VSON-T   (p2t, §4.2)
    from_x(vson_x) -> str                 VSON-X -> VSON-T   (x2t, §4.3)
    turtle_of / load / sniff              the same reading, at other depths
    caption(...) -> str                   graph -> English, no model (§7)
    fol(...) -> str                       graph -> predicate logic
    diff(a, b) -> DiffReport              triple-level agreement (§5.15)
    canon / canonical_hash / denotes_same canonical form, the §4.6 test

The envelope (`vson.envelope`):

    ENVELOPE_SCHEMA                       tools/schema/vson-output.schema.json
    Envelope + Source, SceneGraph, GraphNode, GraphEdge,
              Conformance, Violation, Extraction, Traits
    envelope_errors(document) -> [str]    schema verdict for any parsed envelope
    response_format / tool_schema / ollama_format
                                          the schema in three vendors' wrappers

The loop (`vson.repair`):

    validate_and_repair(chat_fn, image_or_doc) -> RepairResult
    ChatTurn, ChatFn, RepairRound, RepairResult
    SKILL_PROMPT, SKILL_X_PROMPT          the canonical skills/ bodies
    REPAIR_PROMPT_TEMPLATE, REPAIR_X_PROMPT_TEMPLATE
    MAX_REPAIR_RETRIES, SHACL_REPORT_SLICE_CHARS
    extract_penman, extract_vson_x, looks_like_penman, build_repair_prompt

Errors: `VsonError`, `VsonSyntaxError`, `VsonResourceError`.

What none of it establishes
---------------------------
No function in this package reads an image. A `Verdict` with `conforms=True`
says the document is well-formed under the shapes, the ontology and the
vocabulary — §2.1, unchanged and unweakened by the fact that it is now one
function call away.
"""

from __future__ import annotations

from ._resources import project_version
from .api import (
    DEFAULT_SHAPES,
    SYNTAXES,
    Finding,
    Verdict,
    canon,
    canonical_hash,
    caption,
    denotes_same,
    diff,
    fol,
    from_x,
    load,
    sniff,
    to_turtle,
    turtle_of,
    validate,
)
from .envelope import (
    ENVELOPE_SCHEMA,
    ENVELOPE_VERSIONS,
    LATEST_ENVELOPE_VERSION,
    Conformance,
    Envelope,
    Extraction,
    GraphEdge,
    GraphNode,
    SceneGraph,
    Source,
    Traits,
    Violation,
    envelope_errors,
    ollama_format,
    response_format,
    tool_schema,
)
from .errors import VsonError, VsonResourceError, VsonSyntaxError
from .repair import (
    EXTRACT_USER,
    EXTRACT_USER_X,
    MAX_REPAIR_RETRIES,
    PROMPT_VERSIONS,
    REPAIR_PROMPT_TEMPLATE,
    REPAIR_X_PROMPT_TEMPLATE,
    SHACL_REPORT_SLICE_CHARS,
    SKILL_PROMPT,
    SKILL_X_PROMPT,
    ChatFn,
    ChatTurn,
    RepairResult,
    RepairRound,
    build_repair_prompt,
    extract_penman,
    extract_vson_x,
    looks_like_penman,
    validate_and_repair,
)

#: The `vson-tools` distribution version, read from `pyproject.toml`.
__version__ = project_version()

#: The graph-agreement report `diff` returns — `tools.metrics.smatch.Report`,
#: named here so a caller can annotate against it without importing `tools`.
#: Aliased lazily by `__getattr__` below: naming it eagerly would pull the
#: metric (and `rdflib`) into every `import vson`, and most callers never diff.

__all__ = [
    "__version__",
    # errors
    "VsonError",
    "VsonSyntaxError",
    "VsonResourceError",
    # reading and verifying
    "validate",
    "Verdict",
    "Finding",
    "to_turtle",
    "from_x",
    "turtle_of",
    "load",
    "sniff",
    "caption",
    "fol",
    "diff",
    "DiffReport",
    "canon",
    "canonical_hash",
    "denotes_same",
    "DEFAULT_SHAPES",
    "SYNTAXES",
    # the envelope
    "ENVELOPE_SCHEMA",
    "ENVELOPE_VERSIONS",
    "LATEST_ENVELOPE_VERSION",
    "Envelope",
    "Source",
    "SceneGraph",
    "GraphNode",
    "GraphEdge",
    "Traits",
    "Conformance",
    "Violation",
    "Extraction",
    "envelope_errors",
    "response_format",
    "tool_schema",
    "ollama_format",
    # the repair loop
    "validate_and_repair",
    "ChatFn",
    "ChatTurn",
    "RepairRound",
    "RepairResult",
    "SKILL_PROMPT",
    "SKILL_X_PROMPT",
    "REPAIR_PROMPT_TEMPLATE",
    "REPAIR_X_PROMPT_TEMPLATE",
    "EXTRACT_USER",
    "EXTRACT_USER_X",
    "PROMPT_VERSIONS",
    "MAX_REPAIR_RETRIES",
    "SHACL_REPORT_SLICE_CHARS",
    "build_repair_prompt",
    "extract_penman",
    "extract_vson_x",
    "looks_like_penman",
]


def __getattr__(name: str):
    """`DiffReport`, resolved on first use (PEP 562).

    It is `tools.metrics.smatch.Report`, and importing that module costs the
    whole metric — colour refinement, the hill-climbing search, `rdflib`. A
    caller who only validates should not pay for it at `import vson`.
    """
    if name == "DiffReport":
        from tools.metrics.smatch import Report

        globals()["DiffReport"] = Report
        return Report
    raise AttributeError("module 'vson' has no attribute {!r}".format(name))
