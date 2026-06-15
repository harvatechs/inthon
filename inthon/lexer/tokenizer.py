from __future__ import annotations
import re
from .tokens import Token, TokenType, Span
from .keywords import KEYWORD_MAP

_TOKEN_PATTERNS: list[tuple[TokenType, re.Pattern[str]]] = [
    (TokenType.FLOAT_LIT,   re.compile(r'\d+\.\d*([eE][+-]?\d+)?')),
    (TokenType.INT_LIT,     re.compile(r'\d+')),
    (TokenType.STRING_LIT,  re.compile(r'"(?:[^"\\]|\\.)*"')),
    (TokenType.STRING_LIT,  re.compile(r"'(?:[^'\\]|\\.)*'")),
    (TokenType.ARROW,       re.compile(r'->')),
    (TokenType.EQ_EQ,       re.compile(r'==')),
    (TokenType.BANG_EQ,     re.compile(r'!=')),
    (TokenType.LT_EQ,       re.compile(r'<=')),
    (TokenType.GT_EQ,       re.compile(r'>=')),
    (TokenType.STAR_STAR,   re.compile(r'\*\*')),
    (TokenType.PLUS,        re.compile(r'\+')),
    (TokenType.MINUS,       re.compile(r'-')),
    (TokenType.STAR,        re.compile(r'\*')),
    (TokenType.SLASH,       re.compile(r'/')),
    (TokenType.PERCENT,     re.compile(r'%')),
    (TokenType.EQ,          re.compile(r'=')),
    (TokenType.LT,          re.compile(r'<')),
    (TokenType.GT,          re.compile(r'>')),
    (TokenType.DOT,         re.compile(r'\.')),
    (TokenType.COLON,       re.compile(r':')),
    (TokenType.COMMA,       re.compile(r',')),
    (TokenType.PIPE,        re.compile(r'\|')),
    (TokenType.LPAREN,      re.compile(r'\(')),
    (TokenType.RPAREN,      re.compile(r'\)')),
    (TokenType.LBRACE,      re.compile(r'\{')),
    (TokenType.RBRACE,      re.compile(r'\}')),
    (TokenType.LBRACKET,    re.compile(r'\[')),
    (TokenType.RBRACKET,    re.compile(r'\]')),
    (TokenType.IDENT,       re.compile(r'[A-Za-z_][A-Za-z0-9_]*')),
]

_WHITESPACE    = re.compile(r'[ \t]+')
_NEWLINE       = re.compile(r'\r?\n')
_LINE_COMMENT  = re.compile(r'//[^\n]*')
_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)

class LexerError(Exception):
    def __init__(self, msg: str, span: Span) -> None:
        super().__init__(msg)
        self.span = span

    def __str__(self) -> str:
        return (
            f"\nINTHON_PARSE_LEX_001: {self.args[0]}\n"
            f"  File: {self.span.file}\n"
            f"  Line: {self.span.line}, Column: {self.span.col}\n"
        )

class Tokenizer:
    """
    Single-pass, regex-driven tokenizer.
    Thread-unsafe by design — create one instance per parse call.
    Each `tokenize()` call is idempotent on the same source string.
    """
    def __init__(self, source: str, filename: str = "<stdin>") -> None:
        self._source = source
        self._filename = filename
        self._pos = 0
        self._line = 1
        self._col = 1

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        src = self._source
        while self._pos < len(src):
            # --- skip block comments ---
            m = _BLOCK_COMMENT.match(src, self._pos)
            if m:
                self._advance_by(m.group())
                continue

            # --- skip line comments ---
            m = _LINE_COMMENT.match(src, self._pos)
            if m:
                self._advance_by(m.group())
                continue

            # --- newlines (significant at statement boundary) ---
            m = _NEWLINE.match(src, self._pos)
            if m:
                tokens.append(self._make_token(TokenType.NEWLINE, m.group()))
                self._pos += len(m.group())
                self._line += 1
                self._col = 1
                continue

            # --- whitespace ---
            m = _WHITESPACE.match(src, self._pos)
            if m:
                self._advance_by(m.group())
                continue

            # --- token patterns ---
            matched = False
            for tok_type, pattern in _TOKEN_PATTERNS:
                m = pattern.match(src, self._pos)
                if m:
                    raw = m.group()
                    # Resolve IDENT -> keyword if applicable
                    resolved_type = KEYWORD_MAP.get(raw, tok_type) if tok_type == TokenType.IDENT else tok_type
                    tokens.append(self._make_token(resolved_type, raw))
                    self._advance_by(raw)
                    matched = True
                    break

            if not matched:
                span = self._current_span(1)
                raise LexerError(
                    f"Unexpected character {src[self._pos]!r}",
                    span
                )

        tokens.append(self._make_token(TokenType.EOF, ""))
        return tokens

    # ------------------------------------------------------------------ #
    # private helpers
    # ------------------------------------------------------------------ #
    def _make_token(self, ttype: TokenType, raw: str) -> Token:
        span = Span(
            file=self._filename,
            line=self._line,
            col=self._col,
            offset=self._pos,
            length=len(raw),
        )
        return Token(type=ttype, value=raw, span=span)

    def _advance_by(self, text: str) -> None:
        self._pos += len(text)
        nl_count = text.count('\n')
        if nl_count:
            self._line += nl_count
            self._col = len(text) - text.rfind('\n')
        else:
            self._col += len(text)

    def _current_span(self, length: int) -> Span:
        return Span(self._filename, self._line, self._col, self._pos, length)
