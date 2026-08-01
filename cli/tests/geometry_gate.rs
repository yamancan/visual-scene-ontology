//! `vson verify --geometry` — the fourth construct, at the binary boundary.
//!
//! The load-bearing test is `conformant_and_geometry_inconsistent`. It runs
//! both subcommands over one file and pins the combination the whole of
//! docs/vson.md §5.13 is about: `validate` exits 0 — SHACL, OWL 2 RL and C2 all
//! green, so the document is conformant VSON — while `verify --geometry` exits
//! 1, because the relation it asserts is refuted by the rectangles it asserts
//! beside it. If a future shape ever starts rejecting that fixture, the claim
//! that geometry inconsistency is invisible to the conformance surface has
//! stopped being true, and this test says so.
//!
//! The rest pin the interface: which exit code means what, that a check must be
//! named, and that stdout stays scriptable.

use std::path::{Path, PathBuf};
use std::process::{Command, Output};

const CONSISTENT: &str = "tests/fixtures/geometry_consistent.ttl";
const BAD_RCC: &str = "tests/fixtures/geometry_inconsistent_rcc.ttl";
const BAD_DIRECTIONAL: &str = "tests/fixtures/geometry_inconsistent_directional.ttl";

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
fn a_consistent_document_clears_the_gate() {
    let out = vson(&repo_root(), &["verify", "--geometry", CONSISTENT]);
    assert_eq!(
        out.status.code(),
        Some(0),
        "expected exit 0\n{}",
        both_streams(&out)
    );
    assert!(stdout_of(&out).contains("OK  "), "{}", stdout_of(&out));
}

#[test]
fn a_refuted_rcc_relation_fails_the_gate() {
    let out = vson(&repo_root(), &["verify", "--geometry", BAD_RCC]);
    assert_eq!(
        out.status.code(),
        Some(1),
        "expected exit 1\n{}",
        both_streams(&out)
    );
    assert!(
        stdout_of(&out).contains("(geometry)"),
        "the failure must be attributed to the geometry check\n{}",
        stdout_of(&out)
    );
    // Asserting on the refutation itself, not on the word "fail": the report
    // has to say which relation was refuted and why.
    let combined = both_streams(&out);
    assert!(combined.contains("sf_mug_shelf"), "{combined}");
    assert!(combined.contains("NTPP entails"), "{combined}");
}

#[test]
fn a_refuted_direction_fails_the_gate() {
    let out = vson(&repo_root(), &["verify", "--geometry", BAD_DIRECTIONAL]);
    assert_eq!(out.status.code(), Some(1), "{}", both_streams(&out));
    let combined = both_streams(&out);
    assert!(combined.contains("sf_sign_door"), "{combined}");
    assert!(combined.contains("left_of"), "{combined}");
}

#[test]
fn conformant_and_geometry_inconsistent() {
    let root = repo_root();
    for fixture in [BAD_RCC, BAD_DIRECTIONAL] {
        let validate = vson(&root, &["validate", fixture]);
        assert_eq!(
            validate.status.code(),
            Some(0),
            "{fixture} must pass all three conformance gates\n{}",
            both_streams(&validate)
        );
        let verify = vson(&root, &["verify", "--geometry", fixture]);
        assert_eq!(
            verify.status.code(),
            Some(1),
            "{fixture} must fail the geometry check\n{}",
            both_streams(&verify)
        );
    }
}

#[test]
fn the_report_never_calls_a_document_correct() {
    // docs/vson.md §2.1: no tool may present a passing result as evidence about
    // the image. This gate is the one most likely to be over-read, so it says
    // what it read on every run.
    let out = vson(
        &repo_root(),
        &["verify", "--geometry", "--verbose", CONSISTENT],
    );
    let combined = both_streams(&out);
    assert!(combined.contains("No image was read."), "{combined}");
    for forbidden in ["accurate", "faithful", "verified against the image"] {
        assert!(
            !combined.contains(forbidden),
            "the report must not say {forbidden:?}\n{combined}"
        );
    }
}

#[test]
fn a_vson_input_is_reported_under_the_name_the_user_typed() {
    // A .vson is transpiled to a temp .ttl first. The report must still name
    // the source, or the output points at a file that no longer exists.
    let out = vson(
        &repo_root(),
        &[
            "verify",
            "--geometry",
            "--verbose",
            "examples/gallery/10_geometry_bbox.vson",
        ],
    );
    assert_eq!(out.status.code(), Some(0), "{}", both_streams(&out));
    let combined = both_streams(&out);
    assert!(
        combined.contains("examples/gallery/10_geometry_bbox.vson"),
        "{combined}"
    );
    assert!(
        !combined.contains("/vson_10_geometry_bbox_"),
        "the temp file's name leaked into the report\n{combined}"
    );
}

#[test]
fn stdout_carries_only_the_verdict_lines() {
    // `vson verify` is scriptable on the same terms as `vson validate`: the
    // human-readable report is stderr, so stdout is one line per input.
    let out = vson(
        &repo_root(),
        &["verify", "--geometry", "--verbose", CONSISTENT, BAD_RCC],
    );
    let stdout = stdout_of(&out);
    let lines: Vec<&str> = stdout.lines().collect();
    assert_eq!(lines.len(), 2, "stdout was:\n{stdout}");
    assert!(lines[0].starts_with("OK  "), "{stdout}");
    assert!(lines[1].starts_with("FAIL "), "{stdout}");
}

#[test]
fn verify_without_a_named_check_is_a_usage_error() {
    // Not a shorthand for "run everything": a second check landing later must
    // not change what an existing command line means. Exit 2 — no verdict.
    // This one needs no python3: it fails in Rust before anything is spawned.
    let out = vson(&repo_root(), &["verify", CONSISTENT]);
    assert_eq!(
        out.status.code(),
        Some(2),
        "expected exit 2\n{}",
        both_streams(&out)
    );
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("--geometry"),
        "the error must name the checks that exist\n{}",
        both_streams(&out)
    );
}

#[test]
fn a_wrong_home_is_a_usage_error_not_a_verdict() {
    // Exit 2, again without python3: the checker's own source is missing under
    // the home, so no verdict is possible and none is invented.
    let out = vson(
        &repo_root(),
        &[
            "verify",
            "--geometry",
            "--home",
            "/nonexistent-vson-home",
            CONSISTENT,
        ],
    );
    assert_eq!(
        out.status.code(),
        Some(2),
        "expected exit 2\n{}",
        both_streams(&out)
    );
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("tools/geometry_check.py"),
        "{}",
        both_streams(&out)
    );
}
