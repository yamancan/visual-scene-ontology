"""Executable grammars — docs/vson.md Appendix B, Appendix D and §D.10.

The two concrete syntaxes VSON authors write by hand, VSON-P (Penman) and
VSON-X, are specified as EBNF in `docs/vson.md`. This package is what makes
those blocks executable: it extracts them from the spec, translates them
mechanically into a parser generator's input, and runs the result against the
corpora on every commit (`make grammar-check`).

The spec is the source. No module here carries a copy of a production, a
terminal, a closed token vocabulary or a scanner order — every one of those is
read out of `docs/vson.md` at run time, so a grammar that changes in the spec
changes here in the same commit or the gate goes red.
"""
