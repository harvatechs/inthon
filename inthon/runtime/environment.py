"""Lexical environments with const tracking and closure support."""

from __future__ import annotations

import difflib
from typing import Optional

from ..errors import InthonConstError, InthonDuplicateError, InthonNameError, Span
from .values import InthonValue


class Environment:
    """A scope: a name→value map with a parent chain (closures capture it)."""

    __slots__ = ("vars", "consts", "parent", "kind", "label")

    def __init__(
        self,
        parent: Optional["Environment"] = None,
        kind: str = "block",
        label: str = "",
    ):
        self.vars: dict[str, InthonValue] = {}
        self.consts: set[str] = set()
        self.parent = parent
        self.kind = kind
        self.label = label

    def names(self) -> list[str]:
        out = []
        env: Optional[Environment] = self
        while env is not None:
            out.extend(env.vars.keys())
            env = env.parent
        return out

    def is_defined_here(self, name: str) -> bool:
        if name in self.vars:
            if type(self.vars[name]).__name__ == "InthonBuiltin":
                return False
            return True
        return False

    def is_defined(self, name: str) -> bool:
        env: Optional[Environment] = self
        while env is not None:
            if name in env.vars:
                return True
            env = env.parent
        return False

    def define(
        self,
        name: str,
        value: InthonValue,
        mutable: bool = True,
        span: Optional[Span] = None,
    ):
        if name in self.vars:
            if type(self.vars[name]).__name__ == "InthonBuiltin":
                # Shadowing builtin is allowed
                pass
            else:
                raise InthonDuplicateError(
                    f"Name '{name}' is already defined in this scope",
                    span=span,
                    hint="Rename the new binding, or assign without 'let'/'const' to update it.",
                )
        self.vars[name] = value
        if not mutable:
            self.consts.add(name)
        else:
            self.consts.discard(name)

    def assign(self, name: str, value: InthonValue, span: Optional[Span] = None):
        env: Optional[Environment] = self
        while env is not None:
            if name in env.vars:
                if name in env.consts:
                    raise InthonConstError(
                        f"Cannot reassign const '{name}'",
                        span=span,
                        hint="Declare it with 'let' if it must change, or create a new binding.",
                    )
                env.vars[name] = value
                return
            env = env.parent
        raise self._undefined(name, span)

    def lookup(self, name: str, span: Optional[Span] = None) -> InthonValue:
        env: Optional[Environment] = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise self._undefined(name, span)

    def set_local(self, name: str, value: InthonValue):
        """Define-or-update in this scope only (loop variables, catch bindings)."""
        self.vars[name] = value
        self.consts.discard(name)

    def _undefined(self, name: str, span: Optional[Span]) -> InthonNameError:
        hint = None
        candidates = [n for n in self.names() if not n.startswith("__")]
        close = difflib.get_close_matches(name, candidates, n=1, cutoff=0.7)
        if close:
            hint = f"Did you mean '{close[0]}'?"
        else:
            hint = "Declare it first with 'let' or 'const', or import it with 'use'."
        return InthonNameError(f"Undefined name '{name}'", span=span, hint=hint)
