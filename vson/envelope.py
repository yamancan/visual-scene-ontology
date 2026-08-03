"""The extractor envelope as a Python type, and the schema it answers to.

`ENVELOPE_SCHEMA` is `tools/schema/vson-output.schema.json`, read from the
checkout — the same document `docs/vson.md` §6.1 and Appendix A.1 point at and
`scripts/envelope_check.py` validates the shipped corpus against. `Envelope` and
the dataclasses below are that schema expressed as types: one field per
property, one class per object, nothing invented and nothing left out.

**The schema outranks these classes.** They are a convenience for writing and
reading envelopes in Python; a document is valid because `ENVELOPE_SCHEMA` says
so, which is what `errors()` asks. Two consequences worth stating:

  * `from_json` is strict about *shape*, not about *validity*. It will happily
    build an `Envelope` whose `version` is not in the enum. Call `errors()` for
    the verdict.
  * `to_json` omits every field left at `None` and emits every field that is
    set, including one set to `""` or `[]`. The schema distinguishes an absent
    `vson_x` from an empty one (§6.1's if/then rule turns on exactly that), so
    a round trip that collapsed the two would change what a document says.

Two JSON keys are Python keywords and are spelled with a trailing underscore:
`GraphNode.class_` for `"class"` and `GraphEdge.from_` for `"from"`. Those are
the only two renames; every other attribute is its JSON key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ._resources import read_json

#: The JSON Schema itself (Draft 2020-12), as shipped.
ENVELOPE_SCHEMA: Dict[str, Any] = read_json("tools", "schema", "vson-output.schema.json")

#: Every spec version an envelope may declare, in the schema's own order.
ENVELOPE_VERSIONS: List[str] = list(ENVELOPE_SCHEMA["properties"]["version"]["enum"])

#: The newest of them. The schema's own description says this enum "only ever
#: grows" — every v1.0 envelope stays valid under newer spec versions — so the
#: last member is the current spec document, with no second place to restate it.
LATEST_ENVELOPE_VERSION: str = ENVELOPE_VERSIONS[-1]


def _drop_none(pairs: List[Any]) -> Dict[str, Any]:
    return {key: value for key, value in pairs if value is not None}


@dataclass
class Source:
    """`source` — provenance. Producers SHOULD populate it for anything not
    hand-authored; the schema only requires `kind` once the object is present."""

    kind: str
    uri: Optional[str] = None
    sha256: Optional[str] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    captured_at: Optional[str] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Source":
        return cls(
            kind=data["kind"],
            uri=data.get("uri"),
            sha256=data.get("sha256"),
            width_px=data.get("width_px"),
            height_px=data.get("height_px"),
            captured_at=data.get("captured_at"),
        )

    def to_json(self) -> Dict[str, Any]:
        return _drop_none(
            [
                ("kind", self.kind),
                ("uri", self.uri),
                ("sha256", self.sha256),
                ("width_px", self.width_px),
                ("height_px", self.height_px),
                ("captured_at", self.captured_at),
            ]
        )


@dataclass
class Traits:
    """A node's trait bundle (§3.2). Every slot is optional in the projection."""

    individuation: Optional[str] = None
    animacy: Optional[str] = None
    countability: Optional[str] = None
    affordance: Optional[List[str]] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Traits":
        return cls(
            individuation=data.get("individuation"),
            animacy=data.get("animacy"),
            countability=data.get("countability"),
            affordance=data.get("affordance"),
        )

    def to_json(self) -> Dict[str, Any]:
        return _drop_none(
            [
                ("individuation", self.individuation),
                ("animacy", self.animacy),
                ("countability", self.countability),
                ("affordance", self.affordance),
            ]
        )


@dataclass
class GraphNode:
    """One node of the optional `graph` projection. `class_` is `"class"`."""

    id: str
    kind: str
    class_: Optional[str] = None
    traits: Optional[Traits] = None
    properties: Optional[Dict[str, Any]] = None
    bbox2d: Optional[str] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "GraphNode":
        traits = data.get("traits")
        return cls(
            id=data["id"],
            kind=data["kind"],
            class_=data.get("class"),
            traits=Traits.from_json(traits) if traits is not None else None,
            properties=data.get("properties"),
            bbox2d=data.get("bbox2d"),
        )

    def to_json(self) -> Dict[str, Any]:
        return _drop_none(
            [
                ("id", self.id),
                ("kind", self.kind),
                ("class", self.class_),
                ("traits", self.traits.to_json() if self.traits else None),
                ("properties", self.properties),
                ("bbox2d", self.bbox2d),
            ]
        )


@dataclass
class GraphEdge:
    """One edge. `from_` is `"from"`; `to` needs no escape."""

    from_: str
    to: str
    label: str
    qualifiers: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "GraphEdge":
        return cls(
            from_=data["from"],
            to=data["to"],
            label=data["label"],
            qualifiers=data.get("qualifiers"),
        )

    def to_json(self) -> Dict[str, Any]:
        return _drop_none(
            [
                ("from", self.from_),
                ("to", self.to),
                ("label", self.label),
                ("qualifiers", self.qualifiers),
            ]
        )


@dataclass
class SceneGraph:
    """`graph` — the lossy UI projection. `vson_t` is the full-fidelity form."""

    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "SceneGraph":
        return cls(
            nodes=[GraphNode.from_json(n) for n in data.get("nodes", [])],
            edges=[GraphEdge.from_json(e) for e in data.get("edges", [])],
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_json() for n in self.nodes],
            "edges": [e.to_json() for e in self.edges],
        }


@dataclass
class Violation:
    """One SHACL violation as the envelope records it.

    A near-relative of `vson.Finding` (§5.16.1) with fewer fields: this is the
    envelope's older, smaller shape and the schema fixes it. `Envelope.
    from_verdict` is where a `Finding` becomes one of these.
    """

    message: str
    shape: str
    focus_node: Optional[str] = None
    result_path: Optional[str] = None
    severity: Optional[str] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Violation":
        return cls(
            message=data["message"],
            shape=data["shape"],
            focus_node=data.get("focus_node"),
            result_path=data.get("result_path"),
            severity=data.get("severity"),
        )

    def to_json(self) -> Dict[str, Any]:
        return _drop_none(
            [
                ("message", self.message),
                ("shape", self.shape),
                ("focus_node", self.focus_node),
                ("result_path", self.result_path),
                ("severity", self.severity),
            ]
        )


@dataclass
class Conformance:
    """`conformance` — the verdict, carried with the document it is about."""

    conforms: bool
    profile: Optional[str] = None
    violations: Optional[List[Violation]] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Conformance":
        violations = data.get("violations")
        return cls(
            conforms=data["conforms"],
            profile=data.get("profile"),
            violations=(
                [Violation.from_json(v) for v in violations]
                if violations is not None
                else None
            ),
        )

    def to_json(self) -> Dict[str, Any]:
        return _drop_none(
            [
                ("conforms", self.conforms),
                ("profile", self.profile),
                (
                    "violations",
                    (
                        [v.to_json() for v in self.violations]
                        if self.violations is not None
                        else None
                    ),
                ),
            ]
        )


@dataclass
class Extraction:
    """`extraction` — how the document was produced.

    `shacl_retries` is the field `validate_and_repair` exists to populate
    honestly: the number of repair rounds that ran, not an estimate of them.
    """

    model: Optional[str] = None
    prompt_version: Optional[str] = None
    shacl_retries: Optional[int] = None
    latency_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    confidence_overall: Optional[float] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Extraction":
        return cls(
            model=data.get("model"),
            prompt_version=data.get("prompt_version"),
            shacl_retries=data.get("shacl_retries"),
            latency_ms=data.get("latency_ms"),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            confidence_overall=data.get("confidence_overall"),
        )

    def to_json(self) -> Dict[str, Any]:
        return _drop_none(
            [
                ("model", self.model),
                ("prompt_version", self.prompt_version),
                ("shacl_retries", self.shacl_retries),
                ("latency_ms", self.latency_ms),
                ("input_tokens", self.input_tokens),
                ("output_tokens", self.output_tokens),
                ("confidence_overall", self.confidence_overall),
            ]
        )


@dataclass
class Envelope:
    """The image-extractor response envelope (§4.5, §6.1, Appendix A.1).

    Required: `scene_id`, `version`, `vson_p`, `vson_t`, `conformance`. In
    VSON-X mode `vson_p` is the empty string and `vson_x` carries the document;
    the schema's if/then rule requires at least one of the two to be non-empty
    from v1.1 on.
    """

    scene_id: str
    version: str
    vson_p: str
    vson_t: str
    conformance: Conformance
    source: Optional[Source] = None
    vson_x: Optional[str] = None
    graph: Optional[SceneGraph] = None
    extraction: Optional[Extraction] = None

    # -- JSON ---------------------------------------------------------------

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Envelope":
        """Build one from a parsed envelope document."""
        source = data.get("source")
        graph = data.get("graph")
        extraction = data.get("extraction")
        return cls(
            scene_id=data["scene_id"],
            version=data["version"],
            vson_p=data["vson_p"],
            vson_t=data["vson_t"],
            conformance=Conformance.from_json(data["conformance"]),
            source=Source.from_json(source) if source is not None else None,
            vson_x=data.get("vson_x"),
            graph=SceneGraph.from_json(graph) if graph is not None else None,
            extraction=(
                Extraction.from_json(extraction) if extraction is not None else None
            ),
        )

    def to_json(self) -> Dict[str, Any]:
        """Back to a JSON-serializable dict, in the schema's property order."""
        return _drop_none(
            [
                ("scene_id", self.scene_id),
                ("version", self.version),
                ("source", self.source.to_json() if self.source else None),
                ("vson_p", self.vson_p),
                ("vson_t", self.vson_t),
                ("vson_x", self.vson_x),
                ("graph", self.graph.to_json() if self.graph else None),
                ("conformance", self.conformance.to_json()),
                (
                    "extraction",
                    self.extraction.to_json() if self.extraction else None,
                ),
            ]
        )

    # -- validation ---------------------------------------------------------

    def errors(self) -> List[str]:
        """Every way this envelope fails `ENVELOPE_SCHEMA`, or an empty list.

        Sorted by JSON Pointer path so two runs over one envelope report the
        same list in the same order. Needs `jsonschema` (a declared dependency);
        without it, `VsonResourceError` — never a silent pass, which is the bug
        `scripts/deploy_preflight.sh` had before `jsonschema` was pinned.
        """
        return envelope_errors(self.to_json())


def envelope_errors(document: Dict[str, Any]) -> List[str]:
    """Validate any parsed envelope document against `ENVELOPE_SCHEMA`."""
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover — declared dependency
        from .errors import VsonResourceError

        raise VsonResourceError(
            "vson: jsonschema is required to validate an envelope "
            "(pip install -e . installs it; see pyproject.toml)"
        ) from exc

    validator_for = jsonschema.validators.validator_for(ENVELOPE_SCHEMA)
    validator = validator_for(ENVELOPE_SCHEMA)
    found = []
    for error in validator.iter_errors(document):
        pointer = "/".join(str(part) for part in error.absolute_path)
        found.append("/{}: {}".format(pointer, error.message))
    return sorted(found)


# ---------------------------------------------------------------------------
# Structured-output bindings
# ---------------------------------------------------------------------------
#
# Three vendors spell "constrain the model to this JSON Schema" three ways, and
# all three take the same schema object. These helpers are the wrapper and
# nothing else: no SDK is imported, no network call is made, no key is read, and
# no request is built. What this repository can check about them — and what
# `tests/test_client_library.py` does check — is that each puts the schema at
# the key it says it does. Whether a given vendor accepts a given schema is a
# fact about that vendor's API on the day you call it, which no gate here can
# establish, so none of these claims it.
#
# One thing worth saying plainly before using them on the envelope: an envelope
# carries fields a model cannot produce. `vson_t` is derived by transpiling
# `vson_p`, and `conformance` is a verdict from the three gates — a model
# constrained to emit the whole envelope is being asked to invent both. The flow
# that does not ask it to is `validate_and_repair`: constrain nothing, extract
# the document, derive and validate locally. These helpers are for the other
# job — a consumer that *exchanges or stores* envelopes and wants the schema in
# their vendor's wrapper shape, which is why `schema` is a parameter.


def response_format(
    schema: Optional[Dict[str, Any]] = None,
    name: str = "vson_envelope",
    strict: bool = False,
) -> Dict[str, Any]:
    """The OpenAI-style `response_format` wrapper around a JSON Schema.

    `strict` defaults to `False` and this function will not transform the schema
    to satisfy a strict subset. The envelope schema uses `allOf`, `if`/`then`,
    `default`, `examples`, `format` and `pattern`; a transformed schema would be
    a *different* schema shipped under the envelope's name, and silently
    weakening a document's constraints is worse than a request the vendor
    rejects. Pass `strict=True` only with a schema you know qualifies.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": ENVELOPE_SCHEMA if schema is None else schema,
            "strict": strict,
        },
    }


def tool_schema(
    schema: Optional[Dict[str, Any]] = None,
    name: str = "emit_vson_envelope",
    description: str = "Return one VSON extractor response envelope.",
) -> Dict[str, Any]:
    """The Anthropic-style tool definition: `name`, `description`, `input_schema`."""
    return {
        "name": name,
        "description": description,
        "input_schema": ENVELOPE_SCHEMA if schema is None else schema,
    }


def ollama_format(schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The Ollama-style `format` value: the bare JSON Schema, unwrapped."""
    return ENVELOPE_SCHEMA if schema is None else schema
