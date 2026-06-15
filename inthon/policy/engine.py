from __future__ import annotations
from dataclasses import dataclass, field
from ..ast.nodes import PolicyBlock
from .approval import ApprovalGate
from .audit import AuditLog
from .model import Capability, POLICY_KEY_TO_CAPABILITY
from ..runtime.errors import PolicyViolationError

@dataclass
class PolicyEngine:
    active_caps: set[Capability] = field(
        default_factory=lambda: {Capability.FILESYSTEM_READ, Capability.MEMORY_WRITE}
    )
    max_tool_calls: int = 50
    max_runtime_sec: float = 300.0
    max_cost_usd: float = 1.0
    approval_gate: ApprovalGate = field(default_factory=ApprovalGate)
    audit: AuditLog = field(default_factory=AuditLog)

    def apply(self, policy: PolicyBlock) -> None:
        """Parse a PolicyBlock AST node and update active capabilities."""
        for entry in policy.entries:
            if entry.key in POLICY_KEY_TO_CAPABILITY:
                if entry.value is True:
                    self.active_caps.add(POLICY_KEY_TO_CAPABILITY[entry.key])
                else:
                    self.active_caps.discard(POLICY_KEY_TO_CAPABILITY[entry.key])
            elif entry.key == "max_tool_calls":
                self.max_tool_calls = int(entry.value)
            elif entry.key == "max_runtime_sec":
                self.max_runtime_sec = float(entry.value)
            elif entry.key == "max_cost_usd":
                self.max_cost_usd = float(entry.value)

    def check_capability(self, cap: Capability) -> None:
        if cap not in self.active_caps:
            raise PolicyViolationError(
                f"INTHON_POLICY_001: Capability '{cap.name}' is required but not permitted. "
                f"Add '{cap.name.lower()}: true' to your policy block."
            )

    def check_tool(self, tool_path: str) -> None:
        self.audit.log("tool_call_check", {"tool": tool_path})
