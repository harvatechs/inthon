"""Hand-written, single-pass INTHON tokenizer (engine spec §3.1).

The lexer consumes the source character stream and produces a list of
Span-annotated tokens.  It is used by the formatter, the `inthon lex`
debugging command, and tooling integrations.  The canonical parser is
driven by grammar.lark (Lark LALR); both share the same token model.
"""

from __future__ import annotations

from typing import List, Optional

from ..errors import InthonLexError, Span
from .keywords import KEYWORDS
from .tokens import Token, TokenType

_TWO_CHAR_OPS = {
    "**": TokenType.STAR_STAR,
    "==": TokenType.EQ_EQ,
    "!=": TokenType.NOT_EQ,
    "<=": TokenType.LT_EQ,
    ">=": TokenType.GT_EQ,
    "->": TokenType.ARROW,
}

_ONE_CHAR_OPS = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    "<": TokenType.LT,
    ">": TokenType.GT,
    "=": TokenType.ASSIGN,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ".": TokenType.DOT,
    ",": TokenType.COMMA,
    ":": TokenType.COLON,
    ";": TokenType.SEMICOLON,
}

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "0": "\0",
}


class Lexer:
    """Single-pass character-stream tokenizer."""

    def __init__(self, source: str, filename: str = "<stdin>"):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    # -- cursor helpers -----------------------------------------------------
    def _peek(self, offset: int = 0) -> Optional[str]:
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else None

    def _advance(self) -> Optional[str]:
        ch = self._peek()
        if ch is None:
            return None
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _span(self, line: int, col: int, offset: int) -> Span:
        return Span(
            filename=self.filename,
            line=line,
            col=col,
            offset=offset,
            length=max(1, self.pos - offset),
        )

    def _error(self, message: str, line: int, col: int, offset: int) -> InthonLexError:
        src_line = self._line_text(line)
        return InthonLexError(
            message,
            span=self._span(line, col, offset),
            source_line=src_line,
        )

    def _line_text(self, line: int) -> str:
        lines = self.source.splitlines()
        if 1 <= line <= len(lines):
            return lines[line - 1]
        return ""

    # -- main loop -----------------------------------------------------------
    def tokenize(self) -> List[Token]:
        while True:
            ch = self._peek()
            if ch is None:
                break
            if ch in " \t\r":
                self._advance()
                continue
            if ch == "\n":
                line, col, off = self.line, self.col, self.pos
                self._advance()
                self.tokens.append(Token(TokenType.NEWLINE, "\n", self._span(line, col, off)))
                continue
            if ch == "/" and self._peek(1) == "/":
                self._skip_line_comment()
                continue
            if ch == "/" and self._peek(1) == "*":
                self._skip_block_comment()
                continue
            if ch.isdigit():
                self.tokens.append(self._number())
                continue
            if ch in ('"', "'"):
                self.tokens.append(self._string())
                continue
            if ch.isalpha() or ch == "_":
                self.tokens.append(self._identifier())
                continue
            two = ch + (self._peek(1) or "")
            if two in _TWO_CHAR_OPS:
                line, col, off = self.line, self.col, self.pos
                self._advance()
                self._advance()
                self.tokens.append(Token(_TWO_CHAR_OPS[two], two, self._span(line, col, off)))
                continue
            if ch in _ONE_CHAR_OPS:
                line, col, off = self.line, self.col, self.pos
                self._advance()
                self.tokens.append(Token(_ONE_CHAR_OPS[ch], ch, self._span(line, col, off)))
                continue
            raise self._error(f"Unexpected character {ch!r}", self.line, self.col, self.pos)

        eof_span = Span(self.filename, self.line, self.col, offset=self.pos, length=1)
        self.tokens.append(Token(TokenType.EOF, None, eof_span))
        return self.tokens

    # -- comment handling -----------------------------------------------------
    def _skip_line_comment(self) -> None:
        while self._peek() not in (None, "\n"):
            self._advance()

    def _skip_block_comment(self) -> None:
        start_line, start_col, start_off = self.line, self.col, self.pos
        self._advance()  # /
        self._advance()  # *
        while True:
            ch = self._peek()
            if ch is None:
                raise self._error(
                    "Unterminated block comment", start_line, start_col, start_off
                )
            if ch == "*" and self._peek(1) == "/":
                self._advance()
                self._advance()
                return
            self._advance()

    # -- numbers ---------------------------------------------------------------
    def _number(self) -> Token:
        line, col, off = self.line, self.col, self.pos
        start = self.pos
        while self._peek() and (self._peek().isdigit() or self._peek() == "_"):
            self._advance()
        is_float = False
        if self._peek() == "." and self._peek(1) and self._peek(1).isdigit():
            is_float = True
            self._advance()
            while self._peek() and (self._peek().isdigit() or self._peek() == "_"):
                self._advance()
        if self._peek() in ("e", "E") and self._peek(1) and (
            self._peek(1).isdigit() or (self._peek(1) in "+-" and self._peek(2) and self._peek(2).isdigit())
        ):
            is_float = True
            self._advance()
            if self._peek() in "+-":
                self._advance()
            while self._peek() and self._peek().isdigit():
                self._advance()
        text = self.source[start:self.pos].replace("_", "")
        try:
            value = float(text) if is_float else int(text)
        except ValueError:  # pragma: no cover - defensive
            raise self._error(f"Invalid numeric literal {text!r}", line, col, off)
        return Token(TokenType.FLOAT if is_float else TokenType.INT, value, self._span(line, col, off))

    # -- strings ---------------------------------------------------------------
    def _string(self) -> Token:
        line, col, off = self.line, self.col, self.pos
        quote = self._advance()
        chars: list[str] = []
        while True:
            ch = self._peek()
            if ch is None or ch == "\n":
                raise self._error("Unterminated string literal", line, col, off)
            if ch == quote:
                self._advance()
                break
            if ch == "\\":
                self._advance()
                esc = self._peek()
                if esc is None:
                    raise self._error("Unterminated string escape", line, col, off)
                if esc in _ESCAPES:
                    chars.append(_ESCAPES[esc])
                    self._advance()
                else:
                    raise self._error(
                        f"Unknown escape sequence '\\{esc}'",
                        self.line, self.col, self.pos,
                    )
                continue
            chars.append(ch)
            self._advance()
        return Token(TokenType.STRING, quote + "".join(chars) + quote, self._span(line, col, off))

    # -- identifiers / keywords -------------------------------------------------
    def _identifier(self) -> Token:
        line, col, off = self.line, self.col, self.pos
        start = self.pos
        while self._peek() and (self._peek().isalnum() or self._peek() == "_"):
            self._advance()
        text = self.source[start:self.pos]
        kw = KEYWORDS.get(text)
        if kw is not None:
            if kw == "BOOL":
                return Token(TokenType.BOOL, text == "true", self._span(line, col, off))
            if kw == "NONE":
                return Token(TokenType.NONE, None, self._span(line, col, off))
            return Token(TokenType[kw], text, self._span(line, col, off))
        return Token(TokenType.IDENT, text, self._span(line, col, off))


def tokenize(source: str, filename: str = "<stdin>") -> List[Token]:
    """Tokenize *source* and return the token list (ends with EOF)."""
    return Lexer(source, filename).tokenize()


# Backward compatibility aliases
Tokenizer = Lexer
LexerError = InthonLexError
