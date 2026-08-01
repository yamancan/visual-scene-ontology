#!/usr/bin/env bash
# Headless-browser hydration smoke for the static studio build.
#
# curl-level checks cannot see a client-side death: the page prerenders fully,
# then an uncaught error during hydration leaves every control inert (exactly
# the rolldown circular-chunk incident this gate exists to catch). A real
# browser executes the bundle and proves three things: zero uncaught errors,
# the prerendered shell is present, and client-side mounting actually ran
# (DemoStrip injects its demo thumbnails only after hydration).
#
# Dependency-free: drives the installed Chrome via CLI. Override with CHROME=.
set -euo pipefail

BUILD_DIR="${1:-web/build}"
[ -f "$BUILD_DIR/index.html" ] || {
	echo "browser-smoke: no build at $BUILD_DIR — run the web build first"
	exit 1
}

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
if [ ! -x "$CHROME" ]; then
	CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)"
fi
[ -n "$CHROME" ] && [ -x "$CHROME" ] || {
	echo "browser-smoke: no Chrome/Chromium found — set CHROME=/path/to/binary"
	exit 1
}

PORT="${PORT:-8799}"
python3 -m http.server "$PORT" -d "$BUILD_DIR" >/dev/null 2>&1 &
SRV=$!
trap 'kill "$SRV" 2>/dev/null || true' EXIT
sleep 1

LOG="$(mktemp)"
DOM="$(mktemp)"
"$CHROME" --headless=new --disable-gpu --enable-logging=stderr --v=0 \
	--virtual-time-budget=8000 --dump-dom "http://localhost:$PORT/" >"$DOM" 2>"$LOG" || true

if grep -q "Uncaught" "$LOG"; then
	echo "browser-smoke: FAIL — uncaught error during hydration:"
	grep "Uncaught" "$LOG"
	exit 1
fi
grep -q "drop image here" "$DOM" || {
	echo "browser-smoke: FAIL — prerendered shell missing from DOM"
	exit 1
}
IMG_COUNT="$(grep -o "<img" "$DOM" | wc -l | tr -d ' ')"
if [ "$IMG_COUNT" -lt 5 ]; then
	echo "browser-smoke: FAIL — hydration dead ($IMG_COUNT imgs; DemoStrip mounts >=5 thumbnails only after hydration)"
	exit 1
fi
echo "browser-smoke: OK — hydration live, $IMG_COUNT imgs, zero uncaught errors"
