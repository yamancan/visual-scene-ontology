"""
Corpus-level conformance check for the vson-extractor-x skill.

Walks examples/gallery-x/*.x.vson, transpiles each to Turtle via the canonical
Python parser (tools.vson_x.vson_x.to_turtle), and validates against the
strict SHACL profile (shapes/vson-shapes.ttl + ontology). Fails if any example
in the corpus does not conform — those are the worked examples shipped inside
the skill prompt, so divergence between the prompt and the corpus would teach
the LLM bad patterns.

Independent of LLM-emission smoke (scripts/d_smoke_eval.sh): this gate runs
in CI without API credentials.

Usage (from the repo root, so the `tools` package resolves):
    python3 -m tools.vson_x.skill_check
    python3 -m tools.vson_x.skill_check --corpus examples/gallery-x \\
        --config skills/vson-extractor-x/conformance.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import List, Tuple

from rdflib import Graph

from tools.shacl_helper import validate_graph
from tools.vson_x.vson_x import to_turtle

# Repo root, used only to default --corpus/--config and to shorten printed
# paths — tools/vson_x/skill_check.py -> tools/vson_x -> tools -> repo root.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def evaluate(path: str) -> Tuple[bool, str]:
    """Return (conforms, message). Captures exceptions as parse failures."""
    try:
        src = open(path, "r", encoding="utf8").read()
    except OSError as e:
        return False, f"read error: {e}"
    try:
        ttl = to_turtle(src)
    except Exception as e:  # noqa: BLE001 — broad on purpose; surface any error
        return False, f"transpile error: {e}"
    try:
        g = Graph().parse(data=ttl, format="turtle")
    except Exception as e:  # noqa: BLE001
        return False, f"turtle parse error: {e}"
    conforms, report = validate_graph(g)
    if conforms:
        return True, f"conforms ({len(g)} triples)"
    return False, report.strip().splitlines()[0] if report else "non-conforming"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus",
        default=os.path.join(_REPO, "examples/gallery-x"),
        help="directory containing *.x.vson files",
    )
    ap.add_argument(
        "--config",
        default=os.path.join(_REPO, "skills/vson-extractor-x/conformance.json"),
        help="path to skill conformance.json (for target_first_try threshold)",
    )
    args = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.corpus, "*.x.vson")))
    if not files:
        print(f"no *.x.vson under {args.corpus}", file=sys.stderr)
        return 2

    target = 1.0  # default: 100% of corpus must conform
    try:
        with open(args.config, "r", encoding="utf8") as f:
            cfg = json.load(f)
        if isinstance(cfg.get("target_first_try"), (int, float)):
            target = float(cfg["target_first_try"])
    except OSError:
        pass

    passed = 0
    print(f"==> VSON-X corpus skill-check ({len(files)} files, target {target:.2f})")
    for path in files:
        rel = os.path.relpath(path, _REPO)
        ok, msg = evaluate(path)
        flag = "OK  " if ok else "FAIL"
        print(f"  {flag} {rel:<50} {msg}")
        if ok:
            passed += 1

    rate = passed / len(files)
    print(f"\nresult: {passed}/{len(files)} pass ({rate:.0%})")
    if rate < target:
        print(f"FAIL: below target {target:.0%}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
