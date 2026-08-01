//! The repository files this binary carries, and the directory it writes them
//! to when there is no checkout to read them from.
//!
//! Six of the nine subcommands need files that used to exist only inside a
//! checkout: `validate` reads the three ontology files and the shapes and runs
//! two Python gates; `verify`, `diff`, `convert x2t`, `export caption` and
//! `export fol` each run a Python module out of `tools/`. A binary copied
//! anywhere else therefore exited 2 on all six — an install trap, and the
//! reason this module exists. Only `convert p2t` and `export cypher` (pure
//! Rust) ever worked standalone.
//!
//! What is carried is [`ASSETS`]: all three ontology files, both shape files,
//! the Python package closure every spawned module imports, the caption
//! renderer's `verbs.json`, and `routing-tables.json` — which the Python
//! transpiler reads back out of `cli/src/penman/`, so the materialized tree has
//! to reproduce that path too, not just the file.
//!
//! **Why a directory on disk rather than memory.** The three consumers are
//! `pyshacl` (a separate process that takes file paths), `python3 -m tools.…`
//! (an import system that reads a package tree off `sys.path`), and those
//! modules' own `os.path.join(ROOT, "ontology/vso.ttl")` reads. None of them
//! can be handed a `&str`, so the files have to become files.
//!
//! **What the host must still provide.** Not a Python runtime: `python3`,
//! `rdflib`, `pyshacl` and `owlrl` remain host dependencies. This binary is
//! self-contained with respect to *repository files* only, which is what
//! `cli/README.md` claims in those words and no more.
//!
//! **Why the mirror under `cli/assets/` exists.** `include_str!` may not reach
//! outside the crate root — a `../../ontology/vso.ttl` path compiles inside a
//! checkout but fails the isolated verify build `cargo package` runs, which
//! would make the crate unpublishable (the same constraint that put
//! `routing-tables.json` inside `src/penman/`). So the crate carries a
//! byte-identical mirror, and `scripts/check_embedded_assets.py` — run by `make
//! cli-check` — is what proves it is still a mirror: byte equality against the
//! repository original, no orphan mirrored file, no `tools.…` import that
//! escapes the embedded closure, and no path named in `cli/src/` that is not
//! carried. `--sync` refreshes it.

use super::{Error, Result};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

/// `(path relative to the materialized home, contents)`.
///
/// The left column is where the file has to land for the Python side to find
/// it: `tools/` is the package `python3 -m` imports, `ontology/` and `shapes/`
/// are what `os.path.join(ROOT, …)` and `pyshacl -s` read, and
/// `cli/src/penman/routing-tables.json` is where `tools/penman/vson_penman.py`
/// looks — three directories up from itself, i.e. back at the home root.
///
/// `scripts/check_embedded_assets.py` parses this list; keep it a flat array of
/// `("<rel path>", include_str!("<crate path>"))` pairs.
pub const ASSETS: &[(&str, &str)] = &[
    (
        "ontology/vso.ttl",
        include_str!("../../assets/ontology/vso.ttl"),
    ),
    (
        "ontology/rcc8.ttl",
        include_str!("../../assets/ontology/rcc8.ttl"),
    ),
    (
        "ontology/allen.ttl",
        include_str!("../../assets/ontology/allen.ttl"),
    ),
    (
        "shapes/vson-shapes.ttl",
        include_str!("../../assets/shapes/vson-shapes.ttl"),
    ),
    (
        "shapes/vson-shapes-relaxed.ttl",
        include_str!("../../assets/shapes/vson-shapes-relaxed.ttl"),
    ),
    (
        "cli/src/penman/routing-tables.json",
        include_str!("../penman/routing-tables.json"),
    ),
    (
        "tools/__init__.py",
        include_str!("../../assets/tools/__init__.py"),
    ),
    (
        "tools/vson_ast.py",
        include_str!("../../assets/tools/vson_ast.py"),
    ),
    (
        "tools/c2_check.py",
        include_str!("../../assets/tools/c2_check.py"),
    ),
    (
        "tools/owlrl_check.py",
        include_str!("../../assets/tools/owlrl_check.py"),
    ),
    (
        "tools/geometry_check.py",
        include_str!("../../assets/tools/geometry_check.py"),
    ),
    (
        "tools/penman/__init__.py",
        include_str!("../../assets/tools/penman/__init__.py"),
    ),
    (
        "tools/penman/vson_penman.py",
        include_str!("../../assets/tools/penman/vson_penman.py"),
    ),
    (
        "tools/render/__init__.py",
        include_str!("../../assets/tools/render/__init__.py"),
    ),
    (
        "tools/render/caption.py",
        include_str!("../../assets/tools/render/caption.py"),
    ),
    (
        "tools/render/fol.py",
        include_str!("../../assets/tools/render/fol.py"),
    ),
    (
        "tools/render/verbs.json",
        include_str!("../../assets/tools/render/verbs.json"),
    ),
    (
        "tools/vson_x/__init__.py",
        include_str!("../../assets/tools/vson_x/__init__.py"),
    ),
    (
        "tools/vson_x/vson_x.py",
        include_str!("../../assets/tools/vson_x/vson_x.py"),
    ),
    (
        "tools/metrics/__init__.py",
        include_str!("../../assets/tools/metrics/__init__.py"),
    ),
    (
        "tools/metrics/smatch.py",
        include_str!("../../assets/tools/metrics/smatch.py"),
    ),
];

/// Written last, and read first: a materialized home is only trusted once this
/// file says the payload that produced it is the payload this binary carries.
/// A process killed mid-write leaves no stamp, so the next run rewrites.
const STAMP: &str = ".vson-embedded";

/// FNV-1a over every `(path, body)` pair.
///
/// The version alone is not enough to key the cache: two development builds of
/// the same version differ in payload every time a shape or a renderer is
/// edited, and a stale materialized tree would then be validated against while
/// the checkout said otherwise. Not a security property — nothing here defends
/// against a hostile cache directory — just a change detector, which is why a
/// 64-bit non-cryptographic hash is the right size.
fn fingerprint() -> String {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    let mut eat = |bytes: &[u8]| {
        for byte in bytes {
            hash ^= u64::from(*byte);
            hash = hash.wrapping_mul(0x1000_0000_01b3);
        }
    };
    for (path, body) in ASSETS {
        eat(path.as_bytes());
        eat(b"\0");
        eat(body.as_bytes());
        eat(b"\0");
    }
    format!("{hash:016x}")
}

fn stamp_body() -> String {
    format!(
        "vson {} {} ({} files)\n",
        env!("CARGO_PKG_VERSION"),
        fingerprint(),
        ASSETS.len()
    )
}

/// `$HOME`-relative cache location, per platform convention.
#[cfg(target_os = "macos")]
fn platform_cache(home: &Path) -> PathBuf {
    home.join("Library/Caches/vson")
}

#[cfg(not(target_os = "macos"))]
fn platform_cache(home: &Path) -> PathBuf {
    home.join(".cache/vson")
}

/// A non-empty variable, as a path. Empty is treated as unset: `VSON_CACHE_DIR=`
/// in a shell profile must not resolve the cache to `/`.
fn as_dir(value: Option<std::ffi::OsString>) -> Option<PathBuf> {
    value.filter(|v| !v.is_empty()).map(PathBuf::from)
}

fn env_dir(key: &str) -> Option<PathBuf> {
    as_dir(std::env::var_os(key))
}

/// Where the embedded copy is written, *before* the per-version segment.
///
/// `$VSON_CACHE_DIR` first, so a read-only or non-existent home directory —
/// containers, CI runners, `nobody` — has one documented escape hatch that
/// needs no checkout. Then the XDG variable, then the platform default, and
/// finally the temp directory, which is always writable and always the wrong
/// place to keep something across reboots.
///
/// The lookup is a parameter so the precedence can be tested without writing to
/// the process environment: `std::env::set_var` is global, and cargo runs tests
/// in threads.
fn cache_root_from(lookup: impl Fn(&str) -> Option<PathBuf>) -> PathBuf {
    if let Some(dir) = lookup("VSON_CACHE_DIR") {
        return dir;
    }
    if let Some(dir) = lookup("XDG_CACHE_HOME") {
        return dir.join("vson");
    }
    // Windows sets LOCALAPPDATA and usually no HOME; checking it before HOME
    // costs nothing anywhere else, since no other platform sets it.
    if let Some(dir) = lookup("LOCALAPPDATA") {
        return dir.join("vson");
    }
    if let Some(dir) = lookup("HOME") {
        return platform_cache(&dir);
    }
    std::env::temp_dir().join("vson-cache")
}

fn cache_root() -> PathBuf {
    cache_root_from(env_dir)
}

fn unwritable(dir: &Path, e: &std::io::Error) -> Error {
    Error::Usage(format!(
        "could not write the files embedded in this binary to {}: {}\n\
         Set VSON_CACHE_DIR to a writable directory, or VSON_HOME to a VSON \
         checkout, and the copy is not needed at all.",
        dir.display(),
        e
    ))
}

/// Write `body` to `dest` through a temp file in the same directory, so a
/// concurrent reader sees either the old file or the whole new one. Two `vson`
/// processes materializing at once write identical bytes, so which rename wins
/// does not matter.
fn write_atomic(dest: &Path, body: &str) -> std::io::Result<()> {
    static SEQ: AtomicUsize = AtomicUsize::new(0);
    let parent = dest.parent().unwrap_or(Path::new("."));
    let name = dest.file_name().unwrap_or_default().to_string_lossy();
    let tmp = parent.join(format!(
        ".{}.{}.{}.tmp",
        name,
        std::process::id(),
        SEQ.fetch_add(1, Ordering::Relaxed)
    ));
    std::fs::write(&tmp, body)?;
    match std::fs::rename(&tmp, dest) {
        Ok(()) => Ok(()),
        Err(e) => {
            let _ = std::fs::remove_file(&tmp);
            Err(e)
        }
    }
}

/// Materialize the embedded files and return the directory they live in.
///
/// Per version *and* per payload: `<cache>/vson/<version>/`, refreshed whenever
/// the stamp does not match this binary's payload. Already-materialized trees
/// cost one small read.
pub fn materialize() -> Result<PathBuf> {
    let root = cache_root().join(env!("CARGO_PKG_VERSION"));
    let stamp = root.join(STAMP);
    let want = stamp_body();
    if std::fs::read_to_string(&stamp).is_ok_and(|found| found == want) {
        return Ok(root);
    }

    for (rel, body) in ASSETS {
        let dest = root.join(rel);
        if let Some(parent) = dest.parent() {
            std::fs::create_dir_all(parent).map_err(|e| unwritable(parent, &e))?;
        }
        write_atomic(&dest, body).map_err(|e| unwritable(&root, &e))?;
    }
    write_atomic(&stamp, &want).map_err(|e| unwritable(&root, &e))?;
    Ok(root)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_asset_lands_under_the_home_root() {
        // A `..` or an absolute path would write outside the cache directory.
        for (rel, _) in ASSETS {
            assert!(
                !rel.starts_with('/') && !rel.split('/').any(|seg| seg == ".."),
                "{rel} must be a plain relative path"
            );
        }
    }

    #[test]
    fn no_asset_is_listed_twice() {
        let mut seen: Vec<&str> = ASSETS.iter().map(|(rel, _)| *rel).collect();
        seen.sort_unstable();
        let before = seen.len();
        seen.dedup();
        assert_eq!(before, seen.len(), "duplicate path in ASSETS");
    }

    #[test]
    fn the_python_package_carries_its_init_files() {
        // `python3 -m tools.render.caption` imports `tools`, then `tools.render`
        // before the module itself: a package directory without `__init__.py`
        // resolves as a namespace package and the relative imports inside it
        // fail. Cheap to lose, and only the runtime notices.
        for package in ["tools", "tools/penman", "tools/render", "tools/vson_x"] {
            let init = format!("{package}/__init__.py");
            assert!(
                ASSETS.iter().any(|(rel, _)| *rel == init),
                "{init} must be embedded"
            );
        }
    }

    #[test]
    fn the_fingerprint_covers_the_payload() {
        // Same list, same fingerprint — otherwise the stamp would rewrite the
        // tree on every run.
        assert_eq!(fingerprint(), fingerprint());
        assert_eq!(fingerprint().len(), 16);
    }

    /// A fake environment: only the named variables are set.
    fn only<'a>(set: &'a [(&'a str, &'a str)]) -> impl Fn(&str) -> Option<PathBuf> + 'a {
        move |key| {
            set.iter()
                .find(|(k, _)| *k == key)
                .map(|(_, v)| PathBuf::from(v))
        }
    }

    #[test]
    fn the_explicit_cache_override_outranks_every_convention() {
        assert_eq!(
            cache_root_from(only(&[
                ("VSON_CACHE_DIR", "/pinned"),
                ("XDG_CACHE_HOME", "/xdg"),
                ("HOME", "/home/u"),
            ])),
            PathBuf::from("/pinned"),
        );
    }

    #[test]
    fn the_conventions_are_tried_in_order() {
        assert_eq!(
            cache_root_from(only(&[("XDG_CACHE_HOME", "/xdg"), ("HOME", "/home/u")])),
            PathBuf::from("/xdg/vson"),
        );
        assert_eq!(
            cache_root_from(only(&[("HOME", "/home/u")])),
            platform_cache(Path::new("/home/u")),
        );
        // No home of any kind — a daemon, a container with no passwd entry.
        // The temp directory is always writable, and the least durable place
        // this could land, which is the right trade for a fallback.
        assert_eq!(
            cache_root_from(only(&[])),
            std::env::temp_dir().join("vson-cache"),
        );
    }

    #[test]
    fn an_empty_variable_is_not_a_path() {
        // `VSON_CACHE_DIR=` exported by a shell profile must not resolve the
        // cache to the filesystem root.
        assert_eq!(as_dir(Some(std::ffi::OsString::from(""))), None);
        assert_eq!(as_dir(None), None);
        assert_eq!(
            as_dir(Some(std::ffi::OsString::from("/x"))),
            Some(PathBuf::from("/x"))
        );
    }

    #[test]
    fn the_stamp_names_the_version_it_was_written_by() {
        // The cache directory is per version; the stamp is what catches the
        // other half — a payload edited without a version bump, which is every
        // development build.
        let stamp = stamp_body();
        assert!(stamp.contains(env!("CARGO_PKG_VERSION")), "{stamp}");
        assert!(stamp.contains(&fingerprint()), "{stamp}");
    }
}
