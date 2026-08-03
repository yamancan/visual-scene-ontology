//! `vson` — the VSON v1.3 reference CLI.
//!
//! Subcommands:
//!
//! - `validate <files...>` — both of the gates `make check` runs: SHACL
//!   conformance via `pyshacl`, then OWL 2 RL consistency via
//!   `python3 -m tools.owlrl_check`. Reads `-` as standard input, and
//!   `--format json|sarif` turns each violation into a structured record —
//!   shape, focus node, result path, severity, and the source line the Penman
//!   variable was declared on — so a build can annotate the offending line
//!   (docs/vson.md §5.16).
//! - `verify --geometry <files...>` — the checks that are *not* conformance.
//!   Today one: whether the spatial relations a document asserts agree with the
//!   `vso:bbox2d` rectangles it asserts beside them (docs/vson.md §5.13). It
//!   reads no image, and a document that fails it is still conformant — which
//!   is exactly why it is not a `validate` gate.
//! - `diff <a> <b>` — Smatch graph agreement between two documents: the
//!   variable alignment that maximizes matched triples, then precision, recall
//!   and F1 overall and per layer (docs/vson.md §5.15). Exit 0 identical, 1
//!   differing. It reads no image, and agreement is not correctness.
//! - `convert p2t|t2p|x2t <file>` — Penman/VSON-X <-> Turtle transpilation.
//! - `export cypher <file>` — emit Cypher CREATE statements from Turtle.
//! - `export caption <file>` — render a deterministic English caption for
//!   image-generation models (shells out to `tools/render/caption.py`; a native
//!   Rust port is planned for v1.2).
//! - `export fol <file>` — render Prolog-style first-order-logic facts (shells
//!   out to `tools/render/fol.py`).
//! - `mcp` — serve `validate`, `convert`, `export` and the extractor skill to
//!   an agent as Model Context Protocol tools, JSON-RPC 2.0 over stdio (shells
//!   out to `python3 -m vson.mcp`; docs/vson.md §5.18). It reads and writes the
//!   protocol stream on this process's own stdin and stdout, so it is the one
//!   subcommand whose output is not for a person.
//!
//! Exit codes: 0 success; 1 a document genuinely failed a gate; 2 the command
//! never reached a verdict (usage error, missing toolchain, unparseable input).
//! See `commands::validate` for why 1 and 2 cannot be read off a child
//! process's exit status alone.

use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process::ExitCode;

mod commands;
mod penman;

#[derive(Parser)]
#[command(name = "vson", version, about = "VSON v1.3 CLI", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Validate one or more files against the VSON shapes.
    Validate {
        /// Files to validate (.ttl or .vson), or `-` for standard input.
        #[arg(required = true)]
        files: Vec<PathBuf>,
        /// Report shape: `text` (default), `json`, or `sarif` (2.1.0).
        #[arg(long, default_value = "text")]
        format: String,
        /// Validation profile: `strict` (default). See docs/vson.md §6.1.
        #[arg(long, default_value = "strict")]
        profile: String,
        /// Path to the repo root containing ontology/ and shapes/.
        #[arg(long, env = "VSON_HOME")]
        home: Option<PathBuf>,
    },
    /// Run a non-conformance check. Name the check: `--geometry`.
    Verify {
        /// Files to check (.ttl or .vson).
        #[arg(required = true)]
        files: Vec<PathBuf>,
        /// Check asserted spatial relations against the document's own
        /// vso:bbox2d rectangles (docs/vson.md §5.13). Reads no image.
        #[arg(long)]
        geometry: bool,
        /// Report every relation's verdict, not only the contradicted ones.
        #[arg(long)]
        verbose: bool,
        /// Path to the repo root containing tools/.
        #[arg(long, env = "VSON_HOME")]
        home: Option<PathBuf>,
    },
    /// Compare two documents: Smatch graph agreement, overall and per layer.
    Diff {
        /// First document (.ttl, .vson or .x.vson).
        a: PathBuf,
        /// Second document (.ttl, .vson or .x.vson).
        b: PathBuf,
        /// Report shape: `text` (default) or `json`.
        #[arg(long, default_value = "text")]
        format: String,
        /// Path to the repo root containing tools/.
        #[arg(long, env = "VSON_HOME")]
        home: Option<PathBuf>,
    },
    /// Convert between concrete syntaxes.
    Convert {
        #[command(subcommand)]
        direction: ConvertDirection,
    },
    /// Export to other graph formats.
    Export {
        #[command(subcommand)]
        target: ExportTarget,
    },
    /// Serve validate/convert/export/skill to an agent as MCP tools over stdio.
    Mcp {
        /// Path to the repo root containing vson/ and tools/.
        #[arg(long, env = "VSON_HOME")]
        home: Option<PathBuf>,
    },
}

#[derive(Subcommand)]
enum ConvertDirection {
    /// Penman -> Turtle.
    P2t { file: PathBuf },
    /// Turtle -> Penman (not implemented; use the Python reference).
    T2p { file: PathBuf },
    /// VSON-X compact syntax -> Turtle (shells out to the Python reference).
    X2t { file: PathBuf },
}

#[derive(Subcommand)]
enum ExportTarget {
    /// Emit Cypher CREATE statements.
    Cypher { file: PathBuf },
    /// Render a deterministic English caption for image-generation models.
    Caption { file: PathBuf },
    /// Render Prolog-style first-order-logic facts.
    Fol { file: PathBuf },
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    let result = match cli.command {
        Cmd::Validate {
            files,
            format,
            profile,
            home,
        } => commands::validate::run(&files, home.as_deref(), &format, &profile),
        Cmd::Verify {
            files,
            geometry,
            verbose,
            home,
        } => commands::verify::run(&files, home.as_deref(), geometry, verbose),
        Cmd::Diff { a, b, format, home } => commands::diff::run(&a, &b, &format, home.as_deref()),
        Cmd::Convert {
            direction: ConvertDirection::P2t { file },
        } => commands::convert::p2t(&file),
        Cmd::Convert {
            direction: ConvertDirection::T2p { file },
        } => commands::convert::t2p(&file),
        Cmd::Convert {
            direction: ConvertDirection::X2t { file },
        } => commands::convert_x2t::x2t(&file),
        Cmd::Export {
            target: ExportTarget::Cypher { file },
        } => commands::export_cypher::run(&file),
        Cmd::Export {
            target: ExportTarget::Caption { file },
        } => commands::export_caption::run(&file),
        Cmd::Export {
            target: ExportTarget::Fol { file },
        } => commands::export_fol::run(&file),
        Cmd::Mcp { home } => commands::mcp::run(home.as_deref()),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        // The wording lives in `Error`'s `Display`; only the exit code is
        // decided here, so the two cannot drift apart. `Validation` is the one
        // variant meaning "the tool ran and the document is bad" — everything
        // else means we never got a verdict.
        Err(e) => {
            eprintln!("{e}");
            match e {
                commands::Error::Validation(_) => ExitCode::from(1),
                _ => ExitCode::from(2),
            }
        }
    }
}
