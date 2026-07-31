//! `vson export caption <file>` — render a VSON Penman document to a
//! deterministic English caption suitable for image-generation models.
//!
//! Implementation: shells out to the canonical Python renderer at
//! `tools/render/caption.py` through `super::python_bridge`. A native Rust port
//! is not shipped; until it is, the Python implementation is the single source
//! of truth so the Rust binary cannot drift from the deterministic CI fixtures
//! under `tests/fixtures/captions/`.
//!
//! Exit codes:
//!   0  on success (caption printed to stdout)
//!   2  on usage error (python3 missing, file unreadable, repo home cannot be
//!      located, the renderer itself failed)

use super::{python_bridge, Result};
use std::path::Path;

pub fn run(file: &Path) -> Result<()> {
    python_bridge::run_python_module("tools.render.caption", "tools/render/caption.py", &[], file)
}
