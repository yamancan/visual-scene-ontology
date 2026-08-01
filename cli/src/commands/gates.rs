//! Shared plumbing for running an external checker as a gate.
//!
//! Two subcommands run Python checkers over a document: `validate` (SHACL, then
//! OWL 2 RL, then C2 — the conformance gates of docs/vson.md §2) and `verify`
//! (geometry consistency, §5.13, which is not a conformance gate at all). They
//! differ in *which* checkers run and in what a failure means; everything
//! around that is identical, and lives here once.
//!
//! The part worth reading is [`python_gate`]. Telling "the document is bad"
//! from "the checker never ran" takes more than the child's exit status: every
//! checker in `tools/` exits 1 both for a genuine failure and for an uncaught
//! exception, so an unparseable `.ttl` and a missing `rdflib` land on the same
//! code. Each checker therefore prints a summary line only once it has truly
//! finished, and that line — [`PyGate::tell`] — is what separates exit 1 from
//! exit 2 here.

use super::home::Home;
use super::{Error, Result};
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicUsize, Ordering};

/// A temp file that deletes itself on drop.
///
/// The drop guard is the point: a gate can bail out through `?` between
/// creating a temp file and reaching any cleanup line, and a `remove_file` at
/// the bottom of the loop never runs on those paths.
pub struct TempFile(PathBuf);

impl TempFile {
    pub fn create(stem: &str, body: &str) -> Result<Self> {
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

    pub fn path(&self) -> &Path {
        &self.0
    }
}

impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

/// Where the ontology, shapes and `tools/` package are found, for the three
/// subcommands that take a `--home` flag and a *list* of inputs.
///
/// The list is why `near` is `None`: with several inputs there is no single
/// file whose directory could be walked up from, so resolution goes explicit
/// home, then the working directory and its parents, then the copy embedded in
/// the binary. [`super::home`] carries the full order and the reasoning.
///
/// `probe` is the home-relative file the caller is about to read, so the walk
/// passes over a checkout too old to carry it.
pub fn vson_home(explicit: Option<&Path>, probe: &str) -> Result<Home> {
    super::home::resolve(explicit, None, probe)
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

/// Compile a `.vson` (Penman) input to a temp Turtle file the gates can read.
pub fn transpile_to_temp(file: &Path) -> Result<TempFile> {
    let src = std::fs::read_to_string(file)?;
    let ttl = crate::penman::to_turtle(&src).map_err(Error::Parse)?;
    TempFile::create(&temp_stem(file), &ttl)
}

/// The child's cwd is the resolved home, so a relative input path given
/// against *our* cwd would not resolve there.
pub fn absolutize(p: &Path) -> PathBuf {
    std::fs::canonicalize(p).unwrap_or_else(|_| p.to_path_buf())
}

/// Run a gate, turning a failed spawn into the "your toolchain is not set up"
/// usage error rather than a bare `io` error.
pub fn spawn(cmd: &mut Command, program: &str) -> Result<Output> {
    cmd.output().map_err(|e| {
        Error::Usage(format!(
            "could not run `{}`: {}\n\
             The Python gates need python3 with pyshacl, rdflib and owlrl. \
             Install them with `make deps` from the repo root.",
            program, e
        ))
    })
}

/// How much of a child's stderr a message carries. A Python traceback runs to
/// 30+ frames and only its last lines say anything a CLI user can act on.
const MAX_STDERR_LINES: usize = 12;

pub fn exit_status(out: &Output) -> String {
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

/// Everything a gate said, on *our* stderr. The child's own stderr is forwarded
/// too — it is normally empty on a verdict, but a Python warning landing there
/// is exactly the kind of thing that must not be swallowed.
pub fn forward(report: &str, child_stderr: &[u8]) {
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
pub fn stderr_excerpt(bytes: &[u8]) -> String {
    let text = tail(&String::from_utf8_lossy(bytes), MAX_STDERR_LINES);
    if text.is_empty() {
        "(the tool wrote nothing to stderr)".to_string()
    } else {
        text
    }
}

/// One Python checker, run as a gate.
///
/// `tell` is the prefix the checker prints on its own summary line, and only
/// once it has actually finished: the overloaded exit 1 is the trap described
/// in this module's header.
pub struct PyGate {
    /// The `python3 -m` module path.
    pub module: &'static str,
    /// The file that must exist under home for the module to be runnable.
    pub script: &'static str,
    /// The summary-line prefix the checker prints only when it truly ran.
    pub tell: &'static str,
    /// Names the gate in the "never reached a verdict" error.
    pub what: &'static str,
    /// Names the gate in the `FAIL <file> (<label>)` line.
    pub label: &'static str,
}

/// One invocation of one gate over one document.
pub struct GateRun<'a> {
    pub gate: &'a PyGate,
    /// The home the checker runs from — a checkout, or the embedded copy.
    pub home: &'a Home,
    /// The Turtle the checker reads — a temp copy, for a `.vson` input.
    pub data: &'a Path,
    /// The path the *user* named, for messages. Not always `data`.
    pub label: &'a Path,
    /// The checker's own flags, which precede the input path.
    pub args: &'a [&'a str],
    /// Forward the checker's report even when the gate was cleared. `validate`
    /// wants silence on success; `verify --verbose` wants the detail.
    pub echo: bool,
}

/// Run one gate over one document.
///
/// `Ok(true)` cleared the gate, `Ok(false)` is a genuine failure of it,
/// `Err(Usage)` means the checker never reached a verdict.
///
/// Module form, matching the Makefile targets and each checker's documented
/// usage: `python3 -m` puts the cwd on `sys.path`, so the `tools` package
/// resolves from `home`.
pub fn python_gate(run: GateRun) -> Result<bool> {
    let program = format!("python3 -m {}", run.gate.module);
    let out = spawn(
        Command::new("python3")
            .arg("-m")
            .arg(run.gate.module)
            .args(run.args)
            .arg(absolutize(run.data))
            .current_dir(run.home.path()),
        &program,
    )?;
    let report = String::from_utf8_lossy(&out.stdout);

    match out.status.code() {
        Some(0) => {
            if run.echo {
                // stdout is reserved for the OK / FAIL lines, so the checker's
                // own report goes to stderr like every human-readable report.
                forward(&report, &out.stderr);
            }
            Ok(true)
        }
        Some(1) if report.contains(run.gate.tell) => {
            forward(&report, &out.stderr);
            Ok(false)
        }
        _ => Err(Error::Usage(format!(
            "{} could not check {} ({}):\n{}",
            run.gate.what,
            run.label.display(),
            exit_status(&out),
            stderr_excerpt(&out.stderr)
        ))),
    }
}

/// Fail early when the module a gate runs is not under `home`.
pub fn require_script(gate: &PyGate, home: &Home) -> Result<()> {
    if home.join(gate.script).exists() {
        return Ok(());
    }
    Err(super::home::missing(home, gate.script, gate.what))
}
