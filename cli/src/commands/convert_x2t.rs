//! `vson convert x2t <file.x.vson>` — VSON-X compact syntax to Turtle.
//!
//! Implementation: shells out to the canonical Python parser at
//! `tools/vson_x/vson_x.py` through `super::python_bridge`. A native Rust port
//! is not shipped; until it is, the Python implementation is the single source
//! of truth so the Rust binary cannot drift from the round-trip CI fixtures
//! under `examples/gallery-x/`.

use super::{python_bridge, Result};
use std::ffi::OsStr;
use std::path::Path;

pub fn x2t(file: &Path) -> Result<()> {
    python_bridge::run_python_module(
        "tools.vson_x.vson_x",
        "tools/vson_x/vson_x.py",
        &[OsStr::new("to-turtle")],
        file,
    )
}
