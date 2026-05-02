//! VSON-P AST -> Turtle emitter. Mirrors `Emitter.emit_node` /
//! `Emitter.route_bare_id` in the Python reference.

use super::parser::{parse, Node, Term};
use super::routing::ROUTING;
use std::collections::HashSet;

struct Emitter {
    triples: Vec<String>,
    declared_vars: HashSet<String>,
}

impl Emitter {
    fn new() -> Self {
        Self { triples: Vec::new(), declared_vars: HashSet::new() }
    }

    fn iri_for_var(&self, var: &str) -> String {
        format!(":{var}")
    }

    fn role_to_iri(&self, role: &str) -> String {
        match ROUTING.role_namespace_overrides.get(role) {
            Some(ns) => format!("<{ns}{role}>"),
            None => format!("<{}{}>", ROUTING.vso, role),
        }
    }

    fn concept_to_iri(&self, concept: &str) -> String {
        format!("<{}{}>", ROUTING.vso, concept)
    }

    fn render_string(raw: &str) -> String {
        let esc = raw.replace('\\', "\\\\").replace('"', "\\\"");
        format!("\"{esc}\"")
    }

    fn render_number(raw: &str) -> String {
        if raw.contains('.') {
            format!("\"{raw}\"^^<http://www.w3.org/2001/XMLSchema#decimal>")
        } else {
            format!("\"{raw}\"^^<http://www.w3.org/2001/XMLSchema#integer>")
        }
    }

    fn route_bare_id(&self, name: &str, role: &str) -> String {
        // Mirror the Python reference's precedence: role-as-literal wins over
        // var-collision because lemmas / venues / styles are spec-typed string
        // even when the token shares spelling with a sibling node's var.
        if ROUTING.role_value_as_string.contains(role) {
            return Self::render_string(name);
        }
        if self.declared_vars.contains(name) {
            return self.iri_for_var(name);
        }
        if ROUTING.role_value_to_rcc.contains(role) && ROUTING.rcc_values.contains(name) {
            return format!("<{}{}>", ROUTING.rcc, name);
        }
        if ROUTING.role_value_to_vso.contains(role) {
            return format!("<{}{}>", ROUTING.vso, name);
        }
        format!(":{name}")
    }

    fn term_to_iri(&mut self, term: &Term, role: &str) -> String {
        match term {
            Term::Node(n) => self.emit_node(n),
            Term::Ref(v) => self.route_bare_id(v, role),
            Term::StrLit(s) => Self::render_string(s),
            Term::UnitLit(s) => Self::render_string(s),
            Term::NumLit(s) => {
                if ROUTING.role_value_as_string.contains(role) {
                    Self::render_string(s)
                } else {
                    Self::render_number(s)
                }
            }
        }
    }

    fn collect_declared(&mut self, node: &Node) {
        if node.concept.is_some() {
            self.declared_vars.insert(node.var.clone());
        }
        for (_role, target) in &node.edges {
            if let Term::Node(n) = target {
                self.collect_declared(n);
            }
        }
    }

    fn emit_node(&mut self, node: &Node) -> String {
        let subj = self.iri_for_var(&node.var);
        if let Some(c) = &node.concept {
            self.triples.push(format!("{} a {} .", subj, self.concept_to_iri(c)));
        }
        for (role, target) in &node.edges {
            if ROUTING.container_roles.contains(role) {
                let inner = match target {
                    Term::Node(n) => n,
                    _ => continue, // mirrors Python which raises; tolerate by skipping
                };
                let inner_subj = self.iri_for_var(&inner.var);
                for (inner_role, inner_target) in &inner.edges {
                    let p = self.role_to_iri(inner_role);
                    let o = self.term_to_iri(inner_target, inner_role);
                    self.triples.push(format!("{inner_subj} {p} {o} ."));
                }
                continue;
            }
            let p = self.role_to_iri(role);
            let o = self.term_to_iri(target, role);
            self.triples.push(format!("{subj} {p} {o} ."));
        }
        subj
    }

    fn emit(mut self, root: &Node) -> String {
        self.collect_declared(root);
        self.emit_node(root);
        let head = format!(
            "@prefix vso:   <{}> .\n\
             @prefix allen: <{}> .\n\
             @prefix rcc:   <{}> .\n\
             @prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .\n\
             @prefix :      <{}> .\n\n",
            ROUTING.vso, ROUTING.allen, ROUTING.rcc, ROUTING.default
        );
        let body = self.triples.join("\n");
        format!("{head}{body}\n")
    }
}

pub fn to_turtle(src: &str) -> Result<String, String> {
    let ast = parse(src)?;
    Ok(Emitter::new().emit(&ast))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn smallest_node_emits_class_triple() {
        let out = to_turtle("(s / Composition)").unwrap();
        assert!(out.contains(":s a <https://vson.dev/v1/ontology#Composition> ."));
    }

    #[test]
    fn rcc_routes_to_rcc_namespace() {
        let out = to_turtle("(f / SpatialFact :rcc EC)").unwrap();
        assert!(out.contains("<https://vson.dev/v1/rcc8#EC>"));
    }

    #[test]
    fn allen_role_uses_allen_namespace() {
        let out = to_turtle("(e / Event :before other)").unwrap();
        assert!(out.contains("<https://vson.dev/v1/allen#before>"));
    }

    #[test]
    fn unit_literal_becomes_string() {
        let out = to_turtle("(c / CameraView :focalLength 35mm)").unwrap();
        assert!(out.contains("\"35mm\""));
    }
}
