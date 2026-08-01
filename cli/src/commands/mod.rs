pub mod convert;
pub mod convert_x2t;
pub mod diff;
pub mod embed;
pub mod export_caption;
pub mod export_cypher;
pub mod export_fol;
pub mod gates;
pub mod home;
pub mod python_bridge;
pub mod report;
pub mod sourcemap;
pub mod validate;
pub mod verify;

use std::fmt;

/// The four failure kinds the binary distinguishes. `main` maps `Validation`
/// to exit 1 and everything else to exit 2 — see `validate.rs` for why that
/// distinction is drawn from a tool's *output*, not just its exit status.
#[derive(Debug)]
pub enum Error {
    Validation(String),
    Usage(String),
    Io(std::io::Error),
    Parse(String),
}

/// The exact text `main` prints to stderr, so the message lives next to the
/// variant instead of being re-spelled at every call site.
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Validation(msg) | Error::Usage(msg) => write!(f, "{}", msg),
            Error::Io(e) => write!(f, "io: {}", e),
            Error::Parse(msg) => write!(f, "parse: {}", msg),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Error::Io(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Error::Io(e)
    }
}

pub type Result<T> = std::result::Result<T, Error>;
