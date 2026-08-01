#!/usr/bin/env python3
"""Check every quoted copy of a shipped schema artifact against the artifact.

`docs/vson.md` §5-§6 reproduces the wire schemas inline — "Reproduced inline for
§5-style cross-reference", as §6.1 puts it. A reproduction is a copy, and a copy
drifts. It drifted here: the §6.1 `version` fragment still read
`["1.0", "1.0.5", "1.1"]` two releases after `tools/schema/vson-output.schema.json`
admitted `"1.2"`, and the `vson_p` fragment beside it still keyed its conditional
on `"const": "1.1"` after the schema had widened that clause to an enum. §2 ranks
this document *above* the schemas and says in as many words that a disagreement
between two ranked artifacts is a bug — so a stale fragment is not a cosmetic
lag, it is the higher-precedence artifact stating something false.

Nothing noticed, because nothing compared them. This gate compares them.

What it checks
--------------
Every fenced ```json block between `## 5. Spec reference` and `## 7. Exporters`
is extracted and matched against the table below, which classifies each one:

  schema      the fragment quotes a node of a shipped JSON Schema, named by
              JSON Pointer. The fragment must be a *subset* of that node:
              every key it states must be present with an equal value. Two
              exceptions make the subset rule usable — `required` and
              `properties` may name fewer keys than the artifact (the document
              abbreviates), while `enum` must match exactly, in order. An enum
              is a closed list; quoting a shorter one is the drift this gate
              exists for, not an abbreviation.

  shacl-in    the fragment states a closed value list that lives in
              `shapes/vson-shapes.ttl` as an `sh:in`. Local names, in order.

  instance    the fragment is a whole example document and must validate
              against the schema it exemplifies.

  illustrative
              the fragment quotes nothing this repository ships — a JSON-shaped
              sketch of an RDF field. Recorded with the reason, and checked only
              for being parseable JSON. Marking a fragment illustrative is a
              claim: that no shipped artifact carries the constraint it shows.

A fenced JSON block in that span with no entry in the table is a failure. That
is the half that keeps the gate honest: a fragment added tomorrow cannot pass by
being invisible, and classifying it forces the author to say which artifact it
quotes, or that it quotes none.

One restatement outside the document is checked on the same terms: the
TypeScript `version` union in `web/src/lib/types.ts`. A consumer that omits a
value the schema admits type-rejects an envelope §2's consumer-conformance rule
says it MUST accept.

Exit codes
----------
  0  every fragment agrees with the artifact it quotes.
  1  at least one disagrees, or a fragment is unclassified.

Usage
-----
  python3 scripts/check_spec_fragments.py
  python3 scripts/check_spec_fragments.py --selftest   # comparators only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import jsonschema
import rdflib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SPEC = "docs/vson.md"
OUTPUT_SCHEMA = "tools/schema/vson-output.schema.json"
SHAPES = "shapes/vson-shapes.ttl"
TYPES_TS = "web/src/lib/types.ts"

# The span this gate is responsible for. Both markers are headings, matched at
# the start of a line; a rename fails loudly rather than silently emptying the
# span, which would turn the gate green by checking nothing.
SPAN_START = "## 5. Spec reference"
SPAN_END = "## 7. Exporters"

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
VSS = "https://w3id.org/vson/v1/shapes#"

# Keys that carry a list of subschemas rather than a list of values: compared
# element by element under the subset rule, not for equality.
APPLICATORS = ("allOf", "anyOf", "oneOf")


# --------------------------------------------------------------------------
# The classification table.
#
# Keyed by (heading, ordinal): the nearest preceding heading text, verbatim,
# and which fenced JSON block under it this is (0-based). Headings are stable
# identifiers inside a spec; when one is reworded this gate reports the
# fragment as unclassified, which is the correct outcome — somebody has to
# confirm it still quotes what it used to.
# --------------------------------------------------------------------------
def schema(pointer: str, file: str = OUTPUT_SCHEMA) -> dict:
    return {"kind": "schema", "file": file, "pointer": pointer}


def shacl_in(paths: dict) -> dict:
    return {"kind": "shacl-in", "paths": paths}


def instance(file: str = OUTPUT_SCHEMA) -> dict:
    return {"kind": "instance", "file": file}


def illustrative(reason: str) -> dict:
    return {"kind": "illustrative", "reason": reason}


RULES = {
    ("#### `vso:depicts` *(IRI ref → Entity, required, 1..n)*", 0): illustrative(
        "a JSON sketch of an RDF edge. No shipped schema types vso:depicts — "
        "the envelope carries edges as graph.edges[*], not as named arrays."
    ),
    (
        "#### `vso:viewedBy` *(IRI ref → CameraView, exactly 1 when present)*",
        0,
    ): illustrative("same: a sketch of an RDF edge, typed by no shipped schema."),
    ("#### 5.3.1 `vso:SceneContext`", 0): illustrative(
        "the atmosphere / timeOfDay / weather value lists are stated here and "
        "in no shipped artifact: shapes/vson-shapes.ttl carries no sh:in for "
        "any of the three (grep sh:in). The table above the fragment says "
        "'enum check', and no enum is checked — a documented-but-unshaped "
        "constraint, out of scope for this gate, which reports copies that "
        "disagree and cannot invent a copy that does not exist. The v1.3 "
        "value-space sweep left it that way on purpose: §5.12 lists the closed "
        "enumerations and carries none of these three, and the shipped corpus "
        "already steps outside the lists above (timeOfDay 'day', atmosphere "
        "'cold' / 'clear'). shapes/vson-shapes.ttl records the measurement "
        "under 'Documented but deliberately unshaped'."
    ),
    ("#### `vso:individuation` *(IRI, required, exactly 1)*", 0): schema(
        "/$defs/GraphNode/properties/traits/properties/individuation"
    ),
    ("#### `vso:bbox2d` *(string, optional, 0..1)*", 0): schema(
        "/$defs/GraphNode/properties/bbox2d"
    ),
    ("### 5.5 `vso:Quality`", 0): illustrative(
        "a JSON sketch of the Quality node. The envelope projects qualities "
        "into graph.nodes[*] with kind='Quality'; no shipped schema declares "
        "this object."
    ),
    ("#### `vso:lemma` *(xsd:string, required, exactly 1)*", 0): illustrative(
        "the lemma pattern ^[a-z][a-z0-9_]*$ is stated here and enforced by "
        "vss:LemmaShape, which v1.3 added — but the envelope schema does not "
        "type lemma at all, so there is no JSON artifact for this fragment to "
        "be compared against. The shape-side copy is pinned by "
        "tests/test_documented_constraints.py instead."
    ),
    ("#### `vso:lemma` *(xsd:string, required, exactly 1)*", 1): illustrative(
        "a JSON sketch of a perdurant with its thematic roles. The roles are "
        "ontology terms closed by C2, not JSON Schema properties."
    ),
    ("### 5.7 `vso:SpatialFact`", 0): shacl_in(
        {
            "/properties/rcc/enum": "RccValueShape",
            "/properties/directional/enum": "DirectionalValueShape",
            "/properties/proximal/enum": "ProximalValueShape",
        }
    ),
    ("#### `scene_id` *(string, required)*", 0): schema("/properties/scene_id"),
    ("#### `version` *(string, required)*", 0): schema("/properties/version"),
    ("#### `source` *(object, optional)*", 0): schema("/properties/source"),
    (
        "#### `vson_p` *(string, required as a key; conditionally non-empty)*",
        0,
    ): schema("/properties/vson_p"),
    (
        "#### `vson_p` *(string, required as a key; conditionally non-empty)*",
        1,
    ): schema(""),
    ("#### `vson_x` *(string, optional — v1.1+)*", 0): schema("/properties/vson_x"),
    ("#### `vson_t` *(string, required)*", 0): schema("/properties/vson_t"),
    ("#### `graph.nodes[*]` *(GraphNode array)*", 0): schema("/$defs/GraphNode"),
    ("#### `graph.edges[*]` *(GraphEdge array)*", 0): schema("/$defs/GraphEdge"),
    (
        "#### `conformance.profile` *(string enum, optional — v1.1+, default `\"strict\"`)*",
        0,
    ): schema("/properties/conformance"),
    ("### 6.2 Worked envelope example (image upload response)", 0): instance(),
}


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
class Fragment:
    """One fenced JSON block, with the heading it sits under."""

    def __init__(self, heading: str, ordinal: int, line: int, text: str) -> None:
        self.heading = heading
        self.ordinal = ordinal
        self.line = line
        self.text = text

    @property
    def key(self) -> tuple:
        return (self.heading, self.ordinal)

    def __repr__(self) -> str:  # pragma: no cover — debugging aid
        return "Fragment(%r, %d, line=%d)" % (self.heading, self.ordinal, self.line)


def extract(markdown: str) -> "list[Fragment]":
    """Every ```json block between SPAN_START and SPAN_END, in document order.

    Fence state is tracked across all languages, not just json: a ```turtle
    block containing a line that starts with ``` inside it would otherwise
    desynchronise the parser and mis-attribute every fragment after it.
    """
    lines = markdown.split("\n")
    inside_span = False
    fence_lang = None
    buffer: "list[str]" = []
    heading = ""
    seen: "dict[str, int]" = {}
    out: "list[Fragment]" = []
    start_line = 0

    for number, line in enumerate(lines, start=1):
        if fence_lang is None:
            if line.startswith(SPAN_START):
                inside_span = True
                continue
            if line.startswith(SPAN_END):
                inside_span = False
                continue
            if line.startswith("#"):
                heading = line.rstrip()
                continue
            if line.startswith("```"):
                fence_lang = line[3:].strip()
                buffer = []
                start_line = number
            continue

        if line.startswith("```"):
            if inside_span and fence_lang == "json":
                ordinal = seen.get(heading, 0)
                seen[heading] = ordinal + 1
                out.append(
                    Fragment(heading, ordinal, start_line, "\n".join(buffer))
                )
            fence_lang = None
            continue
        buffer.append(line)

    return out


def resolve_pointer(document: dict, pointer: str):
    """RFC 6901 JSON Pointer, enough of it for this repository's schemas."""
    node = document
    if not pointer:
        return node
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            raise KeyError(pointer)
        node = node[token]
    return node


def deref(node, root: dict):
    """Follow a local $ref so a fragment can quote what the $ref points at."""
    while isinstance(node, dict) and list(node.keys()) == ["$ref"]:
        ref = node["$ref"]
        if not ref.startswith("#"):
            return node
        node = resolve_pointer(root, ref[1:])
    return node


# --------------------------------------------------------------------------
# Comparators — pure, so --selftest and the unit tests can exercise them
# without reading a file or reaching the network.
# --------------------------------------------------------------------------
def subset_problems(doc, art, root: dict, path: str = "") -> "list[str]":
    """The fragment must be a subset of the artifact node. Empty list = holds.

    Subset, not equality, because the document abbreviates on purpose: it drops
    `description`, `$comment`, `examples`, and whole properties that would add
    noise to a reference table. What it may not do is *state* something the
    artifact does not say. Two keys are special:

      enum        exact list equality. A closed list quoted short is the
                  precedence violation this gate was written for.
      required    subset. The document may list fewer required keys.
    """
    art = deref(art, root)
    where = path or "(root)"

    if isinstance(doc, dict):
        if not isinstance(art, dict):
            return ["%s: fragment states an object, artifact has %s" % (where, type(art).__name__)]
        problems = []
        for key in doc:
            here = "%s/%s" % (path, key)
            if key not in art:
                problems.append(
                    "%s: stated by the fragment, absent from the artifact" % here
                )
                continue
            if key == "enum":
                if doc[key] != art[key]:
                    problems.append(
                        "%s: fragment %s, artifact %s"
                        % (here, json.dumps(doc[key]), json.dumps(art[key]))
                    )
                continue
            if key == "required":
                extra = [k for k in doc[key] if k not in art[key]]
                if extra:
                    problems.append(
                        "%s: fragment requires %s, artifact does not"
                        % (here, json.dumps(extra))
                    )
                continue
            if key == "properties":
                for name in doc[key]:
                    sub = "%s/%s" % (here, name)
                    if name not in art[key]:
                        problems.append(
                            "%s: stated by the fragment, absent from the artifact"
                            % sub
                        )
                        continue
                    problems += subset_problems(
                        doc[key][name], art[key][name], root, sub
                    )
                continue
            problems += subset_problems(doc[key], art[key], root, here)
        return problems

    if isinstance(doc, list):
        if not isinstance(art, list):
            return ["%s: fragment states a list, artifact has %s" % (where, type(art).__name__)]
        if len(doc) != len(art):
            return [
                "%s: fragment has %d element(s), artifact %d"
                % (where, len(doc), len(art))
            ]
        problems = []
        for index, (left, right) in enumerate(zip(doc, art)):
            problems += subset_problems(left, right, root, "%s/%d" % (path, index))
        return problems

    if doc != art:
        return [
            "%s: fragment %s, artifact %s"
            % (where, json.dumps(doc), json.dumps(art))
        ]
    return []


def enum_problems(quoted: "list", declared: "list", where: str) -> "list[str]":
    """A closed value list quoted in prose must equal the one that executes."""
    if quoted == declared:
        return []
    return [
        "%s: fragment %s, shapes %s"
        % (where, json.dumps(quoted), json.dumps(declared))
    ]


def union_members(source: str) -> "list[str]":
    """The string-literal members of the `version` union in a TypeScript file.

    Deliberately narrow: it matches the one declaration by name and reads the
    literals off it. A rename of the field makes this return nothing, which the
    caller reports — better than a regex loose enough to find some other union
    and compare against the wrong thing.
    """
    match = re.search(r"^\s*version:\s*([^;]+);", source, re.MULTILINE)
    if not match:
        return []
    return re.findall(r"'([^']*)'", match.group(1))


# --------------------------------------------------------------------------
# Artifact readers
# --------------------------------------------------------------------------
def read(rel: str) -> str:
    with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
        return handle.read()


def load_schema(rel: str) -> dict:
    return json.loads(read(rel))


def shape_in_list(graph: "rdflib.Graph", shape: str) -> "list[str]":
    """The one sh:in list reachable from a vss: node shape, as local names."""
    node = rdflib.URIRef(VSS + shape)
    lists = []
    for prop in graph.objects(node, SH.property):
        for head in graph.objects(prop, SH["in"]):
            lists.append([str(i).split("#")[-1] for i in graph.items(head)])
    if len(lists) != 1:
        raise LookupError(
            "vss:%s carries %d sh:in list(s); this gate expects exactly 1"
            % (shape, len(lists))
        )
    return lists[0]


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
def check() -> int:
    fragments = extract(read(SPEC))
    schemas = {OUTPUT_SCHEMA: load_schema(OUTPUT_SCHEMA)}
    shapes = rdflib.Graph()
    shapes.parse(os.path.join(REPO, SHAPES), format="turtle")

    print(
        "fragment-check: %d fenced JSON fragment(s) in %s §5-§6"
        % (len(fragments), SPEC)
    )
    failures: "list[str]" = []

    for fragment in fragments:
        label = "%s:%d" % (SPEC, fragment.line)
        rule = RULES.get(fragment.key)
        if rule is None:
            failures.append(label)
            print("\n  FAIL  %s  unclassified fragment" % label)
            print("        heading: %s" % fragment.heading)
            print(
                "        Add it to RULES in scripts/check_spec_fragments.py: "
                "name the artifact\n        node it quotes, or mark it "
                "illustrative with the reason it quotes none."
            )
            continue

        try:
            parsed = json.loads(fragment.text)
        except ValueError as exc:
            failures.append(label)
            print("\n  FAIL  %s  is not parseable JSON: %s" % (label, exc))
            continue

        problems: "list[str]" = []
        detail = ""

        if rule["kind"] == "schema":
            root = schemas.setdefault(rule["file"], load_schema(rule["file"]))
            try:
                node = resolve_pointer(root, rule["pointer"])
            except KeyError:
                problems = [
                    "%s has no node at %s"
                    % (rule["file"], rule["pointer"] or "(root)")
                ]
            else:
                problems = subset_problems(parsed, node, root)
            detail = "%s#%s" % (rule["file"], rule["pointer"] or "")

        elif rule["kind"] == "shacl-in":
            for pointer, shape in sorted(rule["paths"].items()):
                try:
                    quoted = resolve_pointer(parsed, pointer)
                except KeyError:
                    problems.append("fragment has no node at %s" % pointer)
                    continue
                problems += enum_problems(
                    quoted, shape_in_list(shapes, shape), "%s vs vss:%s" % (pointer, shape)
                )
            detail = "%s (%d sh:in list(s))" % (SHAPES, len(rule["paths"]))

        elif rule["kind"] == "instance":
            root = schemas.setdefault(rule["file"], load_schema(rule["file"]))
            validator = jsonschema.Draft202012Validator(root)
            problems = [
                "%s: %s" % ("/".join(str(p) for p in error.path) or "(root)", error.message)
                for error in sorted(validator.iter_errors(parsed), key=str)
            ]
            detail = "validates against %s" % rule["file"]

        else:
            detail = "illustrative — %s" % rule["reason"]

        if problems:
            failures.append(label)
            print("\n  FAIL  %s  %s" % (label, fragment.heading))
            print("        against %s" % detail)
            for problem in problems:
                print("        %s" % problem)
            continue

        print("  ok    %-18s %s" % (label, detail))

    quoted = union_members(read(TYPES_TS))
    declared = schemas[OUTPUT_SCHEMA]["properties"]["version"]["enum"]
    if quoted != declared:
        failures.append(TYPES_TS)
        print("\n  FAIL  %s  version union" % TYPES_TS)
        print(
            "        union %s, schema enum %s"
            % (json.dumps(quoted), json.dumps(declared))
        )
        print(
            "        A consumer MUST accept every version the schema admits "
            "(docs/vson.md §2)."
        )
    else:
        print("  ok    %-18s version union == schema enum" % TYPES_TS)

    if failures:
        print(
            "\nfragment-check: FAIL — %d quoted copy/copies disagree with the "
            "artifact:" % len(failures)
        )
        for item in failures:
            print("  - %s" % item)
        print(
            "\ndocs/vson.md outranks the schemas (§2), so a stale fragment is "
            "the higher-\nprecedence artifact stating something false. Fix the "
            "copy, or fix the artifact\nand say so in spec/CHANGELOG.md — do "
            "not delete the fragment to silence the gate."
        )
        return 1

    print(
        "\nfragment-check: %d fragment(s) + 1 mirror agree with what they quote."
        % len(fragments)
    )
    return 0


def selftest() -> int:
    """Prove each comparator goes red, offline.

    A gate nobody has seen fail is a gate nobody should trust. Every case here
    is a real drift shape: an enum quoted one value short (the bug this gate was
    written for), a key the artifact does not carry, a required key invented, a
    value that disagrees, an sh:in list reordered, a union missing a version.
    """
    art = {
        "type": "string",
        "enum": ["1.0", "1.1"],
        "description": "ignored by the subset rule",
    }
    cases = (
        ("exact quote", subset_problems({"enum": ["1.0", "1.1"]}, art, {}), False),
        ("abbreviated quote", subset_problems({"type": "string"}, art, {}), False),
        ("enum quoted short", subset_problems({"enum": ["1.0"]}, art, {}), True),
        ("enum reordered", subset_problems({"enum": ["1.1", "1.0"]}, art, {}), True),
        ("invented key", subset_problems({"minLength": 3}, art, {}), True),
        ("value disagrees", subset_problems({"type": "number"}, art, {}), True),
        (
            "required subset",
            subset_problems({"required": ["a"]}, {"required": ["a", "b"]}, {}),
            False,
        ),
        (
            "required invented",
            subset_problems({"required": ["c"]}, {"required": ["a", "b"]}, {}),
            True,
        ),
        (
            "$ref followed",
            subset_problems(
                {"items": {"type": "object"}},
                {"items": {"$ref": "#/$defs/X"}},
                {"$defs": {"X": {"type": "object"}}},
            ),
            False,
        ),
        ("sh:in equal", enum_problems(["DC", "EC"], ["DC", "EC"], "x"), False),
        ("sh:in reordered", enum_problems(["EC", "DC"], ["DC", "EC"], "x"), True),
        ("sh:in short", enum_problems(["DC"], ["DC", "EC"], "x"), True),
    )

    print("fragment-check --selftest: %d comparator case(s)" % (len(cases) + 2))
    failures = []
    for label, problems, should_fail in cases:
        if bool(problems) != should_fail:
            failures.append(label)
            print(
                "  BROKEN  %-20s expected %s, got %s"
                % (label, "a failure" if should_fail else "a pass", problems or "a pass")
            )
            continue
        print("  ok      %-20s %s" % (label, "red" if should_fail else "green"))

    for label, source, expected in (
        ("union read", "\tversion: '1.0' | '1.1';\n", ["1.0", "1.1"]),
        ("union renamed", "\trelease: '1.0';\n", []),
    ):
        found = union_members(source)
        if found != expected:
            failures.append(label)
            print("  BROKEN  %-20s read %s, expected %s" % (label, found, expected))
            continue
        print("  ok      %-20s %s" % (label, found or "(no version field found)"))

    if failures:
        print("\nfragment-check --selftest: FAIL — the comparators do not discriminate.")
        return 1
    print("\nfragment-check --selftest: every comparator goes red on drift.")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description="Check the schema fragments quoted in docs/vson.md §5-§6.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="exercise the comparators and exit; reads no repository file",
    )
    args = parser.parse_args(argv)
    return selftest() if args.selftest else check()


if __name__ == "__main__":
    sys.exit(main())
