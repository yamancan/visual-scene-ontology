//! `vson export cypher <file>` — emit Cypher CREATE statements from a
//! VSON-P (Penman) file. Mirrors the mapping declared in
//! `spec/vson-spec-v1.md:177`:
//!
//!   :s :p :o          ->  (s)-[r:p]->(o)
//!   :s vso:role lit   ->  s.role = lit              (when target is literal)
//!   :s a vso:Concept  ->  (s:Concept)
//!
//! We accept Penman (VSON-P) input only — Turtle import is deferred until a
//! native Rust Turtle parser lands.

use super::{Error, Result};
use crate::penman::parser::{parse, Node, Term};
use std::collections::HashSet;
use std::io::Write;
use std::path::Path;

pub fn run(file: &Path) -> Result<()> {
    let src = std::fs::read_to_string(file)?;
    let ast = parse(&src).map_err(Error::Parse)?;
    let mut out = String::new();
    let mut declared = HashSet::new();
    collect_declared(&ast, &mut declared);
    emit_node(&ast, &declared, &mut out);
    std::io::stdout().write_all(out.as_bytes())?;
    Ok(())
}

fn collect_declared(node: &Node, declared: &mut HashSet<String>) {
    if node.concept.is_some() {
        declared.insert(node.var.clone());
    }
    for (_, t) in &node.edges {
        if let Term::Node(n) = t {
            collect_declared(n, declared);
        }
    }
}

fn cypher_id(s: &str) -> String {
    s.replace('-', "_")
}

/// Quote a value as a Cypher single-quoted string literal. Backslashes must be
/// escaped *before* quotes, otherwise a trailing `\` would escape the closing
/// quote and a literal `\` would be reinterpreted as a Cypher escape sequence.
fn quote_cypher(value: &str) -> String {
    let escaped = value.replace('\\', "\\\\").replace('\'', "\\'");
    format!("'{escaped}'")
}

fn render_lit(value: &str, is_string: bool) -> String {
    // String literals are always quoted. For bare refs, keep numbers unquoted
    // and quote everything else for safety.
    if !is_string && value.chars().all(|c| c.is_ascii_digit() || c == '.' || c == '-') {
        value.to_string()
    } else {
        quote_cypher(value)
    }
}

fn emit_node(node: &Node, declared: &HashSet<String>, out: &mut String) {
    let var = cypher_id(&node.var);
    if let Some(c) = &node.concept {
        // Sanitize the label too — an unescaped hyphenated concept is invalid Cypher.
        let label = cypher_id(c);
        out.push_str(&format!("CREATE ({var}:{label} {{id: '{var}'}});\n"));
    }
    for (role, target) in &node.edges {
        match target {
            Term::Node(child) => {
                emit_node(child, declared, out);
                let cvar = cypher_id(&child.var);
                out.push_str(&format!("CREATE ({var})-[:{role}]->({cvar});\n"));
            }
            Term::Ref(name) => {
                if declared.contains(name) {
                    let n = cypher_id(name);
                    out.push_str(&format!("CREATE ({var})-[:{role}]->({n});\n"));
                } else {
                    let lit = render_lit(name, false);
                    out.push_str(&format!("SET {var}.{role} = {lit};\n"));
                }
            }
            Term::StrLit(s) => {
                let lit = render_lit(s, true);
                out.push_str(&format!("SET {var}.{role} = {lit};\n"));
            }
            Term::NumLit(n) => {
                out.push_str(&format!("SET {var}.{role} = {n};\n"));
            }
            Term::UnitLit(s) => {
                let lit = render_lit(s, true);
                out.push_str(&format!("SET {var}.{role} = {lit};\n"));
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quote_escapes_backslashes_before_quotes() {
        // A trailing backslash must not escape the closing quote.
        assert_eq!(quote_cypher("a\\"), "'a\\\\'");
        // A literal backslash is doubled so Cypher doesn't reinterpret it.
        assert_eq!(quote_cypher("a\\b"), "'a\\\\b'");
        // Single quotes are still escaped.
        assert_eq!(quote_cypher("it's"), "'it\\'s'");
    }

    #[test]
    fn numbers_stay_bare_strings_are_quoted() {
        assert_eq!(render_lit("42", false), "42");
        assert_eq!(render_lit("-1.5", false), "-1.5");
        assert_eq!(render_lit("north", false), "'north'");
        assert_eq!(render_lit("42", true), "'42'");
    }

    #[test]
    fn hyphenated_labels_are_sanitized() {
        assert_eq!(cypher_id("foo-bar"), "foo_bar");
    }
}
