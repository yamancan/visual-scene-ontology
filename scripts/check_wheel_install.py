#!/usr/bin/env python3
"""Prove that `pip install .` — not `-e .` — yields a working `import vson`.

Every other gate in this repository runs against the checkout, and an editable
install *is* the checkout: `tools/*.py` resolve `ontology/`, `shapes/` and
`cli/src/penman/routing-tables.json` one or three dirnames up from themselves,
`vson/_resources.py` resolves `skills/` and `tools/schema/` the same way, and in
a checkout every one of those paths is a real file. A wheel carries only what
`pyproject.toml` declares, so none of that is evidence about the distribution
people actually install — and for three releases it was false there:
`import vson` raised `VsonResourceError` on its first line.

This gate is the only place that difference is visible. It builds the wheel,
installs it into a throwaway virtualenv with nothing else in it, and runs the
API from a directory that is not the checkout and contains no `tools/` or
`vson/` to shadow the installed one. What it asserts is behaviour, not file
lists: three-gate verdicts on four inline documents, the emitter byte-equal to
the checkout's, an envelope parsed against the schema the wheel carries.

Network posture — this is a RELEASE gate, not part of `make check`
------------------------------------------------------------------
Building the wheel is offline: the venv gets `setuptools` from PyPI once and
then `pip wheel --no-build-isolation` reuses it rather than provisioning a
second isolated build environment. *Installing* it is not: `validate()` is
`pyshacl` + `rdflib` + `owlrl` and `Envelope.errors()` is `jsonschema`, all four
of them declared dependencies that a fresh venv has to fetch. A gate that needs
PyPI cannot be a gate that fails when PyPI is down, so `make check` and
`make check-all` do not run this; `make wheel-check` and a release do. A warm
pip cache makes it fast, never network-free.

The one thing here that *is* offline is the packaging pre-flight, which reads
`pyproject.toml` and the source tree: `[tool.setuptools] packages` is written
out by hand (the `tools._data.*` entries have no source directory, so
`packages.find` cannot be used alongside them), and a hand-written list is a
list someone will forget to extend. It runs first and needs no venv.

Usage
-----
  python3 scripts/check_wheel_install.py
  python3 scripts/check_wheel_install.py --keep      # leave the venv in place
  python3 scripts/check_wheel_install.py --preflight # the offline half only

Exit codes
----------
  0  the wheel installs and the full API works outside a checkout.
  1  it does not; the failure is printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The document every assertion below is built from — the smallest conformant
# scene in the gallery, and the one `make cli-check` already holds the two
# emitters byte-identical on.
WITNESS = "examples/gallery/01_minimal.vson"

# The same scene in the compact surface, so `from_x` is exercised against a
# document `make x-check` already round-trips rather than an invented one.
WITNESS_X = "examples/gallery-x/01_minimal.x.vson"

# A committed studio envelope. `make envelope-check` already validates every
# one of these against the strict shapes, so a parse failure here is about the
# wheel, never about the fixture.
ENVELOPE = "web/static/demos/envelopes/lamp.json"

VSO = "https://w3id.org/vson/v1/ontology#"
SCENE = "https://example.org/scene#"


# ---------------------------------------------------------------------------
# The offline half: the hand-written package list still covers the source tree
# ---------------------------------------------------------------------------


def declared_packages() -> "list[str]":
    """The `packages = [...]` list of `[tool.setuptools]`, in file order."""
    with open(os.path.join(REPO, "pyproject.toml"), encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(
        r"^\[tool\.setuptools\]$.*?^packages\s*=\s*\[(.*?)\]",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise SystemExit("pyproject.toml: no [tool.setuptools] packages list")
    return re.findall(r"\"([^\"]+)\"", match.group(1))


def importable_packages() -> "list[str]":
    """Every directory under `tools/` and `vson/` that `import` can reach."""
    found = []
    for top in ("tools", "vson"):
        for dirpath, dirs, names in os.walk(os.path.join(REPO, top)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            if "__init__.py" not in names:
                continue
            rel = os.path.relpath(dirpath, REPO)
            found.append(rel.replace(os.sep, "."))
    return sorted(found)


def preflight() -> "list[str]":
    declared = set(declared_packages())
    failures = []
    for package in importable_packages():
        if package not in declared:
            failures.append(
                "{} is importable but not in [tool.setuptools] packages — a "
                "wheel would not carry it".format(package)
            )
    for package in sorted(declared):
        if package.startswith("tools._data."):
            continue
        if not os.path.isfile(
            os.path.join(REPO, package.replace(".", os.sep), "__init__.py")
        ):
            failures.append(
                "{} is declared in [tool.setuptools] packages but has no "
                "__init__.py".format(package)
            )
    return failures


# ---------------------------------------------------------------------------
# The documents the installed package is asked about
# ---------------------------------------------------------------------------


def documents() -> "dict[str, str]":
    """One conformant document and one for each gate, all inline.

    The three failures are the checkout's own negative cases, lifted from
    `tests/test_validate_report.py`, and each is built so the two gates *before*
    it pass — the gates short-circuit in §2's order, so a document that fails
    SHACL can never demonstrate that OWL RL or C2 ran at all.
    """
    sys.path.insert(0, REPO)
    from tools.penman.vson_penman import to_turtle  # pure stdlib, no venv needed

    with open(os.path.join(REPO, WITNESS), encoding="utf-8") as fh:
        good = fh.read()
    turtle = to_turtle(good)

    return {
        # Conformant, in the authoring surface: transpiles, then passes all three.
        "good": good,
        # A SpatialFact with none of vso:rcc / vso:directional / vso:proximal.
        "bad_shacl": """(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing close_up)
   :depicts (a / PhysicalObject
               :individuation Generic :animacy Inert :countability Count :class Apple)
   :depicts (b / PhysicalObject
               :individuation Generic :animacy Inert :countability Count :class Apple)
   :viewedBy cam
   :hasFact (sf / SpatialFact :figure a :ground b :rel left_of))
""",
        # vso:Frame owl:disjointWith vso:Entity (ontology/vso.ttl).
        "bad_owl": turtle
        + "\n<{}ghost> a <{}Frame>, <{}Entity> .\n".format(SCENE, VSO, VSO),
        # A term in the VSO namespace that no ontology file declares (clause C2).
        "bad_c2": turtle
        + "\n<{}apple> <{}inventedRole> \"nothing\" .\n".format(SCENE, VSO),
        # What the installed emitter must reproduce byte for byte.
        "expected_turtle": turtle,
    }


# ---------------------------------------------------------------------------
# What runs inside the throwaway venv, from a directory that is not the checkout
# ---------------------------------------------------------------------------

ACCEPTANCE = r'''"""Run entirely inside the throwaway venv. Prints one line per assertion."""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "fixtures.json"), encoding="utf-8") as fh:
    FIX = json.load(fh)

CHECKS = 0


def ok(label, got, want):
    global CHECKS
    CHECKS += 1
    if got != want:
        print("  FAIL {}: {!r} != {!r}".format(label, got, want))
        sys.exit(1)
    shown = want
    if isinstance(want, str) and len(want) > 200:
        shown = "<{} bytes>".format(len(want))
    print("  ok   {}: {}".format(label, shown))


import vson

# Nothing here may come from a checkout: this process must be reading the
# installed distribution and only that.
site = os.path.realpath(FIX["site_packages"])
for module in (vson, sys.modules["tools"]):
    root = os.path.realpath(os.path.dirname(os.path.dirname(module.__file__)))
    ok("{} is installed, not a checkout".format(module.__name__), root, site)
ok("cwd is not the checkout", os.path.realpath(os.getcwd()) != FIX["repo"], True)

ok("vson.__version__", vson.__version__, FIX["version"])
ok("__all__ resolves", sorted(n for n in vson.__all__ if not hasattr(vson, n)), [])

# The three gates, on one conformant document and one per gate.
good = vson.validate(FIX["good"])
ok("validate(good).conforms", good.conforms, True)
ok("validate(good).gate", good.gate, None)
ok("validate(good).findings", good.findings, [])
for name, gate in (("bad_shacl", "shacl"), ("bad_owl", "owl-consistency"), ("bad_c2", "c2")):
    verdict = vson.validate(FIX[name])
    ok("validate({}).conforms".format(name), verdict.conforms, False)
    ok("validate({}).gate".format(name), verdict.gate, gate)
    ok("validate({}) has findings".format(name), bool(verdict.messages), True)

# The emitter, byte for byte against the checkout's.
ok("to_turtle == checkout emitter", vson.to_turtle(FIX["good"]), FIX["expected_turtle"])

# The rest of the surface, each of which reaches a different resource.
ok("from_x", vson.from_x(FIX["vson_x"]).count("Composition") >= 1, True)
ok("caption", vson.caption(FIX["good"]).strip() != "", True)
ok("fol", "Composition" in vson.fol(FIX["good"]), True)
ok("canon is stable", vson.canon(FIX["good"]), vson.canon(FIX["expected_turtle"]))
ok("denotes_same across syntaxes", vson.denotes_same(FIX["good"], FIX["expected_turtle"]), True)
ok("diff identical", vson.diff(FIX["good"], FIX["expected_turtle"]).identical, True)

# The envelope, against the schema the wheel carries.
envelope = vson.Envelope.from_json(FIX["envelope"])
ok("Envelope.scene_id", envelope.scene_id, FIX["envelope"]["scene_id"])
ok("Envelope.errors()", envelope.errors(), [])
ok("envelope_errors(round trip)", vson.envelope_errors(envelope.to_json()), [])
ok("Envelope.vson_t validates", vson.validate(envelope.vson_t, syntax="t").conforms, True)

# The prompts, read out of the data the wheel carries rather than the checkout.
ok("SKILL_PROMPT", vson.SKILL_PROMPT, FIX["skill_prompt"])
ok("SKILL_X_PROMPT length", len(vson.SKILL_X_PROMPT) > 0, True)
ok("REPAIR_PROMPT_TEMPLATE length", len(vson.REPAIR_PROMPT_TEMPLATE) > 0, True)
ok("validate_and_repair is callable", callable(vson.validate_and_repair), True)
ok("DEFAULT_SHAPES exists", os.path.isfile(vson.DEFAULT_SHAPES), True)

print("\nwheel-check: OK, {} assertions from {}".format(CHECKS, os.getcwd()))
'''


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run(argv, **kwargs) -> None:
    print("  $ {}".format(" ".join(argv)))
    # The child writes to the same terminal; without this its output lands
    # before every line this process has printed so far.
    sys.stdout.flush()
    subprocess.run(argv, check=True, **kwargs)


def venv_python(venv: str) -> str:
    binary = os.path.join(venv, "Scripts" if os.name == "nt" else "bin", "python")
    return binary + (".exe" if os.name == "nt" else "")


def site_packages(python: str) -> str:
    out = subprocess.run(
        [python, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Non-editable install acceptance gate.")
    ap.add_argument(
        "--keep",
        action="store_true",
        help="leave the virtualenv and its wheel behind for inspection",
    )
    ap.add_argument(
        "--preflight",
        action="store_true",
        help="run only the offline packaging check (no venv, no network)",
    )
    args = ap.parse_args()

    print("==> wheel-check: [tool.setuptools] packages covers the source tree")
    failures = preflight()
    if failures:
        print("wheel-check: FAIL")
        for line in failures:
            print("  - {}".format(line))
        return 1
    print("  OK {} package(s) declared".format(len(declared_packages())))
    if args.preflight:
        return 0

    work = tempfile.mkdtemp(prefix="vson-wheel-check-")
    venv = os.path.join(work, "venv")
    wheels = os.path.join(work, "wheels")
    neutral = os.path.join(work, "neutral")
    os.makedirs(neutral)
    try:
        print("\n==> wheel-check: a virtualenv with nothing in it ({})".format(venv))
        run([sys.executable, "-m", "venv", venv])
        python = venv_python(venv)
        run([python, "-m", "pip", "install", "--quiet", "--upgrade",
             "pip", "setuptools>=61", "wheel"])

        print("\n==> wheel-check: build the wheel with that venv's setuptools")
        # --no-build-isolation: the venv already has the declared build backend,
        # so this step provisions nothing and touches no index.
        run([python, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
             "--wheel-dir", wheels, REPO])
        built = sorted(f for f in os.listdir(wheels) if f.endswith(".whl"))
        if len(built) != 1:
            print("wheel-check: FAIL — expected one wheel, got {}".format(built))
            return 1
        wheel = os.path.join(wheels, built[0])
        print("  built {}".format(built[0]))

        print("\n==> wheel-check: install it, with its declared dependencies")
        run([python, "-m", "pip", "install", "--quiet", wheel])

        print("\n==> wheel-check: run the API from {}".format(neutral))
        fixtures = documents()
        with open(os.path.join(REPO, ENVELOPE), encoding="utf-8") as fh:
            fixtures["envelope"] = json.load(fh)
        with open(
            os.path.join(REPO, "skills/vson-extractor/SKILL.md"), encoding="utf-8"
        ) as fh:
            fixtures["skill_prompt"] = fh.read()
        with open(os.path.join(REPO, WITNESS_X), encoding="utf-8") as fh:
            fixtures["vson_x"] = fh.read()
        fixtures["version"] = version_of()
        fixtures["repo"] = os.path.realpath(REPO)
        fixtures["site_packages"] = site_packages(python)

        with open(os.path.join(neutral, "fixtures.json"), "w", encoding="utf-8") as fh:
            json.dump(fixtures, fh)
        script = os.path.join(neutral, "acceptance.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(ACCEPTANCE)

        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        # A venv still honours ~/.local site-packages; a checkout installed there
        # would make this gate assert nothing.
        env["PYTHONNOUSERSITE"] = "1"
        run([python, script], cwd=neutral, env=env)
    finally:
        if args.keep:
            print("\nwheel-check: kept {}".format(work))
        else:
            shutil.rmtree(work, ignore_errors=True)
    return 0


def version_of() -> str:
    with open(os.path.join(REPO, "pyproject.toml"), encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(
        r"^\[project\]$.*?^version\s*=\s*[\"']([^\"']+)[\"']",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise SystemExit("pyproject.toml: no [project] version")
    return match.group(1)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print("\nwheel-check: FAIL — {} exited {}".format(exc.cmd[0], exc.returncode))
        sys.exit(1)
