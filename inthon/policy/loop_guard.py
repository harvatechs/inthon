"""
inthon.policy.loop_guard — Metacognitive loop protection for INTHON agents.

Tracks tool calls and execution jump patterns to prevent infinite execution loops and cost runaways.
"""

from __future__ import annotations
from typing import Any
from ..runtime.errors import PolicyViolationError

class LoopDetectedError(PolicyViolationError):
    """Exception raised when an execution loop is detected."""
    pass


class LoopGuard:
    """
    Protects against VM infinite loops and repeating tool execution chains.
    """

    def __init__(self, max_tool_repetitions: int = 3, max_vm_iterations: int = 1000) -> None:
        self.max_tool_repetitions = max_tool_repetitions
        self.max_vm_iterations = max_vm_iterations

        # History of tool call signatures: (tool_path, args_repr, kwargs_repr)
        self._tool_history: list[tuple[str, str, str]] = []

        # Count of backward jumps by target IP
        self._backward_jumps: dict[int, int] = {}

    def record_tool_call(self, tool_path: str, args: list[Any], kwargs: dict[str, Any]) -> None:
        """
        Record a tool call signature and analyze for loops or repeating cycles.
        """
        sig = (tool_path, repr(args), repr(kwargs))
        self._tool_history.append(sig)

        # 1. Direct repetition check
        consecutive_count = 0
        for entry in reversed(self._tool_history):
            if entry == sig:
                consecutive_count += 1
            else:
                break

        if consecutive_count > self.max_tool_repetitions:
            raise LoopDetectedError(
                f"INTHON_LOOP_001: Tool loop detected. Repeatedly calling '{tool_path}' "
                f"with same arguments ({args}, {kwargs})."
            )

        # 2. Cycle detection (e.g., A -> B -> A -> B)
        # Check patterns of length 2, 3, 4
        for pattern_len in (2, 3, 4):
            if len(self._tool_history) >= pattern_len * 3:
                # Extract the last 3 repetitions of pattern
                p1 = self._tool_history[-pattern_len:]
                p2 = self._tool_history[-2*pattern_len:-pattern_len]
                p3 = self._tool_history[-3*pattern_len:-2*pattern_len]
                if p1 == p2 == p3:
                    cycle_str = " -> ".join(item[0] for item in p1)
                    raise LoopDetectedError(
                        f"INTHON_LOOP_002: Multi-tool cycle loop detected: {cycle_str}"
                    )

    def record_backward_jump(self, target_ip: int) -> None:
        """
        Record a backward jump to detect infinite CPU loops.
        """
        self._backward_jumps[target_ip] = self._backward_jumps.get(target_ip, 0) + 1
        if self._backward_jumps[target_ip] > self.max_vm_iterations:
            raise LoopDetectedError(
                f"INTHON_LOOP_003: Infinite control flow loop detected at instruction pointer {target_ip}."
            )

    def reset(self) -> None:
        """Reset history counters."""
        self._tool_history.clear()
        self._backward_jumps.clear()
