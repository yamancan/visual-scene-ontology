"""
VSON-X compact concrete-syntax parser.

VSON-X is the third surface form for VSON, alongside VSON-T (Turtle-star,
canonical) and VSON-P (Penman, formal authoring). VSON-X uses sigil-based
prefix tokens for ~30-50% token economy versus Penman, targeted at LLM
authoring/extraction and image-generator pipelines.

This module produces the same AST shape as the Penman parser
(tools.vson_ast.Node / Ref / Lit / Term) so the existing Turtle emitter
in tools.penman.vson_penman.Emitter renders both syntaxes identically.

Spec: docs/vson-x-semantics.md (working tree, gitignored).

Usage:
    from tools.vson_x import to_turtle
    turtle = to_turtle(open("scene.x.vson").read())

Currently implemented (incremental):
    - Composition root (~scene)
    - Frame declarations (/CameraView, /VisualStyle, /SceneContext)
    - Frame direct properties (*K V on Frame)
    - Entity declarations (handle /Class trait* *K V*)
    - Entity special direct properties (*class, *bbox2d, etc.)
    - Entity Quality dispatch (*K V -> hasQuality)
    - Composition Quality dispatch (*K V on root)
    - Viewer anchor (^cam)
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Import shared AST types so we feed the same Emitter as Penman.
_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_REPO = os.path.dirname(_TOOLS)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
from tools.vson_ast import Lit, Node, Ref, Term  # noqa: E402
from tools.penman.vson_penman import Emitter  # noqa: E402


# ---------------------------------------------------------------------------
# Spec constants (mirror docs/vson-x-semantics.md)
# ---------------------------------------------------------------------------

TRAIT_INDIVIDUATION = {"Generic", "Named", "Skolem", "Kind"}
TRAIT_ANIMACY = {"Agentive", "Inert"}
TRAIT_COUNTABILITY = {"Count", "Mass", "Collective"}
TRAIT_AFFORDANCE = {"Holdable", "Wearable", "Mountable", "Container", "Edible"}
TRAIT_KEYWORDS = (
    TRAIT_INDIVIDUATION | TRAIT_ANIMACY | TRAIT_COUNTABILITY | TRAIT_AFFORDANCE
)

# Lemma -> (lhs_slot, [pos_slots]) routing per spec §5. Open lemmas not
# in these tables default to ("agent", ["patient"]) for `>>` form and
# ("holder", ["theme"]) for `>` form, with a parse warning.

STATIVE_LEMMAS = {
    "hold":     ("holder", ["theme"]),
    "wear":     ("holder", ["theme"]),
    "carry":    ("holder", ["theme"]),
    "own":      ("holder", ["theme"]),
    "sit":      ("holder", []),
    "stand":    ("holder", []),
    "lie":      ("holder", []),
    "lean":     ("holder", []),
    "look_at":  ("experiencer", ["stimulus"]),
    "gaze_at":  ("experiencer", ["stimulus"]),
    "see":      ("experiencer", ["stimulus"]),
    "hear":     ("experiencer", ["stimulus"]),
    "know":     ("experiencer", ["stimulus"]),
    "believe":  ("experiencer", ["stimulus"]),
    "intend":   ("experiencer", ["stimulus"]),
}

EVENT_LEMMAS = {
    "strike":  ("agent",  ["patient"]),
    "throw":   ("agent",  ["theme"]),
    "fall":    ("patient", []),
    "give":    ("agent",  ["theme", "recipient"]),
    "send":    ("agent",  ["theme", "recipient"]),
    "arrive":  ("agent",  []),
    "depart":  ("agent",  []),
    "break":   ("agent",  ["patient"]),
    "catch":   ("agent",  ["patient"]),
    "drop":    ("agent",  ["patient"]),
    "charge":  ("agent",  []),   # canonical gallery 11 maps charge to Event
}

PROCESS_LEMMAS = {
    "run":     ("agent", []),
    "walk":    ("agent", []),
    "swim":    ("agent", []),
    "fly":     ("agent", []),
    "dance":   ("agent", []),
    "burn":    ("patient", []),
    "bleed":   ("patient", []),
    "flow":    ("agent", []),
    "pour":    ("agent", ["theme"]),
}

# Symmetric proximal lemmas (close enum). `&` form emits two SpatialFact
# nodes with figure/ground swapped. `next_to` and `facing_each_other`
# deferred to v1.2 (vso:proximal enum currently {near, far, adjacent}).
SYMMETRIC_LEMMAS = {"near", "far", "adjacent"}

# Asymmetric `!` spatial relations.
RCC_TOKENS = {"DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPi", "NTPPi"}
DIRECTIONAL_TOKENS = {
    "above", "below",
    "left_of", "leftOf",
    "right_of", "rightOf",
    "in_front_of", "inFrontOf",
    "behind",
}

# Frame kinds that take direct-property dispatch (CameraView, VisualStyle,
# SceneContext). Composition and Persona have their own dispatch rules
# (Composition -> Quality, Persona -> hasInvariant Quality).
METADATA_FRAME_KINDS = {"CameraView", "VisualStyle", "SceneContext"}

# Closed concept kinds usable after `/`. Domain class strings (Knight,
# Crown, Sword) NEVER appear here — they are values of `*class`.
CONCEPT_KINDS = {
    "PhysicalObject",
    "Aggregate",
    "Substance",
    "CameraView",
    "VisualStyle",
    "SceneContext",
    "Persona",
    "Quality",
    "Event",
    "Process",
    "Stative",
    "SpatialFact",
}

# Entity-level *key names that emit direct properties (NOT Quality).
ENTITY_DIRECT_KEYS = {
    "class",
    "bbox2d",
    "position3d",
    "scale3d",
    "rotation",
    "visibleFraction",
    "embodies",
}

# Composition-level *key names that emit direct properties (NOT Quality).
COMPOSITION_DIRECT_KEYS = {"rendersAs"}


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

# Tokens (in priority order):
#   ~       composition sigil (must be first significant char)
#   /       concept marker (after handle, before kind)
#   @       handle prefix (Named/Skolem)
#   ^       viewer anchor
#   *       quality/property kv prefix
#   ~mod    inside *K V it can be followed by a modifier — disambiguated by parser
#   STRING  quoted "..."
#   UNIT    35mm / 1.5x
#   NUM     bare number
#   IDENT   bareword identifier
TOKEN_RE = re.compile(
    r"""
    \#[^\n]*                                      # comment to EOL (skipped)
    | (>>)                                        # event/process arrow (must precede single >)
    | (>)                                         # stative arrow
    | (~)                                         # tilde sigil (composition root, modifier prefix)
    | (\^)                                        # viewer anchor
    | (\*)                                        # quality/property prefix
    | (/)                                         # concept marker
    | (@)                                         # handle prefix
    | (!)                                         # asym spatial arrow
    | (&)                                         # sym spatial arrow
    | "((?:[^"\\]|\\.)*)"                         # double-quoted string
    | (-?\d+(?:\.\d+)?[A-Za-z_][\w\-]*)           # number-prefixed unit literal (35mm)
    | (-?\d+(?:\.\d+)?)                           # bare number
    | ([A-Za-z_][\w\-]*)                          # bareword identifier
    | (\S)                                        # any other char (lexer error)
    """,
    re.VERBOSE,
)


@dataclass
class Tok:
    kind: str  # "~", "^", "*", "/", "@", ">", ">>", "!", "&", "STR", "UNIT", "NUM", "IDENT"
    value: str


def tokenize(src: str) -> List[Tok]:
    """Lexer producing a flat token stream.

    Newlines and other whitespace are skipped — VSON-X uses lead-token
    detection (spec §3.7) for item boundaries, NOT physical lines.
    """
    out: List[Tok] = []
    for m in TOKEN_RE.finditer(src):
        text = m.group(0)
        if text.startswith("#"):
            continue
        if text.isspace():
            continue
        if m.group(1):
            out.append(Tok(">>", ">>"))
        elif m.group(2):
            out.append(Tok(">", ">"))
        elif m.group(3):
            out.append(Tok("~", "~"))
        elif m.group(4):
            out.append(Tok("^", "^"))
        elif m.group(5):
            out.append(Tok("*", "*"))
        elif m.group(6):
            out.append(Tok("/", "/"))
        elif m.group(7):
            out.append(Tok("@", "@"))
        elif m.group(8):
            out.append(Tok("!", "!"))
        elif m.group(9):
            out.append(Tok("&", "&"))
        elif m.group(10) is not None:  # group(10) captures the inner string body
            out.append(Tok("STR", m.group(10)))
        elif m.group(11):
            out.append(Tok("UNIT", m.group(11)))
        elif m.group(12):
            out.append(Tok("NUM", m.group(12)))
        elif m.group(13):
            out.append(Tok("IDENT", m.group(13)))
        elif m.group(14):
            raise SyntaxError(f"unexpected character: {m.group(14)!r}")
    return out


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class Parser:
    """Lead-token-driven recursive descent (spec §3.7).

    Items are flat top-level entries inside a Composition block. Each item
    is identified by its lead token:
        ~IDENT          composition root (must be first item)
        @IDENT /        entity_decl (Named/Skolem)
        IDENT /         entity_decl (Generic) [bareword + slash]
        /KIND           frame_decl (no handle) or framedef with handle nearby
        ^IDENT          viewer_anchor
        IDENT >         stative
        IDENT >>        event/process (Penman never sees `>>`; we synthesize it)

    The result is a single Node(var=scene_id, concept="Composition") with
    children attached via :framedBy, :viewedBy, :depicts, :hasQuality, etc.
    """

    def __init__(self, toks: List[Tok]):
        self.toks = toks
        self.i = 0
        # Auto-generated counters for blank-node-like vars (Quality, etc.)
        self._gen_counter = 0

    # ------------------------------------------------------------------
    # Token utilities
    # ------------------------------------------------------------------
    def peek(self, k: int = 0) -> Optional[Tok]:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def consume(self, kind: str) -> Tok:
        t = self.peek()
        if t is None or t.kind != kind:
            raise SyntaxError(f"expected {kind}, got {t}")
        self.i += 1
        return t

    def eat(self, kind: str) -> Optional[Tok]:
        t = self.peek()
        if t is not None and t.kind == kind:
            self.i += 1
            return t
        return None

    def gen(self, prefix: str) -> str:
        """Generate a fresh blank-node-like var name. The leading `_`
        signals to the shared Penman emitter that this var should
        render as an RDF blank node — appropriate for auto-generated
        Quality / Stative / Event / Process / SpatialFact nodes that
        have no author-meaningful identity."""
        self._gen_counter += 1
        return f"_{prefix}{self._gen_counter}"

    def gen_named(self, prefix: str) -> str:
        """Generate a fresh named-IRI var name (no leading underscore).
        Used for Frame declarations that lack an explicit handle but
        SHOULD be addressable in the document namespace (e.g. an
        anonymous /VisualStyle that may be later targeted by
        *rendersAs)."""
        self._gen_counter += 1
        return f"{prefix}{self._gen_counter}"

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------
    def parse_document(self) -> Node:
        # Document = composition
        self.consume("~")
        root_id = self.consume("IDENT").value
        scene = Node(var=root_id, concept="Composition", edges=[])

        # Optional Composition-level *K V before block items
        while self.peek() and self.peek().kind == "*":
            self._parse_composition_kv(scene)

        # Block items until EOF
        while self.peek() is not None:
            self._parse_item(scene)

        return scene

    # ------------------------------------------------------------------
    # Composition-level *K V (Quality dispatch + rendersAs special)
    # ------------------------------------------------------------------
    def _parse_composition_kv(self, scene: Node) -> None:
        self.consume("*")
        key = self.consume("IDENT").value
        value_term = self._parse_value()
        modifier = self._maybe_modifier()

        if key in COMPOSITION_DIRECT_KEYS:
            # *rendersAs @style -> direct property
            scene.edges.append((key, value_term))
            if modifier is not None:
                raise SyntaxError(f"modifier ~{modifier} not valid on direct property *{key}")
            return

        # Default: Composition Quality (Layout, Focal, etc.)
        q_var = self.gen("q")
        q_node = Node(var=q_var, concept="Quality", edges=[
            ("dimension", Ref(_pascal_case(key))),
            ("value", value_term),
        ])
        if modifier is not None:
            q_node.edges.append(("modifier", Lit(modifier, is_string=True)))
        scene.edges.append(("hasQuality", q_node))

    # ------------------------------------------------------------------
    # Item dispatch by lead token
    # ------------------------------------------------------------------
    def _parse_item(self, scene: Node) -> None:
        t = self.peek()
        if t is None:
            return
        if t.kind == "/":
            self._parse_frame_decl(scene)
            return
        if t.kind == "^":
            self._parse_viewer_anchor(scene)
            return
        if t.kind == "@":
            self._parse_handle_item(scene, named=True)
            return
        if t.kind == "IDENT":
            self._parse_handle_item(scene, named=False)
            return
        raise SyntaxError(f"unexpected lead token: {t}")

    # ------------------------------------------------------------------
    # /Frame declarations (CameraView, VisualStyle, SceneContext)
    # ------------------------------------------------------------------
    def _parse_frame_decl(self, scene: Node) -> None:
        self.consume("/")
        kind = self.consume("IDENT").value
        if kind not in CONCEPT_KINDS:
            raise SyntaxError(f"unknown concept after /: {kind}")

        # Optional handle: /CameraView @cam   or   /CameraView cam
        var: Optional[str] = None
        if self.peek() and self.peek().kind == "@":
            self.consume("@")
            var = self.consume("IDENT").value
        elif self.peek() and self.peek().kind == "IDENT" and not _is_trait(self.peek().value):
            # Lookahead: a bare ident here is a handle, not a trait. We
            # can't easily distinguish from a trait without next-next
            # peek; for now accept only @-prefixed handles on Frames
            # (matches spec recommendation).
            pass

        if var is None:
            # Frames get NAMED IRIs (no leading underscore) so they
            # remain addressable in the document namespace. Quality /
            # Stative / Event / Process / SpatialFact use gen() (with
            # leading underscore -> blank node).
            var = self.gen_named(kind[:3].lower())

        node = Node(var=var, concept=kind, edges=[])

        # Direct-property *K V (Frame fields like *angle, *focalLength)
        while self.peek() and self.peek().kind == "*":
            self.consume("*")
            key = self.consume("IDENT").value
            value_term = self._parse_value()
            mod = self._maybe_modifier()
            if mod is not None:
                raise SyntaxError(
                    f"modifier ~{mod} not valid on Frame direct property *{key}"
                )
            node.edges.append((key, value_term))

        scene.edges.append(("framedBy", node))

    # ------------------------------------------------------------------
    # ^viewer (Composition-level only, for now)
    # ------------------------------------------------------------------
    def _parse_viewer_anchor(self, scene: Node) -> None:
        self.consume("^")
        var = self.consume("IDENT").value
        scene.edges.append(("viewedBy", Ref(var)))

    # ------------------------------------------------------------------
    # @handle / bare-handle items: entity_decl OR stative/event/spatial.
    # ------------------------------------------------------------------
    def _parse_handle_item(self, scene: Node, named: bool) -> None:
        if named:
            self.consume("@")
        var = self.consume("IDENT").value

        nxt = self.peek()
        if nxt is None:
            raise SyntaxError(f"unexpected EOF after handle '{var}'")
        if nxt.kind == "/":
            self._parse_entity_decl(scene, var, named)
            return
        if nxt.kind == ">":
            self._parse_stative(scene, var)
            return
        if nxt.kind == ">>":
            self._parse_event_or_process(scene, var)
            return
        if nxt.kind == "!":
            self._parse_spatial_asym(scene, var)
            return
        if nxt.kind == "&":
            self._parse_spatial_sym(scene, var)
            return
        raise SyntaxError(
            f"after handle '{var}': expected '/', '>', '>>', '!', or '&', got {nxt}"
        )

    def _parse_entity_decl(self, scene: Node, var: str, named: bool) -> None:
        self.consume("/")
        kind = self.consume("IDENT").value
        if kind not in CONCEPT_KINDS:
            raise SyntaxError(f"unknown concept after /: {kind}")

        node = Node(var=var, concept=kind, edges=[])

        # Implicit individuation from sigil: bare = Generic, @ = Named.
        # Explicit trait keyword overrides — we collect them first, then
        # apply default if no individuation trait was given.
        seen_individuation = False

        while self.peek():
            t = self.peek()
            if t.kind == "IDENT" and _is_trait(t.value):
                self.consume("IDENT")
                trait_value = t.value
                if trait_value in TRAIT_INDIVIDUATION:
                    node.edges.append(("individuation", Ref(trait_value)))
                    seen_individuation = True
                elif trait_value in TRAIT_ANIMACY:
                    node.edges.append(("animacy", Ref(trait_value)))
                elif trait_value in TRAIT_COUNTABILITY:
                    node.edges.append(("countability", Ref(trait_value)))
                elif trait_value in TRAIT_AFFORDANCE:
                    node.edges.append(("affordance", Ref(trait_value)))
                continue
            if t.kind == "*":
                self._parse_entity_kv(node)
                continue
            break

        if not seen_individuation:
            default = "Named" if named else "Generic"
            # Insert at position 0 so the trait appears before *K V — keeps
            # output consistent with spec's recommended ordering.
            node.edges.insert(0, ("individuation", Ref(default)))

        scene.edges.append(("depicts", node))

    def _parse_entity_kv(self, entity: Node) -> None:
        self.consume("*")
        key = self.consume("IDENT").value
        value_term = self._parse_value()
        modifier = self._maybe_modifier()

        if key in ENTITY_DIRECT_KEYS:
            entity.edges.append((key, value_term))
            if modifier is not None:
                raise SyntaxError(
                    f"modifier ~{modifier} not valid on Entity direct property *{key}"
                )
            return

        # Default: Quality dispatch via hasQuality
        q_var = self.gen("q")
        q_node = Node(var=q_var, concept="Quality", edges=[
            ("dimension", Ref(_pascal_case(key))),
            ("value", value_term),
        ])
        if modifier is not None:
            q_node.edges.append(("modifier", Lit(modifier, is_string=True)))
        entity.edges.append(("hasQuality", q_node))

    # ------------------------------------------------------------------
    # Stative `>`  /  Event-Process `>>`
    # ------------------------------------------------------------------
    def _parse_stative(self, scene: Node, lhs_var: str) -> None:
        self.consume(">")
        lemma = self.consume("IDENT").value
        refs, kvs = self._parse_arglist()

        if lemma in EVENT_LEMMAS or lemma in PROCESS_LEMMAS:
            # Sigil mismatch: '>' with an Event/Process lemma. Per spec
            # §5.2 "Author writes `>` with Event/Process-only lemma"
            # is an error.
            raise SyntaxError(
                f"lemma '{lemma}' is Event/Process; use '>>' instead of '>'"
            )

        lhs_slot, pos_slots = STATIVE_LEMMAS.get(
            lemma, ("holder", ["theme"])  # default for unknown lemma
        )
        s_var = self.gen("s")
        s_node = Node(var=s_var, concept="Stative", edges=[
            ("lemma", Ref(lemma)),
            (lhs_slot, Ref(lhs_var)),
        ])
        self._attach_args(s_node, refs, kvs, pos_slots)
        scene.edges.append(("depicts", s_node))

    def _parse_event_or_process(self, scene: Node, lhs_var: str) -> None:
        self.consume(">>")
        lemma = self.consume("IDENT").value
        refs, kvs = self._parse_arglist()

        if lemma in STATIVE_LEMMAS and lemma not in EVENT_LEMMAS and lemma not in PROCESS_LEMMAS:
            raise SyntaxError(
                f"lemma '{lemma}' is Stative; use '>' instead of '>>'"
            )

        if lemma in PROCESS_LEMMAS:
            kind = "Process"
            lhs_slot, pos_slots = PROCESS_LEMMAS[lemma]
            prefix = "p"
        elif lemma in EVENT_LEMMAS:
            kind = "Event"
            lhs_slot, pos_slots = EVENT_LEMMAS[lemma]
            prefix = "e"
        else:
            # Open lemma — default to Event with agent/patient
            kind = "Event"
            lhs_slot, pos_slots = ("agent", ["patient"])
            prefix = "e"

        n_var = self.gen(prefix)
        node = Node(var=n_var, concept=kind, edges=[
            ("lemma", Ref(lemma)),
            (lhs_slot, Ref(lhs_var)),
        ])
        self._attach_args(node, refs, kvs, pos_slots)
        scene.edges.append(("depicts", node))

    def _attach_args(
        self,
        node: Node,
        refs: List[Term],
        kvs: List[Tuple[str, Term, Optional[str]]],
        pos_slots: List[str],
    ) -> None:
        """Bind positional refs to their named slots per the lemma table,
        then append `*K V` named arguments. Excess positional refs are a
        parse error (clearer than silently dropping)."""
        if len(refs) > len(pos_slots):
            raise SyntaxError(
                f"too many positional arguments: lemma expects {len(pos_slots)}, got {len(refs)}"
            )
        for i, ref in enumerate(refs):
            node.edges.append((pos_slots[i], ref))
        for key, value, modifier in kvs:
            node.edges.append((key, value))
            if modifier is not None:
                # Modifier on a thematic role (`*manner forceful ~very`) is
                # unusual; for v1.1 we attach it as a sibling triple if
                # the value is a node, else accept the modifier silently.
                # The spec leaves this open; tests don't exercise it.
                pass

    # ------------------------------------------------------------------
    # SpatialFact `!` (asymmetric)  and  `&` (symmetric)
    # ------------------------------------------------------------------
    def _parse_spatial_asym(self, scene: Node, figure_var: str) -> None:
        self.consume("!")
        rel_tok = self.consume("IDENT")
        rel_value = rel_tok.value
        if rel_value not in RCC_TOKENS and rel_value not in DIRECTIONAL_TOKENS:
            raise SyntaxError(
                f"unknown spatial relation '{rel_value}': "
                f"expected one of {sorted(RCC_TOKENS | DIRECTIONAL_TOKENS)}"
            )

        # Ground
        if self.peek() and self.peek().kind == "@":
            self.consume("@")
        ground_var = self.consume("IDENT").value

        # Optional viewer anchor
        viewer_var: Optional[str] = None
        if self.peek() and self.peek().kind == "^":
            self.consume("^")
            viewer_var = self.consume("IDENT").value

        # Optional *K V (e.g. *dir above when rel was an RCC)
        directional_value: Optional[str] = None
        proximal_value: Optional[str] = None
        extra_kvs: List[Tuple[str, Term, Optional[str]]] = []
        while self.peek() and self.peek().kind == "*":
            self.consume("*")
            key = self.consume("IDENT").value
            value = self._parse_value()
            modifier = self._maybe_modifier()
            if key == "dir":
                if not isinstance(value, Ref):
                    raise SyntaxError("*dir value must be a directional bareword")
                directional_value = value.var
            elif key == "prox":
                if not isinstance(value, Ref):
                    raise SyntaxError("*prox value must be a proximal bareword")
                proximal_value = value.var
            else:
                extra_kvs.append((key, value, modifier))

        # If rel itself was a directional token, treat as directional
        if rel_value in DIRECTIONAL_TOKENS:
            directional_value = rel_value
            rcc_value: Optional[str] = None
        else:
            rcc_value = rel_value

        # Talmy resolution: directional requires viewer (parser-level fail-fast).
        if directional_value is not None and viewer_var is None:
            raise SyntaxError(
                "directional spatial fact requires a viewer anchor (^cam); "
                "see spec §4.10.2"
            )

        sf_var = self.gen("sf")
        edges: List[Tuple[str, Term]] = [
            ("figure", Ref(figure_var)),
            ("ground", Ref(ground_var)),
        ]
        if rcc_value is not None:
            edges.append(("rcc", Ref(rcc_value)))
        if directional_value is not None:
            edges.append(("directional", Ref(directional_value)))
        if proximal_value is not None:
            edges.append(("proximal", Ref(proximal_value)))
        if viewer_var is not None:
            edges.append(("viewer", Ref(viewer_var)))
        for k, v, _mod in extra_kvs:
            edges.append((k, v))

        sf_node = Node(var=sf_var, concept="SpatialFact", edges=edges)
        scene.edges.append(("depicts", sf_node))

    def _parse_spatial_sym(self, scene: Node, figure_var: str) -> None:
        self.consume("&")
        lemma = self.consume("IDENT").value
        if lemma not in SYMMETRIC_LEMMAS:
            raise SyntaxError(
                f"'{lemma}' is not a symmetric proximal lemma; "
                f"expected one of {sorted(SYMMETRIC_LEMMAS)}"
            )
        # Closing & is required by grammar
        self.consume("&")
        if self.peek() and self.peek().kind == "@":
            self.consume("@")
        ground_var = self.consume("IDENT").value

        # Spec §4.9: emit two SpatialFact nodes (figure/ground swapped).
        sf1 = Node(var=self.gen("sf"), concept="SpatialFact", edges=[
            ("figure", Ref(figure_var)),
            ("ground", Ref(ground_var)),
            ("proximal", Ref(lemma)),
        ])
        sf2 = Node(var=self.gen("sf"), concept="SpatialFact", edges=[
            ("figure", Ref(ground_var)),
            ("ground", Ref(figure_var)),
            ("proximal", Ref(lemma)),
        ])
        scene.edges.append(("depicts", sf1))
        scene.edges.append(("depicts", sf2))

    # ------------------------------------------------------------------
    # Argument list — positional refs + named *K V (Stative/Event)
    # ------------------------------------------------------------------
    def _parse_arglist(self) -> Tuple[List[Term], List[Tuple[str, Term, Optional[str]]]]:
        """Parse `<ref>* (*K V)*` until the next item lead token.

        Refs in arglist context use `@<IDENT>` form. Bare-id positional
        refs are not supported (would be ambiguous with trait keywords
        in entity_decl context).
        """
        refs: List[Term] = []
        kvs: List[Tuple[str, Term, Optional[str]]] = []

        while True:
            t = self.peek()
            if t is None:
                break
            if t.kind == "*":
                self.consume("*")
                key = self.consume("IDENT").value
                value = self._parse_value()
                modifier = self._maybe_modifier()
                kvs.append((key, value, modifier))
                continue
            if t.kind == "@":
                # Lookahead: is this a new item (`@bob > ...`) or a positional ref?
                nxt = self.peek(2)
                if nxt is not None and nxt.kind in {"/", ">", ">>", "!", "&"}:
                    break
                self.consume("@")
                ident = self.consume("IDENT").value
                refs.append(Ref(ident))
                continue
            if t.kind == "IDENT":
                # Bare-ID positional ref. Look ahead — if the IMMEDIATELY
                # next token is a boundary-implying sigil, this IDENT is
                # the start of a new top-level item, not a positional ref.
                # (For @-prefixed handles the lookahead is one further
                # because we have to skip the @ token itself.)
                nxt = self.peek(1)
                if nxt is not None and nxt.kind in {"/", ">", ">>", "!", "&"}:
                    break
                # Otherwise it's a positional ref to a previously-declared
                # generic entity (e.g. `> hold sword` where sword was
                # declared bare).
                self.consume("IDENT")
                refs.append(Ref(t.value))
                continue
            # Anything else terminates the arglist.
            break

        return refs, kvs

    # ------------------------------------------------------------------
    # Value parsing (literal or ref)
    # ------------------------------------------------------------------
    def _parse_value(self) -> Term:
        t = self.peek()
        if t is None:
            raise SyntaxError("unexpected EOF in value")
        if t.kind == "STR":
            self.consume("STR")
            return Lit(t.value, is_string=True)
        if t.kind == "NUM":
            self.consume("NUM")
            return Lit(t.value, is_number=True)
        if t.kind == "UNIT":
            self.consume("UNIT")
            return Lit(t.value, is_string=True)
        if t.kind == "@":
            self.consume("@")
            ident = self.consume("IDENT").value
            return Ref(ident)
        if t.kind == "IDENT":
            self.consume("IDENT")
            return Ref(t.value)
        raise SyntaxError(f"unexpected value token: {t}")

    def _maybe_modifier(self) -> Optional[str]:
        """If a `~mod` follows a value, consume and return the modifier name.

        The `~` token is also the composition root sigil — we only treat
        it as a modifier when it appears immediately after a value in a
        *K V position. Caller must ensure we're not at item boundary.
        """
        t = self.peek()
        if t is None or t.kind != "~":
            return None
        # Lookahead: ~ must be followed by IDENT for a modifier; if it's
        # followed by anything else, this is a top-level composition root
        # (which would be a syntax error here anyway since we already
        # have a root).
        nxt = self.peek(1)
        if nxt is None or nxt.kind != "IDENT":
            return None
        # And the IDENT must NOT be a trait keyword (we'd misread it).
        if _is_trait(nxt.value):
            return None
        self.consume("~")
        return self.consume("IDENT").value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_trait(name: str) -> bool:
    return name in TRAIT_KEYWORDS


def _pascal_case(name: str) -> str:
    """Convert snake_case or lowercase key to PascalCase dimension name.

    `*color`        -> Color
    `*action_state` -> ActionState
    `*hair`         -> Hair
    `*Hair`         -> Hair (idempotent)
    """
    if not name:
        return name
    parts = name.split("_")
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse(src: str) -> Node:
    """Parse VSON-X source text into a shared-AST Composition node."""
    toks = tokenize(src)
    return Parser(toks).parse_document()


def to_turtle(src: str) -> str:
    """Parse VSON-X and emit Turtle via the shared Penman emitter."""
    ast = parse(src)
    return Emitter().emit(ast)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: List[str]) -> int:
    if len(argv) < 3:
        print("usage: python -m tools.vson_x.vson_x to-turtle <file.x.vson>", file=sys.stderr)
        return 2
    cmd, path = argv[1], argv[2]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if cmd == "to-turtle":
        sys.stdout.write(to_turtle(text))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
