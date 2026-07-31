//! `vson` — the VSON v1.3 reference CLI.
//!
//! Subcommands:
//!
//! - `validate <files...>` — both of the gates `make check` runs: SHACL
//!   conformance via `pyshacl`, then OWL 2 RL consistency via
//!   `python3 -m tools.owlrl_check`.
//! - `convert p2t|t2p|x2t <file>` — Penman/VSON-X <-> Turtle transpilation.
//! - `export cypher <file>` — emit Cypher CREATE statements from Turtle.
//! - `export caption <file>` — render a deterministic English caption for
//!   image-generation models (shells out to `tools/render/caption.py`; a native
//!   Rust port is planned for v1.2).
//! - `export fol <file>` — render Prolog-style first-order-logic facts (shells
//!   out to `tools/render/fol.py`).
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
        /// Files to validate (.ttl or .vson).
        #[arg(required = true)]
        files: Vec<PathBuf>,
        /// Path to the repo root containing ontology/ and shapes/.
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
        Cmd::Validate { files, home } => commands::validate::run(&files, home.as_deref()),
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
