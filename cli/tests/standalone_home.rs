//! The binary, alone in an empty directory, with no checkout anywhere.
//!
//! This is the adoption test. Every other integration test in this crate runs
//! from the repository root, where the ontology, the shapes and the `tools/`
//! package are all one relative path away — which is exactly the condition a
//! downloaded release binary does not satisfy. Before the payload of
//! `src/commands/embed.rs` existed, six of the nine subcommands exited 2 here.
//!
//! Each test therefore:
//!
//! 1. makes an empty directory outside the checkout,
//! 2. **copies the binary into it** and runs that copy — not the one in
//!    `target/`, so nothing can be resolved relative to the build tree,
//! 3. writes its fixture there, so no input path leads back to a checkout,
//! 4. unsets `VSON_HOME` and points `VSON_CACHE_DIR` at a directory inside the
//!    sandbox, so the run is hermetic and the materialized tree can be
//!    asserted on.
//!
//! **What this does not claim.** The host still needs `python3` with `rdflib`,
//! `pyshacl` and `owlrl`: the binary is self-contained with respect to
//! *repository files*, not with respect to the Python runtime, and a machine
//! without those fails these tests for a reason the embedding cannot fix. That
//! boundary is stated in `cli/README.md` in the same words.

use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicUsize, Ordering};

/// The smallest SHACL-conformant scene (`examples/gallery/01_minimal.vson`),
/// inline rather than read from the checkout — a test about working without one
/// may not open a file inside it.
const MINIMAL_VSON: &str = "\
(scene / Composition
   :framedBy (cam / CameraView :angle eye_level :focalLength 50mm :framing close_up)
   :viewedBy cam
   :depicts (apple / PhysicalObject
               :individuation Generic
               :animacy Inert
               :countability Count
               :class Apple))
";

/// The same scene in VSON-X (`examples/gallery-x/01_minimal.x.vson`).
const MINIMAL_X: &str = "\
~scene
  /CameraView @cam *angle eye_level *focalLength 50mm *framing close_up
  ^cam
  apple /PhysicalObject Inert Count *class Apple
";

/// An empty directory holding a copy of the binary and nothing else, deleted on
/// drop.
struct Sandbox {
    dir: PathBuf,
    exe: PathBuf,
}

impl Sandbox {
    fn new(name: &str) -> Self {
        static SEQ: AtomicUsize = AtomicUsize::new(0);
        let dir = std::env::temp_dir().join(format!(
            "vson_standalone_{}_{}_{}",
            name,
            std::process::id(),
            SEQ.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).expect("temp dir must be creatable");

        let built = PathBuf::from(env!("CARGO_BIN_EXE_vson"));
        let exe = dir.join(built.file_name().expect("the binary has a file name"));
        std::fs::copy(&built, &exe).expect("the binary must be copyable");

        // No ancestor of the temp directory may be a checkout, or the test
        // would prove nothing. Belt and braces: the walk the binary does is the
        // walk asserted against here.
        let mut cur: Option<&Path> = Some(dir.as_path());
        while let Some(d) = cur {
            assert!(
                !d.join("ontology/vso.ttl").exists(),
                "{} is inside a VSON checkout; this test needs a directory that is not",
                dir.display()
            );
            cur = d.parent();
        }
        Sandbox { dir, exe }
    }

    fn write(&self, name: &str, body: &str) -> PathBuf {
        let path = self.dir.join(name);
        std::fs::write(&path, body).expect("sandbox must be writable");
        path
    }

    /// The cache the embedded copy is materialized into, inside the sandbox.
    fn cache(&self) -> PathBuf {
        self.dir.join("cache")
    }

    fn run(&self, args: &[&str]) -> Output {
        Command::new(&self.exe)
            .args(args)
            .current_dir(&self.dir)
            .env_remove("VSON_HOME")
            .env("VSON_CACHE_DIR", self.cache())
            .output()
            .expect("the copied binary must be runnable")
    }
}

impl Drop for Sandbox {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

fn assert_ok(out: &Output, what: &str) -> String {
    assert_eq!(
        out.status.code(),
        Some(0),
        "{what} must succeed outside a checkout, got {:?}\nstdout: {}\nstderr: {}",
        out.status.code(),
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr),
    );
    String::from_utf8_lossy(&out.stdout).into_owned()
}

#[test]
fn validate_conforms_with_no_checkout_present() {
    // The heaviest path: pyshacl over the embedded shapes and the three
    // embedded ontology files, then two Python gates imported out of the
    // embedded `tools/` package.
    let sandbox = Sandbox::new("validate");
    sandbox.write("scene.vson", MINIMAL_VSON);
    let out = sandbox.run(&["validate", "scene.vson"]);
    let stdout = assert_ok(&out, "vson validate");
    assert!(stdout.contains("OK  scene.vson"), "{stdout}");
}

#[test]
fn convert_p2t_emits_turtle_with_no_checkout_present() {
    // Pure Rust, and the one subcommand that always worked standalone. Here to
    // pin that the new home resolution did not break the case that needs none.
    let sandbox = Sandbox::new("p2t");
    sandbox.write("scene.vson", MINIMAL_VSON);
    let out = sandbox.run(&["convert", "p2t", "scene.vson"]);
    let stdout = assert_ok(&out, "vson convert p2t");
    assert!(stdout.contains("@prefix vso:"), "{stdout}");
    assert!(
        stdout.contains("Composition"),
        "the scene node must survive: {stdout}"
    );
}

#[test]
fn export_caption_renders_with_no_checkout_present() {
    // `tools/render/caption.py` plus the `verbs.json` beside it plus
    // `tools/penman/vson_penman.py` plus the routing tables that module reads
    // back out of `cli/src/penman/` — four embedded files, one line of output.
    let sandbox = Sandbox::new("caption");
    sandbox.write("scene.vson", MINIMAL_VSON);
    let out = sandbox.run(&["export", "caption", "scene.vson"]);
    let stdout = assert_ok(&out, "vson export caption");
    assert!(stdout.to_lowercase().contains("apple"), "{stdout}");
}

#[test]
fn export_fol_renders_with_no_checkout_present() {
    let sandbox = Sandbox::new("fol");
    sandbox.write("scene.vson", MINIMAL_VSON);
    let out = sandbox.run(&["export", "fol", "scene.vson"]);
    let stdout = assert_ok(&out, "vson export fol");
    assert!(stdout.contains("Composition(scene)."), "{stdout}");
}

#[test]
fn export_cypher_emits_one_statement_with_no_checkout_present() {
    let sandbox = Sandbox::new("cypher");
    sandbox.write("scene.vson", MINIMAL_VSON);
    let out = sandbox.run(&["export", "cypher", "scene.vson"]);
    let stdout = assert_ok(&out, "vson export cypher");
    assert!(stdout.starts_with("CREATE\n"), "{stdout}");
}

#[test]
fn convert_x2t_emits_turtle_with_no_checkout_present() {
    let sandbox = Sandbox::new("x2t");
    sandbox.write("scene.x.vson", MINIMAL_X);
    let out = sandbox.run(&["convert", "x2t", "scene.x.vson"]);
    let stdout = assert_ok(&out, "vson convert x2t");
    assert!(stdout.contains("@prefix vso:"), "{stdout}");
}

#[test]
fn verify_geometry_reaches_a_verdict_with_no_checkout_present() {
    let sandbox = Sandbox::new("geometry");
    sandbox.write("scene.vson", MINIMAL_VSON);
    let out = sandbox.run(&["verify", "--geometry", "scene.vson"]);
    let stdout = assert_ok(&out, "vson verify --geometry");
    assert!(stdout.contains("OK  scene.vson"), "{stdout}");
}

#[test]
fn diff_scores_two_surfaces_with_no_checkout_present() {
    // Cross-syntax, so the metric has to load both transpilers out of the
    // embedded package: `tools.penman` for the Penman file and `tools.vson_x`
    // for the compact one. Exit 0 is the assertion — the same scene, written
    // twice, is one graph.
    let sandbox = Sandbox::new("diff");
    sandbox.write("a.vson", MINIMAL_VSON);
    sandbox.write("b.x.vson", MINIMAL_X);
    let out = sandbox.run(&["diff", "a.vson", "b.x.vson"]);
    let stdout = assert_ok(&out, "vson diff");
    assert!(stdout.contains("F1 1.0000"), "{stdout}");
}

#[test]
fn the_embedded_files_are_written_once_and_reused() {
    // Materialization is keyed by version *and* payload: the second run must
    // find the stamp and not rewrite. Asserted through the file system, since
    // that is where the cost would be.
    let sandbox = Sandbox::new("cache");
    sandbox.write("scene.vson", MINIMAL_VSON);

    assert!(
        !sandbox.cache().exists(),
        "the sandbox starts with no cache"
    );
    assert_ok(
        &sandbox.run(&["export", "cypher", "scene.vson"]),
        "vson export cypher (pure Rust)",
    );
    assert!(
        !sandbox.cache().exists(),
        "a subcommand that needs no home must not materialize one"
    );

    assert_ok(
        &sandbox.run(&["export", "fol", "scene.vson"]),
        "vson export fol (first run)",
    );
    let version_dir = sandbox.cache().join(env!("CARGO_PKG_VERSION"));
    for rel in [
        "ontology/vso.ttl",
        "shapes/vson-shapes.ttl",
        "tools/render/fol.py",
        "tools/render/verbs.json",
        "cli/src/penman/routing-tables.json",
    ] {
        assert!(
            version_dir.join(rel).exists(),
            "{rel} must be materialized under {}",
            version_dir.display()
        );
    }

    let stamp = version_dir.join(".vson-embedded");
    let first = std::fs::metadata(&stamp).expect("the stamp is written last");
    assert_ok(
        &sandbox.run(&["export", "fol", "scene.vson"]),
        "vson export fol (second run)",
    );
    let second = std::fs::metadata(&stamp).expect("the stamp survives a second run");
    assert_eq!(
        first.modified().ok(),
        second.modified().ok(),
        "a materialized cache must be reused, not rewritten"
    );
}

#[test]
fn a_stale_vson_home_is_reported_rather_than_silently_replaced() {
    // The other half of the contract. An explicit home never falls back to the
    // embedded copy: a contributor who points VSON_HOME at the wrong directory
    // has to be told, not quietly handed shapes from a month ago.
    let sandbox = Sandbox::new("stale_home");
    sandbox.write("scene.vson", MINIMAL_VSON);
    let out = Command::new(&sandbox.exe)
        .args(["export", "fol", "scene.vson"])
        .current_dir(&sandbox.dir)
        .env("VSON_HOME", "/nonexistent-vson-home")
        .env("VSON_CACHE_DIR", sandbox.cache())
        .output()
        .expect("the copied binary must be runnable");

    assert_eq!(out.status.code(), Some(2), "a wrong home is not a verdict");
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("/nonexistent-vson-home"), "{stderr}");
    assert!(stderr.contains("tools/render/fol.py"), "{stderr}");
    assert!(
        stderr.contains("unset VSON_HOME"),
        "the message must name the way out: {stderr}"
    );
}
