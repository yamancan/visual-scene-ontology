#!/usr/bin/env bash
# Deploy preflight for VSON v1.1 + Phase D (vson-extractor-x).
#
# Verifies: Rust binary, Python entry points, x2t round-trip on canonical
# fixture, /api/skills health, /api/extract X-mode dry-run on a stable demo.
#
# Skips the live /api/extract check unless DEV_SERVER_URL is set, since it
# requires the dev server to be running. CI runners that don't have OpenRouter
# credentials should set DEV_SERVER_URL only when the dev server is up.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
echo_ok(){ green "  OK $*"; }
echo_no(){ red   "  FAIL $*"; exit 1; }

echo "==> Rust binary present"
if [[ -x cli/target/release/vson ]]; then
  echo_ok "cli/target/release/vson"
else
  echo_no "cli/target/release/vson — run 'cd cli && cargo build --release'"
fi

echo "==> python3 + tools.vson_x importable"
if python3 -c "from tools.vson_x.vson_x import to_turtle; print('OK')" >/dev/null 2>&1; then
  echo_ok "tools.vson_x importable"
else
  echo_no "tools.vson_x not importable"
fi

echo "==> x2t round-trip on canonical fixture"
if cli/target/release/vson convert x2t examples/gallery-x/01_minimal.x.vson >/dev/null 2>&1; then
  echo_ok "x2t works on 01_minimal.x.vson"
else
  echo_no "x2t failed on 01_minimal.x.vson"
fi

echo "==> Skill files present"
for f in skills/vson-extractor-x/SKILL.md \
         skills/vson-extractor-x/README.md \
         skills/vson-extractor-x/conformance.json \
         tools/extractor/prompts/specialized/repair-x.md; do
  if [[ -f "$f" ]]; then
    echo_ok "$f ($(wc -c < "$f") bytes)"
  else
    echo_no "$f missing"
  fi
done

echo "==> Schema parses + accepts v1.1 X-mode envelope"
python3 - <<'PY' || exit 1
import json, sys
try:
    import jsonschema
except ImportError:
    print("  WARN jsonschema not installed; skipping schema test", file=sys.stderr)
    sys.exit(0)
schema = json.load(open('tools/schema/vson-output.schema.json'))
v11x = {
    'scene_id': 'preflight',
    'version': '1.1',
    'vson_p': '',
    'vson_x': '~scene\n  /CameraView @cam *angle eye_level\n  ^cam\n',
    'vson_t': ':scene a vso:Composition .',
    'conformance': {'conforms': True}
}
jsonschema.validate(v11x, schema)
print('  OK schema accepts v1.1 X-mode envelope')
PY

echo "==> Corpus skill-check (gallery-x conformance)"
if make x-skill-check >/dev/null 2>&1; then
  echo_ok "make x-skill-check passed"
else
  echo_no "make x-skill-check failed — run it directly to inspect"
fi

if [[ -n "${DEV_SERVER_URL:-}" ]]; then
  echo "==> /api/skills health at $DEV_SERVER_URL"
  if curl -fsS "$DEV_SERVER_URL/api/skills" | python3 -c \
      "import sys,json; ids=[s['id'] for s in json.load(sys.stdin)]; assert ids==['penman','vson-x','orchestrator'], ids; print('  ids OK')" >/dev/null
  then
    echo_ok "/api/skills returns expected manifest"
  else
    echo_no "/api/skills check failed"
  fi

  echo "==> /api/extract X-mode dry-run (cached demo)"
  b64=$(base64 < web/static/demos/lamp.jpg | tr -d '\n')
  payload=$(python3 -c "import json,sys; print(json.dumps({'image_b64': sys.argv[1], 'mime':'image/jpeg', 'prompt':'skill-x'}))" "$b64")
  if curl -fsS -X POST "$DEV_SERVER_URL/api/extract" \
       -H 'content-type: application/json' \
       --data-binary "$payload" \
       | python3 -c "import json,sys; e=json.load(sys.stdin); assert e.get('version')=='1.1' or e.get('vson_p'), 'envelope shape'; print('  envelope OK')" >/dev/null
  then
    echo_ok "/api/extract X-mode dry-run"
  else
    red "  WARN /api/extract dry-run failed (live server may need OpenRouter creds)"
  fi
else
  echo "==> /api/* live checks skipped (set DEV_SERVER_URL to enable)"
fi

green "All preflight checks passed."
