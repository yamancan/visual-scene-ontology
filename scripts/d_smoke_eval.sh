#!/usr/bin/env bash
# Phase D smoke eval for the vson-extractor-x skill. Hits a running web dev
# server (default http://localhost:5173), submits each demo image with
# ?prompt=skill-x, records the envelope, and reports pass/fail against two
# gates:
#
#   1. parseable        — vson_x is non-empty
#   2. shacl_conform    — conformance.conforms is true
#
# Pass criteria (Phase D, gallery-x informed):
#   parseable      ≥ 70% of the images run (ceil)
#   shacl_conform  ≥ 70% of the images run (ceil)
#
# A third gate stood here until 2026-08-04: one image was pinned MUST-conform
# because a directional fact needs a viewer (Talmy). That image was withdrawn
# (spec/CHANGELOG.md), and the requirement it stood for is not carried by any
# one image — C5 and vss:DirectionalNeedsViewerShape decide it on every
# envelope, so shacl_conform above already refuses a directional fact with no
# viewer, whichever image produced it.
#
# The run covers the four bundled demos in web/static/demos. To widen it,
# drop extra images into tests/fixtures/d_smoke_images/ (not in-repo —
# create it yourself); symlinks are fine.
set -euo pipefail

API_URL="${API_URL:-http://localhost:5173/api/extract}"
DEMO_DIR="${DEMO_DIR:-web/static/demos}"
EXTRA_DIR="${EXTRA_DIR:-tests/fixtures/d_smoke_images}"
OUT_DIR="${OUT_DIR:-reports/d_smoke}"

mkdir -p "$OUT_DIR"

# Collect candidate images. Bundled demos first; extras (if any) appended.
IMAGES=()
for f in "$DEMO_DIR"/*.jpg; do
  [[ -f "$f" ]] && IMAGES+=("$f")
done
if [[ -d "$EXTRA_DIR" ]]; then
  for f in "$EXTRA_DIR"/*.jpg "$EXTRA_DIR"/*.jpeg "$EXTRA_DIR"/*.png; do
    [[ -f "$f" ]] && IMAGES+=("$f")
  done
fi

if (( ${#IMAGES[@]} == 0 )); then
  echo "no images found under $DEMO_DIR or $EXTRA_DIR" >&2
  exit 2
fi

echo "==> running smoke against ${#IMAGES[@]} images"
echo "    api:    $API_URL"
echo "    output: $OUT_DIR"

for img in "${IMAGES[@]}"; do
  name=$(basename "$img")
  base="${name%.*}"
  ext="${name##*.}"
  case "$ext" in
    jpg|jpeg) mime="image/jpeg" ;;
    png)      mime="image/png"  ;;
    *)        echo "skip $img (unsupported)"; continue ;;
  esac
  echo "  → $name"
  b64=$(base64 < "$img" | tr -d '\n')
  payload=$(jq -n \
    --arg b64 "$b64" \
    --arg mime "$mime" \
    --arg prompt 'skill-x' \
    '{image_b64:$b64, mime:$mime, prompt:$prompt}')
  curl -sS -X POST "$API_URL" \
    -H 'content-type: application/json' \
    --data-binary "$payload" \
    > "$OUT_DIR/${base}.json" || {
      echo "    request failed for $name" >&2
      echo '{"_error":"request_failed"}' > "$OUT_DIR/${base}.json"
    }
done

# Aggregate and decide.
python3 - "$OUT_DIR" <<'PY'
import json, glob, sys, pathlib

out = pathlib.Path(sys.argv[1])
files = sorted(out.glob('*.json'))
if not files:
    print('no result files'); sys.exit(2)

results = []
for f in files:
    try:
        env = json.loads(f.read_text())
    except Exception:
        env = {'_error': 'unparseable'}
    name = f.stem
    parseable = bool(env.get('vson_x'))
    conforms = bool(env.get('conformance', {}).get('conforms'))
    results.append((name, parseable, conforms, env))

n = len(results)
parseable_ct = sum(1 for _, p, _, _ in results if p)
shacl_ct = sum(1 for _, _, c, _ in results if c)

mass  = next((r for r in results if r[0] == 'kitchen'), None)
mass_pass  = bool(mass and mass[2])

print()
print('=' * 60)
print(f'parseable:        {parseable_ct}/{n}')
print(f'shacl_conform:    {shacl_ct}/{n}')
print(f'mass_gate:        {"pass" if mass_pass else "fail"} (kitchen.jpg, soft)')
print('=' * 60)

# Per-image summary.
for name, p, c, env in results:
    src = env.get('vson_x', '')[:60].replace('\n', ' ⏎ ')
    flag = '✓' if c else ('~' if p else '✗')
    print(f'  {flag} {name:<20} {src}')

threshold = -(-n * 7 // 10)  # ceil(0.7n) — 70% of whatever was run
ok = parseable_ct >= threshold and shacl_ct >= threshold
print()
print('GATE:', 'PASS' if ok else 'FAIL', f'(threshold {threshold}/{n})')
sys.exit(0 if ok else 1)
PY
