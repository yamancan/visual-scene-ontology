# Specialized Prompt — SHACL Repair

> Used at stage S8 when SHACL validation of the orchestrator's emission fails.
> Receives: the failed VSON-P document + the SHACL report.
> Returns: a corrected VSON-P document.

---

```
The previous VSON-P document failed SHACL validation. Below is the document
and the SHACL report. Produce a CORRECTED document that addresses every
violation. Apply the minimum patch necessary; do not rewrite unaffected parts.

# RULES

1. Address every violation in the report.
2. Preserve all conformant content unchanged.
3. Use only VSV vocabulary.
4. Output begins with `(` and ends with `)`. No prose, no markdown fences.

# COMMON VIOLATIONS AND FIXES

- "Directional spatial facts require a vso:viewer (CameraView)":
  Add `:viewer <camera_var>` to the SpatialFact, where <camera_var> is the
  CameraView declared in this document's Composition.

- "Event must have exactly one vso:lemma":
  Add `:lemma <verb>` to the Event. Pick the most plausible verb from the
  thematic-role pattern (agent + patient → strike/hit; agent + goal →
  approach/charge; experiencer + stimulus → look_at/notice).

- "Quality must have exactly one vso:dimension and one vso:value":
  Add the missing one; if both are missing, drop the Quality.

- "vso:depicts must point to an Entity, not a Frame":
  Move the Frame node from `:depicts` to `:framedBy`.

- "Composition must depict at least one Entity":
  Add at least one PhysicalObject (use class Unknown if needed).

- "rcc value must be one of the eight RCC-8 relations":
  Replace with the closest of {DC, EC, PO, EQ, TPP, NTPP, TPPi, NTPPi}. If
  uncertain, drop `:rcc` and keep only `:directional` or `:proximal`.

# THE FAILED DOCUMENT

{{FAILED_DOCUMENT}}

# THE SHACL REPORT

{{SHACL_REPORT}}

# YOUR CORRECTED DOCUMENT (single Penman tree, nothing else)
```
