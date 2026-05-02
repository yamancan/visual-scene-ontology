//! `vson convert p2t|t2p <file>`. Penman -> Turtle is fully implemented;
//! Turtle -> Penman is deferred to a future sprint (no native Rust Turtle
//! parser yet).

use super::{Error, Result};
use std::io::Write;
use std::path::Path;

pub fn p2t(file: &Path) -> Result<()> {
    let src = std::fs::read_to_string(file)?;
    let ttl = crate::penman::to_turtle(&src).map_err(Error::Parse)?;
    std::io::stdout().write_all(ttl.as_bytes())?;
    Ok(())
}

pub fn t2p(_file: &Path) -> Result<()> {
    Err(Error::Usage(
        "t2p (Turtle -> Penman) is not implemented in v0.1. Use the Python reference: \
         python tools/penman/vson_penman.py to-penman <file.ttl>".into(),
    ))
}
