"""Human-readable AST printer (used by `inthon ast`)."""

from __future__ import annotations

import dataclasses
from typing import Any

from . import nodes


def format_ast(node: nodes.Node, *, color: bool = False) -> str:
    """Render an AST as an indented tree."""
    lines: list[str] = []
    _render(node, lines, prefix="", is_last=True, is_root=True)
    return "\n".join(lines)


def _label(node: Any) -> str:
    if not isinstance(node, nodes.Node):
        return repr(node)
    name = type(node).__name__
    extras = []
    for f in dataclasses.fields(node):
        if f.name == "span":
            continue
        value = getattr(node, f.name)
        if isinstance(value, nodes.Node):
            continue
        if isinstance(value, (list, tuple)) and any(
            isinstance(x, nodes.Node) or (isinstance(x, tuple) and any(isinstance(s, nodes.Node) for s in x))
            for x in value
        ):
            continue
        if value is None or value == () or value == "":
            continue
        extras.append(f"{f.name}={value!r}")
    suffix = (" " + " ".join(extras)) if extras else ""
    span = f" [{node.span.line}:{node.span.col}]" if getattr(node, "span", None) else ""
    return f"{name}{suffix}{span}"


def _children(node: nodes.Node) -> list:
    out = []
    for f in dataclasses.fields(node):
        if f.name == "span":
            continue
        value = getattr(node, f.name)
        if isinstance(value, nodes.Node):
            out.append((f.name, value))
        elif isinstance(value, (list, tuple)) and value:
            items = []
            for item in value:
                if isinstance(item, nodes.Node):
                    items.append(item)
                elif isinstance(item, tuple):
                    for sub in item:
                        if isinstance(sub, nodes.Node):
                            items.append(sub)
            if items:
                out.append((f.name, items))
    return out


def _render(node: Any, lines: list[str], prefix: str, is_last: bool, is_root: bool = False) -> None:
    connector = "" if is_root else ("└── " if is_last else "├── ")
    lines.append(prefix + connector + _label(node))
    if isinstance(node, nodes.Node):
        children = _children(node)
        child_prefix = prefix + ("" if is_root else ("    " if is_last else "│   "))
        flat: list[tuple[str, Any]] = []
        for name, value in children:
            if isinstance(value, list):
                for item in value:
                    flat.append((name, item))
            else:
                flat.append((name, value))
        for i, (_, child) in enumerate(flat):
            _render(child, lines, child_prefix, i == len(flat) - 1)
