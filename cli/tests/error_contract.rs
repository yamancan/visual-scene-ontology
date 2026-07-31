//! The failure half of the CLI contract: what a caller sees when a command
//! never reaches a verdict.
//!
//! Exit 2 means "no verdict" — usage error, missing toolchain, unparseable
//! input — as opposed to exit 1, which means the tool ran and the document is
//! bad (that half is covered by `golden_validate.rs`). Scripts branch on those
//! two codes, so the codes are part of the interface and are pinned here.
//!
//! Every test in this file runs without python3, pyshacl or a network: each
//! command fails in Rust, before anything is spawned. That is deliberate —
//! these are the checks that must still run on a machine with no Python.

use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicUsize, Ordering};

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("the crate dir has a parent")
        .to_path_buf()
}

/// The binary under test, run from `dir`. `CARGO_BIN_EXE_<name>` is set by
/// cargo for integration tests, so no dev-dependency is needed to find it.
fn vson(dir: &Path) -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_vson"));
    cmd.current_dir(dir);
    cmd
}

/// A temp input file that deletes itself on drop, so a failing assertion does
/// not leak it.
struct TempInput(PathBuf);

impl TempInput {
    fn new(suffix: &str, body: &str) -> Self {
        static SEQ: AtomicUsize = AtomicUsize::new(0);
        let mut path = std::env::temp_dir();
        path.push(format!(
            "vson_error_contract_{}_{}{}",
            std::process::id(),
            SEQ.fetch_add(1, Ordering::Relaxed),
            suffix
        ));
        std::fs::write(&path, body).expect("temp dir must be writable");
        TempInput(path)
    }

    fn path(&self) -> &Path {
        &self.0
    }
}

impl Drop for TempInput {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

fn stderr_of(out: &Output) -> String {
    String::from_utf8_lossy(&out.stderr).into_owned()
}

fn assert_exit_2(out: &Output, what: &str) {
    assert_eq!(
        out.status.code(),
        Some(2),
        "{what} must exit 2 (no verdict), got {:?}\nstdout: {}\nstderr: {}",
        out.status.code(),
        String::from_utf8_lossy(&out.stdout),
        stderr_of(out),
    );
}

fn assert_stderr_mentions(out: &Output, needle: &str, what: &str) {
    let stderr = stderr_of(out);
    assert!(
        stderr.contains(needle),
        "{what} stderr must mention {needle:?}\nactual: {stderr}",
    );
}

#[test]
fn unparseable_penman_exits_2_with_a_parse_message() {
    // Unclosed node: the parser hits EOF mid-node. An input the tool cannot
    // read is not a failed document — it is no verdict at all.
    let input = TempInput::new(".vson", "(s / Composition :depicts (a / PhysicalObject)\n");
    let out = vson(&repo_root())
        .args(["convert", "p2t"])
        .arg(input.path())
        .output()
        .expect("binary must be runnable");

    assert_exit_2(&out, "convert p2t on unparseable Penman");
    assert_stderr_mentions(&out, "parse:", "convert p2t on unparseable Penman");
    assert!(
        out.stdout.is_empty(),
        "no partial Turtle may reach stdout: {}",
        String::from_utf8_lossy(&out.stdout),
    );
}

#[test]
fn missing_input_file_exits_2() {
    let missing = repo_root().join("examples/does_not_exist.vson");
    let out = vson(&repo_root())
        .args(["convert", "p2t"])
        .arg(&missing)
        .output()
        .expect("binary must be runnable");

    assert_exit_2(&out, "convert p2t on a missing path");
}

#[test]
fn missing_input_file_exits_2_before_reaching_python() {
    // The Python-backed subcommands check the input first, so a typo'd path
    // reports the typo rather than a python3 traceback — and this assertion
    // holds on a machine with no python3 at all.
    let missing = repo_root().join("examples/does_not_exist.vson");
    let out = vson(&repo_root())
        .args(["export", "caption"])
        .arg(&missing)
        .output()
        .expect("binary must be runnable");

    assert_exit_2(&out, "export caption on a missing path");
    assert_stderr_mentions(&out, "input file not found", "export caption");
}

#[test]
fn convert_t2p_exits_2_and_says_no_implementation_exists() {
    // t2p is a stub: no native Rust Turtle parser exists yet, and Turtle ->
    // Penman is unimplemented in every language in this repo. The error must
    // not send the user off to a Python command that does not exist.
    let out = vson(&repo_root())
        .args(["convert", "t2p", "examples/throne_room.ttl"])
        .output()
        .expect("binary must be runnable");

    assert_exit_2(&out, "convert t2p");
    assert_stderr_mentions(&out, "not implemented", "convert t2p");
    assert_stderr_mentions(&out, "no reference implementation", "convert t2p");

    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        !stderr.contains("to-penman"),
        "convert t2p must not name a `to-penman` subcommand: \
         vson_penman.py has no such command. stderr: {stderr}"
    );
}

#[test]
fn validate_with_a_bogus_home_exits_2_naming_the_missing_ontology() {
    // A wrong --home is the most common validate misconfiguration, and it is
    // caught before pyshacl is spawned — so this needs no Python either.
    let out = vson(&repo_root())
        .args(["validate", "--home", "/nonexistent-vson-home"])
        .arg("examples/throne_room.ttl")
        .output()
        .expect("binary must be runnable");

    assert_exit_2(&out, "validate --home /nonexistent-vson-home");
    assert_stderr_mentions(&out, "ontology/vso.ttl", "validate with a bogus home");
    assert_stderr_mentions(&out, "/nonexistent-vson-home", "validate with a bogus home");
}

#[test]
fn python_backed_command_outside_a_checkout_exits_2_naming_the_probe_path() {
    // Home resolution for the Python-backed subcommands is single-sourced in
    // `commands::python_bridge`: $VSON_HOME, then a walk up from the input
    // file, then the cwd. Run from a temp dir on an input in that temp dir,
    // with VSON_HOME pointing nowhere, all three legs miss — and the message
    // must say which file was being looked for.
    let input = TempInput::new(".vson", "(s / Composition)\n");
    let tmp_dir = input.path().parent().expect("temp files have a parent");
    let out = vson(tmp_dir)
        .args(["export", "fol"])
        .arg(input.path())
        .env("VSON_HOME", "/nonexistent-vson-home")
        .output()
        .expect("binary must be runnable");

    assert_exit_2(&out, "export fol outside a checkout");
    assert_stderr_mentions(&out, "tools/render/fol.py", "export fol outside a checkout");
    assert_stderr_mentions(&out, "VSON_HOME", "export fol outside a checkout");
}
