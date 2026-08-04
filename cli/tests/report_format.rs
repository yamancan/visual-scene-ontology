//! `vson validate --format json|sarif` and `-` — the interface a build reads.
//!
//! Three things are pinned here, and each one is a promise made to somebody
//! who is not at a terminal.
//!
//! **The bytes.** Both structured formats are compared against a frozen golden
//! (`tests/fixtures/validate_report/`). A field that silently changes name,
//! moves, or stops being emitted breaks every consumer that parsed the old
//! shape, and a report format with no golden is a format that drifts. When a
//! change to the output is *intended*, refreeze:
//!
//! ```text
//! cli/target/release/vson validate --format json  tests/fixtures/bad_no_viewer.vson \
//!     > tests/fixtures/validate_report/bad_no_viewer.json
//! cli/target/release/vson validate --format sarif tests/fixtures/bad_no_viewer.vson \
//!     > tests/fixtures/validate_report/bad_no_viewer.sarif
//! ```
//!
//! (run from the repository root, and read the diff before committing it —
//! the crate version is part of the report, so a version bump refreezes both).
//!
//! **The exit codes.** 0 conformant, 1 a document that failed a gate, 2 no
//! verdict. Scripts branch on those, so they are interface, and `--format`
//! must not move them: the same document exits 1 in all three formats.
//!
//! **The verdict itself.** `--format text` runs the three gates from Rust;
//! `--format json` runs them inside one Python process. Two paths to one
//! answer is two chances to disagree, so a fixture that the text path
//! attributes to the C2 gate must be attributed to the C2 gate by the JSON
//! path as well.
//!
//! `--format compact` is pinned here too, and its golden is written out in
//! this file rather than frozen beside the other two: it carries no crate
//! version, so a release would not refreeze it, and a line a human is meant to
//! read is worth reading in the test that asserts it.

use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};

const PENMAN_FIXTURE: &str = "tests/fixtures/bad_no_viewer.vson";
const ORPHAN_FIXTURE: &str = "tests/fixtures/bad_orphan_term.ttl";
const CLEAN_FIXTURE: &str = "examples/throne_room.ttl";
const JSON_GOLDEN: &str = "tests/fixtures/validate_report/bad_no_viewer.json";
const SARIF_GOLDEN: &str = "tests/fixtures/validate_report/bad_no_viewer.sarif";

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("the crate dir has a parent")
        .to_path_buf()
}

fn vson(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_vson"))
        .current_dir(repo_root())
        .args(args)
        .output()
        .expect("the binary under test must run")
}

/// The same, with `stdin` fed from memory.
fn vson_stdin(args: &[&str], input: &str) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_vson"))
        .current_dir(repo_root())
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("the binary under test must run");
    child
        .stdin
        .take()
        .expect("stdin was piped")
        .write_all(input.as_bytes())
        .expect("the child must accept its input");
    child.wait_with_output().expect("the child must finish")
}

fn stdout_of(out: &Output) -> String {
    String::from_utf8_lossy(&out.stdout).into_owned()
}

fn both_streams(out: &Output) -> String {
    format!(
        "stdout: {}\nstderr: {}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    )
}

fn read(rel: &str) -> String {
    std::fs::read_to_string(repo_root().join(rel)).expect("the fixture must exist")
}

fn json_of(out: &Output) -> serde_json::Value {
    serde_json::from_str(&stdout_of(out)).unwrap_or_else(|e| {
        panic!(
            "stdout must be one JSON document: {e}\n{}",
            both_streams(out)
        )
    })
}

fn assert_frozen(actual: &str, golden: &str) {
    let expected = read(golden);
    assert_eq!(
        actual, expected,
        "the report no longer matches {golden}. If the change is intended, refreeze \
         it (see this file's header) and read the diff before committing."
    );
}

#[test]
fn json_output_matches_the_frozen_golden() {
    let out = vson(&["validate", "--format", "json", PENMAN_FIXTURE]);
    assert_eq!(out.status.code(), Some(1), "{}", both_streams(&out));
    assert_frozen(&stdout_of(&out), JSON_GOLDEN);
}

#[test]
fn sarif_output_matches_the_frozen_golden() {
    let out = vson(&["validate", "--format", "sarif", PENMAN_FIXTURE]);
    assert_eq!(out.status.code(), Some(1), "{}", both_streams(&out));
    assert_frozen(&stdout_of(&out), SARIF_GOLDEN);
}

#[test]
fn sarif_is_minimal_valid_2_1_0() {
    // The required properties of SARIF 2.1.0 (OASIS, March 2020) on the path
    // this tool emits: sarifLog.version and .runs (§3.13), run.tool (§3.14),
    // tool.driver (§3.18), toolComponent.name (§3.19), result.message (§3.27)
    // and message.text (§3.11) — plus the three GitHub needs to place and rank
    // a finding, which the schema itself leaves optional.
    let out = vson(&["validate", "--format", "sarif", PENMAN_FIXTURE]);
    let log = json_of(&out);
    assert_eq!(log["version"], "2.1.0");
    let run = &log["runs"][0];
    assert!(
        run["tool"]["driver"]["name"].is_string(),
        "tool.driver.name"
    );
    let result = &run["results"][0];
    assert!(result["message"]["text"].is_string(), "message.text");
    assert!(result["ruleId"].is_string(), "ruleId");
    assert_eq!(result["level"], "error");
    let location = &result["locations"][0]["physicalLocation"];
    assert_eq!(location["artifactLocation"]["uri"], PENMAN_FIXTURE);
    assert!(location["region"]["startLine"].is_number(), "startLine");
}

#[test]
fn a_conformant_document_exits_zero_with_an_empty_result_set() {
    // Not an empty file: a caller has to be able to tell "clean" from "the tool
    // never ran", and only a report can say the first.
    let out = vson(&["validate", "--format", "json", CLEAN_FIXTURE]);
    assert_eq!(out.status.code(), Some(0), "{}", both_streams(&out));
    let doc = json_of(&out);
    assert_eq!(doc["conforms"], true);
    assert_eq!(doc["summary"]["findings"], 0);
    assert_eq!(doc["files"][0]["gate"], serde_json::Value::Null);
}

#[test]
fn the_text_and_json_paths_agree_on_which_gate_failed() {
    // `--format text` runs the three gates from Rust, one process each;
    // `--format json` runs them inside `tools/validate_report.py`. This fixture
    // clears SHACL and OWL and fails C2 alone, so it is the one that pins the
    // gate order *and* the attribution across both implementations.
    let text = vson(&["validate", ORPHAN_FIXTURE]);
    assert_eq!(text.status.code(), Some(1), "{}", both_streams(&text));
    assert!(
        stdout_of(&text).contains("(c2)"),
        "text path: {}",
        both_streams(&text)
    );

    let structured = vson(&["validate", "--format", "json", ORPHAN_FIXTURE]);
    assert_eq!(
        structured.status.code(),
        Some(1),
        "{}",
        both_streams(&structured)
    );
    let doc = json_of(&structured);
    assert_eq!(doc["files"][0]["gate"], "c2");
    assert_eq!(
        doc["files"][0]["findings"][0]["rule"],
        "vson/c2/orphan-term"
    );
    // A C2 orphan has no focus node — it is a *name* the document uses — so the
    // position comes from where the term is mentioned.
    assert_eq!(doc["files"][0]["findings"][0]["location"]["line"], 35);
}

#[test]
fn stdin_is_read_when_the_input_is_a_dash() {
    let source = read(PENMAN_FIXTURE);
    let out = vson_stdin(&["validate", "--format", "json", "-"], &source);
    assert_eq!(out.status.code(), Some(1), "{}", both_streams(&out));
    let doc = json_of(&out);
    assert_eq!(doc["files"][0]["path"], "-");
    // Sniffed, not guessed from a filename there isn't one of.
    assert_eq!(doc["files"][0]["syntax"], "penman");
    // And the position is the same one the file on disk resolves to: the
    // resolver reads the source it was handed, wherever it came from.
    let located = &doc["files"][0]["findings"][0]["location"];
    assert_eq!(located["line"], 26);
    assert_eq!(located["column"], 14);
    assert_eq!(located["resolved_from"], "penman-variable");
}

#[test]
fn stdin_accepts_turtle_too_and_exits_zero_on_a_clean_document() {
    let out = vson_stdin(&["validate", "-"], &read(CLEAN_FIXTURE));
    assert_eq!(out.status.code(), Some(0), "{}", both_streams(&out));
    assert_eq!(stdout_of(&out).trim_end(), "OK  -");
}

#[test]
fn compact_prints_one_line_per_finding_and_then_the_verdict() {
    // The whole format, byte for byte. This fixture has one finding, so the
    // run is two lines: where it is, which rule fired, what it said — then the
    // same `FAIL <file> (<gate>)` line `--format text` prints.
    let out = vson(&["validate", "--format", "compact", PENMAN_FIXTURE]);
    assert_eq!(out.status.code(), Some(1), "{}", both_streams(&out));
    assert_eq!(
        stdout_of(&out),
        "tests/fixtures/bad_no_viewer.vson:26:14  \
         vson/shacl/DirectionalNeedsViewerShape  \
         Directional spatial facts require exactly one vso:viewer for construal \
         disambiguation (C5), and that viewer must be a CameraView, never an Entity.\n\
         FAIL tests/fixtures/bad_no_viewer.vson (shacl)\n",
        "{}",
        both_streams(&out)
    );
}

#[test]
fn a_compact_finding_starts_with_a_position_grep_can_cut_on() {
    // The property the format exists for: every finding line begins
    // `path:line:col`, and none of them wraps. A log scraper and a person
    // reading a failing build want the same two things.
    let out = vson(&["validate", "--format", "compact", PENMAN_FIXTURE]);
    let text = stdout_of(&out);
    let mut lines = text.lines();
    let finding = lines.next().expect("one finding line");
    let (position, _) = finding.split_once("  ").expect("two-space separated");
    let parts: Vec<&str> = position.rsplitn(3, ':').collect();
    assert_eq!(parts[2], PENMAN_FIXTURE, "{finding}");
    assert_eq!(parts[1].parse::<u32>().ok(), Some(26), "{finding}");
    assert_eq!(parts[0].parse::<u32>().ok(), Some(14), "{finding}");
    assert!(lines.next().unwrap().starts_with("FAIL "), "{text}");
    assert_eq!(lines.next(), None, "{text}");
}

#[test]
fn a_clean_compact_run_says_so_rather_than_saying_nothing() {
    // §5.16's rule for every structured format, in this one's shape: silence
    // and success must not look alike.
    let out = vson(&["validate", "--format", "compact", CLEAN_FIXTURE]);
    assert_eq!(out.status.code(), Some(0), "{}", both_streams(&out));
    assert_eq!(stdout_of(&out), format!("OK  {CLEAN_FIXTURE}\n"));
}

#[test]
fn compact_reaches_the_same_verdict_as_the_other_formats() {
    // The C2 fixture: a different gate, a finding with no focus node, and a
    // position resolved from a mention rather than from a declaration. The
    // format must not move the gate attribution or the exit code.
    let out = vson(&["validate", "--format", "compact", ORPHAN_FIXTURE]);
    assert_eq!(out.status.code(), Some(1), "{}", both_streams(&out));
    let text = stdout_of(&out);
    assert!(
        text.starts_with(&format!("{ORPHAN_FIXTURE}:35:")),
        "the position the JSON path reports, in this format: {text}"
    );
    assert!(text.contains("  vson/c2/orphan-term  "), "{text}");
    assert!(
        text.ends_with(&format!("FAIL {ORPHAN_FIXTURE} (c2)\n")),
        "{text}"
    );
}

#[test]
fn an_unknown_format_exits_2_and_lists_the_ones_that_exist() {
    let out = vson(&["validate", "--format", "yaml", CLEAN_FIXTURE]);
    assert_eq!(out.status.code(), Some(2), "{}", both_streams(&out));
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("text, json, sarif"), "{stderr}");
    assert!(
        out.stdout.is_empty(),
        "nothing may reach stdout when no verdict was reached"
    );
}

#[test]
fn the_relaxed_profile_is_refused_rather_than_silently_run_as_strict() {
    // shapes/vson-shapes-relaxed.ttl ships and is embedded, and no command
    // selects it (docs/vson.md §6.1). Answering a request for it with a strict
    // run would report a conformance verdict about a profile nobody validated
    // against, which is worse than an error.
    let out = vson(&["validate", "--profile", "relaxed", CLEAN_FIXTURE]);
    assert_eq!(out.status.code(), Some(2), "{}", both_streams(&out));
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("not implemented"), "{stderr}");
    assert!(stderr.contains("§6.1"), "{stderr}");
}

#[test]
fn standard_input_may_be_named_once() {
    let out = vson(&["validate", "-", "-"]);
    assert_eq!(out.status.code(), Some(2), "{}", both_streams(&out));
    assert!(String::from_utf8_lossy(&out.stderr).contains("once"));
}

#[test]
fn a_missing_input_is_reported_before_any_gate_runs() {
    // Exit 2, and from Rust: no Python is spawned, so this holds on a machine
    // that has none.
    let out = vson(&["validate", "--format", "json", "examples/nope.ttl"]);
    assert_eq!(out.status.code(), Some(2), "{}", both_streams(&out));
    assert!(out.stdout.is_empty());
}
