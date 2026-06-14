"""
VSON-P (Penman) ↔ VSON-T (Turtle-star) reference transpiler.

Scope: this is a reference, not a production parser. It implements:
  - VSON-P parser (Penman concrete syntax tuned to VSV concept names)
  - VSON-P → Turtle-star emitter
  - Triple-set normalizer (sort + canonicalize blank-node ids) for diffing

Usage:
  python3 vson_penman.py to-turtle <file.vson>
  python3 vson_penman.py normalize <file.ttl|file.vson>

Concept names appearing after `/` are interpreted in the VSO namespace by
default. Role names (after `:`) are interpreted in the VSO namespace; a few
known temporal/causal roles route to the Allen and core namespaces.

This file has no third-party dependencies — pure stdlib so the repo can be
exercised without an install step. For production use, swap the Turtle parser
in `normalize` for rdflib.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass

# Shared AST types live in tools/vson_ast.py so the upcoming VSON-X
# parser can produce the same tree without duplicating the dataclasses.
# We re-export them at module level for back-compat with any caller that
# imports Ref/Lit/Node/Term/Triple from this module.
#
# Import strategy: prefer the qualified package path `tools.vson_ast`
# so import identity is stable (`tools.vson_ast.Node is
# tools.penman.vson_penman.Node`). Fall back to the bare `vson_ast`
# import for the direct-invocation case (`python3 vson_penman.py ...`)
# where the package root might not be on sys.path.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_PARENT = os.path.dirname(_REPO_ROOT)
if _REPO_PARENT not in sys.path:
    sys.path.insert(0, _REPO_PARENT)
try:
    from tools.vson_ast import Lit, Node, Ref, Term, Triple  # noqa: E402,F401
except ImportError:
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    from vson_ast import Lit, Node, Ref, Term, Triple  # type: ignore  # noqa: E402,F401

# Routing tables live in a sibling JSON file; both this reference and the
# Rust CLI consume the same file so they cannot drift.
_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "routing-tables.json"), "r", encoding="utf-8") as _f:
    _ROUTING = json.load(_f)

VSO = _ROUTING["namespaces"]["vso"]
ALLEN = _ROUTING["namespaces"]["allen"]
RCC = _ROUTING["namespaces"]["rcc"]
RDF = _ROUTING["namespaces"]["rdf"]
DEFAULT_NS = _ROUTING["namespaces"]["default"]
_NS = _ROUTING["namespaces"]

ROLE_NAMESPACE_OVERRIDES = {
    role: _NS[ns_key] for role, ns_key in _ROUTING["role_namespace_overrides"].items()
}
CONTAINER_ROLES = set(_ROUTING["container_roles"])
RCC_VALUES = set(_ROUTING["rcc_values"])
ROLE_VALUE_TO_VSO = set(_ROUTING["role_value_to_vso"])
ROLE_VALUE_TO_RCC = set(_ROUTING["role_value_to_rcc"])
ROLE_VALUE_AS_STRING = set(_ROUTING["role_value_as_string"])


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r"""
    \#[^\n]*                                      # comment to EOL
    | \(                                          # open paren
    | \)                                          # close paren
    | "((?:[^"\\]|\\.)*)"                         # double-quoted string
    | (:[A-Za-z_][\w\-]*)                         # role  (e.g. :agent)
    | (/)                                         # concept marker
    | (-?\d+(?:\.\d+)?[A-Za-z_][\w\-]*)           # number-prefixed unit literal (35mm, 1.5x)
    | (-?\d+(?:\.\d+)?)                           # bare number
    | ([A-Za-z_][\w\-]*)                          # bare identifier (variable, concept, value)
    | (\S)                                        # any other char (lexer error sentinel)
    """,
    re.VERBOSE,
)


@dataclass
class Tok:
    kind: str  # "(", ")", "ROLE", "/", "ID", "NUM", "STR"
    value: str


# Turtle ECHAR set, decoded at lex-time so a STR token carries the *true* string
# value (real newline/tab/quote), then re-encoded for Turtle at emit time.
# Without this, a source `\n` would pass through verbatim and the emitter's
# backslash-doubling would corrupt it to a literal backslash-n, and a raw
# newline inside a quoted value would emit as invalid (unparseable) Turtle.
_STR_ESCAPES = {
    "t": "\t", "b": "\b", "n": "\n", "r": "\r", "f": "\f",
    '"': '"', "'": "'", "\\": "\\", "/": "/",
}


def _decode_escapes(body: str) -> str:
    out = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n:
            out.append(_STR_ESCAPES.get(body[i + 1], body[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def tokenize(src: str):
    out = []
    for m in TOKEN_RE.finditer(src):
        text = m.group(0)
        if text.startswith("#"):
            continue
        if text.isspace():
            continue
        if text == "(":
            out.append(Tok("(", "("))
        elif text == ")":
            out.append(Tok(")", ")"))
        elif m.group(1) is not None:                   # quoted string body
            out.append(Tok("STR", _decode_escapes(m.group(1))))
        elif m.group(2) is not None:                   # :role
            out.append(Tok("ROLE", m.group(2)[1:]))
        elif m.group(3) is not None:                   # /
            out.append(Tok("/", "/"))
        elif m.group(4) is not None:                   # number+unit literal (35mm)
            out.append(Tok("UNIT", m.group(4)))
        elif m.group(5) is not None:                   # bare number
            out.append(Tok("NUM", m.group(5)))
        elif m.group(6) is not None:                   # bare id
            out.append(Tok("ID", m.group(6)))
        elif m.group(7) is not None:
            raise SyntaxError(f"Unexpected character: {m.group(7)!r}")
    return out


# ---------------------------------------------------------------------------
# AST — Ref, Lit, Node, Term are imported from tools.vson_ast above.
# Keeping them re-exported here preserves any historical callers that
# imported via `from tools.penman.vson_penman import Node`.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self, k: int = 0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def consume(self, kind: str) -> Tok:
        t = self.peek()
        if t is None or t.kind != kind:
            raise SyntaxError(f"expected {kind}, got {t}")
        self.i += 1
        return t

    def parse_node(self) -> Node:
        self.consume("(")
        var_tok = self.consume("ID")
        node = Node(var=var_tok.value, concept=None)
        # optional concept "/ Concept"
        if self.peek() and self.peek().kind == "/":
            self.consume("/")
            ctok = self.consume("ID")
            node.concept = ctok.value
        # edges
        while True:
            t = self.peek()
            if t is None:
                raise SyntaxError("unexpected EOF inside node")
            if t.kind == ")":
                self.consume(")")
                return node
            if t.kind != "ROLE":
                raise SyntaxError(f"expected role or ')', got {t}")
            self.consume("ROLE")
            role = t.value
            target = self.parse_term(role)
            node.edges.append((role, target))

    def parse_term(self, role: str) -> Term:
        t = self.peek()
        if t is None:
            raise SyntaxError("unexpected EOF in term")
        if t.kind == "(":
            return self.parse_node()
        if t.kind == "STR":
            self.consume("STR")
            return Lit(t.value, is_string=True)
        if t.kind == "NUM":
            self.consume("NUM")
            return Lit(t.value, is_number=True)
        if t.kind == "UNIT":
            # number+unit: emit as a string literal (e.g. "35mm")
            self.consume("UNIT")
            return Lit(t.value, is_string=True)
        if t.kind == "ID":
            self.consume("ID")
            return Ref(t.value)
        raise SyntaxError(f"unexpected term: {t}")


def parse(src: str) -> Node:
    p = Parser(tokenize(src))
    node = p.parse_node()
    trailing = p.peek()
    if trailing is not None:
        raise SyntaxError(
            f"unexpected trailing token after top-level node: {trailing}"
        )
    return node


# ---------------------------------------------------------------------------
# Emitter — VSON-P AST → Turtle-star
# ---------------------------------------------------------------------------

# Triple is also imported from tools.vson_ast (see top of file).


class Emitter:
    def __init__(self, default_ns: str = DEFAULT_NS):
        self.default_ns = default_ns
        self.triples = []
        self.var_to_iri = {}
        self.declared_vars = set()  # variables introduced via `(var / Concept ...)`

    def iri_for_var(self, var: str) -> str:
        if var not in self.var_to_iri:
            # Vars beginning with '_' (e.g. auto-generated `_q1`, `_sf3`)
            # are treated as RDF blank nodes so graph-iso comparison
            # ignores their identity. Author-written vars (no leading
            # underscore) become named IRIs in the default namespace,
            # preserving Penman's reentrancy semantics. This is the
            # cross-syntax convention shared between VSON-P (where users
            # rarely if ever start vars with '_') and the VSON-X parser
            # (which always uses '_'-prefixed names for auto-generated
            # Quality / Stative / Event / SpatialFact nodes that have no
            # author-meaningful identity).
            #
            # The full var (underscores included) is the blank-node label:
            # an injective, always-valid Turtle BLANK_NODE_LABEL. The prior
            # `var.lstrip('_')` collapsed distinct vars (`_a`/`__a` → `a`)
            # and produced an invalid empty label for a bare `_`.
            if var.startswith("_"):
                self.var_to_iri[var] = f"_:{var}"
            else:
                self.var_to_iri[var] = f":{var}"
        return self.var_to_iri[var]

    def role_to_iri(self, role: str) -> str:
        if role in ROLE_NAMESPACE_OVERRIDES:
            return f"<{ROLE_NAMESPACE_OVERRIDES[role]}{role}>"
        return f"<{VSO}{role}>"

    def concept_to_iri(self, concept: str) -> str:
        return f"<{VSO}{concept}>"

    def render_string(self, raw: str) -> str:
        # Encode the true value into a single-line Turtle string literal.
        # Backslash MUST be escaped first; control chars become Turtle escapes
        # (a raw newline/CR/tab inside "..." is not valid Turtle).
        esc = (
            raw.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{esc}"'

    def render_number(self, raw: str) -> str:
        if "." in raw:
            return f'"{raw}"^^<http://www.w3.org/2001/XMLSchema#decimal>'
        return f'"{raw}"^^<http://www.w3.org/2001/XMLSchema#integer>'

    def route_bare_id(self, name: str, role: str) -> str:
        """Route a bare identifier in object position by role-specific rules.

        Precedence (role-as-literal wins over var-collision because lemmas /
        venues / styles are always string-typed by the spec, even when the
        token happens to share its spelling with a sibling node's var):
          1. If role is in ROLE_VALUE_AS_STRING, render as a string literal.
          2. If the name was declared as a node variable, it's a reentrant ref.
          3. If role is in ROLE_VALUE_TO_RCC and name is an RCC-8 base, route to rcc:.
          4. If role is in ROLE_VALUE_TO_VSO, route to vso:.
          5. Otherwise emit as a local IRI under the document namespace.
        """
        if role in ROLE_VALUE_AS_STRING:
            return self.render_string(name)
        if name in self.declared_vars:
            return self.iri_for_var(name)
        if role in ROLE_VALUE_TO_RCC and name in RCC_VALUES:
            return f"<{RCC}{name}>"
        if role in ROLE_VALUE_TO_VSO:
            return f"<{VSO}{name}>"
        return f":{name}"

    def term_to_iri(self, term, role: str) -> str:
        if isinstance(term, Node):
            return self.emit_node(term)
        if isinstance(term, Ref):
            return self.route_bare_id(term.var, role)
        if isinstance(term, Lit):
            if term.is_string:
                return self.render_string(term.value)
            if term.is_number:
                if role in ROLE_VALUE_AS_STRING:
                    return self.render_string(term.value)
                return self.render_number(term.value)
            return self.route_bare_id(term.value, role)
        raise TypeError(term)

    def collect_declared(self, node: Node) -> None:
        """First pass: register every variable that's introduced with `/ Concept`."""
        if node.concept is not None:
            self.declared_vars.add(node.var)
        for role, target in node.edges:
            if isinstance(target, Node):
                self.collect_declared(target)

    def emit_node(self, node: Node) -> str:
        subj = self.iri_for_var(node.var)
        if node.concept is not None:
            self.triples.append(Triple(subj, "a", self.concept_to_iri(node.concept)))
        for role, target in node.edges:
            if role in CONTAINER_ROLES:
                # container: target is a Node whose first edge is the actual
                # predicate, e.g. (charge :causes strike) under :causal —
                # which Penman parses as Node(var=charge, edges=[(causes, Ref(strike))])
                if not isinstance(target, Node):
                    raise SyntaxError(f"{role} container expects nested node")
                inner_subj = self.iri_for_var(target.var)
                for inner_role, inner_target in target.edges:
                    self.triples.append(Triple(
                        inner_subj,
                        self.role_to_iri(inner_role),
                        self.term_to_iri(inner_target, inner_role),
                    ))
                continue
            obj = self.term_to_iri(target, role)
            self.triples.append(Triple(subj, self.role_to_iri(role), obj))
        return subj

    def emit(self, root: Node) -> str:
        self.collect_declared(root)
        self.emit_node(root)
        head = (
            "@prefix vso:   <https://vson.dev/v1/ontology#> .\n"
            "@prefix allen: <https://vson.dev/v1/allen#> .\n"
            "@prefix rcc:   <https://vson.dev/v1/rcc8#> .\n"
            "@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .\n"
            f"@prefix :      <{self.default_ns}> .\n\n"
        )
        body = "\n".join(t.render() for t in self.triples)
        return head + body + "\n"


def to_turtle(src_text: str) -> str:
    ast = parse(src_text)
    return Emitter().emit(ast)


# ---------------------------------------------------------------------------
# Normalizer — for round-trip diffing
# ---------------------------------------------------------------------------

TRIPLE_LINE_RE = re.compile(r"^\s*([^\s].*?)\s+\.\s*$")


def normalize(text: str) -> str:
    """Strip prefixes/comments, sort triple lines, return canonical form.

    This is a *lexical* normalizer for diffing the emitter's output against
    a hand-authored Turtle file with simple triple shapes (no Turtle property
    lists or object lists). Documents using compact Turtle features should be
    expanded first via rdflib.
    """
    out_lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("@prefix"):
            continue
        m = TRIPLE_LINE_RE.match(s)
        if not m:
            continue
        out_lines.append(m.group(1).strip() + " .")
    out_lines.sort()
    return "\n".join(out_lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, path = argv[1], argv[2]
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"error: cannot read {path}: {e.strerror}", file=sys.stderr)
        return 2
    if cmd == "to-turtle":
        sys.stdout.write(to_turtle(text))
        return 0
    if cmd == "normalize":
        if path.endswith(".vson"):
            text = to_turtle(text)
        sys.stdout.write(normalize(text))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
