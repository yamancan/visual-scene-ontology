//! `vson export cypher <file>` — emit a Cypher `CREATE` statement from a
//! VSON-P (Penman) file. Mirrors the mapping declared in
//! `spec/vson-spec-v1.md:177`:
//!
//!   :s :p :o          ->  (s)-[:p]->(o)
//!   :s vso:role lit   ->  a property inside (s)'s node map
//!   :s a vso:Concept  ->  (s:Concept)
//!
//! The whole scene is emitted as ONE statement:
//!
//!   CREATE
//!     (scene:Composition {id: 'scene'}),
//!     (ctx:SceneContext {id: 'ctx', venue: 'throne_room'}),
//!     (scene)-[:framedBy]->(ctx);
//!
//! Every node pattern comes first, then every relationship pattern reusing the
//! variables those node patterns bound. This is load-bearing: in Cypher a
//! variable's scope is the statement, so splitting the scene into one
//! `CREATE ...;` per line would leave each relationship's endpoints unbound and
//! silently create a fresh empty node per line. Emitting one statement is what
//! makes the output loadable as-is.
//!
//! We accept Penman (VSON-P) input only — Turtle import is deferred until a
//! native Rust Turtle parser lands.

use super::{Error, Result};
use crate::penman::parser::{parse, Node, Term};
use std::collections::{HashMap, HashSet};
use std::io::Write;
use std::path::Path;

pub fn run(file: &Path) -> Result<()> {
    let src = std::fs::read_to_string(file)?;
    let out = to_cypher(&src)?;
    std::io::stdout().write_all(out.as_bytes())?;
    Ok(())
}

fn to_cypher(src: &str) -> Result<String> {
    let ast = parse(src).map_err(Error::Parse)?;
    let mut declared = HashSet::new();
    collect_declared(&ast, &mut declared);
    let mut graph = CypherGraph::default();
    graph.walk(&ast, &declared);
    Ok(graph.render())
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

/// Map a Penman identifier onto a legal *unquoted* Cypher identifier. The VSON-P
/// lexer accepts `-` in variables, concepts and roles (`[A-Za-z_][\w\-]*`), but
/// a bare `-` in Cypher parses as subtraction, so it must be folded away. Every
/// other character the lexer admits is already `\w`, and the leading character
/// is always a letter or `_`, so the result needs no backticks.
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
    if !is_string
        && value
            .chars()
            .all(|c| c.is_ascii_digit() || c == '.' || c == '-')
    {
        value.to_string()
    } else {
        quote_cypher(value)
    }
}

/// One node pattern: `(var:Label {k: v, ...})`.
struct CypherNode {
    /// Sanitized concept, or `None` for a re-entrant node term that carries
    /// edges but no `/ Concept` (e.g. `(charge :causes strike)`).
    label: Option<String>,
    /// Insertion-ordered so output is deterministic across runs.
    props: Vec<(String, String)>,
}

/// The flattened scene: node patterns (in first-seen order) plus relationship
/// patterns, ready to be joined into a single `CREATE`.
#[derive(Default)]
struct CypherGraph {
    order: Vec<String>,
    nodes: HashMap<String, CypherNode>,
    /// (source var, relationship type, target var) — all already sanitized.
    rels: Vec<(String, String, String)>,
}

impl CypherGraph {
    /// Fetch (creating on first sight) the node pattern for `var`. Every
    /// variable that appears anywhere — including a bare re-entrancy target —
    /// gets exactly one node pattern, which is what keeps the relationship
    /// patterns from referring to unbound variables.
    fn node_entry(&mut self, var: &str) -> &mut CypherNode {
        if !self.nodes.contains_key(var) {
            self.order.push(var.to_string());
            self.nodes.insert(
                var.to_string(),
                CypherNode {
                    label: None,
                    props: vec![("id".into(), quote_cypher(var))],
                },
            );
        }
        self.nodes.get_mut(var).expect("entry inserted above")
    }

    fn set_prop(&mut self, var: &str, key: &str, value: String) {
        let entry = self.node_entry(var);
        // Property keys go through `cypher_id`, so two distinct roles can
        // collide after sanitization (`:focal-length` and `:focal_length` both
        // become `focal_length`), as can a role named `:id` colliding with the
        // synthetic `id`. A Cypher map may not repeat a key, so collisions
        // resolve last-write-wins rather than emitting an invalid duplicate.
        match entry.props.iter_mut().find(|(k, _)| k == key) {
            Some(slot) => slot.1 = value,
            None => entry.props.push((key.to_string(), value)),
        }
    }

    fn walk(&mut self, node: &Node, declared: &HashSet<String>) {
        let var = cypher_id(&node.var);
        // Touch the entry even when there is no concept: a bare re-entrancy
        // like `(charge :causes strike)` still has to be a bound variable.
        let entry = self.node_entry(&var);
        if let Some(c) = &node.concept {
            entry.label = Some(cypher_id(c));
        }
        for (role, target) in &node.edges {
            let rel = cypher_id(role);
            match target {
                Term::Node(child) => {
                    self.rels.push((var.clone(), rel, cypher_id(&child.var)));
                    self.walk(child, declared);
                }
                // A ref to a variable declared elsewhere in the scene is an
                // edge; anything else is an atom and lands as a property.
                Term::Ref(name) => {
                    if declared.contains(name) {
                        self.rels.push((var.clone(), rel, cypher_id(name)));
                    } else {
                        self.set_prop(&var, &rel, render_lit(name, false));
                    }
                }
                Term::StrLit(s) | Term::UnitLit(s) => {
                    self.set_prop(&var, &rel, render_lit(s, true));
                }
                Term::NumLit(n) => {
                    self.set_prop(&var, &rel, n.clone());
                }
            }
        }
    }

    fn render(&self) -> String {
        let mut patterns: Vec<String> = Vec::with_capacity(self.order.len() + self.rels.len());
        for var in &self.order {
            let node = &self.nodes[var];
            let label = match &node.label {
                Some(l) => format!(":{l}"),
                None => String::new(),
            };
            let props: Vec<String> = node
                .props
                .iter()
                .map(|(k, v)| format!("{k}: {v}"))
                .collect();
            patterns.push(format!("({var}{label} {{{}}})", props.join(", ")));
        }
        for (src, rel, dst) in &self.rels {
            patterns.push(format!("({src})-[:{rel}]->({dst})"));
        }
        // Exactly one terminating `;` — the statement boundary is the variable
        // scope boundary, so there must not be a second one.
        format!("CREATE\n  {};\n", patterns.join(",\n  "))
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

    /// The shape check for the whole emitter. Verified by construction against
    /// the Cypher grammar (one statement, so every variable a relationship
    /// pattern names is bound by an earlier node pattern in the same `CREATE`);
    /// no Neo4j server or `cypher-shell` was available in this environment, so
    /// this has NOT been confirmed by a live load.
    #[test]
    fn two_node_graph_is_one_statement_without_set() {
        let out = to_cypher("(s / Composition :venue throne_room :depicts (a / PhysicalObject))")
            .unwrap();
        assert_eq!(
            out,
            "CREATE\n  \
             (s:Composition {id: 's', venue: 'throne_room'}),\n  \
             (a:PhysicalObject {id: 'a'}),\n  \
             (s)-[:depicts]->(a);\n"
        );
        assert_eq!(
            out.matches(';').count(),
            1,
            "exactly one statement terminator"
        );
        assert!(
            !out.contains("SET "),
            "properties belong in the node map, not a SET clause"
        );
    }

    #[test]
    fn hyphenated_roles_are_sanitized_in_rels_and_props() {
        // The Penman lexer admits `-` in roles; Cypher does not, in either a
        // relationship type or a property key.
        let out =
            to_cypher("(s / Composition :focal-length 35mm :shot-by (c / CameraView))").unwrap();
        assert!(out.contains("focal_length: '35mm'"), "got: {out}");
        assert!(out.contains("(s)-[:shot_by]->(c)"), "got: {out}");
        assert!(
            !out.contains("focal-length") && !out.contains("shot-by"),
            "got: {out}"
        );
    }

    #[test]
    fn reentrant_node_reuses_one_binding() {
        // `(b ...)` appears twice: once with a concept, once as a bare
        // re-entrancy carrying an edge. Cypher allows a variable to be bound
        // only once, so exactly one node pattern may be emitted for it.
        let out =
            to_cypher("(s / Composition :depicts (b / Event :lemma strike) :causal (b :causes s))")
                .unwrap();
        assert_eq!(out.matches("(b:Event").count(), 1, "got: {out}");
        assert!(out.contains("(b)-[:causes]->(s)"), "got: {out}");
        assert_eq!(out.matches(';').count(), 1);
    }

    #[test]
    fn colliding_property_keys_resolve_last_write_wins() {
        // `:focal-length` and `:focal_length` sanitize to the same key; a Cypher
        // map may not repeat a key, so the last one wins.
        let out = to_cypher("(s / Composition :focal-length 35mm :focal_length 50mm)").unwrap();
        assert_eq!(out.matches("focal_length").count(), 1, "got: {out}");
        assert!(out.contains("focal_length: '50mm'"), "got: {out}");
    }

    #[test]
    fn every_relationship_endpoint_is_bound_by_a_node_pattern() {
        let src = std::fs::read_to_string(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .unwrap()
                .join("examples/throne_room.vson"),
        )
        .expect("canonical example must exist");
        let out = to_cypher(&src).unwrap();
        assert!(out.starts_with("CREATE\n"));
        assert_eq!(out.matches(';').count(), 1);
        assert!(!out.contains("SET "));
        let bound: HashSet<&str> = out
            .lines()
            .filter_map(|l| l.trim_start().strip_prefix('('))
            .filter(|l| !l.contains(")-["))
            .filter_map(|l| l.split([':', ' ']).next())
            .collect();
        for line in out
            .lines()
            .map(str::trim_start)
            .filter(|l| l.contains(")-["))
        {
            let (src_var, rest) = line[1..].split_once(")-[").expect("relationship pattern");
            let dst_var = rest.rsplit_once("->(").expect("relationship target").1;
            let dst_var = dst_var.trim_end_matches([';', ',']).trim_end_matches(')');
            assert!(
                bound.contains(src_var),
                "unbound source {src_var} in: {line}"
            );
            assert!(
                bound.contains(dst_var),
                "unbound target {dst_var} in: {line}"
            );
        }
    }
}
