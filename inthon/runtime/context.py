"""ExecutionContext: the shared runtime state for both backends."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..errors import Span
from ..memory import InMemoryStore, SQLiteMemoryStore
from ..policy import ApprovalGate, Policy, PolicyEngine
from ..pybridge import SafeModuleImporter, default_importer
from ..tools import ToolRegistry, default_registry
from .environment import Environment
from .sandbox import Sandbox
from .trace import TraceLogger

_SESSION_NAMESPACES = {"session", "default", "scratch", "tmp"}


@dataclass
class RunOptions:
    """How to execute an INTHON program."""

    mock: bool = True                      # use mock tool implementations
    backend: str = "tree"                  # "tree" (interpreter) | "vm" (bytecode)
    trace: bool = True
    policy: Optional[Policy] = None        # base policy (host-level); program may narrow
    auto_approve: bool = False
    approval_handler: Optional[Callable] = None
    memory_dir: Optional[str] = None       # SQLite memory location (default: cwd/.inthon)
    registry: Optional[ToolRegistry] = None
    importer: Optional[SafeModuleImporter] = None
    strict_types: bool = True
    filename: str = "<stdin>"
    source: str = ""
    dry_run: bool = False
    write_out: Optional[Callable[[str], None]] = None   # print sink (test injectable)
    write_err: Optional[Callable[[str], None]] = None


class ExecutionContext:
    """Everything a run needs: scopes, tools, policy, memory, trace, sandbox."""

    def __init__(self, options: Optional[RunOptions] = None, **kwargs):
        self.options = options or RunOptions(**kwargs)
        self.filename = self.options.filename
        self.mock = self.options.mock
        self.dry_run = self.options.dry_run
        self.backend = self.options.backend
        self.started_at = time.time()

        self.tracer = TraceLogger(
            program=self.options.source,
            filename=self.filename,
            backend=self.backend,
            enabled=self.options.trace,
        )
        self.tools = self.options.registry or default_registry()
        self.importer = self.options.importer or default_importer()
        self.policy = PolicyEngine(
            base=self.options.policy or Policy(),
            tracer=self.tracer,
            ceiling=self.options.policy is not None,
        )
        self.approvals = ApprovalGate(
            handler=self.options.approval_handler,
            tracer=self.tracer,
            auto_approve=self.options.auto_approve,
        )
        self.policy.approval_gate = self.approvals
        self.sandbox = Sandbox(self)

        # memory
        self._session_store = InMemoryStore()
        self._persistent_store: Optional[SQLiteMemoryStore] = None
        self.declared_memory: set[str] = set()

        # agent execution state
        self.agent_stack: list[str] = []
        self.criteria_tables: dict[str, object] = {}

        # output sinks
        self._write_out = self.options.write_out or (lambda s: print(s))
        self._write_err = self.options.write_err or (lambda s: print(s, file=__import__("sys").stderr))

        # global scope with builtins installed by the interpreter
        self.env = Environment(kind="global", label="global")

        # Scope stack compatibility layer for old VM
        self._scope_stack: list[dict[str, Any]] = [{}]
        # Memory compatibility layer
        self.memory = MemoryCompat(self)
        self.tool_call_count = 0
        self.cost_usd = 0.0
        self.py_call_count = 0

    # -- output -------------------------------------------------------------
    def write_out(self, text: str):
        self._write_out(text)

    def write_err(self, text: str):
        self._write_err(text)

    # -- memory -------------------------------------------------------------
    def memory_store_for(self, namespace: str):
        if namespace in _SESSION_NAMESPACES:
            return self._session_store
        if self._persistent_store is None:
            import os

            memory_dir = self.options.memory_dir or os.path.join(os.getcwd(), ".inthon")
            self._persistent_store = SQLiteMemoryStore(os.path.join(memory_dir, "memory.db"))
        return self._persistent_store

    def declare_memory(self, namespace: str):
        self.declared_memory.add(namespace)

    def check_memory_declared(self, namespace: str, span: Optional[Span] = None):
        if namespace not in self.declared_memory:
            from ..errors import InthonCapabilityError

            raise InthonCapabilityError(
                f"Memory namespace '{namespace}' used without declaration",
                span=span,
                hint=f"Add 'use memory.{namespace}' before remember/recall/forget.",
            )

    # -- agents ---------------------------------------------------------------
    @property
    def current_agent(self) -> Optional[str]:
        return self.agent_stack[-1] if self.agent_stack else getattr(self, "_current_agent", None)

    @current_agent.setter
    def current_agent(self, value):
        self._current_agent = value

    @property
    def agent_goal(self) -> Optional[str]:
        return getattr(self, "_agent_goal", None)

    @agent_goal.setter
    def agent_goal(self, value):
        self._agent_goal = value

    # -- compatibility scope stack --------------------------------------------
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
        if name in self.env.vars:
            return self.env.vars[name]
        raise RuntimeError(f"INTHON_RUNTIME_001: Undefined variable '{name}'")

    def has_var(self, name: str) -> bool:
        if name in self.env.vars:
            return True
        return any(name in s for s in self._scope_stack)

    def close(self):
        if self._persistent_store is not None:
            self._persistent_store.close()


class MemoryCompat:
    def __init__(self, ctx):
        self.ctx = ctx

    def write(self, key, val, namespace):
        store = self.ctx.memory_store_for(namespace)
        store.remember(key, val)

    def delete(self, key, namespace):
        store = self.ctx.memory_store_for(namespace)
        return store.forget(key)

    def search(self, query, namespace):
        store = self.ctx.memory_store_for(namespace)
        return store.recall(query)

