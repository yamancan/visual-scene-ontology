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
//!       input, wrong `--home`, an unknown `--format` or `--profile`, ...).
//!
//! Telling 1 from 2 takes more than the child's exit status; `commands::gates`
//! carries that machinery and the reasoning behind it.
//!
//! Output discipline: under `--format text` the `OK` / `FAIL` lines are the
//! only thing on stdout, so `vson validate` is scriptable, and every
//! human-readable report goes to stderr. Under `--format json` and `--format
//! sarif` the report *is* the product, so stdout carries exactly one parseable
//! document and nothing else — including on a clean run, which emits a report
//! with no findings rather than nothing at all (docs/vson.md §5.16).
//! `--format compact` is the report as lines rather than as a document: one
//! finding per line, `path:line:col` first, then the same verdict line `text`
//! prints — all of it on stdout, because here the findings *are* what a reader
//! grepped for.
//!
//! Inputs are file paths, or `-` for standard input. For `.vson` inputs — and
//! for a `-` stream that sniffs as Penman — the source is transpiled to a temp
//! `.ttl` first, and every gate reads that temp file. The structured formats
//! keep the *original* text on hand as well, because a line number belongs to
//! the file the author wrote and not to a temp file they never saw
//! (`commands::sourcemap`).

use super::gates::{
    absolutize, exit_status, forward, python_gate, require_script, spawn, stderr_excerpt,
    transpile_text_to_temp, vson_home, GateRun, PyGate, TempFile,
};
use super::report::{FileReport, Records, Report, RECORDS_VERSION};
use super::sourcemap::{sniff, SourceMap, Syntax};
use super::{Error, Result};
use std::io::{Read, Write};
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

/// The structured reporter. Not a [`PyGate`]: its verdict is not read off a
/// summary line but off the JSON document it either produced or did not.
const REPORTER_MODULE: &str = "tools.validate_report";
const REPORTER_SCRIPT: &str = "tools/validate_report.py";

const FORMATS: &[&str] = &["text", "json", "sarif", "compact"];

/// The stdin marker, spelled the way every POSIX tool spells it.
const STDIN: &str = "-";

/// The shapes file each profile names (docs/vson.md §6.1). `relaxed` ships as a
/// file and is embedded in this binary, but no command selects it — see
/// [`shapes_for`] for why that refusal is explicit rather than a silent
/// fallback to `strict`.
const STRICT_SHAPES: &str = "shapes/vson-shapes.ttl";

/// `(shapes file, the profile's name as the report states it)`.
fn shapes_for(profile: &str) -> Result<(&'static str, &'static str)> {
    match profile {
        "strict" => Ok((STRICT_SHAPES, "strict")),
        "relaxed" => Err(Error::Usage(
            "vson validate: --profile relaxed is not implemented.\n\
             shapes/vson-shapes-relaxed.ttl ships and is embedded in this binary, but no \
             command selects it (docs/vson.md §6.1). Falling back to the strict shapes \
             under a relaxed name would report a conformance verdict about a profile \
             nobody validated against, so this is an error instead. Use --profile strict \
             (the default)."
                .into(),
        )),
        other => Err(Error::Usage(format!(
            "vson validate: unknown --profile {:?}. Available: strict (relaxed is defined \
             in docs/vson.md §6.1 but no command selects it yet).",
            other
        ))),
    }
}

/// Gate 1 — SHACL. `Ok(true)` conforms, `Ok(false)` is a genuine violation,
/// `Err(Usage)` means pyshacl never reached a verdict.
fn shacl_gate(shapes: &Path, ontology: &Path, data: &Path, label: &str) -> Result<bool> {
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
            label,
            exit_status(&out),
            stderr_excerpt(&out.stderr)
        ))),
    }
}

/// One resolved input: what to call it, the Turtle the gates read, and — for
/// the structured formats — the source the author actually wrote.
struct Input {
    label: String,
    data: PathBuf,
    /// Deletes the transpiled or captured Turtle when the input goes out of
    /// scope. Held, never read.
    _temp: Option<TempFile>,
    map: Option<SourceMap>,
}

/// Read every byte of standard input.
fn read_stdin() -> Result<String> {
    let mut buffer = String::new();
    std::io::stdin().read_to_string(&mut buffer)?;
    Ok(buffer)
}

/// Resolve one command-line argument into an [`Input`].
///
/// `structured` decides whether the source text is kept: `--format text`
/// resolves no positions, and reading a Turtle file this process never
/// otherwise opens would be work for nothing.
fn resolve(arg: &Path, structured: bool) -> Result<Input> {
    let label = arg.display().to_string();
    if label == STDIN {
        let text = read_stdin()?;
        let syntax = sniff(&text);
        let turtle = match syntax {
            Syntax::Penman => crate::penman::to_turtle(&text).map_err(Error::Parse)?,
            Syntax::Turtle => text.clone(),
        };
        let temp = TempFile::create("stdin", &turtle)?;
        return Ok(Input {
            label,
            data: temp.path().to_path_buf(),
            _temp: Some(temp),
            map: structured.then(|| SourceMap::new(&text, syntax)),
        });
    }
    let penman = arg.extension().and_then(|e| e.to_str()) == Some("vson");
    if penman {
        // Read once: the same bytes are compiled for the gates and indexed for
        // the position map.
        let text = std::fs::read_to_string(arg)?;
        let temp = transpile_text_to_temp(arg, &text)?;
        return Ok(Input {
            label,
            data: temp.path().to_path_buf(),
            _temp: Some(temp),
            map: structured.then(|| SourceMap::new(&text, Syntax::Penman)),
        });
    }
    let map = if structured {
        Some(SourceMap::new(
            &std::fs::read_to_string(arg)?,
            Syntax::Turtle,
        ))
    } else {
        None
    };
    Ok(Input {
        label,
        data: arg.to_path_buf(),
        _temp: None,
        map,
    })
}

/// Run the structured reporter over one document.
///
/// The 1-vs-2 split needs no summary-line tell here: a parseable JSON document
/// on stdout *is* the verdict, and anything else — a traceback, a truncated
/// stream, a version this binary does not know — means no verdict was reached.
fn records_for(input: &Input, home: &super::home::Home, shapes: &Path) -> Result<Records> {
    let program = format!("python3 -m {}", REPORTER_MODULE);
    let out = spawn(
        Command::new("python3")
            .arg("-m")
            .arg(REPORTER_MODULE)
            .arg("--shapes")
            .arg(absolutize(shapes))
            .arg("--label")
            .arg(&input.label)
            .arg(absolutize(&input.data))
            .current_dir(home.path()),
        &program,
    )?;
    let stdout = String::from_utf8_lossy(&out.stdout);
    let no_verdict = |why: &str| {
        Error::Usage(format!(
            "the structured reporter could not check {} ({}): {}\n{}",
            input.label,
            exit_status(&out),
            why,
            stderr_excerpt(&out.stderr)
        ))
    };
    if !matches!(out.status.code(), Some(0) | Some(1)) {
        return Err(no_verdict("it exited without producing a report"));
    }
    let records: Records = serde_json::from_str(&stdout)
        .map_err(|e| no_verdict(&format!("unreadable report: {e}")))?;
    if records.report != RECORDS_VERSION {
        return Err(no_verdict(&format!(
            "this binary reads {RECORDS_VERSION}; the reporter under {} announced {}",
            home.describe(),
            records.report
        )));
    }
    Ok(records)
}

/// `--format json` / `--format sarif` / `--format compact`: one report over
/// every input, rendered three ways.
///
/// All three take this path rather than the text one because all three carry
/// findings, and findings come from the structured reporter — including
/// `compact`, whose lines are the same records with everything but the
/// position, the rule and the message dropped.
fn structured(
    inputs: &[Input],
    home: &super::home::Home,
    shapes: &Path,
    format: &str,
    profile: &'static str,
) -> Result<()> {
    let mut files = Vec::with_capacity(inputs.len());
    for input in inputs {
        let records = records_for(input, home, shapes)?;
        files.push(FileReport::new(
            input.label.clone(),
            records,
            input.map.as_ref(),
        ));
    }
    let report = Report::new(profile, files);
    let document = match format {
        "sarif" => report.to_sarif(),
        "compact" => report.to_compact(),
        _ => report.to_json(),
    };
    std::io::stdout().write_all(document.as_bytes())?;
    if report.conforms() {
        Ok(())
    } else {
        Err(Error::Validation(
            "one or more files failed validation".into(),
        ))
    }
}

/// `--format text`: the `OK` / `FAIL` lines, gate by gate.
fn text(inputs: &[Input], home: &super::home::Home, shapes: &Path) -> Result<()> {
    let ont_files = [
        "ontology/vso.ttl",
        "ontology/rcc8.ttl",
        "ontology/allen.ttl",
    ];
    // pyshacl takes a single ontology graph, so the three ontology files are
    // concatenated into one temp Turtle file for inoculation. Built once: the
    // blob does not depend on the input being checked.
    let ont_blob = ont_files
        .iter()
        .map(|p| std::fs::read_to_string(home.join(p)))
        .collect::<std::io::Result<Vec<_>>>()?
        .join("\n");
    let ontology = TempFile::create("ont", &ont_blob)?;
    let gates = [OWL_GATE, C2_GATE];
    let mut any_failed = false;

    for input in inputs {
        let data = input.data.as_path();
        if !shacl_gate(shapes, ontology.path(), data, &input.label)? {
            println!("FAIL {} (shacl)", input.label);
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
                    home,
                    data,
                    label: Path::new(&input.label),
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
            println!("FAIL {} ({})", input.label, label);
            any_failed = true;
            continue;
        }
        println!("OK  {}", input.label);
    }

    if any_failed {
        Err(Error::Validation(
            "one or more files failed validation".into(),
        ))
    } else {
        Ok(())
    }
}

pub fn run(files: &[PathBuf], home: Option<&Path>, format: &str, profile: &str) -> Result<()> {
    if !FORMATS.contains(&format) {
        return Err(Error::Usage(format!(
            "vson validate: unknown --format {:?}. Available: {}",
            format,
            FORMATS.join(", ")
        )));
    }
    let (shapes_rel, profile) = shapes_for(profile)?;
    if files.iter().filter(|f| f.as_os_str() == STDIN).count() > 1 {
        return Err(Error::Usage(
            "vson validate: `-` may be named once — standard input is one stream, and a \
             second `-` would read an empty one."
                .into(),
        ));
    }
    let structured_format = format != "text";

    let ont_files = [
        "ontology/vso.ttl",
        "ontology/rcc8.ttl",
        "ontology/allen.ttl",
    ];
    // `ontology/vso.ttl` is the probe: a directory that has it is a home, and a
    // binary run outside every checkout materializes its own copy of one.
    let home = vson_home(home, super::home::MARKER)?;
    let shapes = home.join(shapes_rel);

    for path in &ont_files {
        if !home.join(path).exists() {
            return Err(super::home::missing(&home, path, "the SHACL gate"));
        }
    }
    if !shapes.exists() {
        return Err(super::home::missing(&home, shapes_rel, "the SHACL gate"));
    }
    if structured_format {
        if !home.join(REPORTER_SCRIPT).exists() {
            return Err(super::home::missing(
                &home,
                REPORTER_SCRIPT,
                "the structured reporter",
            ));
        }
    } else {
        for gate in &[OWL_GATE, C2_GATE] {
            require_script(gate, &home)?;
        }
    }

    // Every input is resolved before any gate runs, so a typo in the last path
    // is reported before a minute of Python has been spent on the first.
    let inputs = files
        .iter()
        .map(|f| resolve(f, structured_format))
        .collect::<Result<Vec<_>>>()?;

    if structured_format {
        structured(&inputs, &home, &shapes, format, profile)
    } else {
        text(&inputs, &home, &shapes)
    }
}
