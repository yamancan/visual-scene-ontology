//! Which directory a subcommand reads the ontology, the shapes and the
//! `tools/` package out of — and, when there is no such directory anywhere,
//! writing one.
//!
//! Every subcommand that spawns something needs a *home*: a directory laid out
//! like this repository. Four things can be one, in this order:
//!
//! 1. **`--home` / `$VSON_HOME`**, taken verbatim. An explicit home is never
//!    second-guessed and never falls back: a contributor testing an edit to
//!    `shapes/vson-shapes.ttl` must find out that the path is wrong, not
//!    silently get the copy compiled into the binary a month ago. Each command
//!    then reports whichever file it could not find there.
//! 2. **The input file's directory and its parents**, for the subcommands that
//!    take exactly one input. `vson export caption ~/checkout/scenes/x.vson`
//!    run from anywhere uses that checkout.
//! 3. **The working directory and its parents** — running from a checkout, or
//!    from anywhere inside one, keeps using it.
//! 4. **The copy embedded in this binary** ([`super::embed`]), materialized to
//!    a per-version cache directory. This is the leg that makes the binary work
//!    on a machine that has never seen a checkout.
//!
//! Legs 2 and 3 look for the file the caller is about to need — `probe` — not
//! for a generic marker, so a checkout too old to carry it is passed over
//! rather than picked and then blamed.

use super::{embed, Error, Result};
use std::path::{Path, PathBuf};

/// The file every home contains, and the one `validate` needs first. Used as
/// the probe by the subcommands that name several inputs and so have no single
/// module to look for.
pub const MARKER: &str = "ontology/vso.ttl";

/// Which of the four legs produced a home. Carried so that an error can say
/// where the directory it is complaining about came from — the difference
/// between "your `$VSON_HOME` is wrong" and "this binary's own copy is
/// incomplete" is the whole of what a reader needs.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Source {
    Given,
    Checkout,
    Embedded,
}

#[derive(Debug, Clone)]
pub struct Home {
    path: PathBuf,
    source: Source,
}

impl Home {
    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn source(&self) -> Source {
        self.source
    }

    pub fn join(&self, rel: impl AsRef<Path>) -> PathBuf {
        self.path.join(rel)
    }

    /// The home, named the way an error message should name it.
    pub fn describe(&self) -> String {
        match self.source {
            Source::Given => format!("{} (from --home / $VSON_HOME)", self.path.display()),
            Source::Checkout => format!("{} (the checkout found from here)", self.path.display()),
            Source::Embedded => {
                format!("{} (the copy embedded in this binary)", self.path.display())
            }
        }
    }
}

/// The first directory at or above `start` that contains `probe`.
fn checkout_above(start: &Path, probe: &str) -> Option<PathBuf> {
    let mut cur = Some(start);
    while let Some(dir) = cur {
        if dir.join(probe).exists() {
            return Some(dir.to_path_buf());
        }
        cur = dir.parent();
    }
    None
}

/// Resolve a home. `near` is the single input file a subcommand was given, if
/// it has exactly one; `probe` is the home-relative file that subcommand is
/// about to read.
///
/// The only error is a home that had to be materialized and could not be
/// written — everything else has already been decided by then.
pub fn resolve(explicit: Option<&Path>, near: Option<&Path>, probe: &str) -> Result<Home> {
    if let Some(path) = explicit {
        return Ok(Home {
            path: path.to_path_buf(),
            source: Source::Given,
        });
    }
    // `validate`, `verify` and `diff` declare `$VSON_HOME` to clap, so it
    // arrives as `explicit` above; the Python-backed three have no flag and
    // read it here. Both routes land on the same verbatim treatment.
    if let Some(value) = std::env::var_os("VSON_HOME").filter(|v| !v.is_empty()) {
        return Ok(Home {
            path: PathBuf::from(value),
            source: Source::Given,
        });
    }
    let from_input = near
        .and_then(|f| f.parent())
        .and_then(|dir| checkout_above(dir, probe));
    let found = from_input.or_else(|| {
        std::env::current_dir()
            .ok()
            .and_then(|cwd| checkout_above(&cwd, probe))
    });
    if let Some(path) = found {
        return Ok(Home {
            path,
            source: Source::Checkout,
        });
    }
    Ok(Home {
        path: embed::materialize()?,
        source: Source::Embedded,
    })
}

/// Fail with the message a missing file under a resolved home deserves: what
/// was looked for, where, and how that where was chosen.
pub fn missing(home: &Home, rel: &str, needed_by: &str) -> Error {
    let fix = match home.source() {
        Source::Given => {
            "Point --home / $VSON_HOME at a VSON checkout that has it, or unset \
             VSON_HOME to use the copy embedded in this binary."
        }
        Source::Checkout => {
            "This checkout does not carry it. Pass --home / $VSON_HOME for one \
             that does, or run from outside a checkout to use the copy embedded \
             in this binary."
        }
        Source::Embedded => {
            "This is a bug: the file is embedded in the binary and should have \
             been written here. Delete the directory and try again, or pass \
             --home / $VSON_HOME to use a checkout."
        }
    };
    Error::Usage(format!(
        "{} not found under {}; {} needs it.\n{}",
        rel,
        home.describe(),
        needed_by,
        fix
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_explicit_home_is_taken_verbatim() {
        let given = Path::new("/nonexistent-vson-home");
        let home = resolve(Some(given), None, MARKER).expect("explicit never materializes");
        assert_eq!(home.path(), given);
        assert_eq!(home.source(), Source::Given);
    }

    #[test]
    fn an_explicit_home_is_named_in_its_own_error() {
        let home = resolve(Some(Path::new("/nonexistent-vson-home")), None, MARKER).unwrap();
        let msg = missing(&home, MARKER, "the SHACL gate").to_string();
        assert!(msg.contains("/nonexistent-vson-home"), "{msg}");
        assert!(msg.contains(MARKER), "{msg}");
        assert!(msg.contains("VSON_HOME"), "{msg}");
    }

    #[test]
    fn the_checkout_walk_stops_at_the_first_directory_holding_the_probe() {
        // The crate's own tree: `src/commands/` has no `Cargo.toml`, `cli/` does.
        let crate_root = Path::new(env!("CARGO_MANIFEST_DIR"));
        let start = crate_root.join("src/commands");
        assert_eq!(
            checkout_above(&start, "Cargo.toml").as_deref(),
            Some(crate_root)
        );
        assert_eq!(checkout_above(&start, "no-such-file-anywhere"), None);
    }
}
