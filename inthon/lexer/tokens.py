"""INTHON token definitions (engine spec §3.1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from ..errors import Span


class TokenType(Enum):
    # --- Structural ---
    NEWLINE = auto()
    INDENT = auto()  # reserved (unused: INTHON uses braces)
    DEDENT = auto()  # reserved (unused: INTHON uses braces)
    EOF = auto()

    # --- Literals ---
    IDENT = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    BOOL = auto()
    NONE = auto()

    # --- Keywords: declarations ---
    LET = auto()
    CONST = auto()
    FN = auto()
    AGENT = auto()

    # --- Keywords: control flow ---
    IF = auto()
    ELSE = auto()
    FOR = auto()
    WHILE = auto()
    IN = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()

    # --- Keywords: agent ---
    GOAL = auto()
    INPUTS = auto()
    OUTPUTS = auto()
    USE = auto()
    POLICY = auto()
    PLAN = auto()
    TOOL = auto()
    PY = auto()
    MEMORY = auto()
    AS = auto()
    APPROVE = auto()
    BEFORE = auto()
    REMEMBER = auto()
    RECALL = auto()
    FORGET = auto()
    FROM = auto()
    GUARD = auto()
    RETRY = auto()
    WITH = auto()
    BACKOFF = auto()
    CATCH = auto()
    EVAL = auto()
    AGAINST = auto()
    ON = auto()
    FAIL = auto()
    REWRITE = auto()
    CRITERIA = auto()
    REWRITER = auto()

    # --- Operators: arithmetic ---
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    STAR_STAR = auto()

    # --- Operators: comparison ---
    EQ_EQ = auto()
    NOT_EQ = auto()
    LT = auto()
    GT = auto()
    LT_EQ = auto()
    GT_EQ = auto()

    # --- Operators: logical ---
    AND = auto()
    OR = auto()
    NOT = auto()

    # --- Operators: assignment / other ---
    ASSIGN = auto()
    ARROW = auto()
    DOT = auto()
    COMMA = auto()
    COLON = auto()
    SEMICOLON = auto()

    # --- Delimiters ---
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()

    # --- Aliases ---
    STRING_LIT = STRING
    EQ = ASSIGN
    INT_LIT = INT
    FLOAT_LIT = FLOAT


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: object
    span: Span

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"Token({self.type.name}, {self.value!r}, {self.span.line}:{self.span.col})"
        )
