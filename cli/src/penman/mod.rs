//! VSON-P (Penman) transpilation.
//!
//! Mirrors the Python reference at `tools/penman/vson_penman.py`. Both this
//! module and the reference consume the same `tools/penman/routing-tables.json`
//! file as their single source of truth.

pub mod lexer;
pub mod parser;
pub mod emitter;
pub mod routing;

pub use emitter::to_turtle;
