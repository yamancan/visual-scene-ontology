//! `vson export caption <file>` — render a VSON Penman document to a
//! deterministic English caption suitable for image-generation models.
//!
//! Implementation: shells out to the canonical Python renderer at
//! `tools/render/caption.py`. A native Rust port is planned for v1.2; until
//! then the Python implementation is the single source of truth so the
//! Rust binary cannot drift from the deterministic CI fixtures under
//! `tests/fixtures/captions/`.
//!
//! Exit codes:
//!   0  on success (caption printed to stdout)
//!   2  on usage error (python3 missing, file unreadable, repo home
//!      cannot be located, Python invocation failed)

use super::{Error, Result};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Locate the repo root so `python3 -m tools.render.caption` can resolve
/// the module. Strategy: VSON_HOME env, then walk up from the input file
/// looking for `tools/render/caption.py`, then current working directory.
fn locate_home(file: &Path) -> Result<PathBuf> {
    if let Ok(p) = std::env::var("VSON_HOME") {
        let home = PathBuf::from(p);
        if home.join("tools/render/caption.py").exists() {
            return Ok(home);
        }
    }

    let abs = if file.is_absolute() {
        file.to_path_buf()
    } else {
        std::env::current_dir()
            .ok()
            .map(|cwd| cwd.join(file))
            .unwrap_or_else(|| file.to_path_buf())
    };

    let mut cur = abs.parent().map(|p| p.to_path_buf());
    while let Some(dir) = cur {
        if dir.join("tools/render/caption.py").exists() {
            return Ok(dir);
        }
        cur = dir.parent().map(|p| p.to_path_buf());
    }

    let cwd = std::env::current_dir().map_err(Error::Io)?;
    if cwd.join("tools/render/caption.py").exists() {
        return Ok(cwd);
    }

    Err(Error::Usage(
        "could not locate repo root containing tools/render/caption.py; \
         set VSON_HOME or invoke from the repo root"
            .into(),
    ))
}

fn ensure_python_available() -> Result<()> {
    match Command::new("python3").arg("--version").output() {
        Ok(_) => Ok(()),
        Err(_) => Err(Error::Usage(
            "python3 not on PATH; required for `vson export caption` \
             (Rust native renderer planned for v1.2)"
                .into(),
        )),
    }
}

pub fn run(file: &Path) -> Result<()> {
    ensure_python_available()?;

    if !file.exists() {
        return Err(Error::Usage(format!(
            "input file not found: {}",
            file.display()
        )));
    }

    let home = locate_home(file)?;
    let abs_file = if file.is_absolute() {
        file.to_path_buf()
    } else {
        std::env::current_dir().map_err(Error::Io)?.join(file)
    };

    let output = Command::new("python3")
        .args(["-m", "tools.render.caption"])
        .arg(&abs_file)
        .current_dir(&home)
        .output()
        .map_err(Error::Io)?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        return Err(Error::Usage(format!(
            "caption renderer failed (exit {}): {}",
            output.status.code().unwrap_or(-1),
            stderr.trim()
        )));
    }

    std::io::stdout().write_all(&output.stdout)?;
    Ok(())
}
