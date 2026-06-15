from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any
from ..lexer.tokens import Span

class SymbolKind(Enum):
    VARIABLE  = auto()
    CONSTANT  = auto()
    FUNCTION  = auto()
    AGENT     = auto()
    TOOL      = auto()
    PY_MODULE = auto()
    PARAM     = auto()

@dataclass
class Symbol:
    name: str
    kind: SymbolKind
    type_ann: Any | None = None  # TypeExpr | None
    mutable: bool = True
    source_span: Span | None = None

class SemanticError(Exception):
    def __init__(self, message: str, span: Span | None = None) -> None:
        super().__init__(message)
        self.span = span

    def __str__(self) -> str:
        # Standard INTHON_SEM_* error code format
        code = "INTHON_SEM_GENERIC"
        for word in self.args[0].split():
            if word.startswith("INTHON_SEM_"):
                code = word.rstrip(":")
                break
        msg = self.args[0].replace(code + ": ", "")
        
        span_info = ""
        if self.span:
            span_info = (
                f"  File: {self.span.file}\n"
                f"  Line: {self.span.line}, Column: {self.span.col}\n"
            )
            
        return f"\n{code}:\n{msg}\n{span_info}"

class ScopeChain:
    """
    Linked list of symbol tables.
    Lookup climbs the chain; define always writes to the innermost scope.
    """
    def __init__(self, parent: ScopeChain | None = None) -> None:
        self._table: dict[str, Symbol] = {}
        self._parent = parent

    def define(self, symbol: Symbol) -> None:
        if symbol.name in self._table:
            existing = self._table[symbol.name]
            span_str = f" line {existing.source_span.line}" if existing.source_span else " unknown line"
            raise SemanticError(
                f"INTHON_SEM_001: '{symbol.name}' is already declared in this scope "
                f"(first declared at{span_str})",
                symbol.source_span,
            )
        self._table[symbol.name] = symbol

    def lookup(self, name: str) -> Symbol | None:
        if name in self._table:
            return self._table[name]
        if self._parent is not None:
            return self._parent.lookup(name)
        return None

    def child(self) -> ScopeChain:
        return ScopeChain(parent=self)
