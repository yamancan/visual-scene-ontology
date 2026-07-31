//! `vson export fol <file>` — render a VSON document as Prolog-style
//! first-order-logic facts. Implementation shells out to the canonical Python
//! renderer at `tools/render/fol.py` through `super::python_bridge`, exactly as
//! `export_caption` and `convert_x2t` do.

use super::{python_bridge, Result};
use std::path::Path;

pub fn run(file: &Path) -> Result<()> {
    python_bridge::run_python_module("tools.render.fol", "tools/render/fol.py", &[], file)
}
