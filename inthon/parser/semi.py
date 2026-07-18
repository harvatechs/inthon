"""Go-style automatic semicolon insertion (spec extension, FE-13).

INTHON is brace-delimited and mostly whitespace-insensitive; naive newline
insensitivity creates the classic continuation hazard:

    f(1)
    [1, 2]        — parses as f(1)[1, 2] (indexing) without ASI

This pass tokenizes the source with the hand-written lexer and splices a
";" into the text at every newline that ends a statement, using Go's rule:

  insert after a line whose last significant token can end a statement
  (identifier, literal, ), ], }, return, break, continue)

  ...unless the next significant token shows the statement continues
  (an operator, opening ( [ { . , : or a continuation keyword like else).

Newlines inside ( ) and [ ] and inside dict literals never terminate a
statement.  Braces are classified block-vs-dict by the preceding token.

The spliced ";" is inserted immediately after the previous token (before
any trailing comment), so line/column numbers for real code never shift.
Runs in a single O(n) pass.
"""

from __future__ import annotations

from ..lexer.tokens import Token, TokenType
from ..lexer.tokenizer import Lexer

_AFTER = {
    TokenType.IDENT,
    TokenType.INT,
    TokenType.FLOAT,
    TokenType.STRING,
    TokenType.BOOL,
    TokenType.NONE,
    TokenType.RPAREN,
    TokenType.RBRACKET,
    TokenType.RBRACE,
    TokenType.RETURN,
    TokenType.BREAK,
    TokenType.CONTINUE,
}

_CONTINUATION = {
    TokenType.PLUS,
    TokenType.MINUS,
    TokenType.STAR,
    TokenType.SLASH,
    TokenType.PERCENT,
    TokenType.STAR_STAR,
    TokenType.EQ_EQ,
    TokenType.NOT_EQ,
    TokenType.LT,
    TokenType.GT,
    TokenType.LT_EQ,
    TokenType.GT_EQ,
    TokenType.AND,
    TokenType.OR,
    TokenType.DOT,
    TokenType.COMMA,
    TokenType.COLON,
    TokenType.ASSIGN,
    TokenType.LBRACE,
    # continuation keywords
    TokenType.ELSE,
    TokenType.CATCH,
    TokenType.ON,
    TokenType.IN,
    TokenType.FROM,
    TokenType.BEFORE,
    TokenType.WITH,
    TokenType.BACKOFF,
    TokenType.AGAINST,
    TokenType.AS,
}

# tokens after which "{" opens a dict literal rather than a block
_DICT_PRECEDERS = {
    TokenType.ASSIGN,
    TokenType.LPAREN,
    TokenType.LBRACKET,
    TokenType.COMMA,
    TokenType.COLON,
    TokenType.RETURN,
    TokenType.PLUS,
    TokenType.MINUS,
    TokenType.STAR,
    TokenType.SLASH,
    TokenType.PERCENT,
    TokenType.STAR_STAR,
    TokenType.AND,
    TokenType.OR,
    TokenType.NOT,
    TokenType.EQ_EQ,
    TokenType.NOT_EQ,
    TokenType.LT,
    TokenType.GT,
    TokenType.LT_EQ,
    TokenType.GT_EQ,
    TokenType.IN,
}


def insert_semicolons(source: str, filename: str = "<stdin>") -> str:
    tokens = Lexer(source, filename).tokenize()
    insertions: list[int] = []

    depth = 0  # () and [] nesting
    brace_stack: list[bool] = []  # True = dict literal, False = block
    prev: Token | None = None  # last significant token
    pending = False  # saw a newline awaiting a decision

    for tok in tokens:
        if tok.type == TokenType.NEWLINE:
            pending = True
            continue
        if pending:
            if (
                depth == 0
                and not (brace_stack and brace_stack[-1])
                and prev is not None
                and tok.type != TokenType.EOF
                and prev.type in _AFTER
                and tok.type not in _CONTINUATION
            ):
                insertions.append(prev.span.offset + prev.span.length)
            pending = False
        if tok.type in (TokenType.LPAREN, TokenType.LBRACKET):
            depth += 1
        elif tok.type in (TokenType.RPAREN, TokenType.RBRACKET):
            depth = max(0, depth - 1)
        elif tok.type == TokenType.LBRACE:
            is_dict = prev is not None and prev.type in _DICT_PRECEDERS
            brace_stack.append(is_dict)
        elif tok.type == TokenType.RBRACE:
            if brace_stack:
                brace_stack.pop()
        prev = tok

    if not insertions:
        return source
    out = []
    last = 0
    for pos in sorted(set(insertions)):
        out.append(source[last:pos])
        out.append(";")
        last = pos
    out.append(source[last:])
    return "".join(out)
