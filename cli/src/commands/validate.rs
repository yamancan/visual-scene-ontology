//! `vson validate <files...>` — shells out to `pyshacl --abort` and maps
//! its exit code to ours. Exits 0 on conform, 1 on violation.
//!
//! For .vson inputs we transpile to a temp .ttl first.

use super::{Error, Result};
use std::path::{Path, PathBuf};
use std::process::Command;

fn vson_home(explicit: Option<&Path>) -> PathBuf {
    if let Some(p) = explicit {
        return p.to_path_buf();
    }
    if let Ok(p) = std::env::var("VSON_HOME") {
        return PathBuf::from(p);
    }
    // Fall back to the working directory; the user is expected to invoke from
    // the repo root, which is the documented v0.1 contract.
    PathBuf::from(".")
}

fn ensure_pyshacl_available() -> Result<()> {
    match Command::new("pyshacl").arg("--help").output() {
        Ok(_) => Ok(()),
        Err(_) => Err(Error::Usage(
            "pyshacl not on PATH. Install with: pip install pyshacl".into(),
        )),
    }
}

fn transpile_to_temp(file: &Path) -> Result<PathBuf> {
    let src = std::fs::read_to_string(file)?;
    let ttl = crate::penman::to_turtle(&src).map_err(Error::Parse)?;
    let mut tmp = std::env::temp_dir();
    let stem = file.file_stem().and_then(|s| s.to_str()).unwrap_or("vson");
    tmp.push(format!("vson_{}_{}.ttl", stem, std::process::id()));
    std::fs::write(&tmp, ttl)?;
    Ok(tmp)
}

pub fn run(files: &[PathBuf], home: Option<&Path>) -> Result<()> {
    ensure_pyshacl_available()?;
    let home = vson_home(home);
    let shapes = home.join("shapes/vson-shapes.ttl");
    let ont_files = ["ontology/vso.ttl", "ontology/rcc8.ttl", "ontology/allen.ttl"];

    for path in &ont_files {
        if !home.join(path).exists() {
            return Err(Error::Usage(format!(
                "{} not found under VSON_HOME={}; pass --home or set VSON_HOME",
                path,
                home.display()
            )));
        }
    }
    if !shapes.exists() {
        return Err(Error::Usage(format!(
            "shapes/vson-shapes.ttl not found under VSON_HOME={}",
            home.display()
        )));
    }

    let mut any_failed = false;
    for file in files {
        let (data_path, _tmp_guard): (PathBuf, Option<PathBuf>) = match file
            .extension()
            .and_then(|e| e.to_str())
        {
            Some("vson") => {
                let p = transpile_to_temp(file)?;
                (p.clone(), Some(p))
            }
            _ => (file.clone(), None),
        };

        // pyshacl supports a single ontology graph; concatenate the three
        // ontology files into a temp Turtle file for inoculation.
        let ont_blob = ont_files
            .iter()
            .map(|p| std::fs::read_to_string(home.join(p)))
            .collect::<std::io::Result<Vec<_>>>()?
            .join("\n");
        let mut ont_tmp = std::env::temp_dir();
        ont_tmp.push(format!("vson_ont_{}.ttl", std::process::id()));
        std::fs::write(&ont_tmp, ont_blob)?;

        let status = Command::new("pyshacl")
            .arg("--abort")
            .args(["-s", shapes.to_str().unwrap()])
            .args(["-e", ont_tmp.to_str().unwrap()])
            .args(["-i", "rdfs"])
            .arg(data_path.to_str().unwrap())
            .status()?;
        let _ = std::fs::remove_file(&ont_tmp);
        if let Some(t) = _tmp_guard {
            let _ = std::fs::remove_file(t);
        }

        if status.success() {
            println!("OK  {}", file.display());
        } else {
            println!("FAIL {}", file.display());
            any_failed = true;
        }
    }

    if any_failed {
        Err(Error::Validation("one or more files failed validation".into()))
    } else {
        Ok(())
    }
}
