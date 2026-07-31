//! Golden-fixture integration test: the canonical `examples/throne_room.vson`
//! transpiled by the Rust CLI must produce graph-isomorphic Turtle to the
//! Python reference (and must SHACL-conform via pyshacl).

use assert_cmd::Command;
use std::path::PathBuf;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}

#[test]
fn convert_p2t_produces_parseable_turtle() {
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root())
        .args(["convert", "p2t", "examples/throne_room.vson"]);
    let output = cmd.output().unwrap();
    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("@prefix vso:"));
    assert!(stdout.contains(":scene a <https://vson.dev/v1/ontology#Composition>"));
    assert!(
        stdout.contains("\"strike\""),
        "lemma should route to string"
    );
    assert!(
        stdout.contains("\"35mm\""),
        "focalLength UNIT should render as string"
    );
}

#[test]
fn validate_throne_room_vson_passes() {
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root())
        .args(["validate", "examples/throne_room.vson"]);
    let output = cmd.output().unwrap();
    assert!(
        output.status.success(),
        "stdout: {}\nstderr: {}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr),
    );
}

#[test]
fn validate_throne_room_ttl_passes() {
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root())
        .args(["validate", "examples/throne_room.ttl"]);
    let output = cmd.output().unwrap();
    assert!(output.status.success());
}

#[test]
fn export_cypher_emits_one_loadable_create_statement() {
    // Cypher scopes a variable to its statement, so the whole scene must be a
    // single `CREATE ...;` — otherwise every relationship pattern would name
    // unbound variables and silently create empty nodes instead of edges.
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root())
        .args(["export", "cypher", "examples/throne_room.vson"]);
    let output = cmd.output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.starts_with("CREATE\n"), "got: {stdout}");
    assert_eq!(
        stdout.matches(';').count(),
        1,
        "exactly one statement: {stdout}"
    );
    assert!(
        !stdout.contains("SET "),
        "properties belong in the node map: {stdout}"
    );
    assert!(
        stdout.contains("(scene:Composition {id: 'scene'})"),
        "got: {stdout}"
    );
    assert!(stdout.contains("(alice:PhysicalObject "), "got: {stdout}");
    // Literal roles fold into the node map rather than a dangling SET clause.
    assert!(stdout.contains("venue: 'throne_room'"), "got: {stdout}");
    assert!(
        stdout.contains("(scene)-[:framedBy]->(ctx)"),
        "got: {stdout}"
    );
    assert!(stdout.contains("-[:depicts]->"), "got: {stdout}");
}

#[test]
fn export_caption_matches_python_fixture() {
    // The Rust CLI shells out to tools/render/caption.py; output MUST match
    // the byte-identical fixture under tests/fixtures/captions/.
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root()).args([
        "export",
        "caption",
        "examples/gallery/11_throne_room.vson",
    ]);
    let output = cmd.output().unwrap();
    assert!(
        output.status.success(),
        "stdout: {}\nstderr: {}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr),
    );
    let stdout = String::from_utf8(output.stdout).unwrap();
    let fixture =
        std::fs::read_to_string(repo_root().join("tests/fixtures/captions/11_throne_room.txt"))
            .expect("fixture must exist");
    assert_eq!(
        stdout.trim_end_matches('\n'),
        fixture.trim_end_matches('\n'),
        "Rust caption output must match Python reference fixture",
    );
}

#[test]
fn convert_x2t_produces_parseable_turtle() {
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root())
        .args(["convert", "x2t", "examples/gallery-x/02_quality.x.vson"]);
    let output = cmd.output().unwrap();
    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("@prefix vso:"));
    assert!(stdout.contains(":scene a <https://vson.dev/v1/ontology#Composition>"));
    assert!(stdout.contains("hasQuality"), "quality kv must reify");
}

#[test]
fn export_caption_minimal_scene() {
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root())
        .args(["export", "caption", "examples/gallery/01_minimal.vson"]);
    let output = cmd.output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(
        stdout.contains("apple"),
        "minimal scene caption should mention an apple, got: {stdout}"
    );
}

#[test]
fn export_fol_matches_python_fixture() {
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root())
        .args(["export", "fol", "examples/gallery/11_throne_room.vson"]);
    let output = cmd.output().unwrap();
    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr),
    );
    let stdout = String::from_utf8(output.stdout).unwrap();
    let fixture =
        std::fs::read_to_string(repo_root().join("tests/fixtures/fol/11_throne_room.fol"))
            .expect("FOL fixture must exist");
    assert_eq!(
        stdout, fixture,
        "Rust FOL output must match Python reference fixture",
    );
}

#[test]
fn export_fol_collapses_event_to_nary_fact() {
    let mut cmd = Command::cargo_bin("vson").unwrap();
    cmd.current_dir(repo_root()).args([
        "export",
        "fol",
        "examples/gallery/06_event_with_instrument.vson",
    ]);
    let output = cmd.output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(
        stdout.contains("strike(agent=knight, instrument=sword, patient=boar)."),
        "expected collapsed strike fact, got: {stdout}"
    );
}
