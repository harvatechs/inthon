"""INTHON parser — drives the canonical grammar.lark (Lark LALR).

Responsibilities:
  * load grammar.lark once (cached) with lexer="basic" (reserved keywords)
  * convert Lark errors into INTHON_PARSE_* diagnostics with expected-token
    lists, did-you-mean hints, and source carets
  * expose parse() / parse_file() / parse_expression_fragment()
"""

from __future__ import annotations

import difflib
import functools
from pathlib import Path
from typing import Optional

from lark import Lark
from lark.exceptions import (
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedInput,
    UnexpectedToken,
    VisitError,
)

from ..ast import nodes
from ..errors import InthonError, InthonParseError, Span
from ..errors import ParseError as ParseError
from ..lexer.keywords import KEYWORDS, NOT_KEYWORDS
from .transformer import InthonTransformer

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"


@functools.lru_cache(maxsize=1)
def get_parser() -> Lark:
    return Lark.open(
        str(_GRAMMAR_PATH),
        parser="lalr",
        lexer="basic",
        start=["program", "expr_fragment"],
        propagate_positions=True,
        maybe_placeholders=False,
    )


def _line_text(source: str, line: int) -> Optional[str]:
    lines = source.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1]
    return None


def _friendly_terminal(parser: Lark, term_name: str) -> str:
    """Map an internal terminal name to a human-readable display string."""
    display = {
        "CNAME": "an identifier",
        "INT": "an integer",
        "FLOAT": "a number",
        "STRING": "a string",
        "BOOL_LIT": "true or false",
        "NONE_LIT": "none",
        "COMPARISON_OP": "a comparison operator",
        "ADD_OP": "'+' or '-'",
        "MUL_OP": "'*', '/' or '%'",
        "DOT": "'.'",
        "COMMA": "','",
        "COLON": "':'",
        "LPAREN": "'('",
        "RPAREN": "')'",
        "LBRACE": "'{'",
        "RBRACE": "'}'",
        "LBRACKET": "'['",
        "RBRACKET": "']'",
        "EQUAL": "'='",
    }
    if term_name in display:
        return display[term_name]
    # Anonymous terminals from string literals: recover the literal text.
    try:
        term = parser._terminals_dict.get(term_name)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive
        term = None
    if term is not None:
        pattern = getattr(term, "pattern", None)
        value = getattr(pattern, "value", None)
        if value and isinstance(value, str) and value.isprintable():
            return f"'{value}'"
    lowered = term_name.lower()
    if lowered in KEYWORDS:
        return f"'{lowered}'"
    return f"'{term_name}'"


def _did_you_mean(word: str) -> Optional[str]:
    if word in NOT_KEYWORDS:
        suggestion = NOT_KEYWORDS[word]
        return f"'{word}' is not an INTHON keyword — use {suggestion}."
    close = difflib.get_close_matches(word, KEYWORDS.keys(), n=1, cutoff=0.75)
    if close:
        return f"Did you mean '{close[0]}'?"
    return None


def parse(source: str, filename: str = "<stdin>") -> nodes.Program:
    """Parse INTHON source into a Program AST."""
    from .semi import insert_semicolons

    source = insert_semicolons(source, filename)
    parser = get_parser()
    try:
        tree = parser.parse(source, start="program")
    except UnexpectedToken as exc:
        raise _convert_token_error(exc, source, filename, parser) from exc
    except UnexpectedCharacters as exc:
        raise _convert_char_error(exc, source, filename, parser) from exc
    except UnexpectedEOF as exc:
        raise _convert_eof_error(exc, source, filename, parser) from exc
    except UnexpectedInput as exc:  # pragma: no cover - safety net
        span = Span(
            filename, getattr(exc, "line", 1) or 1, getattr(exc, "column", 1) or 1
        )
        raise InthonParseError(
            "Unexpected input", span=span, source_line=_line_text(source, span.line)
        ) from exc
    transformer = InthonTransformer(filename=filename, source=source)
    try:
        program = transformer.transform(tree)
    except VisitError as exc:
        original = getattr(exc, "orig_exc", exc)
        if isinstance(original, InthonError):
            raise original from exc
        raise  # pragma: no cover - defensive
    return program


def parse_file(path: str) -> nodes.Program:
    src = Path(path).read_text(encoding="utf-8")
    return parse(src, filename=path)


def parse_expression_fragment(src: str, filename: str, span: Span) -> nodes.Expression:
    """Parse a standalone expression (used for string interpolation)."""
    parser = get_parser()
    try:
        tree = parser.parse(src, start="expr_fragment")
    except UnexpectedInput as exc:
        raise InthonParseError(f"Cannot parse expression {src!r}", span=span) from exc
    transformer = InthonTransformer(filename=filename)
    try:
        result = transformer.transform(tree)
    except VisitError as exc:
        original = getattr(exc, "orig_exc", exc)
        if isinstance(original, InthonError):
            raise original from exc
        raise  # pragma: no cover
    return result


def _convert_token_error(
    exc: UnexpectedToken, source: str, filename: str, parser: Lark
) -> InthonParseError:
    token = exc.token
    value = str(token)
    line = getattr(exc, "line", None) or getattr(token, "line", 1) or 1
    col = getattr(exc, "column", None) or getattr(token, "column", 1) or 1
    span = Span(filename, line, col, length=max(1, len(value)))

    if getattr(token, "type", "") == "$END":
        message = "Unexpected end of file"
    else:
        message = f"Unexpected token {value!r}"

    expected = sorted({_friendly_terminal(parser, t) for t in (exc.expected or set())})
    hint = None
    if value:
        hint = _did_you_mean(value)
    if hint is None and expected:
        show = expected[:6]
        hint = "Expected " + ", ".join(show)
        if len(expected) > 6:
            hint += f" (+{len(expected) - 6} more)"
    return InthonParseError(
        message, span=span, hint=hint, source_line=_line_text(source, line)
    )


def _convert_char_error(
    exc: UnexpectedCharacters, source: str, filename: str, parser: Lark
) -> InthonParseError:
    line = exc.line or 1
    col = exc.column or 1
    span = Span(filename, line, col)
    lines = source.splitlines()
    char = ""
    if 1 <= line <= len(lines) and col <= len(lines[line - 1]):
        char = lines[line - 1][col - 1]
    message = f"Unexpected character {char!r}" if char else "Unexpected character"
    hint = None
    if char in "()[]{}":
        hint = "Check for unbalanced delimiters."
    elif char == "=":
        hint = "Use '==' to compare, '=' to assign."
    return InthonParseError(
        message, span=span, hint=hint, source_line=_line_text(source, line)
    )


def _convert_eof_error(
    exc: UnexpectedEOF, source: str, filename: str, parser: Lark
) -> InthonParseError:
    lines = source.splitlines()
    line = len(lines) if lines else 1
    col = len(lines[-1]) + 1 if lines else 1
    span = Span(filename, line, col)
    expected = sorted({_friendly_terminal(parser, t) for t in (exc.expected or set())})
    hint = "The file ended unexpectedly."
    if expected:
        hint += " Expected " + ", ".join(expected[:6]) + "."
    if "'}'" in expected:
        hint += " Did you forget a closing brace?"
    return InthonParseError(
        "Unexpected end of file",
        span=span,
        hint=hint,
        source_line=lines[-1] if lines else None,
    )
