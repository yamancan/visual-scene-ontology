//! `vson mcp` — serve the gates, the transpilers, the renderers and the
//! extractor skill to an agent as Model Context Protocol tools, over stdio.
//!
//! Implementation: shells out to `python3 -m vson.mcp` through
//! [`super::home`], exactly as `export caption`, `export fol` and
//! `convert x2t` shell out to their Python references — and for the same
//! reason, that the Python implementation is the single source of truth those
//! subcommands' CI fixtures are frozen against. There is no second protocol
//! implementation here, and there is deliberately no Rust MCP server: what a
//! Rust one would have to expose is the *Python* gates, so it would be this
//! same child process with a JSON-RPC layer in front of it.
//!
//! **This subcommand does not use [`super::python_bridge`].** That helper
//! captures the child's output and copies it out afterwards, which is right for
//! a renderer that prints once and exits. An MCP server is a conversation: the
//! client writes a request and waits for the response before writing the next
//! one, so a buffered child deadlocks on the first call. All three streams are
//! therefore *inherited* — the client's stdin and stdout are the server's, and
//! this process only waits.
//!
//! Nothing here may write to stdout. Every byte on it belongs to the JSON-RPC
//! stream, and a stray line would be a parse error inside somebody's agent.
//!
//! Two environment variables are handed to the child, both documented in
//! `vson/mcp.py`:
//!
//! * `VSON_MCP_CWD` — the directory the user ran `vson mcp` in. The child runs
//!   in the resolved home instead, because `python3 -m` imports off its own
//!   working directory; without this a relative `path` argument would resolve
//!   against the home and quietly miss.
//! * `VSON_CLI` — this binary's own path. Cypher is the one rendering with no
//!   Python implementation (`export_cypher.rs` is native Rust over the Penman
//!   AST), so the server shells back out here for it rather than keeping a
//!   second copy of the mapping. Setting it means `vson mcp` always has all
//!   three export formats, whereas a bare `python3 -m vson.mcp` has Cypher only
//!   when a binary is findable on `PATH` or in a checkout.
//!
//! Exit codes: 0 when the server exited cleanly (a client closing stdin is the
//! normal shutdown), 2 otherwise — a server that could not run never reached a
//! verdict about anything.

use super::{home, Error, Result};
use std::path::Path;
use std::process::{Command, Stdio};

/// The module the child runs, and the file whose presence proves a home can
/// import it.
const MODULE: &str = "vson.mcp";
const PROBE: &str = "vson/mcp.py";

pub fn run(explicit_home: Option<&Path>) -> Result<()> {
    let home = home::resolve(explicit_home, None, PROBE)?;
    if !home.join(PROBE).exists() {
        return Err(home::missing(
            &home,
            PROBE,
            &format!("`python3 -m {MODULE}`"),
        ));
    }

    let mut command = Command::new("python3");
    command
        .arg("-m")
        .arg(MODULE)
        .current_dir(home.path())
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());
    if let Ok(cwd) = std::env::current_dir() {
        command.env("VSON_MCP_CWD", cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        command.env("VSON_CLI", exe);
    }

    let status = command.status().map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            Error::Usage(format!(
                "python3 not on PATH; `vson mcp` runs `python3 -m {MODULE}`, \
                 the Python reference implementation"
            ))
        } else {
            Error::Io(e)
        }
    })?;

    if status.success() {
        return Ok(());
    }
    Err(Error::Usage(format!(
        "`python3 -m {}` {} in {}. Its diagnostics went to stderr above.",
        MODULE,
        match status.code() {
            Some(c) => format!("exited {c}"),
            None => "was killed by a signal".to_string(),
        },
        home.describe()
    )))
}
