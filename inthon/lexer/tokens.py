from enum import Enum, auto
from dataclasses import dataclass


class TokenType(Enum):
    # Literals
    INT_LIT = auto()
    FLOAT_LIT = auto()
    STRING_LIT = auto()
    BOOL_LIT = auto()
    NONE_LIT = auto()

    # Identifiers & Keywords
    IDENT = auto()
    LET = auto()
    CONST = auto()
    FN = auto()
    RETURN = auto()
    USE = auto()
    TOOL = auto()
    PY = auto()
    AS = auto()
    AGENT = auto()
    GOAL = auto()
    PLAN = auto()
    POLICY = auto()
    OBSERVE = auto()
    ACT = auto()
    APPROVE = auto()
    BEFORE = auto()
    REMEMBER = auto()
    FORGET = auto()
    RECALL = auto()
    FROM = auto()
    IN = auto()
    TO = auto()
    EVAL = auto()
    GUARD = auto()
    RETRY = auto()
    WITH = auto()
    CATCH = auto()
    BACKOFF = auto()
    EXPONENTIAL = auto()
    LOG = auto()
    FAIL = auto()
    SAVE = auto()
    MEMORY = auto()
    TRACE = auto()
    IMPORT = auto()
    IF = auto()
    ELSE = auto()
    FOR = auto()
    WHILE = auto()
    BREAK = auto()
    CONTINUE = auto()

    # Type Keywords
    STR = auto()
    INT_TYPE = auto()
    FLOAT_TYPE = auto()
    BOOL_TYPE = auto()
    BYTES_TYPE = auto()
    ANY_TYPE = auto()
    LIST_TYPE = auto()
    DICT_TYPE = auto()
    TUPLE_TYPE = auto()

    # Operators
    PLUS = auto()  # +
    MINUS = auto()  # -
    STAR = auto()  # *
    SLASH = auto()  # /
    PERCENT = auto()  # %
    STAR_STAR = auto()  # **
    EQ = auto()  # =
    EQ_EQ = auto()  # ==
    BANG_EQ = auto()  # !=
    LT = auto()  # <
    LT_EQ = auto()  # <=
    GT = auto()  # >
    GT_EQ = auto()  # >=
    AND = auto()  # and
    OR = auto()  # or
    NOT = auto()  # not
    DOT = auto()  # .
    COLON = auto()  # :
    COMMA = auto()  # ,
    ARROW = auto()  # ->
    PIPE = auto()  # |

    # Delimiters
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    LBRACE = auto()  # {
    RBRACE = auto()  # }
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]

    # Special
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()
    COMMENT = auto()


@dataclass(frozen=True)
class Span:
    """Byte-precise source location. Survives round-trips through JSON."""

    file: str
    line: int  # 1-indexed
    col: int  # 1-indexed
    offset: int  # byte offset from file start
    length: int  # byte length of token


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str  # raw source text
    span: Span

    def __repr__(self) -> str:
        return (
            f"Token({self.type.name}, {self.value!r}, {self.span.line}:{self.span.col})"
        )
