//! `vson diff` — graph agreement at the binary boundary.
//!
//! The load-bearing test is `the_same_scene_in_two_syntaxes_is_one_graph`. It
//! runs the subcommand over a Penman scene and its VSON-X twin and pins exit 0:
//! the metric is defined over the *materialized* graph, so the surface syntax an
//! input was written in cannot move the score. If a future change to either
//! transpiler breaks that, this says so — and says it in the one place a user
//! would notice, the binary.
//!
//! The rest pin the interface: which exit code means what, that stdout stays
//! parseable under `--format json`, and that a report about two documents never
//! claims either of them is right.

use std::path::{Path, PathBuf};
use std::process::{Command, Output};

const RUN_A: &str = "tests/fixtures/diff/run_a.ttl";
const RUN_B: &str = "tests/fixtures/diff/run_b.ttl";
const PENMAN: &str = "examples/gallery/04_directional_with_viewer.vson";
const VSON_X: &str = "examples/gallery-x/04_directional_with_viewer.x.vson";

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("the crate dir has a parent")
        .to_path_buf()
}

fn vson(root: &Path, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_vson"))
        .current_dir(root)
        .args(args)
        .output()
        .expect("the binary under test must run")
}

fn stdout_of(out: &Output) -> String {
    String::from_utf8_lossy(&out.stdout).into_owned()
}

fn both_streams(out: &Output) -> String {
    format!(
        "{}{}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    )
}

#[test]
fn a_document_against_itself_exits_zero() {
    let out = vson(&repo_root(), &["diff", RUN_A, RUN_A]);
    assert_eq!(
        out.status.code(),
        Some(0),
        "expected exit 0\n{}",
        both_streams(&out)
    );
    let stdout = stdout_of(&out);
    assert!(stdout.contains("F1 1.0000"), "{stdout}");
}

#[test]
fn the_same_scene_in_two_syntaxes_is_one_graph() {
    // VSON-P on the left, VSON-X on the right: different files, different
    // parsers, different node naming (named IRIs against blank nodes), one
    // graph. Exit 0 is the whole claim of "it operates on the materialized
    // graph, so any surface syntax works".
    let out = vson(&repo_root(), &["diff", PENMAN, VSON_X]);
    assert_eq!(
        out.status.code(),
        Some(0),
        "expected exit 0\n{}",
        both_streams(&out)
    );
}

#[test]
fn documents_that_differ_exit_one() {
    let out = vson(&repo_root(), &["diff", RUN_A, RUN_B]);
    assert_eq!(
        out.status.code(),
        Some(1),
        "expected exit 1\n{}",
        both_streams(&out)
    );
    let stdout = stdout_of(&out);
    // The numbers, not just the word "differ": tests/test_smatch.py derives
    // these by hand, and this is the same table through the binary.
    assert!(stdout.contains("F1 0.7755"), "{stdout}");
    for layer in [
        "objects",
        "attributes",
        "spatial",
        "frames",
        "events",
        "other",
    ] {
        assert!(
            stdout.contains(layer),
            "the table must name {layer}\n{stdout}"
        );
    }
    assert!(
        stdout.contains("viewer-blind"),
        "the viewer-blind row is part of the contract\n{stdout}"
    );
}

#[test]
fn json_stdout_is_a_single_parseable_document() {
    let out = vson(&repo_root(), &["diff", "--format", "json", RUN_A, RUN_B]);
    assert_eq!(out.status.code(), Some(1), "{}", both_streams(&out));
    let stdout = stdout_of(&out);
    let payload: serde_json::Value = serde_json::from_str(&stdout)
        .unwrap_or_else(|e| panic!("stdout is not JSON: {e}\n{stdout}"));
    assert_eq!(payload["metric"], "vson-smatch");
    assert_eq!(payload["overall"]["matched_a"], 19);
    assert_eq!(payload["overall"]["triples_a"], 23);
    assert_eq!(payload["overall"]["triples_b"], 26);
    assert_eq!(payload["identical"], false);
    assert!(payload["layers"]["spatial_viewer_blind"].is_object());
    // The summary line would break `| jq`, so in JSON mode it is a payload key
    // and a line on stderr, never a bare line on stdout. `from_str` above
    // already proves stdout is exactly one JSON document; this says which one
    // of the two places the sentence went.
    assert!(payload["summary"]
        .as_str()
        .unwrap_or("")
        .contains("smatch:"));
    assert!(
        !stdout.lines().any(|line| line.starts_with("smatch:")),
        "the summary line leaked onto stdout\n{stdout}"
    );
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("smatch:"),
        "{}",
        both_streams(&out)
    );
}

#[test]
fn swapping_the_arguments_does_not_move_the_f1() {
    let root = repo_root();
    let forward = stdout_of(&vson(&root, &["diff", RUN_A, RUN_B]));
    let backward = stdout_of(&vson(&root, &["diff", RUN_B, RUN_A]));
    assert!(forward.contains("F1 0.7755"), "{forward}");
    assert!(backward.contains("F1 0.7755"), "{backward}");
}

#[test]
fn the_report_never_calls_a_document_correct() {
    // docs/vson.md §2.1. Agreement between two documents is the easiest number
    // in this repository to over-read, so the report says what it read.
    let root = repo_root();
    for args in [vec!["diff", RUN_A, RUN_A], vec!["diff", RUN_A, RUN_B]] {
        let combined = both_streams(&vson(&root, &args));
        assert!(
            combined.contains("No image was read.") || combined.contains("no image was read"),
            "{combined}"
        );
        for forbidden in ["accurate", "faithful", "verified against the image"] {
            assert!(
                !combined.contains(forbidden),
                "the report must not say {forbidden:?}\n{combined}"
            );
        }
    }
}

#[test]
fn an_unknown_format_is_a_usage_error() {
    // Exit 2 — no verdict. This one fails in Rust before anything is spawned,
    // so it needs no python3.
    let out = vson(&repo_root(), &["diff", "--format", "yaml", RUN_A, RUN_B]);
    assert_eq!(
        out.status.code(),
        Some(2),
        "expected exit 2\n{}",
        both_streams(&out)
    );
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("text, json"),
        "the error must name the formats that exist\n{}",
        both_streams(&out)
    );
}

#[test]
fn a_wrong_home_is_a_usage_error_not_a_verdict() {
    let out = vson(
        &repo_root(),
        &["diff", "--home", "/nonexistent-vson-home", RUN_A, RUN_B],
    );
    assert_eq!(
        out.status.code(),
        Some(2),
        "expected exit 2\n{}",
        both_streams(&out)
    );
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("tools/metrics/smatch.py"),
        "{}",
        both_streams(&out)
    );
}

#[test]
fn a_missing_input_is_a_usage_error_not_a_verdict() {
    // "I could not read one of them" and "they differ" are different answers,
    // and an exit code that conflated them would make `vson diff` useless in a
    // CI gate: a typo would read as agreement failure.
    let out = vson(&repo_root(), &["diff", RUN_A, "examples/no_such_scene.ttl"]);
    assert_eq!(
        out.status.code(),
        Some(2),
        "expected exit 2\n{}",
        both_streams(&out)
    );
}
