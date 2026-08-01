//! Where in the *source* a violation is, given the node a gate reported.
//!
//! Every gate reports graph terms: a focus node IRI, a property IRI, an orphan
//! term. A build annotation needs a line and a column in the file the author
//! wrote. Nothing in the pipeline carries that mapping — the SHACL report is a
//! graph, and for a `.vson` input the graph came from a temp Turtle file that
//! the author never saw — so it is reconstructed here, from the source text.
//!
//! **Penman is exact.** The transpiler mints one document-namespace IRI per
//! Penman variable, with the variable as the local name, so a focus node
//! `…/anonymous#sf` is the node declared by `(sf / SpatialFact …)`. The
//! declaration site comes off the lexer's token offsets, not a text scan, so a
//! variable named inside a comment or a quoted literal cannot be mistaken for
//! its declaration.
//!
//! **Turtle is best-effort, and says so.** Reading it exactly would take a
//! Turtle parser that records positions; rdflib is on the other side of a
//! process boundary and reports none. What runs instead is a line scan for the
//! term in subject position — the layout every document in this repository and
//! every transpiler output uses. A subject written some other way (a
//! continuation line, a `[]` blank node, an IRI spelled out where the focus
//! node came through a prefix) resolves to nothing, and a finding with no
//! location is emitted with `location: null` rather than a guessed line.
//!
//! Nothing here ever invents a position: [`Located::resolved_from`] names which
//! of the three strategies produced it, and a caller that finds `None` reports
//! the file alone.

use crate::penman::lexer::{tokenize, TokKind};
use std::collections::HashMap;

/// Which surface a document was written in. Decided by extension, or — for
/// stdin — by [`sniff`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Syntax {
    Penman,
    Turtle,
}

impl Syntax {
    pub fn as_str(self) -> &'static str {
        match self {
            Syntax::Penman => "penman",
            Syntax::Turtle => "turtle",
        }
    }
}

/// A resolved position: 1-based line, 1-based column counted in Unicode scalar
/// values (which is what the SARIF run declares as its `columnKind`).
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct Located {
    pub line: u32,
    pub column: u32,
    /// The text that was matched — the Penman variable, or the term as written.
    pub anchor: String,
    /// How it was found: `penman-variable`, `turtle-subject`, or `mention`.
    pub resolved_from: &'static str,
}

/// Which syntax a byte stream is, when no filename says.
///
/// A VSON-P document's first token is `(`; a Turtle document's is `@prefix`,
/// `PREFIX`, `BASE` or a subject term, and never an opening parenthesis at top
/// level (a parenthesis there would open an RDF collection as a subject, which
/// no VSON document uses — §4.1). Comments start with `#` in both syntaxes and
/// are skipped before the decision.
pub fn sniff(text: &str) -> Syntax {
    for line in text.lines() {
        let line = line.trim_start();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        return if line.starts_with('(') {
            Syntax::Penman
        } else {
            Syntax::Turtle
        };
    }
    // Empty input is not Penman: an empty Turtle document is a legal graph with
    // no triples, an empty Penman document is a parse error, and reporting the
    // gate's verdict beats reporting a parse failure we invented.
    Syntax::Turtle
}

/// One source document, indexed for lookups.
pub struct SourceMap {
    text: String,
    syntax: Syntax,
    /// Penman only: variable -> byte offset of its declaration.
    declarations: HashMap<String, usize>,
}

impl SourceMap {
    pub fn new(text: &str, syntax: Syntax) -> Self {
        let declarations = match syntax {
            Syntax::Penman => penman_declarations(text),
            Syntax::Turtle => HashMap::new(),
        };
        SourceMap {
            text: text.to_string(),
            syntax,
            declarations,
        }
    }

    pub fn syntax(&self) -> Syntax {
        self.syntax
    }

    /// Where the node named by `iri` is declared, if that can be established.
    pub fn locate_node(&self, iri: &str) -> Option<Located> {
        let local = local_name(iri);
        match self.syntax {
            Syntax::Penman => self
                .declarations
                .get(local)
                .map(|offset| self.at(*offset, local, "penman-variable")),
            Syntax::Turtle => self.turtle_subject(iri, local),
        }
    }

    /// Where a term is *mentioned*, for findings that have no focus node — a
    /// C2 orphan term is a name the document uses, not a node it describes.
    pub fn locate_term(&self, iri: &str) -> Option<Located> {
        let local = local_name(iri);
        if let Some(found) = self.locate_node(iri) {
            return Some(found);
        }
        match self.syntax {
            // A Penman document writes `:dimension Ambience`, so the term
            // arrives as a bare identifier token. Tokens again, not a scan: the
            // word must be a token, not a substring of a comment.
            Syntax::Penman => tokenize(&self.text).ok().and_then(|toks| {
                toks.iter()
                    .find(|t| match &t.kind {
                        TokKind::Id(s) | TokKind::Role(s) => s == local,
                        _ => false,
                    })
                    .map(|t| self.at(t.offset, local, "mention"))
            }),
            Syntax::Turtle => self.turtle_mention(iri, local),
        }
    }

    /// Line/column for a byte offset, with the anchor and provenance attached.
    fn at(&self, offset: usize, anchor: &str, resolved_from: &'static str) -> Located {
        let before = &self.text[..offset.min(self.text.len())];
        let line = before.matches('\n').count() as u32 + 1;
        let column = before
            .rfind('\n')
            .map_or(before, |nl| &before[nl + 1..])
            .chars()
            .count() as u32
            + 1;
        Located {
            line,
            column,
            anchor: anchor.to_string(),
            resolved_from,
        }
    }

    /// The first line whose leading term denotes `iri`.
    fn turtle_subject(&self, iri: &str, local: &str) -> Option<Located> {
        let angled = format!("<{}>", iri);
        for (index, line) in self.text.lines().enumerate() {
            let indent = line.len() - line.trim_start().len();
            let first = match line.split_whitespace().next() {
                Some(token) => token.trim_end_matches([',', ';', '.']),
                None => continue,
            };
            if first == angled || denotes(first, iri, local) {
                return Some(Located {
                    line: index as u32 + 1,
                    column: self.column_of(line, indent),
                    anchor: first.to_string(),
                    resolved_from: "turtle-subject",
                });
            }
        }
        None
    }

    /// The first line mentioning the term anywhere, in any triple position.
    fn turtle_mention(&self, iri: &str, local: &str) -> Option<Located> {
        let angled = format!("<{}>", iri);
        for (index, line) in self.text.lines().enumerate() {
            for token in line.split_whitespace() {
                let token = token.trim_end_matches([',', ';', '.']);
                if token == angled || denotes(token, iri, local) {
                    let byte = line.find(token).unwrap_or(0);
                    return Some(Located {
                        line: index as u32 + 1,
                        column: self.column_of(line, byte),
                        anchor: token.to_string(),
                        resolved_from: "mention",
                    });
                }
            }
        }
        None
    }

    /// 1-based column, counted in characters, of a byte offset within a line.
    fn column_of(&self, line: &str, byte: usize) -> u32 {
        line[..byte.min(line.len())].chars().count() as u32 + 1
    }
}

/// Whether a Turtle term as written denotes `iri`.
///
/// Two spellings are accepted: a prefixed name whose local part matches
/// (`:sf`, `vso:Ambience`), and an angle-bracketed IRI ending in the same local
/// name. A prefixed name whose prefix binds some *other* namespace would match
/// here — the scan does not resolve prefixes — which is exactly why a Turtle
/// position is reported as best-effort and never as the finding's evidence.
fn denotes(token: &str, iri: &str, local: &str) -> bool {
    if let Some(inner) = token.strip_prefix('<').and_then(|t| t.strip_suffix('>')) {
        return inner == iri || local_name(inner) == local;
    }
    match token.split_once(':') {
        Some((_prefix, name)) => !name.is_empty() && name == local,
        None => false,
    }
}

/// Every Penman variable and the offset of the token that declares it.
///
/// A variable is declared by the identifier immediately after an opening
/// parenthesis, once; a later `:viewedBy cam` is a reference, and the first
/// binding is the one a reader would go to.
fn penman_declarations(text: &str) -> HashMap<String, usize> {
    let mut out = HashMap::new();
    let toks = match tokenize(text) {
        Ok(toks) => toks,
        // An unparseable document has no declarations to offer, and refusing to
        // report the gate's finding because of it would be the wrong trade.
        Err(_) => return out,
    };
    for pair in toks.windows(2) {
        if let (TokKind::LParen, TokKind::Id(var)) = (&pair[0].kind, &pair[1].kind) {
            out.entry(var.clone()).or_insert(pair[1].offset);
        }
    }
    out
}

/// Everything after the last `#` or `/`.
fn local_name(iri: &str) -> &str {
    match iri.rsplit_once(['#', '/']) {
        Some((_, tail)) if !tail.is_empty() => tail,
        _ => iri,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SCENE: &str = "# a comment naming sf, which is not a declaration\n\
                         (scene / Composition\n   \
                            :hasFact (sf / SpatialFact\n               \
                               :directional left_of))\n";

    #[test]
    fn a_penman_variable_resolves_to_its_declaration_not_its_mention() {
        let map = SourceMap::new(SCENE, Syntax::Penman);
        let found = map
            .locate_node("https://example.org/scenes/anonymous#sf")
            .expect("sf is declared");
        assert_eq!(found.line, 3, "line 1 is the comment that also says 'sf'");
        assert_eq!(found.resolved_from, "penman-variable");
        assert_eq!(found.anchor, "sf");
        // Column points at the variable itself, past `:hasFact (`.
        assert_eq!(&SCENE.lines().nth(2).unwrap()[13..15], "sf");
        assert_eq!(found.column, 14);
    }

    #[test]
    fn an_unknown_variable_resolves_to_nothing() {
        let map = SourceMap::new(SCENE, Syntax::Penman);
        assert!(map.locate_node("https://example.org/x#nowhere").is_none());
    }

    #[test]
    fn a_turtle_subject_resolves_by_line() {
        let ttl = "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n\
                   :scene a vso:Composition .\n\
                   :sf a vso:SpatialFact ;\n    \
                       vso:directional vso:left_of .\n";
        let map = SourceMap::new(ttl, Syntax::Turtle);
        let found = map
            .locate_node("https://example.org/scenes/bad#sf")
            .expect("the subject line is found");
        assert_eq!((found.line, found.column), (3, 1));
        assert_eq!(found.resolved_from, "turtle-subject");
    }

    #[test]
    fn a_term_in_object_position_resolves_only_as_a_mention() {
        let ttl = "@prefix vso: <https://w3id.org/vson/v1/ontology#> .\n\
                   :q vso:dimension vso:Ambience .\n";
        let map = SourceMap::new(ttl, Syntax::Turtle);
        assert!(map
            .locate_node("https://w3id.org/vson/v1/ontology#Ambience")
            .is_none());
        let found = map
            .locate_term("https://w3id.org/vson/v1/ontology#Ambience")
            .expect("the mention is found");
        assert_eq!(found.line, 2);
        assert_eq!(found.resolved_from, "mention");
        assert_eq!(found.anchor, "vso:Ambience");
    }

    #[test]
    fn the_syntax_of_a_stream_is_read_off_its_first_real_token() {
        assert_eq!(
            sniff("# lead comment\n\n(s / Composition)\n"),
            Syntax::Penman
        );
        assert_eq!(sniff("@prefix vso: <x> .\n"), Syntax::Turtle);
        assert_eq!(sniff("  \n"), Syntax::Turtle);
    }

    #[test]
    fn a_column_counts_characters_not_bytes() {
        // SARIF's columnKind is declared as unicodeCodePoints, so a multi-byte
        // character ahead of the token must move the column by one, not by its
        // UTF-8 length.
        let src = "(scene / Composition\n   :venue \"café\" :hasFact (sf / SpatialFact))\n";
        let map = SourceMap::new(src, Syntax::Penman);
        let found = map.locate_node("urn:x#sf").expect("sf is declared");
        assert_eq!(found.line, 2);
        assert_eq!(found.column, 28);
    }
}
