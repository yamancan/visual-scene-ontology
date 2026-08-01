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
    /// Byte offset of the token's match in the source it was lexed from.
    ///
    /// The parser ignores it; `commands::sourcemap` is what reads it, to turn a
    /// focus node reported by a gate back into the line and column where the
    /// Penman variable was declared. Carried on the token rather than
    /// recomputed by a text scan because a scan cannot tell a variable from the
    /// same word inside a comment or a quoted literal, and the lexer already
    /// has.
    pub offset: usize,
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
                // Unknown escape: keep the backslash verbatim rather than
                // dropping it (mirrors the Python reference; lossless round-trip).
                Some(other) => {
                    out.push('\\');
                    out.push(other);
                }
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
        // The whole match starts where the token starts for every branch except
        // the two with a leading sigil, and those report the sigil's position:
        // `:role` is one token to a reader, and pointing a build annotation at
        // the colon is pointing at the role.
        let mut push = |kind: TokKind| {
            out.push(Tok {
                kind,
                offset: m.start(),
            })
        };
        if cap.name("lp").is_some() {
            push(TokKind::LParen);
        } else if cap.name("rp").is_some() {
            push(TokKind::RParen);
        } else if let Some(g) = cap.name("str") {
            push(TokKind::Str(decode_escapes(g.as_str())));
        } else if let Some(g) = cap.name("role") {
            push(TokKind::Role(g.as_str().to_string()));
        } else if cap.name("slash").is_some() {
            push(TokKind::Slash);
        } else if let Some(g) = cap.name("unit") {
            push(TokKind::Unit(g.as_str().to_string()));
        } else if let Some(g) = cap.name("num") {
            push(TokKind::Num(g.as_str().to_string()));
        } else if let Some(g) = cap.name("id") {
            push(TokKind::Id(g.as_str().to_string()));
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

    #[test]
    fn tokens_carry_their_source_offset() {
        // The offsets are what `commands::sourcemap` turns into a line and a
        // column, so a comment before the node must not shift them: they are
        // positions in the source, not in the token stream.
        let src = "# note\n(s / Composition)";
        let toks = tokenize(src).unwrap();
        assert_eq!(toks[0].offset, 7, "'(' sits right after the comment line");
        assert_eq!(&src[toks[1].offset..toks[1].offset + 1], "s");
    }

    #[test]
    fn unknown_escape_keeps_backslash() {
        // `\p` is outside the closed escape set; the backslash is preserved
        // verbatim (lossless), not silently dropped (which would give "C:path").
        let toks = tokenize(r#":k "C:\path""#).unwrap();
        match &toks[1].kind {
            TokKind::Str(s) => assert_eq!(s, r"C:\path"),
            other => panic!("got {:?}", other),
        }
    }
}
