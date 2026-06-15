from __future__ import annotations
from typing import Any, TypeVar

T = TypeVar("T")

class ASTVisitor:
    """
    Generic double-dispatch visitor.
    Subclasses override visit_* methods. Unhandled nodes
    fall through to generic_visit(). The default generic_visit
    walks all child fields and returns None.
    """
    def visit(self, node: Any) -> Any:
        if node is None:
            return None
        method_name = f"visit_{type(node).__name__}"
        method = getattr(self, method_name, self.generic_visit)
        return method(node)

    def generic_visit(self, node: Any) -> Any:
        for field_val in vars(node).values():
            if isinstance(field_val, tuple):
                for child in field_val:
                    if hasattr(child, "__dataclass_fields__"):
                        self.visit(child)
            elif hasattr(field_val, "__dataclass_fields__"):
                self.visit(field_val)
        return None
