"""Sandbox: resource budget enforcement (spec §sandbox, SB-11).

Every side-effecting operation checks the Sandbox before it runs.  The
Sandbox reads its limits from the *currently active* policy frame, so
nested agents get the intersection of their ancestors' budgets.
"""

from __future__ import annotations

import time
from typing import Optional

from ..errors import (
    BudgetExhaustedError,
    InthonIterationLimit,
    InthonRecursionLimit,
    Span,
)


class Sandbox:
    def __init__(self, ctx):
        self.ctx = ctx
        self.tool_calls = 0
        self.py_calls = 0
        self.llm_calls = 0
        self.cost_usd = 0.0
        self.iterations = 0
        self.call_depth = 0
        self.started = time.monotonic()
        # Compatibility properties for old VM
        self.max_tool_calls = 25
        self.max_runtime_sec = 300.0
        self.max_cost_usd = 1.0

    def check_budget(self) -> None:
        pass

    def record_tool_call(self, cost: float) -> None:
        pass

    # -- tools -----------------------------------------------------------------
    def before_tool_call(self, spec, span: Optional[Span] = None):
        policy = self.ctx.policy.current
        if self.tool_calls + 1 > policy.max_tool_calls:
            raise BudgetExhaustedError(
                f"Tool call limit of {policy.max_tool_calls} exceeded",
                span=span,
                hint="Raise max_tool_calls in the policy block, or call fewer tools.",
            )
        if self.cost_usd + spec.cost_usd > policy.max_cost_usd:
            raise BudgetExhaustedError(
                f"Cost budget exceeded ${policy.max_cost_usd} (already spent ${self.cost_usd:.4f})",
                span=span,
                hint="Raise max_cost_usd in the policy block.",
            )
        if spec.path.startswith("llm.") and self.llm_calls + 1 > policy.max_llm_calls:
            raise BudgetExhaustedError(
                f"LLM call budget exhausted (max_llm_calls={policy.max_llm_calls})",
                span=span,
            )

    def after_tool_call(self, spec):
        self.tool_calls += 1
        self.cost_usd = round(self.cost_usd + spec.cost_usd, 10)
        if spec.path.startswith("llm."):
            self.llm_calls += 1

    # -- python calls ---------------------------------------------------------------
    def before_py_call(self, path: str, span: Optional[Span] = None):
        policy = self.ctx.policy.current
        if self.py_calls + 1 > policy.max_py_calls:
            raise BudgetExhaustedError(
                f"Python call budget exhausted (max_py_calls={policy.max_py_calls})",
                span=span,
            )

    def after_py_call(self, path: str):
        self.py_calls += 1

    # -- loops ---------------------------------------------------------------------------
    def tick(self, span: Optional[Span] = None):
        """Called at every loop back-edge: iteration + wall-clock budgets."""
        self.iterations += 1
        policy = self.ctx.policy.current
        if self.iterations > policy.max_iterations:
            raise InthonIterationLimit(
                f"Iteration limit exceeded (max_iterations={policy.max_iterations})",
                span=span,
                hint="This usually means an infinite loop; check your loop condition.",
            )
        elapsed = time.monotonic() - self.started
        if elapsed > policy.max_runtime_sec:
            raise BudgetExhaustedError(
                f"Runtime budget exhausted (max_runtime_sec={policy.max_runtime_sec}s)",
                span=span,
            )

    # -- calls ------------------------------------------------------------------------------
    def enter_call(self, name: str, span: Optional[Span] = None):
        self.call_depth += 1
        policy = self.ctx.policy.current
        if self.call_depth > policy.max_recursion:
            self.call_depth -= 1
            raise InthonRecursionLimit(
                f"Recursion limit exceeded (max_recursion={policy.max_recursion})",
                span=span,
                hint="Add a base case, or raise max_recursion in the policy block.",
            )

    def exit_call(self):
        self.call_depth = max(0, self.call_depth - 1)
