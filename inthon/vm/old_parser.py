from __future__ import annotations
from pathlib import Path
from typing import Any
import lark
from .old_nodes import Program
from .old_transformer import InthonTransformer
from ..errors_diagnostic import SOURCE_CACHE, format_source_diagnostic

_GRAMMAR_PATH = Path(__file__).parent / "old_grammar.lark"
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
        return format_source_diagnostic(
            self.filename,
            self.line,
            self.col,
            f"INTHON_PARSE_001: Expected token/statement. {self.args[0]}",
        )


def parse(source: str, filename: str = "<stdin>") -> Program:
    """Parse INTHON source text into an AST. Raises ParseError on failure."""
    # Strip carriage returns to ensure Lark parser gets clean newlines
    source = source.replace("\r\n", "\n")

    # Extract code from <inthon>...</inthon> or <inth>...</inth> tags
    import re

    xml_match = re.search(
        r"<(inthon|inth)>\s*(.*?)\s*</\1>", source, re.DOTALL | re.IGNORECASE
    )
    if xml_match:
        source = xml_match.group(2)
    else:
        # Extract code from markdown blocks: ```inthon ... ```
        md_match = re.search(
            r"```(?:inthon|inth)?\s*(.*?)\s*```", source, re.DOTALL | re.IGNORECASE
        )
        if md_match:
            source = md_match.group(1)

    # Cache the processed source text for diagnostics formatting
    SOURCE_CACHE[filename] = source

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
        )


def _format_lark_error(exc: lark.exceptions.UnexpectedInput) -> str:
    expected: set[Any] = getattr(exc, "expected", set())
    readable = ", ".join(sorted(str(e) for e in expected)[:5])
    return f"Unexpected token. Expected one of: {readable}"
