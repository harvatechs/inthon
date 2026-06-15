from __future__ import annotations
import time
from dataclasses import dataclass, field
from .errors import SandboxViolationError

@dataclass
class Sandbox:
    max_runtime_sec: float = 300.0
    max_cost_usd: float = 1.0
    max_memory_writes: int = 10_000
    max_tool_calls: int = 200
    _start_time: float = field(default_factory=time.time, init=False)
    _tool_call_count: int = field(default=0, init=False)
    _cost_accumulated: float = field(default=0.0, init=False)

    def check_budget(self) -> None:
        elapsed = time.time() - self._start_time
        if elapsed > self.max_runtime_sec:
            raise SandboxViolationError(
                f"INTHON_RUNTIME_TIMEOUT: Execution exceeded {self.max_runtime_sec}s timeout limit"
            )
        if self._cost_accumulated > self.max_cost_usd:
            raise SandboxViolationError(
                f"INTHON_RUNTIME_COST: Execution exceeded ${self.max_cost_usd:.4f} budget limit"
            )
        if self._tool_call_count >= self.max_tool_calls:
            raise SandboxViolationError(
                f"INTHON_RUNTIME_TOOLS: Tool call limit of {self.max_tool_calls} exceeded"
            )

    def record_tool_call(self, cost_usd: float) -> None:
        self._tool_call_count += 1
        self._cost_accumulated += cost_usd
        self.check_budget()
