//! `vson validate <files...>` — runs all three of the gates CI runs, per input.
//!
//! Gate 1 (SHACL): `pyshacl --abort` over the shapes plus the three ontology
//! files, with `rdfs` inference.
//! Gate 2 (OWL 2 RL): `python3 -m tools.owlrl_check <file>`, run from the
//! resolved home. It catches `owl:disjointWith` / `owl:AllDifferent` clashes
//! that gate 1 is structurally blind to, because `rdfs` inference never
//! processes disjointness.
//! Gate 3 (C2): `python3 -m tools.c2_check <file>`. Clause C2 (docs/vson.md §2)
//! — every VSON-namespace IRI the document asserts is declared in one of the
//! three ontology files. Neither gate above can decide it: a shape would have to
//! assume the ontology sits in the data graph, and an undeclared IRI entails no
//! OWL clash. Until v1.3 nothing checked C2 at validate time and §2 said so.
//! A file is `OK` only once it clears all three.
//!
//! These three, and no more. Geometry consistency (§5.13) is deliberately not
//! here: it decides no numbered clause, a document that fails it is still a
//! conformant VSON document, and folding it in would silently change what
//! `vson validate` reports about conformance. It runs under `vson verify
//! --geometry` instead.
//!
//! Exit contract:
//!   0 — every input cleared all three gates;
//!   1 — an input genuinely failed a gate (SHACL violation, OWL clash, or an
//!       orphan VSO term);
//!   2 — a gate never reached a verdict (missing dependency, unparseable
//!       input, wrong `--home`, ...).
//!
//! Telling 1 from 2 takes more than the child's exit status; `commands::gates`
//! carries that machinery and the reasoning behind it.
//!
//! Output discipline: the `OK` / `FAIL` lines are the only thing on stdout, so
//! `vson validate` is scriptable. Every human-readable report goes to stderr.
//!
//! For `.vson` inputs the Penman source is transpiled to a temp `.ttl` first,
//! and every gate reads that temp file.

use super::gates::{
    forward, python_gate, require_script, spawn, transpile_to_temp, vson_home, GateRun, PyGate,
    TempFile,
};
use super::{Error, Result};
use std::path::{Path, PathBuf};
use std::process::Command;

const OWL_GATE: PyGate = PyGate {
    module: "tools.owlrl_check",
    script: "tools/owlrl_check.py",
    tell: "owl-consistency:",
    what: "the OWL 2 RL gate",
    label: "owl-consistency",
};

const C2_GATE: PyGate = PyGate {
    module: "tools.c2_check",
    script: "tools/c2_check.py",
    tell: "c2-closure:",
    what: "the C2 vocabulary-closure gate",
    label: "c2",
};

/// Gate 1 — SHACL. `Ok(true)` conforms, `Ok(false)` is a genuine violation,
/// `Err(Usage)` means pyshacl never reached a verdict.
fn shacl_gate(shapes: &Path, ontology: &Path, data: &Path, label: &Path) -> Result<bool> {
    let out = spawn(
        Command::new("pyshacl")
            .arg("--abort")
            .arg("-s")
            .arg(shapes)
            .arg("-e")
            .arg(ontology)
            .args(["-i", "rdfs"])
            .arg(data),
        "pyshacl",
    )?;
    let report = String::from_utf8_lossy(&out.stdout);

    // Verified against pyshacl 0.31.0: a violation exits 1 with the report on
    // stdout, while a data graph that will not parse also exits 1 — but with
    // an empty stdout and a traceback on stderr. The report is the tell.
    match out.status.code() {
        Some(0) => Ok(true),
        Some(1) if report.contains("Conforms:") || report.contains("Validation Failure result") => {
            forward(&report, &out.stderr);
            Ok(false)
        }
        _ => Err(Error::Usage(format!(
            "pyshacl could not validate {} ({}):\n{}",
            label.display(),
            super::gates::exit_status(&out),
            super::gates::stderr_excerpt(&out.stderr)
        ))),
    }
}

pub fn run(files: &[PathBuf], home: Option<&Path>) -> Result<()> {
    let ont_files = [
        "ontology/vso.ttl",
        "ontology/rcc8.ttl",
        "ontology/allen.ttl",
    ];
    // `ontology/vso.ttl` is the probe: a directory that has it is a home, and a
    // binary run outside every checkout materializes its own copy of one.
    let home = vson_home(home, super::home::MARKER)?;
    let shapes = home.join("shapes/vson-shapes.ttl");
    let gates = [OWL_GATE, C2_GATE];

    for path in &ont_files {
        if !home.join(path).exists() {
            return Err(super::home::missing(&home, path, "the SHACL gate"));
        }
    }
    if !shapes.exists() {
        return Err(super::home::missing(
            &home,
            "shapes/vson-shapes.ttl",
            "the SHACL gate",
        ));
    }
    for gate in &gates {
        require_script(gate, &home)?;
    }

    // pyshacl takes a single ontology graph, so the three ontology files are
    // concatenated into one temp Turtle file for inoculation. Built once: the
    // blob does not depend on the input being checked.
    let ont_blob = ont_files
        .iter()
        .map(|p| std::fs::read_to_string(home.join(p)))
        .collect::<std::io::Result<Vec<_>>>()?
        .join("\n");
    let ontology = TempFile::create("ont", &ont_blob)?;

    let mut any_failed = false;
    for file in files {
        // The guard lives for the whole iteration, so the transpiled Turtle is
        // still on disk while every gate reads it, and gone after.
        let transpiled = match file.extension().and_then(|e| e.to_str()) {
            Some("vson") => Some(transpile_to_temp(file)?),
            _ => None,
        };
        let data = transpiled.as_ref().map_or(file.as_path(), TempFile::path);

        if !shacl_gate(&shapes, ontology.path(), data, file)? {
            println!("FAIL {} (shacl)", file.display());
            any_failed = true;
            continue;
        }
        // Short-circuits on the first failure: a document already reported
        // non-conformant does not need every remaining gate's opinion, and each
        // one costs a Python process.
        let failed = gates
            .iter()
            .find_map(|gate| {
                let run = GateRun {
                    gate,
                    home: &home,
                    data,
                    label: file,
                    args: &[],
                    echo: false,
                };
                match python_gate(run) {
                    Ok(true) => None,
                    Ok(false) => Some(Ok(gate.label)),
                    Err(e) => Some(Err(e)),
                }
            })
            .transpose()?;
        if let Some(label) = failed {
            println!("FAIL {} ({})", file.display(), label);
            any_failed = true;
            continue;
        }
        println!("OK  {}", file.display());
    }

    if any_failed {
        Err(Error::Validation(
            "one or more files failed validation".into(),
        ))
    } else {
        Ok(())
    }
}
