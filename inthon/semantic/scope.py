"""Static scope tree for the semantic analyzer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..errors import Span
from ..errors import SemanticError as SemanticError


@dataclass
class Symbol:
    name: str
    kind: str            # let | const | fn | agent | param | builtin | tool | py | loop | catch
    span: Optional[Span] = None
    type_annotation: object = None


class Scope:
    __slots__ = ("parent", "kind", "symbols", "children", "label")

    def __init__(self, parent: Optional["Scope"] = None, kind: str = "block", label: str = ""):
        self.parent = parent
        self.kind = kind
        self.label = label
        self.symbols: dict[str, Symbol] = {}
        self.children: list[Scope] = []

    def declare(self, symbol: Symbol) -> Optional[Symbol]:
        """Declare; returns the previous symbol if this is a duplicate."""
        prev = self.symbols.get(symbol.name)
        self.symbols[symbol.name] = symbol
        return prev

    def lookup(self, name: str) -> Optional[Symbol]:
        scope: Optional[Scope] = self
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None

    def lookup_here(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name)

    def all_names(self) -> list[str]:
        out = []
        scope: Optional[Scope] = self
        while scope is not None:
            out.extend(scope.symbols.keys())
            scope = scope.parent
        return out

    def enclosing(self, kind: str) -> Optional["Scope"]:
        scope: Optional[Scope] = self
        while scope is not None:
            if scope.kind == kind:
                return scope
            scope = scope.parent
        return None


ScopeChain = Scope

