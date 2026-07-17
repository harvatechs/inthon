"""Policy model: capabilities + resource budgets (spec §policy).

Default-deny: every external capability starts disabled.  Budgets start
generous but finite.  Capabilities that are purely process-internal
(model compute, session memory) default to enabled — documented rationale:
they cannot affect the outside world, so they are not exfiltration vectors.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from ..errors import InthonSemanticError, Span

FILESYSTEM_MODES = ("none", "read_only", "read_write")

# permission tag on a tool → policy capability it requires
PERMISSION_TO_CAPABILITY = {
    "network": "allow_network",
    "email": "allow_email",
    "filesystem": "filesystem",
    "filesystem_write": "filesystem_write",
    "shell": "allow_shell",
    "payment": "allow_payment",
    "database": "allow_database",
    "model": "allow_model",
    "memory_persist": "allow_memory_persist",
}

BOOL_KEYS = {
    "allow_network",
    "allow_email",
    "allow_shell",
    "allow_payment",
    "allow_database",
    "allow_model",
    "allow_memory_persist",
}

NUMERIC_KEYS = {
    "max_tool_calls",
    "max_cost_usd",
    "max_runtime_sec",
    "max_iterations",
    "max_recursion",
    "max_py_calls",
    "max_llm_calls",
}


@dataclass(frozen=True)
class Policy:
    # capabilities
    allow_network: bool = False
    filesystem: str = "none"
    allow_shell: bool = False
    allow_email: bool = False
    allow_payment: bool = False
    allow_database: bool = False
    allow_model: bool = True
    allow_memory_persist: bool = True
    # budgets
    max_tool_calls: int = 25
    max_cost_usd: float = 1.0
    max_runtime_sec: float = 120.0
    max_iterations: int = 100_000
    max_recursion: int = 64
    max_py_calls: int = 500
    max_llm_calls: int = 50

    # -- construction ---------------------------------------------------------
    @staticmethod
    def permissive() -> "Policy":
        """Everything allowed — used only when the host opts in explicitly."""
        return Policy(
            allow_network=True,
            filesystem="read_write",
            allow_shell=True,
            allow_email=True,
            allow_payment=True,
            allow_database=True,
        )

    @staticmethod
    def from_entries(entries, span: Span = None) -> "Policy":
        """Build from AST PolicyEntry list with compile-time validation (AS-15)."""
        values: dict[str, Any] = {}
        valid = {f.name for f in fields(Policy)}
        for entry in entries:
            key, value = entry.key, entry.value
            if key not in valid:
                raise InthonSemanticError(
                    f"Unknown policy key '{key}'",
                    span=entry.span or span,
                    hint=f"Valid keys: {', '.join(sorted(valid))}",
                )
            if key == "filesystem":
                if value not in FILESYSTEM_MODES:
                    raise InthonSemanticError(
                        f"policy.filesystem must be one of {FILESYSTEM_MODES}, got {value!r}",
                        span=entry.span or span,
                    )
            elif key in BOOL_KEYS:
                if not isinstance(value, bool):
                    raise InthonSemanticError(
                        f"policy.{key} expects true/false, got {value!r}",
                        span=entry.span or span,
                    )
            elif key in NUMERIC_KEYS:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise InthonSemanticError(
                        f"policy.{key} expects a number, got {value!r}",
                        span=entry.span or span,
                    )
                if value < 0:
                    raise InthonSemanticError(
                        f"policy.{key} must be >= 0", span=entry.span or span
                    )
            values[key] = value
        return Policy(**values)

    # -- combination ------------------------------------------------------------
    def intersect(self, child: "Policy") -> "Policy":
        """Effective policy when *child* is applied inside *self* (SB-13):
        capabilities can only narrow, budgets take the minimum."""
        return Policy(
            allow_network=self.allow_network and child.allow_network,
            filesystem=_min_fs(self.filesystem, child.filesystem),
            allow_shell=self.allow_shell and child.allow_shell,
            allow_email=self.allow_email and child.allow_email,
            allow_payment=self.allow_payment and child.allow_payment,
            allow_database=self.allow_database and child.allow_database,
            allow_model=self.allow_model and child.allow_model,
            allow_memory_persist=self.allow_memory_persist and child.allow_memory_persist,
            max_tool_calls=min(self.max_tool_calls, child.max_tool_calls),
            max_cost_usd=min(self.max_cost_usd, child.max_cost_usd),
            max_runtime_sec=min(self.max_runtime_sec, child.max_runtime_sec),
            max_iterations=min(self.max_iterations, child.max_iterations),
            max_recursion=min(self.max_recursion, child.max_recursion),
            max_py_calls=min(self.max_py_calls, child.max_py_calls),
            max_llm_calls=min(self.max_llm_calls, child.max_llm_calls),
        )

    def grants(self, permission: str) -> bool:
        cap = PERMISSION_TO_CAPABILITY.get(permission)
        if cap is None:
            return False
        if cap == "filesystem":
            return self.filesystem in ("read_only", "read_write")
        if cap == "filesystem_write":
            return self.filesystem == "read_write"
        return bool(getattr(self, cap))

    def to_json(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _min_fs(a: str, b: str) -> str:
    order = {"none": 0, "read_only": 1, "read_write": 2}
    return a if order[a] <= order[b] else b


from enum import Enum, auto

class Capability(Enum):
    NETWORK = auto()
    FILESYSTEM_READ = auto()
    FILESYSTEM_WRITE = auto()
    SHELL = auto()
    EMAIL_SEND = auto()
    CALENDAR_WRITE = auto()
    PAYMENT_EXECUTE = auto()
    MEMORY_WRITE = auto()
    DATABASE_WRITE = auto()
    MODEL_DOWNLOAD = auto()

