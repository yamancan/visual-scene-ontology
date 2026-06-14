//! VSON-P tokenizer. Mirrors `tools/penman/vson_penman.py:tokenize`.

use once_cell::sync::Lazy;
use regex::Regex;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TokKind {
    LParen,
    RParen,
    Slash,
    Role(String),
    Id(String),
    Num(String),
    Unit(String),
    Str(String),
}

#[derive(Debug, Clone)]
pub struct Tok {
    pub kind: TokKind,
}

static TOKEN_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        // Group order matches the Python reference; ordering is load-bearing
        // because UNIT must take precedence over NUM and ID.
        r#"(?x)
        \#[^\n]*                                      # comment
        | (?P<lp>\()                                  # open paren
        | (?P<rp>\))                                  # close paren
        | "(?P<str>(?:[^"\\]|\\.)*)"                  # quoted string
        | :(?P<role>[A-Za-z_][\w\-]*)                 # :role
        | (?P<slash>/)                                # /
        | (?P<unit>-?\d+(?:\.\d+)?[A-Za-z_][\w\-]*)   # 35mm
        | (?P<num>-?\d+(?:\.\d+)?)                    # bare number
        | (?P<id>[A-Za-z_][\w\-]*)                    # bare id
        | (?P<bad>\S)                                 # error sentinel
        "#,
    )
    .expect("TOKEN_RE compile")
});

/// Decode the Turtle ECHAR set so a Str token carries the true string value
/// (mirrors `_decode_escapes` in the Python reference). The emitter re-encodes
/// for Turtle at emit time; lexing verbatim would corrupt `\n` and friends.
fn decode_escapes(body: &str) -> String {
    let mut out = String::with_capacity(body.len());
    let mut chars = body.chars();
    while let Some(c) = chars.next() {
        if c == '\\' {
            match chars.next() {
                Some('t') => out.push('\t'),
                Some('b') => out.push('\u{0008}'),
                Some('n') => out.push('\n'),
                Some('r') => out.push('\r'),
                Some('f') => out.push('\u{000C}'),
                Some('"') => out.push('"'),
                Some('\'') => out.push('\''),
                Some('\\') => out.push('\\'),
                Some('/') => out.push('/'),
                Some(other) => out.push(other),
                None => out.push('\\'),
            }
        } else {
            out.push(c);
        }
    }
    out
}

pub fn tokenize(src: &str) -> Result<Vec<Tok>, String> {
    let mut out = Vec::new();
    for cap in TOKEN_RE.captures_iter(src) {
        let m = cap.get(0).unwrap();
        let text = m.as_str();
        if text.starts_with('#') || text.chars().all(char::is_whitespace) {
            continue;
        }
        if cap.name("lp").is_some() {
            out.push(Tok { kind: TokKind::LParen });
        } else if cap.name("rp").is_some() {
            out.push(Tok { kind: TokKind::RParen });
        } else if let Some(g) = cap.name("str") {
            out.push(Tok { kind: TokKind::Str(decode_escapes(g.as_str())) });
        } else if let Some(g) = cap.name("role") {
            out.push(Tok { kind: TokKind::Role(g.as_str().to_string()) });
        } else if cap.name("slash").is_some() {
            out.push(Tok { kind: TokKind::Slash });
        } else if let Some(g) = cap.name("unit") {
            out.push(Tok { kind: TokKind::Unit(g.as_str().to_string()) });
        } else if let Some(g) = cap.name("num") {
            out.push(Tok { kind: TokKind::Num(g.as_str().to_string()) });
        } else if let Some(g) = cap.name("id") {
            out.push(Tok { kind: TokKind::Id(g.as_str().to_string()) });
        } else if let Some(g) = cap.name("bad") {
            return Err(format!("unexpected character: {:?}", g.as_str()));
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paren_pair() {
        let toks = tokenize("()").unwrap();
        assert_eq!(toks.len(), 2);
        assert_eq!(toks[0].kind, TokKind::LParen);
        assert_eq!(toks[1].kind, TokKind::RParen);
    }

    #[test]
    fn role_and_id() {
        let toks = tokenize("(s / Composition :viewedBy cam)").unwrap();
        let kinds: Vec<&TokKind> = toks.iter().map(|t| &t.kind).collect();
        assert!(matches!(kinds[1], TokKind::Id(_)));
        assert!(matches!(kinds[2], TokKind::Slash));
        assert!(matches!(kinds[3], TokKind::Id(_)));
        assert!(matches!(kinds[4], TokKind::Role(_)));
        assert!(matches!(kinds[5], TokKind::Id(_)));
    }

    #[test]
    fn unit_literal() {
        let toks = tokenize(":focalLength 35mm").unwrap();
        match &toks[1].kind {
            TokKind::Unit(s) => assert_eq!(s, "35mm"),
            other => panic!("expected UNIT, got {:?}", other),
        }
    }

    #[test]
    fn comment_skipped() {
        let toks = tokenize("# comment\n(a / B)").unwrap();
        assert_eq!(toks.len(), 5);
    }

    #[test]
    fn quoted_string() {
        // Source `"hello\"world"` lexes to the decoded value `hello"world`.
        let toks = tokenize(":k \"hello\\\"world\"").unwrap();
        match &toks[1].kind {
            TokKind::Str(s) => assert_eq!(s, "hello\"world"),
            other => panic!("got {:?}", other),
        }
    }

    #[test]
    fn escapes_decoded() {
        let toks = tokenize(r#":k "a\nb\tc""#).unwrap();
        match &toks[1].kind {
            TokKind::Str(s) => assert_eq!(s, "a\nb\tc"),
            other => panic!("got {:?}", other),
        }
    }
}
