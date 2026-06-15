"""
inthon.vm.frame — Execution frame for the INTHON stack machine.

Each function call, agent block, or top-level program gets its own Frame.
The VM maintains a call stack of Frames; returning from a function pops the
frame and resumes the parent.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .code_object import CodeObject


@dataclass
class RetryState:
    """Tracks retry-loop progress within a frame."""

    count: int
    backoff: str
    attempt: int = 0
    last_error: Exception | None = None


@dataclass
class Frame:
    """
    Represents one activation record on the call stack.

    Attributes:
        code:       The CodeObject being executed.
        ip:         Instruction pointer (index into code.instructions).
        stack:      Operand stack (list used as LIFO — append/pop).
        locals:     Local variable name → value mapping.
        parent:     Enclosing Frame (None for the top-level module frame).
        return_val: Set when RETURN_VALUE is executed; signals frame completion.
        retry_stack: Stack of active RetryState blocks (supports nested retry).
    """

    code: CodeObject
    ip: int = 0
    stack: list[Any] = field(default_factory=list)
    locals: dict[str, Any] = field(default_factory=dict)
    parent: "Frame | None" = None
    return_val: Any = None
    finished: bool = False
    retry_stack: list[RetryState] = field(default_factory=list)

    # ── Stack helpers ────────────────────────────────────────────────────── #

    def push(self, value: Any) -> None:
        self.stack.append(value)

    def pop(self) -> Any:
        return self.stack.pop()

    def peek(self) -> Any:
        return self.stack[-1]

    def pop_n(self, n: int) -> list[Any]:
        """Pop n items from the stack and return them in push order (bottom first)."""
        if n == 0:
            return []
        items = self.stack[-n:]
        del self.stack[-n:]
        return items

    # ── Local variable helpers ────────────────────────────────────────────── #

    def set_local(self, name: str, value: Any) -> None:
        self.locals[name] = value

    def get_local(self, name: str) -> Any:
        return self.locals[name]

    def has_local(self, name: str) -> bool:
        return name in self.locals

    def __repr__(self) -> str:
        return (
            f"<Frame '{self.code.name}' ip={self.ip} "
            f"stack_depth={len(self.stack)} "
            f"locals={list(self.locals.keys())}>"
        )
