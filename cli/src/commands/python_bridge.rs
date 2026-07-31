//! The shell-out bridge to the Python reference implementations.
//!
//! `convert x2t`, `export caption` and `export fol` all delegate to a Python
//! module under `tools/`: those modules are the single source of truth for the
//! round-trip and renderer fixtures CI checks, so the Rust binary cannot drift
//! from them. All three need exactly the same four things — a repo root to run
//! the module from, an absolute input path, a `python3 -m <module>` invocation,
//! and one error message when any of that fails — so that logic lives here
//! once instead of once per subcommand.

use super::{Error, Result};
use std::ffi::OsStr;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Find the repo root to run the module from, looking in this order:
///
/// 1. `$VSON_HOME`, if it contains `probe`;
/// 2. the input file's directory, then each parent, until one contains `probe`;
/// 3. the current working directory, if it contains `probe`.
///
/// `probe` is the source file of the very module about to be run, so a home
/// that resolves here is a home the module can actually be imported from —
/// `python3 -m` puts the child's cwd on `sys.path`. These subcommands have no
/// `--home` flag; only `validate` does.
///
/// `input_file` must already be absolute, otherwise the walk-up starts from a
/// path that has no parents to walk.
fn locate_home(probe: &str, input_file: &Path) -> Result<PathBuf> {
    if let Ok(p) = std::env::var("VSON_HOME") {
        let home = PathBuf::from(p);
        if home.join(probe).exists() {
            return Ok(home);
        }
    }

    let mut cur = input_file.parent();
    while let Some(dir) = cur {
        if dir.join(probe).exists() {
            return Ok(dir.to_path_buf());
        }
        cur = dir.parent();
    }

    let cwd = std::env::current_dir().map_err(Error::Io)?;
    if cwd.join(probe).exists() {
        return Ok(cwd);
    }

    Err(Error::Usage(format!(
        "could not find a VSON checkout containing {probe}: not under $VSON_HOME, \
         not in any parent directory of {}, not in the current directory. \
         Point VSON_HOME at a checkout, or run from its root.",
        input_file.display()
    )))
}

/// The child runs with the repo root as its cwd, so a path relative to *our*
/// cwd would not resolve there.
fn absolutize(file: &Path) -> Result<PathBuf> {
    if file.is_absolute() {
        Ok(file.to_path_buf())
    } else {
        Ok(std::env::current_dir().map_err(Error::Io)?.join(file))
    }
}

/// A failed spawn is all but always "no python3 on PATH" — the only other
/// input to `Command` is a cwd we just proved exists by finding a file in it.
fn spawn_error(e: std::io::Error, module: &str) -> Error {
    if e.kind() == std::io::ErrorKind::NotFound {
        Error::Usage(format!(
            "python3 not on PATH; this subcommand runs `python3 -m {module}`, \
             the Python reference implementation"
        ))
    } else {
        Error::Io(e)
    }
}

/// Run `python3 -m <module> <args...> <input_file>` from the resolved repo
/// root and copy its stdout to ours.
///
/// `probe_rel_path` is the module's source file relative to the repo root
/// (e.g. `tools/render/fol.py`); it is what home resolution looks for and what
/// the "no checkout found" message names.
pub fn run_python_module(
    module: &str,
    probe_rel_path: &str,
    args: &[&OsStr],
    input_file: &Path,
) -> Result<()> {
    if !input_file.exists() {
        return Err(Error::Usage(format!(
            "input file not found: {}",
            input_file.display()
        )));
    }

    let abs_file = absolutize(input_file)?;
    let home = locate_home(probe_rel_path, &abs_file)?;

    let output = Command::new("python3")
        .arg("-m")
        .arg(module)
        .args(args)
        .arg(&abs_file)
        .current_dir(&home)
        .output()
        .map_err(|e| spawn_error(e, module))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stderr = stderr.trim();
        return Err(Error::Usage(format!(
            "`python3 -m {}` {} in {}:\n{}",
            module,
            match output.status.code() {
                Some(c) => format!("exited {c}"),
                None => "was killed by a signal".to_string(),
            },
            home.display(),
            if stderr.is_empty() {
                "(the module wrote nothing to stderr)"
            } else {
                stderr
            }
        )));
    }

    std::io::stdout().write_all(&output.stdout)?;
    Ok(())
}
