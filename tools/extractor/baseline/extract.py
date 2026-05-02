"""
Bare-VLM baseline: image -> VSON-P -> Turtle -> SHACL.

Records one row per (image, prompt-variant) pair to results.csv.
Run live:  ANTHROPIC_API_KEY=sk-ant-... python extract.py --live --images images/
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.penman import vson_penman as vp  # noqa: E402
from tools.shacl_helper import validate_graph  # noqa: E402

MODEL = "claude-opus-4-7"
MAX_REPAIR_RETRIES = 3
HERE = Path(__file__).resolve().parent
SYSTEM_PROMPT = (ROOT / "tools/extractor/prompts/orchestrator-system.md").read_text()
REPAIR_PROMPT = (ROOT / "tools/extractor/prompts/specialized/repair.md").read_text()
USER_BARE = "No upstream tool evidence is available for this image. Emit your best VSON-P document directly from the image."


def _call(client, system_text, user_blocks):
    t0 = time.time()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_blocks}],
    )
    dt_ms = int((time.time() - t0) * 1000)
    text = "".join(b.text for b in msg.content if b.type == "text")
    return text, dt_ms, msg.usage.input_tokens, msg.usage.output_tokens


def _shacl_ok(penman_text):
    try:
        ttl = vp.to_turtle(penman_text)
    except Exception as e:
        return False, f"penman_parse_error: {e}", None
    import rdflib
    g = rdflib.Graph()
    try:
        g.parse(data=ttl, format="turtle")
    except Exception as e:
        return False, f"turtle_parse_error: {e}", None
    conforms, report = validate_graph(g)
    return conforms, report, ttl


def run_one(client, image_path: Path, system_text: str):
    img_b64 = base64.standard_b64encode(image_path.read_bytes()).decode()
    media_type = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    user_blocks = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
        {"type": "text", "text": USER_BARE},
    ]
    text, dt_ms, in_tok, out_tok = _call(client, system_text, user_blocks)
    parse_ok, report, ttl = _shacl_ok(text)
    first_pass = parse_ok
    retries = 0
    while not parse_ok and retries < MAX_REPAIR_RETRIES:
        retries += 1
        repair_user = REPAIR_PROMPT.replace("{{FAILED_DOCUMENT}}", text).replace("{{SHACL_REPORT}}", str(report)[:2000])
        text, _, _, _ = _call(client, system_text, [{"type": "text", "text": repair_user}])
        parse_ok, report, ttl = _shacl_ok(text)
    return {
        "image": image_path.name,
        "shacl_first_try": first_pass,
        "shacl_after_retries": parse_ok,
        "retries": retries,
        "latency_ms": dt_ms,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="Make real API calls")
    ap.add_argument("--images", default=str(HERE / "images"))
    ap.add_argument("--prompt", default=str(ROOT / "tools/extractor/prompts/orchestrator-system.md"))
    ap.add_argument("--out", default=str(HERE / "results.csv"))
    args = ap.parse_args()
    if not args.live:
        print("dry run — pass --live with ANTHROPIC_API_KEY set to measure")
        return 0
    import anthropic
    client = anthropic.Anthropic()
    system_text = Path(args.prompt).read_text()
    images = sorted(p for p in Path(args.images).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    rows = [run_one(client, p, system_text) for p in images]
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    p_hat = sum(r["shacl_first_try"] for r in rows) / n
    print(f"n={n}  shacl_first_try={p_hat:.2%}  results -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
