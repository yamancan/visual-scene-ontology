//! VSON-P (Penman) transpilation.
//!
//! Mirrors the Python reference at `tools/penman/vson_penman.py`. Both this
//! module and the reference consume the same `cli/src/penman/routing-tables.json`
//! file as their single source of truth — this module at compile time via
//! `include_str!`, the reference by reading it from the checkout at import time.

pub mod emitter;
pub mod lexer;
pub mod parser;
pub mod routing;

pub use emitter::to_turtle;
