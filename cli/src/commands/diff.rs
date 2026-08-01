//! `vson diff <a> <b>` — how far apart two VSON documents are.
//!
//! `validate` asks whether one document is conformant. `verify` asks whether one
//! document contradicts itself. `diff` asks about **two**: how much of the graph
//! they share, once the arbitrary names each one gave its nodes are aligned
//! away. That is Smatch (Cai & Knight 2013, for AMR) — search for the variable
//! alignment maximizing matched triples, then report precision, recall and F1
//! over triples — with the per-layer sub-scores a layered scheme owes its
//! readers (docs/vson.md §5.15).
//!
//! **It is agreement, not correctness.** F1 = 1.0 says the two documents assert
//! the same graph up to renaming. It does not say either one describes the
//! picture: two runs agreeing on the same hallucination score 1.0. No image is
//! read, and §2.1 is untouched by every number this prints.
//!
//! The metric lives in `tools/metrics/smatch.py` and this subcommand shells out
//! to it, like `export fol` and `convert x2t` do. Note what is *not* done here:
//! a `.vson` input is **not** transpiled by the Rust Penman implementation
//! first. The metric has to read `.x.vson` as well, the Python reference is the
//! one implementation that reads all three surface syntaxes, and `make
//! cli-check` proves the two Penman implementations emit isomorphic graphs — so
//! which one compiles the input cannot move the score.
//!
//! Exit contract, the same three codes as `validate` and `verify`:
//!   0 — the two documents are identical at triple level (F1 = 1.0);
//!   1 — they differ;
//!   2 — no verdict: unreadable input, unknown syntax, no python3, wrong
//!       `--home`, an unknown `--format`.

use super::gates::{
    absolutize, exit_status, forward, require_script, spawn, stderr_excerpt, vson_home, PyGate,
};
use super::{Error, Result};
use std::io::Write;
use std::path::Path;
use std::process::Command;

const SMATCH: PyGate = PyGate {
    module: "tools.metrics.smatch",
    script: "tools/metrics/smatch.py",
    tell: "smatch:",
    what: "the graph-agreement metric",
    label: "diff",
};

const FORMATS: &[&str] = &["text", "json"];

pub fn run(a: &Path, b: &Path, format: &str, home: Option<&Path>) -> Result<()> {
    if !FORMATS.contains(&format) {
        return Err(Error::Usage(format!(
            "vson diff: unknown --format {:?}. Available: {}",
            format,
            FORMATS.join(", ")
        )));
    }
    let home = vson_home(home);
    require_script(&SMATCH, &home)?;

    // The child runs from the repo root, so the inputs go over absolute; the
    // labels put the paths the *user* typed back into the report.
    let (abs_a, abs_b) = (absolutize(a), absolutize(b));
    let (shown_a, shown_b) = (a.display().to_string(), b.display().to_string());
    let program = format!("python3 -m {}", SMATCH.module);
    let out = spawn(
        Command::new("python3")
            .arg("-m")
            .arg(SMATCH.module)
            .arg("--format")
            .arg(format)
            .arg("--label-a")
            .arg(&shown_a)
            .arg("--label-b")
            .arg(&shown_b)
            .arg(&abs_a)
            .arg(&abs_b)
            .current_dir(&home),
        &program,
    )?;

    // The report is the product here, not a diagnostic: unlike `validate`,
    // whose stdout carries only OK / FAIL lines, `vson diff` exists to print
    // the table — so the child's stdout is ours. In `--format json` that keeps
    // stdout a single parseable document, with the summary line on stderr.
    let report = String::from_utf8_lossy(&out.stdout);
    let told =
        report.contains(SMATCH.tell) || String::from_utf8_lossy(&out.stderr).contains(SMATCH.tell);

    match out.status.code() {
        Some(0) => {
            std::io::stdout().write_all(&out.stdout)?;
            forward("", &out.stderr);
            Ok(())
        }
        // Exit 1 is a real verdict only if the metric said so on its own summary
        // line: every checker under tools/ exits 1 for an uncaught exception
        // too, and a missing rdflib must not be reported as "these documents
        // differ". `gates` carries the full reasoning.
        Some(1) if told => {
            std::io::stdout().write_all(&out.stdout)?;
            forward("", &out.stderr);
            Err(Error::Validation(format!(
                "{} and {} are not the same graph. This is agreement between two \
                 documents; no image was read and neither document is thereby \
                 correct (docs/vson.md §2.1).",
                shown_a, shown_b
            )))
        }
        _ => Err(Error::Usage(format!(
            "{} could not compare {} with {} ({}):\n{}",
            SMATCH.what,
            shown_a,
            shown_b,
            exit_status(&out),
            stderr_excerpt(&out.stderr)
        ))),
    }
}
