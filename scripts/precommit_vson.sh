#!/usr/bin/env bash
# The `vson-validate` pre-commit hook (.pre-commit-hooks.yaml).
#
# pre-commit clones this repository, then runs this script with the staged
# documents as arguments, from the *user's* repository root. What it has to do
# that the plain `vson validate` line cannot is find a binary: this hook never
# downloads one, so a contributor who has never built the CLI has nothing on
# PATH, and a hook that fails with `command not found` teaches nobody anything.
#
# The search order, and the reason for each step:
#
#   1. $VSON_BIN            — an explicit override always wins, so a
#                             contributor testing a local build is never
#                             second-guessed.
#   2. `vson` on PATH       — an installed binary is the fast path and costs
#                             nothing.
#   3. cli/target/release/  — a build already sitting in this clone.
#   4. cargo build          — the fallback, announced rather than silent: it
#                             takes about twenty seconds the first time and
#                             nothing afterwards. Requires a Rust toolchain.
#
# The Python gates are a separate dependency and are *not* installed here: a
# commit hook that pip-installs into whatever interpreter it happens to find is
# a hook that edits the machine behind the user's back. It reports what is
# missing and the one command that fixes it.
#
# Exit codes are the CLI's own: 0 conformant, 1 a document failed a gate, 2 no
# verdict (which is what a missing toolchain reports, so a broken environment
# never reads as a bad document).

set -eo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$#" -eq 0 ]; then
  exit 0
fi

fail() {
  echo "vson-validate: $1" >&2
  exit 2
}

find_binary() {
  if [ -n "$VSON_BIN" ]; then
    [ -x "$VSON_BIN" ] || fail "\$VSON_BIN is set to $VSON_BIN, which is not executable."
    echo "$VSON_BIN"
    return
  fi
  if command -v vson > /dev/null 2>&1; then
    command -v vson
    return
  fi
  local built="$root/cli/target/release/vson"
  if [ -x "$built" ]; then
    echo "$built"
    return
  fi
  command -v cargo > /dev/null 2>&1 || fail \
    "no vson binary and no cargo to build one. Install a Rust toolchain
  (https://rustup.rs), put a built binary on PATH, or point \$VSON_BIN at one."
  echo "vson-validate: building the CLI from source, once (~20s)." >&2
  cargo build --release --quiet --manifest-path "$root/cli/Cargo.toml" >&2 \
    || fail "cargo build failed; the output above says why."
  echo "$built"
}

python3 -c "import pyshacl, rdflib, owlrl" > /dev/null 2>&1 || fail \
  "the validation gates need python3 with pyshacl, rdflib and owlrl.
  Install them:  python3 -m pip install pyshacl rdflib owlrl"

command -v pyshacl > /dev/null 2>&1 || fail \
  "the SHACL gate runs the \`pyshacl\` console script, which is not on PATH.
  It ships with the package:  python3 -m pip install pyshacl"

binary="$(find_binary)"

# --home pins the ontology, the shapes and the Python gates to this clone —
# the version the hook was pinned to in .pre-commit-config.yaml, rather than
# whatever a binary found on PATH happens to carry.
exec "$binary" validate --home "$root" "$@"
