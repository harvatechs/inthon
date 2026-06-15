from __future__ import annotations
import json
from dataclasses import is_dataclass
from typing import Any
from .visitor import ASTVisitor
from ..lexer.tokens import Span


class ASTPrinter(ASTVisitor):
    def __init__(self) -> None:
        self.indent_level = 0

    def print_node(self, node: Any) -> str:
        if node is None:
            return "None"
        if isinstance(node, (int, float, str, bool)):
            return repr(node)
        if isinstance(node, tuple):
            if not node:
                return "()"
            parts = []
            for item in node:
                parts.append(self.print_node(item))
            return "(" + ", ".join(parts) + ")"

        if is_dataclass(node):
            name = type(node).__name__
            fields = []
            for f_name, f_val in vars(node).items():
                if f_name == "span":
                    continue
                fields.append(f"{f_name}={self.print_node(f_val)}")
            return f"{name}({', '.join(fields)})"

        return str(node)


def print_ast(node: Any) -> None:
    printer = ASTPrinter()
    print(printer.print_node(node))


def ast_to_json(node: Any) -> str:
    def _default(obj: Any) -> Any:
        if isinstance(obj, Span):
            return {
                "file": obj.file,
                "line": obj.line,
                "col": obj.col,
                "offset": obj.offset,
                "length": obj.length,
            }
        if is_dataclass(obj):
            d = {k: v for k, v in vars(obj).items() if k != "span"}
            d["node_type"] = type(obj).__name__
            return d
        if isinstance(obj, set):
            return list(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(node, default=_default, indent=2)
