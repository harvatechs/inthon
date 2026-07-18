from __future__ import annotations
from typing import Any

from ..errors import (
    InthonError as IntHonRuntimeError,
    PolicyViolationError as PolicyViolationError,
    ApprovalDeniedError as ApprovalDeniedError,
    BudgetExhaustedError as SandboxViolationError,
    ToolExecutionError as ToolCallError,
)

__all__ = [
    "IntHonRuntimeError",
    "PolicyViolationError",
    "ApprovalDeniedError",
    "SandboxViolationError",
    "ToolCallError",
    "ApprovalRequiredError",
    "ReturnSignal",
]

class ApprovalRequiredError(IntHonRuntimeError):
    pass

class ReturnSignal(Exception):
    """Control flow exception to return values from function scopes."""

    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value

