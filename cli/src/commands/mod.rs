pub mod validate;
pub mod convert;
pub mod convert_x2t;
pub mod export_cypher;
pub mod export_caption;

#[derive(Debug)]
pub enum Error {
    Validation(String),
    Usage(String),
    Io(std::io::Error),
    Parse(String),
}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self { Error::Io(e) }
}

pub type Result<T> = std::result::Result<T, Error>;
