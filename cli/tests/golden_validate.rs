//! Negative validation fixtures: each must fail with exit 1.
//!
//! The last one is not a SHACL fixture. `bad_orphan_term.ttl` satisfies every
//! shape and is OWL 2 RL consistent; it fails clause C2 alone, so it fails only
//! if `vson validate` really reaches its third gate. Without it, deleting the
//! C2 gate would leave every test in this file green.

use assert_cmd::Command;
use std::path::PathBuf;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}

fn assert_validation_fails(fixture: &str, must_contain: &str) {
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root()).args(["validate", fixture]);
    let output = cmd.output().unwrap();
    assert_eq!(
        output.status.code(),
        Some(1),
        "expected exit 1 for {fixture}, got {:?}\nstdout: {}",
        output.status.code(),
        String::from_utf8_lossy(&output.stdout),
    );
    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr),
    );
    assert!(
        combined.contains(must_contain),
        "expected report to mention {must_contain:?}\nactual: {combined}",
    );
}

#[test]
fn no_viewer_fails() {
    assert_validation_fails("tests/fixtures/bad_no_viewer.ttl", "viewer");
}

#[test]
fn frame_depicted_fails() {
    assert_validation_fails("tests/fixtures/bad_frame_depicted.ttl", "depicts");
}

#[test]
fn event_no_lemma_fails() {
    assert_validation_fails("tests/fixtures/bad_event_no_lemma.ttl", "lemma");
}

#[test]
fn orphan_vso_term_fails() {
    // C2 (docs/vson.md §2). `vso:Ambience` is not a registered dimension, and
    // §5.5.1 names that exact case as a C2 violation. Asserting on the term
    // itself, not on the word "orphan", so the test pins what was rejected.
    assert_validation_fails("tests/fixtures/bad_orphan_term.ttl", "Ambience");
}

#[test]
fn the_c2_gate_runs_after_the_other_two() {
    // Not redundant with the test above: this pins that a C2 failure is
    // *reported as* a C2 failure. If the gate ever moved ahead of SHACL, or the
    // label drifted, the `FAIL ... (c2)` line would change and the surviving
    // assertion above would not notice.
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root())
        .args(["validate", "tests/fixtures/bad_orphan_term.ttl"]);
    let output = cmd.output().unwrap();
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.contains("(c2)"),
        "expected the failure to be attributed to the c2 gate\nstdout: {stdout}",
    );
}
