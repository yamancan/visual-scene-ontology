# Specialized Prompt — VSON-X SHACL Repair

> Used when the VSON-X emission fails parse, x2t transpile, or SHACL validation.
> Receives: the failed VSON-X document + the parser/SHACL report.
> Returns: a corrected VSON-X document.

---

```
You previously emitted a VSON-X document that failed validation.
The first character of your fix MUST be `~`. Do NOT switch to Penman parens
`(scene ...)`. Apply the minimum patch necessary; preserve conformant lines.

# HARD RULES (do not violate)

1. First line starts with `~scene` (optionally followed by Composition `*K V`).
2. Output is VSON-X only. No Penman, no prose, no markdown fences.
3. Address every violation in the report. Use only VSV vocabulary.

# COMMON VIOLATIONS AND FIXES

- "Directional spatial facts require a vso:viewer (CameraView)":
  Add `^cam` to the `!` SpatialFact line BEFORE the `*dir` token. Example:
  `crown ! EC alice ^cam *dir above`. The viewer must reference a declared
  CameraView handle. If your scene has no CameraView, add `/CameraView @cam
  *angle eye_level *focalLength 50mm *framing medium_shot` and a top-level
  `^cam` line right after it.

- "Event must have exactly one vso:lemma":
  Each `>>` arrow must carry a lemma between the arrow and the rhs ref.
  Example: `@bob >> strike @boar *instrument @sword`.

- "Quality must have exactly one vso:dimension and one vso:value":
  `*K V` already provides both — `*color red` → dimension Color, value red.
  If you wrote `*color` without a value, add the value. If neither is right,
  remove the line.

- "vso:depicts must point to an Entity, not a Frame":
  Frames declared with `/CameraView`, `/VisualStyle`, `/SceneContext` attach
  via `framedBy` automatically — never reference them in entity-decl position.

- "Composition must depict at least one Entity":
  Add at least one entity line, e.g. `obj /PhysicalObject Generic Inert Count *class Unknown`.

- "rcc value must be one of the eight RCC-8 relations":
  Replace the relation token between `!` and the ground ref with one of
  `DC EC PO EQ TPP NTPP TPPi NTPPi`.

- "Wrong sigil for lemma":
  - `>>` is for Event/Process lemmas (`strike, throw, run, walk, charge, ...`).
  - `>` is for Stative lemmas (`hold, wear, sit, look_at, see, ...`).
  Swap the sigil to match the lemma.

- "Symmetric & lemma not allowed":
  `&` only works with `near, far, adjacent`. Use `!` with a directional or
  RCC relation for everything else.

- "Penman drift":
  Your previous emission started with `(`. Replace the entire output. The
  first character of every VSON-X document is `~`.

# THE FAILED DOCUMENT

{{FAILED_DOCUMENT}}

# THE PARSER / SHACL REPORT

{{SHACL_REPORT}}

# YOUR CORRECTED DOCUMENT (single VSON-X document, first character `~`, nothing else)
```
