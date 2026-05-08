//! `vson export fol <file>` — render a VSON document as Prolog-style
//! first-order-logic facts. Implementation shells out to the canonical
//! Python renderer at `tools/render/fol.py`; mirrors `export_caption`.

use super::{Error, Result};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

fn locate_home(file: &Path) -> Result<PathBuf> {
    if let Ok(p) = std::env::var("VSON_HOME") {
        let home = PathBuf::from(p);
        if home.join("tools/render/fol.py").exists() {
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
        if dir.join("tools/render/fol.py").exists() {
            return Ok(dir);
        }
        cur = dir.parent().map(|p| p.to_path_buf());
    }

    let cwd = std::env::current_dir().map_err(Error::Io)?;
    if cwd.join("tools/render/fol.py").exists() {
        return Ok(cwd);
    }

    Err(Error::Usage(
        "could not locate repo root containing tools/render/fol.py; \
         set VSON_HOME or invoke from the repo root"
            .into(),
    ))
}

fn ensure_python_available() -> Result<()> {
    match Command::new("python3").arg("--version").output() {
        Ok(_) => Ok(()),
        Err(_) => Err(Error::Usage(
            "python3 not on PATH; required for `vson export fol`".into(),
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
        .args(["-m", "tools.render.fol"])
        .arg(&abs_file)
        .current_dir(&home)
        .output()
        .map_err(Error::Io)?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        return Err(Error::Usage(format!(
            "FOL renderer failed (exit {}): {}",
            output.status.code().unwrap_or(-1),
            stderr.trim()
        )));
    }

    std::io::stdout().write_all(&output.stdout)?;
    Ok(())
}
