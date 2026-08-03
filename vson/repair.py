"""The emit -> validate -> feed-the-violations-back loop, as a library call.

`extraction.shacl_retries` has been in the envelope schema since v1.0: "how many
SHACL repair rounds ran". Until now the only thing that could populate it was
the studio, because the loop lived in `web/src/lib/extract/orchestrator.ts`.
This module is that loop with the browser taken out of it, so a consumer with
their own model access can produce an envelope whose `shacl_retries` is a
measurement rather than a zero.

What it does and does not take
------------------------------
It takes a callable. `chat_fn(turn: ChatTurn) -> str` is the entire model
interface: this package imports no vendor SDK, reads no environment variable,
holds no API key, sets no timeout and retries nothing on the network. A turn
carries the system prompt, the user text, the round number, the reason this
round exists, and — on round 0 only — whatever the caller passed as
`image_or_doc`, untouched and uninspected. Bytes, a path, a base64 string, a
list of content blocks: this module never looks inside it, which is why it can
be any of those.

An exception from `chat_fn` propagates. The studio catches one and ships the
envelope it has, because a browser tab must render something; a library that
swallowed the caller's own exception would be hiding it.

The bounds are the studio's
---------------------------
`MAX_REPAIR_RETRIES = 2` and `SHACL_REPORT_SLICE_CHARS = 4000` are the values in
`web/src/lib/extract/limits.ts`, and they are mirrored rather than re-chosen:
`shacl_retries` in live envelopes has to stay on the same 0-2 ceiling as the
baked demo corpus, or the field stops being comparable across the envelopes this
project has already shipped. `tests/test_client_library.py` reads limits.ts and
fails if these drift from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, List, Optional

from . import api
from ._resources import read_text
from .api import Verdict
from .envelope import (
    LATEST_ENVELOPE_VERSION,
    Conformance,
    Envelope,
    Extraction,
    Source,
    Violation,
)
from .errors import VsonSyntaxError

# ---------------------------------------------------------------------------
# Canonical prompt text, read from the files that ship it
# ---------------------------------------------------------------------------

#: `skills/vson-extractor/SKILL.md` — the ~5 KB distilled VSON-P skill the
#: studio sends as its system prompt, whole file, exactly as
#: `web/src/lib/prompts/bodies.ts` inlines it with a Vite `?raw` import.
SKILL_PROMPT: str = read_text("skills", "vson-extractor", "SKILL.md")

#: `skills/vson-extractor-x/SKILL.md` — the VSON-X skill, same treatment.
SKILL_X_PROMPT: str = read_text("skills", "vson-extractor-x", "SKILL.md")

#: `tools/extractor/prompts/specialized/repair.md`, whole file. The markdown
#: wrapper is part of the prompt the studio sends, so it is part of this one.
REPAIR_PROMPT_TEMPLATE: str = read_text(
    "tools", "extractor", "prompts", "specialized", "repair.md"
)

#: `tools/extractor/prompts/specialized/repair-x.md`, whole file.
REPAIR_X_PROMPT_TEMPLATE: str = read_text(
    "tools", "extractor", "prompts", "specialized", "repair-x.md"
)

#: The bare user instruction for round 0, per notation. Mirrors
#: `BARE_EXTRACT_USER` / `BARE_EXTRACT_USER_X` in web/src/lib/prompts/meta.ts.
EXTRACT_USER = (
    "Emit the VSON-P document for this image. Output ONLY the Penman — "
    "start with `(`, end with `)`. No prose, no fences."
)
EXTRACT_USER_X = (
    "Emit the VSON-X document for this image. The first line MUST start with "
    "`~scene`. Output ONLY VSON-X — no prose, no fences, no Penman parens."
)

#: What `extraction.prompt_version` records for each notation. Mirrors
#: `promptVersionFor` in web/src/lib/prompts/meta.ts, so an envelope produced
#: here is comparable with the studio's on that field.
PROMPT_VERSIONS = {"p": "skill@1.0.0", "x": "skill-x@1.0.0"}

# ---------------------------------------------------------------------------
# Bounds — mirrored from web/src/lib/extract/limits.ts
# ---------------------------------------------------------------------------

#: Repair rounds after the initial emission. Two keeps `shacl_retries`
#: comparable with the baked corpus and caps the worst case at three model
#: calls per extraction.
MAX_REPAIR_RETRIES = 2

#: How much of a violation report a repair prompt carries. A pathological graph
#: can produce an unbounded report; 4000 characters shows every distinct
#: violation class without the prompt drowning in repetition.
SHACL_REPORT_SLICE_CHARS = 4000


# ---------------------------------------------------------------------------
# Tolerant document extraction — the studio's, ported
# ---------------------------------------------------------------------------


def extract_penman(text: str) -> Optional[str]:
    """The Penman tree in a model reply, or `None`.

    Forgiving in the one way models are unreliable: a fenced block is unwrapped
    even though the prompt says not to fence, then the slice from the first `(`
    to the last `)` is taken. This is `extractPenman` from
    `web/src/lib/extract/orchestrator.ts` in Python — the same rules, not a
    transliteration of its regexes.
    """
    body = _unfence(text).strip()
    start = body.find("(")
    end = body.rfind(")")
    if start < 0 or end <= start:
        return None
    return body[start : end + 1].strip()


def extract_vson_x(text: str) -> Optional[str]:
    """The VSON-X document in a model reply, or `None`.

    Line-anchored, because VSON-X is line-significant: the slice runs from the
    start of the first line whose first non-blank character is `~`, to the end,
    with the trailing newline kept. `extractVsonX` in Python.
    """
    body = _unfence(text)
    for line_start in _line_starts(body):
        index = line_start
        while index < len(body) and body[index] in " \t":
            index += 1
        if index < len(body) and body[index] == "~":
            slice_ = body[line_start:].rstrip()
            return slice_ + "\n" if slice_ else None
    return None


def looks_like_penman(text: str) -> bool:
    """True when a reply opens with `(` — the VSON-X drift tell."""
    return text.lstrip().startswith("(")


def _unfence(text: str) -> str:
    """The inside of the first ``` fence, or the text unchanged."""
    opening = text.find("```")
    if opening < 0:
        return text
    after = text.find("\n", opening)
    if after < 0:
        return text
    closing = text.find("```", after)
    if closing < 0:
        return text
    return text[after + 1 : closing].rstrip("\n")


def _line_starts(text: str) -> List[int]:
    starts = [0]
    index = text.find("\n")
    while index >= 0:
        starts.append(index + 1)
        index = text.find("\n", index + 1)
    return starts


def build_repair_prompt(document: str, reason: str, notation: str = "p") -> str:
    """Fill the repair template with the failed document and why it failed.

    The reason is sliced to `SHACL_REPORT_SLICE_CHARS`, which is the only thing
    this does beyond substitution — same two placeholders, same bound, same
    templates as `buildRepairPrompt` / `buildRepairXPrompt` in the studio.
    """
    template = (
        REPAIR_PROMPT_TEMPLATE if _notation(notation) == "p" else REPAIR_X_PROMPT_TEMPLATE
    )
    return template.replace("{{FAILED_DOCUMENT}}", document).replace(
        "{{SHACL_REPORT}}", reason[:SHACL_REPORT_SLICE_CHARS]
    )


def _notation(notation: str) -> str:
    if notation not in ("p", "x"):
        raise ValueError(
            "notation must be 'p' (VSON-P) or 'x' (VSON-X), got {!r}".format(notation)
        )
    return notation


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatTurn:
    """One request the loop makes of the caller's model.

    `attachment` is the caller's `image_or_doc`, forwarded verbatim, and it is
    present on round 0 only — the studio does not re-send the image on a repair
    round either, so neither does this. A caller who wants to re-send it has
    `round` to decide on and the original value in hand.
    """

    #: 0 for the initial emission, 1..max_retries for repair rounds.
    round: int
    #: `"p"` (VSON-P) or `"x"` (VSON-X).
    notation: str
    #: The system prompt — a skill body unless the caller supplied one.
    system: str
    #: The user text: the extraction instruction, or the filled repair template.
    user: str
    #: Round 0 only; `None` on every repair round.
    attachment: Any = None
    #: Why this round exists: `None` on round 0, else the transpile error or
    #: the rendered violation report that the repair prompt already contains.
    reason: Optional[str] = None
    #: The document being repaired; `None` on round 0.
    document: Optional[str] = None


#: What `validate_and_repair` needs from a model.
ChatFn = Callable[[ChatTurn], str]


@dataclass
class RepairRound:
    """What one round produced. Round 0 is the initial emission."""

    index: int
    document: str
    #: The transpiled VSON-T, or `""` when the transpile failed.
    turtle: str
    #: The transpile failure, or `None`.
    error: Optional[str]
    #: The three-gate verdict, or `None` when there was nothing to validate.
    verdict: Optional[Verdict]

    @property
    def conforms(self) -> bool:
        return self.verdict is not None and self.verdict.conforms


@dataclass
class RepairResult:
    """The end of the loop, and every round that got there."""

    notation: str
    document: str
    turtle: str
    verdict: Optional[Verdict]
    #: Repair rounds that ran — the number `extraction.shacl_retries` records.
    shacl_retries: int
    rounds: List[RepairRound] = field(default_factory=list)
    #: The skill version this run used, or `None` when the caller supplied
    #: their own system prompt — in which case no `prompt_version` is invented.
    prompt_version: Optional[str] = None

    @property
    def conforms(self) -> bool:
        return self.verdict is not None and self.verdict.conforms

    def to_envelope(
        self,
        scene_id: str,
        version: str = LATEST_ENVELOPE_VERSION,
        source: Optional[Source] = None,
        extraction: Optional[Extraction] = None,
    ) -> Envelope:
        """Assemble an envelope from this run.

        `shacl_retries` and `prompt_version` are filled from the loop unless the
        caller's `extraction` already sets them; everything else in `extraction`
        is the caller's, since this package measures no latency and counts no
        tokens and will not guess at either.

        `conformance.profile` is `"strict"` because that is the only profile the
        loop validates against (see `validate_and_repair`), and §5.16.6 forbids
        labelling a verdict with a profile that did not produce it.

        This is not `web/src/lib/extract/envelope.ts`, and no byte-compatibility
        with the baked demo corpus is claimed — those envelopes are frozen and
        are never regenerated. What both must satisfy is `ENVELOPE_SCHEMA`,
        which `Envelope.errors()` asks and the tests check.
        """
        stats = extraction if extraction is not None else Extraction()
        stats = replace(
            stats,
            shacl_retries=(
                self.shacl_retries
                if stats.shacl_retries is None
                else stats.shacl_retries
            ),
            prompt_version=(
                self.prompt_version
                if stats.prompt_version is None
                else stats.prompt_version
            ),
        )
        return Envelope(
            scene_id=scene_id,
            version=version,
            vson_p=self.document if self.notation == "p" else "",
            vson_t=self.turtle,
            vson_x=self.document if self.notation == "x" else None,
            conformance=_conformance_of(self.verdict),
            source=source,
            extraction=stats,
        )


def _conformance_of(verdict: Optional[Verdict]) -> Conformance:
    if verdict is None:
        return Conformance(conforms=False, profile="strict")
    violations = [
        Violation(
            message=found.message,
            # The envelope's `shape` is required and is a string. A finding
            # whose shape could not be resolved to a named ancestor (§5.16.1)
            # falls back to its rule id, which is what the record itself falls
            # back to — never a blank node identifier dressed up as a name.
            shape=found.shape or found.rule,
            focus_node=found.focus_node,
            result_path=found.result_path,
            severity=found.severity.capitalize() if found.severity else None,
        )
        for found in verdict.findings
    ]
    return Conformance(
        conforms=verdict.conforms,
        profile="strict",
        violations=violations or None,
    )


def validate_and_repair(
    chat_fn: ChatFn,
    image_or_doc: Any = None,
    notation: str = "p",
    max_retries: int = MAX_REPAIR_RETRIES,
    system_prompt: Optional[str] = None,
    document: Optional[str] = None,
) -> RepairResult:
    """Emit, validate, feed the violations back, and stop at the bound.

    Round 0 calls `chat_fn` with `image_or_doc` attached and the extraction
    instruction; every later round calls it with the filled repair template and
    no attachment. The loop stops when the document transpiles *and* clears all
    three gates, or when `max_retries` repair rounds have run — whichever comes
    first. It never runs more than `max_retries` model calls after the first.

    Pass `document=` to start from a document you already have; round 0 is then
    free (no model call) and `image_or_doc` is unused. One of the two is
    required.

    There is deliberately no `shapes` parameter. This loop always validates
    against the strict profile, because the thing it produces is a conformance
    claim — §6.1: only `strict` decides C3 and therefore conformance — and
    §5.16.6 forbids labelling a verdict with a profile that did not produce it.
    A caller who wants the relaxed shapes wants `vson.validate(..., shapes=...)`
    and their own loop.

    Returns a `RepairResult` whose `conforms` may well be `False`: two rounds
    that did not converge is an outcome to record, not an exception to raise.
    `VsonSyntaxError` is raised only when round 0 produced no document at all —
    there is nothing to repair and nothing to report on.
    """
    notation = _notation(notation)
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0, got {}".format(max_retries))
    if document is None and image_or_doc is None:
        raise ValueError(
            "validate_and_repair needs either image_or_doc (forwarded to "
            "chat_fn on round 0) or document= (a document to start from)"
        )

    system = system_prompt
    if system is None:
        system = SKILL_PROMPT if notation == "p" else SKILL_X_PROMPT

    drifted = False
    if document is None:
        reply = chat_fn(
            ChatTurn(
                round=0,
                notation=notation,
                system=system,
                user=EXTRACT_USER if notation == "p" else EXTRACT_USER_X,
                attachment=image_or_doc,
            )
        )
        found = _extract(reply, notation)
        if found is None:
            # The studio's one concession to a real failure mode: a VSON-X
            # request answered in Penman is not an empty reply, it is a drifted
            # one, and saying so in the repair prompt is what re-anchors `~`.
            if notation == "x" and looks_like_penman(reply):
                current, drifted = reply.strip(), True
            else:
                raise VsonSyntaxError(
                    "the chat function returned no {} document".format(
                        "VSON-P" if notation == "p" else "VSON-X"
                    )
                )
        else:
            current = found
    else:
        current = document

    turtle, error = _try_transpile(current, notation, drifted)
    verdict = _validate(turtle, notation) if error is None else None
    rounds = [RepairRound(0, current, turtle or "", error, verdict)]

    retries = 0
    while retries < max_retries and not _settled(error, verdict):
        retries += 1
        reason = error if error is not None else verdict.report_text()
        reply = chat_fn(
            ChatTurn(
                round=retries,
                notation=notation,
                system=system,
                user=build_repair_prompt(current, reason, notation),
                reason=reason,
                document=current,
            )
        )
        # A repair round that returns nothing usable keeps the previous
        # document, exactly as the studio does: the round is spent, the next
        # one still sees a real document, and the failure repeats visibly
        # rather than turning into an empty one.
        repaired = _extract(reply, notation)
        drifted = repaired is None and notation == "x" and looks_like_penman(reply)
        if repaired is not None:
            current = repaired
        turtle, error = _try_transpile(current, notation, drifted)
        verdict = _validate(turtle, notation) if error is None else None
        rounds.append(RepairRound(retries, current, turtle or "", error, verdict))

    return RepairResult(
        notation=notation,
        document=current,
        turtle=turtle or "",
        verdict=verdict,
        shacl_retries=retries,
        rounds=rounds,
        prompt_version=PROMPT_VERSIONS[notation] if system_prompt is None else None,
    )


def _settled(error: Optional[str], verdict: Optional[Verdict]) -> bool:
    """The loop is done: the document transpiled and cleared all three gates."""
    return error is None and verdict is not None and verdict.conforms


def _extract(reply: str, notation: str) -> Optional[str]:
    return extract_penman(reply) if notation == "p" else extract_vson_x(reply)


def _try_transpile(document: str, notation: str, drifted: bool):
    """(turtle, None) or (None, why it failed)."""
    try:
        turtle = api.to_turtle(document) if notation == "p" else api.from_x(document)
    except VsonSyntaxError as exc:
        message = str(exc)
        if drifted:
            message += (
                " (DRIFT: the reply is Penman, not VSON-X; a VSON-X document's "
                "first character is `~`)"
            )
        return None, message
    return turtle, None


def _validate(turtle: str, notation: str) -> Verdict:
    label = "<vson-{}>".format(notation)
    return api.validate(turtle, syntax="t", label=label)
