//! `vson verify --geometry <files...>` — the checks that are not conformance.
//!
//! `validate` answers one question: is this a conformant VSON document (C1–C9,
//! docs/vson.md §2)? `verify` is where everything else lives — properties worth
//! checking that no numbered clause requires, and that a document may fail
//! while staying fully conformant.
//!
//! Today there is exactly one, `--geometry`: when a `vso:SpatialFact`'s figure
//! and ground both carry a `vso:bbox2d`, the document has asserted two things
//! that can disagree, and `tools/geometry_check.py` reports the disagreements
//! (§5.13). What it establishes is **coherence between the document's own
//! claims** — the rectangles it states against the relations it states. It
//! opens no image, and a clean run is not evidence about the picture (§2.1).
//!
//! **The check must be named.** Running `vson verify` with no check flag is a
//! usage error rather than a shorthand for "all of them". A second check landing
//! next year would otherwise silently change what an existing command line
//! means, and a caller who wrote `vson verify` in CI would start failing on a
//! property they never asked about. Naming the check keeps a command line's
//! meaning fixed for as long as the flag exists.
//!
//! Exit contract, the same three codes as `validate`:
//!   0 — every input cleared every requested check;
//!   1 — an input genuinely failed one (a relation its own geometry refutes);
//!   2 — a check never reached a verdict (no python3, no `--home`, unparseable
//!       input), or no check was named.

use super::gates::{
    python_gate, require_script, transpile_to_temp, vson_home, GateRun, PyGate, TempFile,
};
use super::{Error, Result};
use std::path::{Path, PathBuf};

const GEOMETRY_GATE: PyGate = PyGate {
    module: "tools.geometry_check",
    script: "tools/geometry_check.py",
    tell: "geometry-consistency:",
    what: "the geometry consistency gate",
    label: "geometry",
};

/// The checks `verify` knows about, for the "name one" error message. One
/// entry today; the list is what makes adding the second one cheap.
const AVAILABLE: &[&str] = &["--geometry  asserted relations vs the document's own bbox2d (§5.13)"];

pub fn run(files: &[PathBuf], home: Option<&Path>, geometry: bool, verbose: bool) -> Result<()> {
    if !geometry {
        return Err(Error::Usage(format!(
            "vson verify: name a check to run. Available:\n  {}",
            AVAILABLE.join("\n  ")
        )));
    }
    let home = vson_home(home);
    require_script(&GEOMETRY_GATE, &home)?;

    let mut any_failed = false;
    for file in files {
        // The guard lives for the whole iteration: the transpiled Turtle is on
        // disk while the checker reads it, and gone after.
        let transpiled = match file.extension().and_then(|e| e.to_str()) {
            Some("vson") => Some(transpile_to_temp(file)?),
            _ => None,
        };
        let data = transpiled.as_ref().map_or(file.as_path(), TempFile::path);

        // `--label` is why a `.vson` report names the file the user typed and
        // not the temp Turtle it was compiled to. `--verbose` prints every
        // relation's verdict instead of only the contradicted ones; the report
        // is stderr either way, and stdout carries the OK / FAIL lines alone.
        let shown = file.display().to_string();
        let mut args: Vec<&str> = Vec::new();
        if verbose {
            args.push("--verbose");
        }
        args.push("--label");
        args.push(&shown);

        let run = GateRun {
            gate: &GEOMETRY_GATE,
            home: &home,
            data,
            label: file,
            args: &args,
            echo: verbose,
        };
        if python_gate(run)? {
            println!("OK  {}", file.display());
        } else {
            println!("FAIL {} ({})", file.display(), GEOMETRY_GATE.label);
            any_failed = true;
        }
    }

    if any_failed {
        // Deliberately not "invalid" or "non-conformant": these documents are
        // conformant VSON. What failed is the agreement between two sets of
        // their own assertions.
        Err(Error::Validation(
            "one or more files assert a relation their own geometry contradicts. \
             No image was read; this is not a conformance verdict (docs/vson.md §5.13)."
                .into(),
        ))
    } else {
        Ok(())
    }
}
