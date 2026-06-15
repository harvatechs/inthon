from __future__ import annotations
from pathlib import Path
import lark
from ..ast.nodes import Program
from .transformer import InthonTransformer

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"
_GRAMMAR_TEXT = _GRAMMAR_PATH.read_text(encoding="utf-8")
_PARSER = lark.Lark(
    _GRAMMAR_TEXT,
    parser="lalr",
    propagate_positions=True,
)

class ParseError(Exception):
    def __init__(self, message: str, line: int, col: int, filename: str) -> None:
        super().__init__(message)
        self.line = line
        self.col = col
        self.filename = filename

    def __str__(self) -> str:
        return (
            f"INTHON_PARSE_001:\n"
            f"Expected token/statement.\n"
            f"File: {self.filename}\n"
            f"Line: {self.line}\n"
            f"Column: {self.col}\n"
            f"Hint: check syntax around line {self.line}."
        )

def parse(source: str, filename: str = "<stdin>") -> Program:
    """Parse INTHON source text into an AST. Raises ParseError on failure."""
    # Strip carriage returns to ensure Lark parser gets clean newlines
    source = source.replace('\r\n', '\n')
    try:
        tree = _PARSER.parse(source)
        transformer = InthonTransformer(filename=filename)
        return transformer.transform(tree)
    except lark.exceptions.UnexpectedInput as exc:
        raise ParseError(
            message=_format_lark_error(exc),
            line=getattr(exc, "line", 0),
            col=getattr(exc, "column", 0),
            filename=filename,
        ) from exc

def _format_lark_error(exc: lark.exceptions.UnexpectedInput) -> str:
    expected = getattr(exc, "expected", set())
    readable = ", ".join(sorted(str(e) for e in expected)[:5])
    return f"Unexpected token. Expected one of: {readable}"
