//! `vson` — the VSON v1.1 reference CLI.
//!
//! Subcommands:
//!   - validate <files...>      SHACL conformance (shells out to `pyshacl`).
//!   - convert  p2t|t2p|x2t <file>  Penman/VSON-X <-> Turtle transpilation.
//!   - export   cypher <file>   Emit Cypher CREATE statements from Turtle.
//!   - export   caption <file>  Render a deterministic English caption for
//!                              image-generation models (shells out to
//!                              tools/render/caption.py; native Rust port v1.2).
//!   - export   fol <file>      Render Prolog-style first-order-logic facts
//!                              (shells out to tools/render/fol.py).
//!
//! Exits 0 on success, 1 on validation failure, 2 on usage error.

use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process::ExitCode;

mod commands;
mod penman;

#[derive(Parser)]
#[command(name = "vson", version, about = "VSON v1.1 CLI", long_about = None)]
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
    /// Turtle -> Penman (not implemented in v0.1).
    T2p { file: PathBuf },
    /// VSON-X compact syntax -> Turtle (shells out to Python in v1.1).
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
        Cmd::Convert { direction: ConvertDirection::P2t { file } } => commands::convert::p2t(&file),
        Cmd::Convert { direction: ConvertDirection::T2p { file } } => commands::convert::t2p(&file),
        Cmd::Convert { direction: ConvertDirection::X2t { file } } => commands::convert_x2t::x2t(&file),
        Cmd::Export { target: ExportTarget::Cypher { file } } => commands::export_cypher::run(&file),
        Cmd::Export { target: ExportTarget::Caption { file } } => commands::export_caption::run(&file),
        Cmd::Export { target: ExportTarget::Fol { file } } => commands::export_fol::run(&file),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(commands::Error::Validation(msg)) => {
            eprintln!("{msg}");
            ExitCode::from(1)
        }
        Err(commands::Error::Usage(msg)) => {
            eprintln!("{msg}");
            ExitCode::from(2)
        }
        Err(commands::Error::Io(e)) => {
            eprintln!("io: {e}");
            ExitCode::from(2)
        }
        Err(commands::Error::Parse(msg)) => {
            eprintln!("parse: {msg}");
            ExitCode::from(2)
        }
    }
}
