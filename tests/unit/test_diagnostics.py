from __future__ import annotations
from inthon.errors_diagnostic import SOURCE_CACHE, format_source_diagnostic


def test_format_source_diagnostic_with_cache() -> None:
    filename = "test_memory.inth"
    code = "let x: int = 10\nlet y = x + z\nlet w = 4"
    SOURCE_CACHE[filename] = code

    # Test error formatting on line 2, column 13 (z)
    diag = format_source_diagnostic(
        filename=filename,
        line=2,
        col=13,
        message="INTHON_SEM_002: Undefined variable 'z'",
    )

    assert "INTHON_SEM_002" in diag
    assert "Undefined variable 'z'" in diag
    assert "--> test_memory.inth:2:13" in diag
    assert "2 | let y = x + z" in diag
    assert "            ^" in diag


def test_format_source_diagnostic_fallback() -> None:
    # Test fallback if file is not in cache or filesystem
    diag = format_source_diagnostic(
        filename="nonexistent.inth",
        line=10,
        col=5,
        message="INTHON_PARSE_001: Expected token",
    )

    assert "INTHON_PARSE_001" in diag
    assert "Expected token" in diag
    assert "File: nonexistent.inth" in diag
    assert "Line: 10, Column: 5" in diag
