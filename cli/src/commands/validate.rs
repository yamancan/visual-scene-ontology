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
//! Exit contract:
//!   0 — every input cleared all three gates;
//!   1 — an input genuinely failed a gate (SHACL violation, OWL clash, or an
//!       orphan VSO term);
//!   2 — a gate never reached a verdict (missing dependency, unparseable
//!       input, wrong `--home`, ...).
//!
//! Telling 1 from 2 takes more than the child's exit status. `pyshacl` and both
//! Python gates exit 1 for "did not conform" *and* for "crashed with an
//! uncaught exception" — an unparseable `.ttl` and a missing `owlrl` module
//! both land on the same code. So this module captures the child's stdout and
//! looks for the report each tool writes only when it truly ran; anything else
//! at exit 1 is a broken toolchain, not a broken document.
//!
//! Output discipline: the `OK` / `FAIL` lines are the only thing on stdout, so
//! `vson validate` is scriptable. Every human-readable report goes to stderr.
//!
//! For `.vson` inputs the Penman source is transpiled to a temp `.ttl` first,
//! and both gates read that temp file.

use super::{Error, Result};
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicUsize, Ordering};

/// A temp file that deletes itself on drop.
///
/// The drop guard is the point: the gates can bail out through `?` between
/// creating a temp file and reaching any cleanup line, and a `remove_file` at
/// the bottom of the loop never runs on those paths.
struct TempFile(PathBuf);

impl TempFile {
    fn create(stem: &str, body: &str) -> Result<Self> {
        // pid keeps concurrent `vson` processes apart; the counter keeps two
        // inputs that share a file stem apart within one process.
        static SEQ: AtomicUsize = AtomicUsize::new(0);
        let mut path = std::env::temp_dir();
        path.push(format!(
            "vson_{}_{}_{}.ttl",
            stem,
            std::process::id(),
            SEQ.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::write(&path, body)?;
        Ok(TempFile(path))
    }

    fn path(&self) -> &Path {
        &self.0
    }
}

impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

fn vson_home(explicit: Option<&Path>) -> PathBuf {
    if let Some(p) = explicit {
        return p.to_path_buf();
    }
    if let Ok(p) = std::env::var("VSON_HOME") {
        return PathBuf::from(p);
    }
    // Fall back to the working directory; the user is expected to invoke from
    // the repo root, which is the documented contract.
    PathBuf::from(".")
}

/// A filename-safe stem for a temp file. The input's own stem is user-supplied
/// text that would otherwise land verbatim in a path we construct.
fn temp_stem(file: &Path) -> String {
    let cleaned: String = file
        .file_stem()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default()
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '-')
        .collect();
    if cleaned.is_empty() {
        "input".to_string()
    } else {
        cleaned
    }
}

fn transpile_to_temp(file: &Path) -> Result<TempFile> {
    let src = std::fs::read_to_string(file)?;
    let ttl = crate::penman::to_turtle(&src).map_err(Error::Parse)?;
    TempFile::create(&temp_stem(file), &ttl)
}

/// The child's cwd is the resolved home, so a relative input path given
/// against *our* cwd would not resolve there.
fn absolutize(p: &Path) -> PathBuf {
    std::fs::canonicalize(p).unwrap_or_else(|_| p.to_path_buf())
}

/// Run a gate, turning a failed spawn into the "your toolchain is not set up"
/// usage error rather than a bare `io` error.
fn spawn(cmd: &mut Command, program: &str) -> Result<Output> {
    cmd.output().map_err(|e| {
        Error::Usage(format!(
            "could not run `{}`: {}\n\
             Both validate gates need python3 with pyshacl, rdflib and owlrl. \
             Install them with `make deps` from the repo root.",
            program, e
        ))
    })
}

/// How much of a child's stderr a message carries. A Python traceback runs to
/// 30+ frames and only its last lines say anything a CLI user can act on.
const MAX_STDERR_LINES: usize = 12;

fn exit_status(out: &Output) -> String {
    match out.status.code() {
        Some(c) => format!("exited {}", c),
        None => "was killed by a signal".to_string(),
    }
}

/// The last `max_lines` lines of `text`, flagged when anything was dropped.
fn tail(text: &str, max_lines: usize) -> String {
    let text = text.trim_end();
    let lines: Vec<&str> = text.lines().collect();
    if lines.len() <= max_lines {
        return text.to_string();
    }
    format!(
        "[{} earlier line(s) omitted]\n{}",
        lines.len() - max_lines,
        lines[lines.len() - max_lines..].join("\n")
    )
}

/// Everything a failing gate said, on *our* stderr. The child's own stderr is
/// forwarded too — it is normally empty on a verdict, but a Python warning
/// landing there is exactly the kind of thing that must not be swallowed.
fn forward(report: &str, child_stderr: &[u8]) {
    let report = report.trim_end();
    if !report.is_empty() {
        eprintln!("{}", report);
    }
    let extra = tail(&String::from_utf8_lossy(child_stderr), MAX_STDERR_LINES);
    if !extra.is_empty() {
        eprintln!("{}", extra);
    }
}

/// A child's stderr, shaped for embedding in an error message.
fn stderr_excerpt(bytes: &[u8]) -> String {
    let text = tail(&String::from_utf8_lossy(bytes), MAX_STDERR_LINES);
    if text.is_empty() {
        "(the tool wrote nothing to stderr)".to_string()
    } else {
        text
    }
}

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
            exit_status(&out),
            stderr_excerpt(&out.stderr)
        ))),
    }
}

/// Gates 2 and 3 — the two Python checkers, which differ only in the module
/// they run and the summary line that proves they ran.
///
/// `Ok(true)` cleared the gate, `Ok(false)` is a genuine failure of it,
/// `Err(Usage)` means the checker never reached a verdict.
///
/// `tell` is the prefix each checker prints on its own summary line, and only
/// once it has actually finished: the overloaded exit 1 is the same trap as
/// pyshacl's, where a real violation and a missing dependency are
/// indistinguishable by status alone.
struct PyGate {
    /// The `python3 -m` module path.
    module: &'static str,
    /// The file that must exist under home for the module to be runnable.
    script: &'static str,
    /// The summary-line prefix the checker prints only when it truly ran.
    tell: &'static str,
    /// Names the gate in the "never reached a verdict" error.
    what: &'static str,
    /// Names the gate in the `FAIL <file> (<label>)` line.
    label: &'static str,
}

/// Module form, matching the Makefile targets and each checker's own documented
/// usage: `python3 -m` puts the cwd on sys.path, so the `tools` package resolves
/// from the home set below.
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

fn python_gate(gate: &PyGate, home: &Path, data: &Path, label: &Path) -> Result<bool> {
    let program = format!("python3 -m {}", gate.module);
    let out = spawn(
        Command::new("python3")
            .arg("-m")
            .arg(gate.module)
            .arg(absolutize(data))
            .current_dir(home),
        &program,
    )?;
    let report = String::from_utf8_lossy(&out.stdout);

    match out.status.code() {
        Some(0) => Ok(true),
        Some(1) if report.contains(gate.tell) => {
            forward(&report, &out.stderr);
            Ok(false)
        }
        _ => Err(Error::Usage(format!(
            "{} could not check {} ({}):\n{}",
            gate.what,
            label.display(),
            exit_status(&out),
            stderr_excerpt(&out.stderr)
        ))),
    }
}

pub fn run(files: &[PathBuf], home: Option<&Path>) -> Result<()> {
    let home = vson_home(home);
    let shapes = home.join("shapes/vson-shapes.ttl");
    let gates = [OWL_GATE, C2_GATE];
    let ont_files = [
        "ontology/vso.ttl",
        "ontology/rcc8.ttl",
        "ontology/allen.ttl",
    ];

    for path in &ont_files {
        if !home.join(path).exists() {
            return Err(Error::Usage(format!(
                "{} not found under VSON_HOME={}; pass --home or set VSON_HOME",
                path,
                home.display()
            )));
        }
    }
    if !shapes.exists() {
        return Err(Error::Usage(format!(
            "shapes/vson-shapes.ttl not found under VSON_HOME={}",
            home.display()
        )));
    }
    for gate in &gates {
        if !home.join(gate.script).exists() {
            return Err(Error::Usage(format!(
                "{} not found under VSON_HOME={}; {} needs it",
                gate.script,
                home.display(),
                gate.what
            )));
        }
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
        // still on disk while both gates read it, and gone after.
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
            .find_map(|gate| match python_gate(gate, &home, data, file) {
                Ok(true) => None,
                Ok(false) => Some(Ok(gate.label)),
                Err(e) => Some(Err(e)),
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
