#!/usr/bin/env python3
"""The gates, the transpilers, the renderers and the skill as MCP tools.

    $ vson mcp                 # the CLI subcommand, which runs the line below
    $ python3 -m vson.mcp      # the same server, no Rust binary in the path

VSON's whole loop is *emit, reject, repair*: a model writes a scene, a
validator rejects it with the exact `sh:message` that fired, the model rewrites
it. Until now that loop lived in a studio worker and in
`vson.validate_and_repair`, both of which need someone to write the plumbing.
An agent already has the plumbing — a Model Context Protocol server is a tool
call — so this module is the loop with the plumbing removed, plus the one tool
that closes it *before* the first rejection: `vson_skill_prompt` hands the
agent the closed vocabulary to write against, instead of letting it guess and
be told no.

Four tools, and each of them is `vson/api.py` behind a JSON envelope:

    vson_validate       the three gates of docs/vson.md §2, structured (§5.16)
    vson_convert        p2t / x2t transpilation to VSON-T
    vson_export         caption / fol / cypher renderings
    vson_skill_prompt   skills/vson-extractor{,-x}/SKILL.md, verbatim

Nothing here re-implements anything: every tool lands in `vson.api`, which
lands in `tools/`, which is what `make check` runs. If a tool and the CLI ever
disagree, `docs/vson.md` and the CLI are right.

Why the protocol is hand-rolled
-------------------------------
This server speaks JSON-RPC 2.0 over newline-delimited JSON on stdin/stdout —
the MCP stdio transport — implemented here in the standard library, and it adds
no dependency to this distribution. The official `mcp` Python SDK was
considered and not taken; the reason is stated as a rule about this repository
rather than as a claim about that package, because that package could not be
resolved from the machine where this choice was made and an unverified
characterisation of someone else's release would be worth nothing:

* This distribution has **four** runtime dependencies, each pinned to a range
  and each justified in `pyproject.toml` by a gate that needs it. The
  transpilers under `tools/penman` and `tools/vson_x` are pure standard library
  by policy, so that installing `vson-tools` to *read or write* VSON pulls in
  no machinery.
* `requires-python` is `>=3.9`, because 3.9 is the maintainer's system Python
  and every line under `tools/`, `scripts/`, `tests/` and `vson/` is written to
  it. An external protocol library would set that floor from outside.
* The surface a stdio tool server needs is a handshake, `tools/list`,
  `tools/call` and five JSON-RPC error codes. It is the file you are reading.

So the honest form of the decision is: a dependency here would have to be worth
more than the code below, and the code below is small enough that it is not. If
that stops being true — an MCP revision that adds framing, negotiation or auth
this cannot follow — the SDK is the answer and this module is the thing to
delete.

What it costs is stated plainly: this is the *tools* surface and the handshake,
and nothing else. There are no resources, no prompts, no sampling, no roots, no
completion, no logging, no progress and no subscriptions, and the server
declares none of those capabilities. A client that needs them needs a different
server.

Protocol revisions
------------------
`PROTOCOL_VERSIONS` lists the revisions this server implements the above subset
of. `initialize` echoes the client's requested revision when it is one of them,
and otherwise answers with the newest — which is what a client is told to
expect when it asks for something the server does not have. Revision-specific
behaviour is confined to two places:

* **Batches.** JSON-RPC batching was introduced in 2025-03-26 and removed in
  2025-06-18. An array of messages is accepted on every revision — accepting
  one the newest revision would not send costs nothing and refusing one the
  middle revision requires would be a real incompatibility.
* **`structuredContent`.** `vson_validate` returns its verdict both as a text
  block of JSON and in `structuredContent`, which is the backwards-compatible
  form the newer revisions ask for: a client that predates the field ignores
  it, a client that knows it gets the object without re-parsing. No
  `outputSchema` is declared, because declaring one is a promise to match it on
  every revision this server also answers, including the two that have no such
  field.

What no tool here does
----------------------
No tool reads an image, opens a socket, calls a model, or consults an API key.
`vson_validate` returning `conforms: true` says the document is well-formed
under the shapes, the ontology and the closed vocabulary — docs/vson.md §2.1,
which is unchanged by the verdict having arrived through a tool call.

`path` arguments are read with the privileges of this process, from the
filesystem it is running on, and are resolved against `$VSON_MCP_CWD` when the
`vson mcp` subcommand sets it and the working directory otherwise. This is a
local stdio server started by its own user, the same trust boundary
`vson validate` has always had; it is not a service to expose to input from
anyone else.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from . import api
from ._resources import path_to, project_version
from .errors import VsonError
from .repair import SKILL_PROMPT, SKILL_X_PROMPT

#: The MCP revisions this server implements the handshake and tools surface of,
#: newest first. `initialize` echoes a requested revision that appears here.
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

#: What `initialize` answers when the client asks for a revision not above.
LATEST_PROTOCOL_VERSION = PROTOCOL_VERSIONS[0]

#: `serverInfo.name`. The same name the CLI is installed under.
SERVER_NAME = "vson"

# JSON-RPC 2.0 error codes. The last four are the ones this server can produce;
# -32000.. is the implementation-defined range and nothing here needs it.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

#: Shown to the agent once, at connect time, by clients that surface it. It
#: exists to make the first tool call the right one: a document written against
#: the skill is a document that usually passes, and a document written against
#: a guess is a repair loop.
INSTRUCTIONS = (
    "VSON is a closed-vocabulary notation for visual scenes. Call "
    "vson_skill_prompt FIRST and write the document against the vocabulary it "
    "gives you; then call vson_validate and, while it reports findings, "
    "rewrite the document from the sh:message text it returns. Validation "
    "checks the graph against the shapes, the ontology and the vocabulary. It "
    "reads no image, so a conforming document is not thereby a correct "
    "description of any picture."
)

#: The environment variable `cli/src/commands/mcp.rs` sets to the directory the
#: user ran `vson mcp` in, because the child is started in the repository home
#: instead so that `python3 -m` can import `vson` and `tools`.
CWD_ENV = "VSON_MCP_CWD"

#: Where to look for a `vson` binary for the one renderer that has no Python
#: implementation. `cli/src/commands/mcp.rs` sets it to its own path.
CLI_ENV = "VSON_CLI"


class ToolError(Exception):
    """A call that could not be made: bad arguments, an unreadable path, a
    document that will not parse, a renderer that is not reachable.

    Reported as a tool result with `isError` set rather than as a JSON-RPC
    error, which is the distinction MCP draws: a protocol error is invisible to
    the model, and every one of these is something the model can act on.

    **A failing verdict is not one of these.** A document that breaks a shape
    produces an ordinary result whose `conforms` is `false` — the same line
    `vson/errors.py` draws for the library.
    """


# ---------------------------------------------------------------------------
# The tool surface
# ---------------------------------------------------------------------------

_DOCUMENT_IN = {
    "document": {
        "type": "string",
        "description": (
            "The document text itself. Text that happens to name a file is "
            "still the text, so name a file with `path`. Give this or `path`."
        ),
    },
    "path": {
        "type": "string",
        "description": (
            "Path to a document — .ttl/.turtle (VSON-T), .vson (VSON-P) or "
            ".x.vson (VSON-X). Relative paths resolve against the directory "
            "the server was started in. Give this or `document`."
        ),
    },
}

_SYNTAX_IN = {
    "syntax": {
        "type": "string",
        "enum": list(api.SYNTAXES),
        "description": (
            "Force the surface syntax: t = VSON-T (Turtle-star), p = VSON-P "
            "(Penman), x = VSON-X (compact). Read off the extension for a "
            "path, and off the first non-comment token for text, when omitted."
        ),
    },
}


def _schema(properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    """An input schema in the shape `tools/list` publishes them."""
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


VALIDATE_DESCRIPTION = (
    "Run the three VSON conformance gates over one document and return the "
    "verdict as structured records. The gates are SHACL over the shapes, then "
    "OWL 2 RL disjointness, then C2 vocabulary closure (docs/vson.md §2), and "
    "they stop at the first that fails, so every finding comes from the one "
    "gate the result names. Each finding carries the message a repair should "
    "be written from — for SHACL that is the sh:message text — plus the named "
    "shape, the focus node, the result path and the severity. A "
    "non-conformant document is a normal result with conforms=false, not an "
    "error. NOTE: no image is read. conforms=true says the document is "
    "well-formed under the shapes, the ontology and the closed vocabulary; it "
    "is never evidence that the document describes a picture."
)

CONVERT_DESCRIPTION = (
    "Transpile a VSON document to VSON-T (Turtle-star, docs/vson.md §4.1) and "
    "return the Turtle text. p2t reads VSON-P, the Penman authoring syntax "
    "(§4.2); x2t reads VSON-X, the compact syntax (§4.3). The reverse "
    "directions do not exist: back-conversion from the graph to an authoring "
    "surface is deferred (§6.1), so there is no t2p and no t2x here or in the "
    "CLI."
)

EXPORT_DESCRIPTION = (
    "Render a VSON document into another surface and return the text. "
    "caption = a deterministic English caption for an image-generation model, "
    "template-driven with no model in the loop (§7). fol = Prolog-style "
    "first-order-logic facts, with reified Events, Processes, Statives and "
    "SpatialFacts collapsed back into n-ary predicates. cypher = Neo4j CREATE "
    "statements; that renderer exists only in the Rust CLI, so this tool "
    "shells out to a `vson` binary for it and reads VSON-P input only. The "
    "input is settled before the binary is looked for: input that is not "
    "VSON-P comes back as that error whether or not a binary is reachable, "
    "and input the renderer would read comes back naming the missing binary "
    "when there is none. caption and fol accept all three syntaxes and need "
    "no binary."
)

SKILL_DESCRIPTION = (
    "Return the canonical VSON extractor skill document, verbatim: "
    "skills/vson-extractor/SKILL.md for notation=p (Penman, the default) or "
    "skills/vson-extractor-x/SKILL.md for notation=x (the compact syntax). "
    "Read it BEFORE writing a VSON document. It carries the closed value "
    "vocabularies, the required trait bundles and the clauses a document is "
    "validated against, which is what makes a first attempt likely to pass "
    "vson_validate instead of entering a repair loop. It is the same text the "
    "studio sends as its system prompt and that vson.SKILL_PROMPT holds."
)

#: Every tool this server publishes, in the order `tools/list` returns them.
TOOLS: Tuple[Dict[str, Any], ...] = (
    {
        "name": "vson_validate",
        "description": VALIDATE_DESCRIPTION,
        "inputSchema": _schema(
            dict(
                _DOCUMENT_IN,
                **_SYNTAX_IN,
                **{
                    "profile": {
                        "type": "string",
                        "enum": ["strict", "relaxed"],
                        "description": (
                            "Which shapes file decides. strict (the default) "
                            "is the one that decides conformance; relaxed "
                            "names a shipped shapes file that no CLI command "
                            "selects, and a relaxed verdict is not a "
                            "conformance verdict (§6.1)."
                        ),
                    }
                }
            ),
            [],
        ),
    },
    {
        "name": "vson_convert",
        "description": CONVERT_DESCRIPTION,
        "inputSchema": _schema(
            dict(
                _DOCUMENT_IN,
                **{
                    "direction": {
                        "type": "string",
                        "enum": ["p2t", "x2t"],
                        "description": (
                            "p2t = VSON-P to VSON-T, x2t = VSON-X to VSON-T."
                        ),
                    }
                }
            ),
            ["direction"],
        ),
    },
    {
        "name": "vson_export",
        "description": EXPORT_DESCRIPTION,
        "inputSchema": _schema(
            dict(
                _DOCUMENT_IN,
                **_SYNTAX_IN,
                **{
                    "format": {
                        "type": "string",
                        "enum": ["caption", "fol", "cypher"],
                        "description": "Which rendering to return.",
                    }
                }
            ),
            ["format"],
        ),
    },
    {
        "name": "vson_skill_prompt",
        "description": SKILL_DESCRIPTION,
        "inputSchema": _schema(
            {
                "notation": {
                    "type": "string",
                    "enum": ["p", "x"],
                    "description": (
                        "p = VSON-P (Penman), the default; x = VSON-X."
                    ),
                }
            },
            [],
        ),
    },
)


# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------


def _string(arguments: Dict[str, Any], name: str) -> Optional[str]:
    value = arguments.get(name)
    if value is None or isinstance(value, str):
        return value
    raise ToolError(
        "`{}` must be a string, got {}".format(name, type(value).__name__)
    )


def _choice(
    arguments: Dict[str, Any], name: str, allowed: Tuple[str, ...], default: str
) -> str:
    value = _string(arguments, name)
    if value is None:
        return default
    if value not in allowed:
        raise ToolError(
            "`{}` must be one of {}, got {!r}".format(
                name, ", ".join(allowed), value
            )
        )
    return value


def base_directory() -> str:
    """Where a relative `path` argument is resolved from.

    `$VSON_MCP_CWD` when the CLI subcommand set it — it starts this server in
    the repository home so `python3 -m` can import the packages, which would
    otherwise silently re-root every relative path the user types — and the
    working directory when nothing set it.
    """
    return os.environ.get(CWD_ENV) or os.getcwd()


class _Input(NamedTuple):
    """One call's document argument, resolved — and *which* argument it was.

    `path` is the resolved file when the caller gave `path`, and `None` when
    the caller gave `document`. That field is the whole point of this record:
    the only honest answer to "was this a file?" is the one the caller gave,
    and re-deriving it downstream with `os.path.isfile` would make a
    `document` of `"scene.vson"` — a plausible thing for a model to write —
    silently mean whatever file the server process is standing next to.

    `text` is what the library is handed: the resolved path for a `path`, the
    document text for a `document`. `label` is what an error calls the input.
    """

    text: str
    syntax: Optional[str]
    label: str
    path: Optional[str]

    @property
    def is_path(self) -> bool:
        """What `vson/api.py` is told, so that it guesses nothing either.

        Its input convention is `os.path.isfile` when nobody says otherwise,
        which is the same re-derivation one layer down: without this, a
        `document` reading `scene.vson` reaches `api.validate` as a string that
        names a file, and the verdict comes back about that file.
        """
        return self.path is not None


def _document(arguments: Dict[str, Any]) -> _Input:
    """The `_Input` one call's arguments name.

    Exactly one of `document` and `path`. Naming the two separately is what
    removes the ambiguity from a surface a model is driving, and the record
    returned here carries that answer everywhere the input goes: to `_read` and
    `_penman_source` in this module, and through `is_path` into `vson/api.py`,
    whose own input convention would otherwise re-derive it from the filesystem
    this process happens to stand in.
    """
    document = _string(arguments, "document")
    path = _string(arguments, "path")
    if (document is None) == (path is None):
        raise ToolError(
            "exactly one of `document` (the text) or `path` (a file) is "
            "required; got {}".format(
                "both" if document is not None else "neither"
            )
        )
    syntax = _string(arguments, "syntax")
    if syntax is not None and syntax not in api.SYNTAXES:
        raise ToolError(
            "`syntax` must be one of {}, got {!r}".format(
                ", ".join(api.SYNTAXES), syntax
            )
        )
    if path is not None:
        resolved = os.path.join(base_directory(), os.path.expanduser(path))
        if not os.path.isfile(resolved):
            raise ToolError("no such file: {}".format(resolved))
        return _Input(resolved, syntax, path, resolved)
    return _Input(document, syntax, "<document>", None)


# ---------------------------------------------------------------------------
# The tools
#
# **One order of complaint, for all three document tools.** A call can be wrong
# in several ways at once, and which wrongness it is told about is a contract,
# not an accident of the order somebody wrote the lines in. The rule is:
#
#   1. the declared arguments — an enum given a value its schema does not list;
#   2. the document — a `path` that is no file, a text that will not parse;
#   3. the environment — a `vson` binary for `export cypher`, and nothing else.
#
# Cheapest first, and most certainly the caller's own first: a bad enum is
# wrong on any machine, a missing binary is wrong on this one. A caller who
# fixes what it was told about and calls again meets the next problem, one per
# round, in the same order whichever of the three tools it went to.
# ---------------------------------------------------------------------------


def call_validate(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """`vson.validate`, plus the profile the caller asked for.

    The record is the one `python3 -m tools.validate_report` prints —
    `vson-validate-records/1`, docs/vson.md §5.16.6 — with `profile` added.
    Adding a field is explicitly not a break of that format, and leaving the
    profile out of a report that a `profile` argument can change would be the
    one field a reader cannot recover.
    """
    profile = _choice(arguments, "profile", ("strict", "relaxed"), "strict")
    given = _document(arguments)
    shapes = (
        api.DEFAULT_SHAPES
        if profile == "strict"
        else path_to("shapes", "vson-shapes-relaxed.ttl")
    )
    try:
        verdict = api.validate(
            given.text,
            syntax=given.syntax,
            shapes=shapes,
            label=given.label,
            is_path=given.is_path,
        )
    except VsonError as exc:
        raise ToolError(str(exc))
    record = verdict.as_record()
    record["profile"] = profile
    return record


def call_convert(arguments: Dict[str, Any]) -> str:
    direction = _choice(arguments, "direction", ("p2t", "x2t"), "")
    if not direction:
        raise ToolError("`direction` is required: p2t or x2t")
    body = _read(_document(arguments))
    try:
        return api.to_turtle(body) if direction == "p2t" else api.from_x(body)
    except VsonError as exc:
        raise ToolError(str(exc))


def call_export(arguments: Dict[str, Any]) -> str:
    fmt = _choice(arguments, "format", ("caption", "fol", "cypher"), "")
    if not fmt:
        raise ToolError("`format` is required: caption, fol or cypher")
    given = _document(arguments)
    if fmt == "cypher":
        return _cypher(given)
    render = api.caption if fmt == "caption" else api.fol
    try:
        return render(given.text, syntax=given.syntax, is_path=given.is_path)
    except VsonError as exc:
        raise ToolError(str(exc))


def call_skill_prompt(arguments: Dict[str, Any]) -> str:
    notation = _choice(arguments, "notation", ("p", "x"), "p")
    return SKILL_PROMPT if notation == "p" else SKILL_X_PROMPT


CALLS = {
    "vson_validate": call_validate,
    "vson_convert": call_convert,
    "vson_export": call_export,
    "vson_skill_prompt": call_skill_prompt,
}


def _read(given: _Input) -> str:
    """The document text — off disk when, and only when, `path` was given."""
    if given.path is None:
        return given.text
    try:
        with open(given.path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise ToolError("{}: {}".format(given.path, exc.strerror or exc))


# ---------------------------------------------------------------------------
# Cypher — the one renderer with no Python implementation
# ---------------------------------------------------------------------------


def cli_binary() -> Optional[str]:
    """A `vson` binary to run `export cypher` with, or `None`.

    In order: `$VSON_CLI`, which `cli/src/commands/mcp.rs` sets to its own
    path, so `vson mcp` always has one; a `vson` on `PATH`; the release and
    debug builds inside a checkout. Nothing is downloaded and nothing is built.
    """
    given = os.environ.get(CLI_ENV)
    if given and os.path.isfile(given) and os.access(given, os.X_OK):
        return given
    found = shutil.which(SERVER_NAME)
    if found:
        return found
    for build in ("release", "debug"):
        candidate = api.path_to("cli", "target", build, SERVER_NAME)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _cypher(given: _Input) -> str:
    """`vson export cypher`, run as a child process.

    Not re-implemented here. The Cypher mapping has exactly one implementation
    — `cli/src/commands/export_cypher.rs`, over the Penman AST — and a second
    one in Python would be a copy this repository has no gate to keep honest.
    Two consequences are passed through rather than papered over: the renderer
    reads VSON-P only, because a native Turtle parser is not shipped in the
    crate; and where there is no binary there is no Cypher.
    """
    # Input first, environment second — the rule stated above the tools, and
    # here it is also the tool's published contract (EXPORT_DESCRIPTION). What
    # `_penman_source` settles is which syntax the input *presents* as: an
    # explicit `syntax` argument, or a `.vson` name, or a leading `(`. It is
    # not a parse and does not claim to be one, so `syntax="p"` over nonsense,
    # or a document that begins `(((`, passes here and is rejected further
    # down — by the missing-binary error when there is no binary, and by the
    # renderer's own parser when there is one.
    source = _penman_source(given)
    binary = cli_binary()
    if binary is None:
        raise ToolError(
            "no `vson` binary is reachable, and Cypher is the one rendering "
            "with no Python implementation: it lives in the Rust CLI "
            "(cli/src/commands/export_cypher.rs) and this server shells out "
            "to it rather than keeping a second copy. Build it with "
            "`cargo build --release` in cli/, put `vson` on PATH, or set "
            "${} to it. `caption` and `fol` need none of that.".format(CLI_ENV)
        )
    # `source is None` says the caller gave text, not a file — the same answer
    # `_penman_source` read off `given.path`, and the binary takes a path.
    staged = None
    if source is None:
        staged = source = _staged_penman(given.text)
    try:
        try:
            # `--` before the path: clap ends option parsing there, so the
            # argument is a filename whatever it starts with. Nothing here
            # produces a leading dash today — a `path` is joined against the
            # base directory, a staged file is absolute — but that is a
            # property of two other functions, and this is the call that would
            # pay for it changing.
            done = subprocess.run(
                [binary, "export", "cypher", "--", source],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except OSError as exc:
            raise ToolError("cannot run {}: {}".format(binary, exc))
        except subprocess.TimeoutExpired:
            raise ToolError("`{} export cypher` did not finish".format(binary))
    finally:
        if staged is not None:
            _discard(staged)
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace").strip()
        raise ToolError(
            "`{} export cypher` exited {}: {}".format(
                binary, done.returncode, detail or "(no stderr)"
            )
        )
    return done.stdout.decode("utf-8")


def _staged_penman(body: str) -> str:
    """A `.vson` file holding `body`, for a caller who gave text not a path.

    The binary takes a path, so text has to become a file, and both halves of
    becoming one can fail in ways the caller can act on: a lone surrogate that
    survived `json.loads` is a `str` that cannot be encoded as UTF-8, and a
    full or read-only temp directory cannot hold what does encode. Neither is
    left to arrive as an opaque JSON-RPC internal error, and neither leaves the
    half-written file behind.
    """
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".vson", encoding="utf-8", delete=False
        )
    except OSError as exc:
        raise ToolError(
            "cannot open a temporary file to hand the Cypher renderer, which "
            "reads a path and not a stream: {}. Pass `path` instead of "
            "`document` to skip this step.".format(exc)
        )
    try:
        # `close()` is inside the guard because a text file flushes there:
        # ENOSPC and an unencodable character can both surface at either call.
        try:
            handle.write(body)
        finally:
            handle.close()
    except (OSError, UnicodeError) as exc:
        _discard(handle.name)
        raise ToolError(
            "cannot write the document to {}, the temporary file the Cypher "
            "renderer is handed: {}: {}. Pass `path` instead of `document` to "
            "skip this step.".format(handle.name, type(exc).__name__, exc)
        )
    return handle.name


def _discard(path: str) -> None:
    """Remove a file this server staged, and never fail for it.

    A temp file that will not unlink is a leaked temp file; raising here would
    replace whatever the caller actually asked about with that.
    """
    try:
        os.unlink(path)
    except OSError:
        pass


def _penman_source(given: _Input) -> Optional[str]:
    """The VSON-P file to hand the binary, `None` for "the caller gave text".

    Raises when the input is not VSON-P at all, which is the honest answer:
    the Cypher renderer parses Penman, and there is no t2p to reach it from a
    graph (§6.1).
    """
    actual = given.syntax
    if actual is None:
        actual = (
            _syntax_of(given.path) if given.path else api.sniff(given.text)
        )
    if actual != "p":
        raise ToolError(
            "`export cypher` reads VSON-P (Penman) only, and {} is VSON-{}. "
            "The renderer parses Penman, and no back-conversion from the "
            "graph to an authoring syntax is shipped (§6.1). Use `caption` or "
            "`fol`, which read all three syntaxes.".format(
                given.label, actual.upper()
            )
        )
    return given.path


def _syntax_of(path: str) -> str:
    """The syntax a filename declares — and nothing when it declares none.

    An unrecognised extension is not evidence of anything, so it is not turned
    into a guess: guessing `t` here would answer a `.txt` file full of Penman
    with a confident sentence about VSON-T and advice that cannot work. The
    recognised set is the one `_DOCUMENT_IN` publishes and `vson/api.py` reads.
    """
    lower = path.lower()
    if lower.endswith(".x.vson"):
        return "x"
    if lower.endswith(".vson"):
        return "p"
    if lower.endswith((".ttl", ".turtle")):
        return "t"
    raise ToolError(
        "{}: the extension {} names no VSON syntax, and this server does not "
        "guess one. Recognised: .vson (VSON-P), .x.vson (VSON-X), .ttl and "
        ".turtle (VSON-T). Pass `syntax` to say which one this file is.".format(
            path, os.path.splitext(path)[1] or "(none)"
        )
    )


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------


def negotiate(requested: Any) -> str:
    """The revision to answer `initialize` with.

    The client's, when it is one this server implements; otherwise the newest
    one it does — which is what tells a client that cannot live with the
    difference to disconnect, instead of leaving it to find out on a call.
    """
    if isinstance(requested, str) and requested in PROTOCOL_VERSIONS:
        return requested
    return LATEST_PROTOCOL_VERSION


def _result(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _text_content(body: str) -> List[Dict[str, Any]]:
    return [{"type": "text", "text": body}]


class _Rejected(Exception):
    """A JSON-RPC error, raised where the code that knows about it runs.

    The counterpart of `ToolError`, and the line between them is the one MCP
    draws: this is a protocol failure the model never sees, `ToolError` is a
    result the model is meant to read and act on.
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Server:
    """One connection's worth of MCP, over two byte streams.

    Held as an object for exactly one reason: `initialize` is a handshake, and
    a handshake has state — the negotiated revision, and whether it happened at
    all. Everything else is a function of its arguments.
    """

    def __init__(self, stdin: Any, stdout: Any) -> None:
        self.stdin = stdin
        self.stdout = stdout
        self.protocol_version: Optional[str] = None
        self.initialized = False

    # -- the loop ----------------------------------------------------------

    def serve(self) -> int:
        """Read messages until the stream closes. Returns an exit code.

        A closed stdin is how an MCP client shuts a stdio server down, so it is
        a normal exit and not an error.
        """
        while True:
            line = self.stdin.readline()
            if not line:
                return 0
            reply = self.handle_line(line)
            if reply is not None:
                self.write(reply)

    def write(self, payload: Any) -> None:
        """One message, one line, flushed.

        `json.dumps` escapes every newline inside a string, so a message can
        never contain the byte that ends it — which is what makes the framing
        of this transport safe without a length header.
        """
        self.stdout.write(json.dumps(payload).encode("utf-8") + b"\n")
        self.stdout.flush()

    def handle_line(self, line: bytes) -> Optional[Any]:
        """One line in, one reply out — or `None` for "say nothing"."""
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            return _error(None, PARSE_ERROR, "not UTF-8: {}".format(exc))
        if not text.strip():
            return None
        try:
            message = json.loads(text)
        except ValueError as exc:
            return _error(None, PARSE_ERROR, "not JSON: {}".format(exc))
        return self.handle(message)

    def handle(self, message: Any) -> Optional[Any]:
        """One decoded message — or a batch of them — in."""
        if isinstance(message, list):
            if not message:
                return _error(None, INVALID_REQUEST, "empty batch")
            replies = [
                reply
                for reply in (self.dispatch(one) for one in message)
                if reply is not None
            ]
            return replies or None
        return self.dispatch(message)

    # -- one message -------------------------------------------------------

    def dispatch(self, message: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(message, dict):
            return _error(None, INVALID_REQUEST, "not a JSON-RPC object")
        request_id = message.get("id")
        method = message.get("method")
        if not isinstance(method, str):
            return _error(request_id, INVALID_REQUEST, "no `method`")
        params = message.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return _error(request_id, INVALID_PARAMS, "`params` is not an object")

        # A notification carries no id and is answered with silence, including
        # when it is a method this server does not know: replying to one is a
        # protocol violation, not a courtesy.
        notification = "id" not in message
        if notification:
            self.notify(method, params)
            return None

        try:
            return _result(request_id, self.request(method, params))
        except _Rejected as rejected:
            return _error(request_id, rejected.code, rejected.message)
        except Exception as exc:  # a bug here is a reply, not a dead server
            return _error(
                request_id,
                INTERNAL_ERROR,
                "{}: {}".format(type(exc).__name__, exc),
            )

    def notify(self, method: str, params: Dict[str, Any]) -> None:
        if method == "notifications/initialized":
            self.initialized = True

    def request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if method == "initialize":
            return self.initialize(params)
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [dict(tool) for tool in TOOLS]}
        if method == "tools/call":
            return self.call(params)
        raise _Rejected(METHOD_NOT_FOUND, "unknown method: {}".format(method))

    def initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.protocol_version = negotiate(params.get("protocolVersion"))
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": SERVER_NAME,
                "version": project_version(),
            },
            "instructions": INSTRUCTIONS,
        }

    def call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or name not in CALLS:
            raise _Rejected(
                INVALID_PARAMS,
                "unknown tool: {!r}. Known: {}".format(
                    name, ", ".join(sorted(CALLS))
                ),
            )
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise _Rejected(INVALID_PARAMS, "`arguments` is not an object")

        try:
            produced = CALLS[name](arguments)
        except ToolError as exc:
            return {"content": _text_content(str(exc)), "isError": True}
        except VsonError as exc:  # a document failure that escaped a wrapper
            return {"content": _text_content(str(exc)), "isError": True}

        if isinstance(produced, str):
            return {"content": _text_content(produced), "isError": False}
        body = json.dumps(produced, indent=2, sort_keys=False)
        return {
            "content": _text_content(body),
            "structuredContent": produced,
            "isError": False,
        }


def main(argv: Optional[List[str]] = None) -> int:
    """`python3 -m vson.mcp`. No flags: an MCP server's interface is stdio."""
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("-h", "--help"):
        sys.stderr.write(
            "vson.mcp — the VSON MCP server, JSON-RPC 2.0 over stdio.\n"
            "Tools: {}.\n"
            "Protocol revisions: {}.\n"
            "It takes no arguments: an MCP client speaks to it on stdin and "
            "stdout.\n".format(
                ", ".join(tool["name"] for tool in TOOLS),
                ", ".join(PROTOCOL_VERSIONS),
            )
        )
        return 0
    if argv:
        sys.stderr.write(
            "vson.mcp takes no arguments (got {}); it speaks MCP on stdio.\n"
            .format(" ".join(argv))
        )
        return 2
    return Server(sys.stdin.buffer, sys.stdout.buffer).serve()


if __name__ == "__main__":
    sys.exit(main())
