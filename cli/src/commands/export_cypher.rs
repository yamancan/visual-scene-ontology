//! `vson export cypher <file>` — emit Cypher CREATE statements from a
//! VSON-P (Penman) file. Mirrors the mapping declared in
//! `spec/vson-spec-v1.md:177`:
//!
//!   :s :p :o          ->  (s)-[r:p]->(o)
//!   :s vso:role lit   ->  s.role = lit              (when target is literal)
//!   :s a vso:Concept  ->  (s:Concept)
//!
//! For v0.1 we accept Penman input only — Turtle import is deferred until a
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

fn render_lit(role: &str, value: &str, is_string: bool) -> String {
    if is_string {
        format!("'{}'", value.replace('\'', "\\'"))
    } else {
        // Numbers stay bare; everything else gets quoted as a string for safety.
        if value.chars().all(|c| c.is_ascii_digit() || c == '.' || c == '-') {
            value.to_string()
        } else if role == "lemma" || role == "venue" {
            format!("'{}'", value.replace('\'', "\\'"))
        } else {
            format!("'{}'", value.replace('\'', "\\'"))
        }
    }
}

fn emit_node(node: &Node, declared: &HashSet<String>, out: &mut String) {
    let var = cypher_id(&node.var);
    if let Some(c) = &node.concept {
        out.push_str(&format!("CREATE ({var}:{c} {{id: '{var}'}});\n"));
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
                    let lit = render_lit(role, name, false);
                    out.push_str(&format!("SET {var}.{role} = {lit};\n"));
                }
            }
            Term::StrLit(s) => {
                let lit = render_lit(role, s, true);
                out.push_str(&format!("SET {var}.{role} = {lit};\n"));
            }
            Term::NumLit(n) => {
                out.push_str(&format!("SET {var}.{role} = {n};\n"));
            }
            Term::UnitLit(s) => {
                let lit = render_lit(role, s, true);
                out.push_str(&format!("SET {var}.{role} = {lit};\n"));
            }
        }
    }
}
