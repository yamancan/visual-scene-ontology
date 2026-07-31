#!/usr/bin/env python3
"""Normalize camelCase directional/proximal values in demo envelopes to the
canonical snake_case, then refresh each envelope's stored conformance report.

The bake/extractor path can emit camelCase (leftOf, rightOf, inFrontOf, nextTo);
the ontology + SHACL canonical form is snake_case (left_of, right_of,
in_front_of, next_to), matching docs/vson.md and the gallery. The value-token
rewrite is done on raw text so existing formatting is preserved; the stored
conformance is only re-serialized when it is actually stale.

Run after baking demos, from the repo root so the `tools` package resolves:
  python3 scripts/normalize_demo_directional.py
"""
from __future__ import annotations

import glob
import json
import os
import re

import rdflib

from tools.shacl_helper import validate_graph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV_DIR = os.path.join(ROOT, "web/static/demos/envelopes")
REPL = {
    "leftOf": "left_of",
    "rightOf": "right_of",
    "inFrontOf": "in_front_of",
    "nextTo": "next_to",
}
# Match only whole tokens (word boundaries), so a camelCase directional that
# happens to be a substring of unrelated text (a caption, an identifier like
# `nextToken`, a URL) is left untouched.
_REPL_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in REPL) + r")\b")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def main() -> int:
    files = sorted(glob.glob(os.path.join(ENV_DIR, "**", "*.json"), recursive=True))
    token_fixed = conf_fixed = non_conforming = 0
    for f in files:
        if os.path.basename(f) == "index.json":
            continue
        rel = os.path.relpath(f, ROOT)

        # 1) format-preserving value rewrite (whole-token, see _REPL_RE)
        raw = _read(f)
        new = _REPL_RE.sub(lambda m: REPL[m.group(1)], raw)
        if new != raw:
            _write(f, new)
            token_fixed += 1
            print(f"  token-normalized {rel}")

        # 2) refresh stored conformance from a real SHACL run. Parse `new`
        #    directly — it is already the on-disk content, so no second read.
        env = json.loads(new)
        vson_t = env.get("vson_t")
        if not vson_t:
            continue
        g = rdflib.Graph()
        g.parse(data=vson_t, format="turtle")
        conforms, report = validate_graph(g)
        stored = env.get("conformance", {}) or {}
        if conforms:
            # The snake_case rewrite cleared the directional violations: it is now
            # safe to record a clean report. Rewrite only when the stored record
            # disagrees (was non-conforming, or still carried violations).
            if not stored.get("conforms") or (stored.get("violations") or []):
                env["conformance"] = {"conforms": True, "violations": []}
                _write(f, json.dumps(env, indent=2, ensure_ascii=False) + "\n")
                conf_fixed += 1
                print(f"  conformance-refreshed {rel} (conforms=True)")
        else:
            # Genuinely non-conforming after normalization. Do NOT fabricate an
            # empty violation list — that would erase the diagnostic the studio
            # renders. Leave the stored record intact and surface the report.
            non_conforming += 1
            print(f"  WARNING {rel}: non-conforming after normalize; stored conformance left as-is")
            print("    " + report.strip().replace("\n", "\n    "))

    print(
        f"normalize: {token_fixed} value-rewritten, {conf_fixed} conformance-refreshed, "
        f"{non_conforming} non-conforming"
    )
    return 1 if non_conforming else 0


if __name__ == "__main__":
    raise SystemExit(main())
