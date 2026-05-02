//! Negative SHACL fixtures: each must fail with exit 1.

use assert_cmd::Command;
use std::path::PathBuf;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
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
