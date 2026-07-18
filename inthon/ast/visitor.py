"""AST visitor and transformer utilities (engine spec §5.2)."""

from __future__ import annotations

from typing import Any

from . import nodes


class NodeVisitor:
    """Depth-first visitor; define visit_<ClassName> methods in subclasses."""

    def visit(self, node: Any) -> Any:
        if node is None:
            return None
        # Walk MRO to find the first matching visit method
        method = None
        for cls in type(node).__mro__:
            if cls is object:
                break
            method_name = f"visit_{cls.__name__}"
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                break
        if method is None:
            method = self.generic_visit
        return method(node)

    def generic_visit(self, node: Any) -> Any:
        if isinstance(node, (list, tuple)):
            for item in node:
                self.visit(item)
            return None
        if not isinstance(node, nodes.Node):
            return None
        for field_name, value in _child_fields(node):
            self.visit(value)
        return None


def _child_fields(node: nodes.Node):
    import dataclasses

    for f in dataclasses.fields(node):
        if f.name == "span":
            continue
        value = getattr(node, f.name)
        if isinstance(value, nodes.Node):
            yield f.name, value
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, nodes.Node):
                    yield f.name, item
                elif isinstance(item, tuple):
                    for sub in item:
                        if isinstance(sub, nodes.Node):
                            yield f.name, sub


class NodeTransformer(NodeVisitor):
    """Visitor that may replace nodes; returns the (possibly new) tree."""

    def generic_visit(self, node: Any) -> Any:
        import dataclasses

        if isinstance(node, list):
            return [self.visit(x) for x in node]
        if isinstance(node, tuple):
            return tuple(self.visit(x) for x in node)
        if not isinstance(node, nodes.Node):
            return node
        updates = {}
        for f in dataclasses.fields(node):
            if f.name == "span":
                continue
            value = getattr(node, f.name)
            new_value = (
                self.visit(value)
                if isinstance(value, (nodes.Node, list, tuple))
                else value
            )
            if new_value is not value:
                updates[f.name] = new_value
        if updates:
            return dataclasses.replace(node, **updates)
        return node


ASTVisitor = NodeVisitor
