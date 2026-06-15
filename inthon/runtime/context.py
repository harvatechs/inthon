from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from ..tools.registry import ToolRegistry
from ..policy.engine import PolicyEngine
from ..memory.store import MemoryStore
from .trace import TraceLogger
from .sandbox import Sandbox

@dataclass
class ExecutionContext:
    # Identity
    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    filename: str = "<stdin>"
    started_at: float = field(default_factory=time.time)
    # Variable storage — stack of dicts (innermost last)
    _scope_stack: list[dict[str, Any]] = field(default_factory=lambda: [{}])
    # Subsystems
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    policy: PolicyEngine = field(default_factory=PolicyEngine)
    memory: MemoryStore = field(default_factory=lambda: MemoryStore.in_memory())
    tracer: TraceLogger = field(default_factory=TraceLogger)
    sandbox: Sandbox = field(default_factory=Sandbox)
    # Execution statistics
    tool_call_count: int = 0
    py_call_count: int = 0
    cost_usd: float = 0.0
    errors: list[dict] = field(default_factory=list)
    # Agent state (populated when inside an agent block)
    current_agent: str | None = None
    agent_goal: str | None = None

    # ── Scope helpers ────────────────────────────────────────────────────── #
    def push_scope(self) -> None:
        self._scope_stack.append({})

    def pop_scope(self) -> None:
        if len(self._scope_stack) > 1:
            self._scope_stack.pop()

    def set_var(self, name: str, value: Any) -> None:
        self._scope_stack[-1][name] = value

    def assign_var(self, name: str, value: Any) -> None:
        for scope in reversed(self._scope_stack):
            if name in scope:
                scope[name] = value
                return
        self._scope_stack[-1][name] = value

    def get_var(self, name: str) -> Any:
        for scope in reversed(self._scope_stack):
            if name in scope:
                return scope[name]
        raise RuntimeError(f"INTHON_RUNTIME_001: Undefined variable '{name}'")

    def has_var(self, name: str) -> bool:
        return any(name in s for s in self._scope_stack)

    # ── Finalisation ─────────────────────────────────────────────────────── #
    def to_trace_summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "filename": self.filename,
            "started_at": self.started_at,
            "ended_at": time.time(),
            "duration_ms": round((time.time() - self.started_at) * 1000, 2),
            "tool_calls": self.tracer.tool_events(),
            "py_calls": self.tracer.py_events(),
            "errors": self.errors,
            "cost": {"usd": round(self.cost_usd, 6)},
        }
