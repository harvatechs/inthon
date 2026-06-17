from __future__ import annotations
from pathlib import Path

# Cache of filename -> raw source code string to enable diagnostics on in-memory strings
SOURCE_CACHE: dict[str, str] = {}


def format_source_diagnostic(
    filename: str | None,
    line: int,
    col: int,
    message: str,
    severity: str = "error",
) -> str:
    """
    Format a compiler/runtime error with a Rust-style visual caret pointer
    and source code context.
    """
    if not filename:
        filename = "<stdin>"

    target_line = None
    # 1. Check in-memory source cache
    if filename in SOURCE_CACHE:
        lines = SOURCE_CACHE[filename].splitlines()
        if 0 < line <= len(lines):
            target_line = lines[line - 1]

    # 2. Check filesystem
    if target_line is None and filename != "<stdin>":
        try:
            p = Path(filename)
            if p.is_file():
                lines = p.read_text(encoding="utf-8").splitlines()
                if 0 < line <= len(lines):
                    target_line = lines[line - 1]
        except Exception:
            pass

    # Clean message from prefixes if needed
    clean_msg = message
    if ":" in message:
        parts = message.split(":", 1)
        if parts[0].strip().startswith("INTHON_"):
            clean_msg = parts[1].strip()

    code_prefix = message.split(":", 1)[0].strip() if ":" in message else "INTHON_ERROR"
    if not code_prefix.startswith("INTHON_"):
        code_prefix = f"INTHON_{severity.upper()}"

    if target_line is not None:
        # Build the caret pointer under the exact column
        # Handle tab offsets if any
        prefix_space = ""
        for char in target_line[: col - 1]:
            if char == "\t":
                prefix_space += "\t"
            else:
                prefix_space += " "

        pointer = prefix_space + "^"
        line_prefix = f" {line} | "
        indent = " " * len(line_prefix)

        return (
            f"\n{code_prefix}:\n{clean_msg}\n"
            f"  --> {filename}:{line}:{col}\n"
            f"{indent}\n"
            f"{line_prefix}{target_line}\n"
            f"{indent}{pointer}\n"
        )

    # Fallback formatting if source code lines cannot be read
    return f"\n{code_prefix}:\n{clean_msg}\n  File: {filename}\n  Line: {line}, Column: {col}"
