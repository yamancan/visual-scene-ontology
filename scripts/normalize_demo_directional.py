#!/usr/bin/env python3
"""Normalize camelCase directional/proximal values in demo envelopes to the
canonical snake_case, then refresh each envelope's stored conformance report.

The bake/extractor path can emit camelCase (leftOf, rightOf, inFrontOf, nextTo);
the ontology + SHACL canonical form is snake_case (left_of, right_of,
in_front_of, next_to), matching docs/vson.md and the gallery. The value-token
rewrite is done on raw text so existing formatting is preserved; the stored
conformance is only re-serialized when it is actually stale.

Run after baking demos:  python3 scripts/normalize_demo_directional.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

import rdflib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.shacl_helper import validate_graph  # noqa: E402

ENV_DIR = os.path.join(ROOT, "web/static/demos/envelopes")
REPL = {
    "leftOf": "left_of",
    "rightOf": "right_of",
    "inFrontOf": "in_front_of",
    "nextTo": "next_to",
}


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def main() -> int:
    files = sorted(glob.glob(os.path.join(ENV_DIR, "**", "*.json"), recursive=True))
    token_fixed = conf_fixed = 0
    for f in files:
        if os.path.basename(f) == "index.json":
            continue
        rel = os.path.relpath(f, ROOT)

        # 1) format-preserving value rewrite
        raw = _read(f)
        new = raw
        for a, b in REPL.items():
            new = new.replace(a, b)
        if new != raw:
            _write(f, new)
            token_fixed += 1
            print(f"  token-normalized {rel}")

        # 2) refresh stored conformance only if stale
        env = json.loads(_read(f))
        vson_t = env.get("vson_t")
        if not vson_t:
            continue
        g = rdflib.Graph()
        g.parse(data=vson_t, format="turtle")
        conforms, _ = validate_graph(g)
        stored = env.get("conformance", {}) or {}
        stale = bool(stored.get("conforms")) != bool(conforms) or (
            conforms and (stored.get("violations") or [])
        )
        if stale:
            env["conformance"] = {"conforms": bool(conforms), "violations": []}
            _write(f, json.dumps(env, indent=2, ensure_ascii=False) + "\n")
            conf_fixed += 1
            print(f"  conformance-refreshed {rel} (conforms={conforms})")

    print(f"normalize: {token_fixed} value-rewritten, {conf_fixed} conformance-refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
