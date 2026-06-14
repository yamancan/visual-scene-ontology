//! VSON-P recursive-descent parser. Mirrors
//! `tools/penman/vson_penman.py:Parser.parse_node` and `parse_term`.

use super::lexer::{tokenize, Tok, TokKind};

#[derive(Debug, Clone)]
pub enum Term {
    Node(Node),
    Ref(String),
    StrLit(String),
    NumLit(String),
    UnitLit(String),
}

#[derive(Debug, Clone)]
pub struct Node {
    pub var: String,
    pub concept: Option<String>,
    pub edges: Vec<(String, Term)>,
}

pub struct Parser {
    toks: Vec<Tok>,
    i: usize,
}

impl Parser {
    pub fn new(toks: Vec<Tok>) -> Self {
        Self { toks, i: 0 }
    }

    fn peek(&self) -> Option<&TokKind> {
        self.toks.get(self.i).map(|t| &t.kind)
    }

    fn bump(&mut self) -> Option<&Tok> {
        let t = self.toks.get(self.i);
        self.i += 1;
        t
    }

    pub fn parse_node(&mut self) -> Result<Node, String> {
        match self.peek() {
            Some(TokKind::LParen) => { self.i += 1; }
            other => return Err(format!("expected '(', got {:?}", other)),
        }
        let var = match self.bump().map(|t| t.kind.clone()) {
            Some(TokKind::Id(s)) => s,
            other => return Err(format!("expected variable id, got {:?}", other)),
        };
        let mut concept: Option<String> = None;
        if let Some(TokKind::Slash) = self.peek() {
            self.i += 1;
            concept = match self.bump().map(|t| t.kind.clone()) {
                Some(TokKind::Id(s)) => Some(s),
                other => return Err(format!("expected concept id after '/', got {:?}", other)),
            };
        }
        let mut node = Node { var, concept, edges: Vec::new() };
        loop {
            match self.peek() {
                None => return Err("unexpected EOF inside node".into()),
                Some(TokKind::RParen) => { self.i += 1; return Ok(node); }
                Some(TokKind::Role(_)) => {
                    let role = match self.bump().map(|t| t.kind.clone()) {
                        Some(TokKind::Role(s)) => s,
                        _ => unreachable!(),
                    };
                    let term = self.parse_term()?;
                    node.edges.push((role, term));
                }
                other => return Err(format!("expected role or ')', got {:?}", other)),
            }
        }
    }

    fn parse_term(&mut self) -> Result<Term, String> {
        match self.peek() {
            Some(TokKind::LParen) => Ok(Term::Node(self.parse_node()?)),
            Some(TokKind::Str(_)) => match self.bump().map(|t| t.kind.clone()) {
                Some(TokKind::Str(s)) => Ok(Term::StrLit(s)),
                _ => unreachable!(),
            },
            Some(TokKind::Num(_)) => match self.bump().map(|t| t.kind.clone()) {
                Some(TokKind::Num(s)) => Ok(Term::NumLit(s)),
                _ => unreachable!(),
            },
            Some(TokKind::Unit(_)) => match self.bump().map(|t| t.kind.clone()) {
                Some(TokKind::Unit(s)) => Ok(Term::UnitLit(s)),
                _ => unreachable!(),
            },
            Some(TokKind::Id(_)) => match self.bump().map(|t| t.kind.clone()) {
                Some(TokKind::Id(s)) => Ok(Term::Ref(s)),
                _ => unreachable!(),
            },
            other => Err(format!("unexpected term: {:?}", other)),
        }
    }
}

pub fn parse(src: &str) -> Result<Node, String> {
    let toks = tokenize(src)?;
    let mut p = Parser::new(toks);
    let node = p.parse_node()?;
    if let Some(extra) = p.peek() {
        return Err(format!(
            "unexpected trailing token after top-level node: {extra:?}"
        ));
    }
    Ok(node)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn simple_node() {
        let n = parse("(s / Composition)").unwrap();
        assert_eq!(n.var, "s");
        assert_eq!(n.concept.as_deref(), Some("Composition"));
        assert!(n.edges.is_empty());
    }

    #[test]
    fn nested_node() {
        let n = parse("(s / Composition :depicts (a / PhysicalObject))").unwrap();
        assert_eq!(n.edges.len(), 1);
        let (role, target) = &n.edges[0];
        assert_eq!(role, "depicts");
        assert!(matches!(target, Term::Node(_)));
    }

    #[test]
    fn forward_ref_id() {
        let n = parse("(s / Composition :viewedBy cam)").unwrap();
        let (role, target) = &n.edges[0];
        assert_eq!(role, "viewedBy");
        match target {
            Term::Ref(v) => assert_eq!(v, "cam"),
            other => panic!("expected Ref, got {:?}", other),
        }
    }

    #[test]
    fn trailing_tokens_rejected() {
        // Mirrors the Python reference: a second top-level node is an error,
        // not silently dropped.
        assert!(parse("(a / Foo) (b / Bar)").is_err());
    }
}
