from __future__ import annotations
from typing import Any
from ..lexer.tokens import Span


class IntHonRuntimeError(Exception):
    def __init__(self, message: str, span: Span | None = None) -> None:
        super().__init__(message)
        self.span = span

    def __str__(self) -> str:
        code = "INTHON_RUNTIME_GENERIC"
        for word in self.args[0].split():
            if (
                word.startswith("INTHON_RUNTIME_")
                or word.startswith("INTHON_PYBRIDGE_")
                or word.startswith("INTHON_POLICY_")
                or word.startswith("INTHON_TOOL_")
            ):
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


class ToolCallError(IntHonRuntimeError):
    pass


class PolicyViolationError(IntHonRuntimeError):
    pass


class ApprovalRequiredError(IntHonRuntimeError):
    pass


class ApprovalDeniedError(IntHonRuntimeError):
    pass


class SandboxViolationError(IntHonRuntimeError):
    pass


class ReturnSignal(Exception):
    """Control flow exception to return values from function scopes."""

    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value
