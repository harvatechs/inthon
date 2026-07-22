"""Policy engine: frame stack + capability checks (spec §policy-engine)."""

from __future__ import annotations

from typing import Any, Optional


from ..errors import PolicyViolationError, Span
from .model import Policy


class PolicyCapsSet(set):
    def __init__(self, policy_engine, initial_caps):
        super().__init__(initial_caps)
        self.policy_engine = policy_engine

    def add(self, item):
        super().add(item)
        from .model import Capability

        p = self.policy_engine.current
        if item == Capability.NETWORK:
            object.__setattr__(p, "allow_network", True)
        elif item == Capability.SHELL:
            object.__setattr__(p, "allow_shell", True)
        elif item == Capability.EMAIL_SEND:
            object.__setattr__(p, "allow_email", True)
        elif item == Capability.PAYMENT_EXECUTE:
            object.__setattr__(p, "allow_payment", True)
        elif item == Capability.DATABASE_WRITE:
            object.__setattr__(p, "allow_database", True)
        elif item == Capability.MODEL_DOWNLOAD:
            object.__setattr__(p, "allow_model", True)
        elif item == Capability.FILESYSTEM_READ:
            if p.filesystem == "none":
                object.__setattr__(p, "filesystem", "read_only")
        elif item == Capability.FILESYSTEM_WRITE:
            object.__setattr__(p, "filesystem", "read_write")

    def update(self, items):
        for item in items:
            self.add(item)


class PolicyEngine:
    """PolicyEngine tracks agent capabilities and resources.

    Capabilities:
      * Allowlist validation is done dynamically at execution time.
      * If the host supplied a ceiling policy (RunOptions.policy / inthon.toml),
        every inner policy is *intersected* with it — programs can only narrow
        what the host granted (SB-13).
      * Otherwise a policy block is authoritative for its own scope — this is
        how `policy { allow_network: true }` grants a capability.  Code with
        no policy block at all still runs under default-deny.
    """

    def __init__(
        self, base: Optional[Policy] = None, tracer=None, ceiling: bool = False
    ):
        self.base = base or Policy()
        self.ceiling = ceiling
        self._stack: list[Policy] = [self.base]
        self.tracer = tracer
        self.last_popped: Optional[Policy] = None
        self.approval_gate: Optional[Any] = None

    @property
    def current(self) -> Policy:
        return self._stack[-1]

    @property
    def depth(self) -> int:
        return len(self._stack)

    # -- stack management ---------------------------------------------------------
    def apply(
        self, policy: Policy, span: Optional[Span] = None, label: str = ""
    ) -> Policy:
        current = self.current
        if self.ceiling:
            # Programs can only narrow what host granted (SB-13)
            effective = Policy(
                allow_network=current.allow_network and policy.allow_network,
                allow_shell=current.allow_shell and policy.allow_shell,
                allow_email=current.allow_email and policy.allow_email,
                allow_payment=current.allow_payment and policy.allow_payment,
                allow_database=current.allow_database and policy.allow_database,
                allow_model=current.allow_model and policy.allow_model,
                allow_memory_persist=current.allow_memory_persist
                and policy.allow_memory_persist,
                filesystem="none"
                if current.filesystem == "none" or policy.filesystem == "none"
                else (
                    "read_only"
                    if current.filesystem == "read_only"
                    or policy.filesystem == "read_only"
                    else "read_write"
                ),
                max_cost_usd=min(current.max_cost_usd, policy.max_cost_usd),
                max_runtime_sec=min(current.max_runtime_sec, policy.max_runtime_sec),
            )
        else:
            # Policy block is authoritative for its scope (SB-12)
            effective = policy
        self._stack.append(effective)
        if self.tracer is not None:
            self.tracer.emit(
                "policy_apply", span, label=label, effective=effective.to_json()
            )
        return effective

    def pop(self, span: Optional[Span] = None, label: str = "") -> Policy:
        if len(self._stack) > 1:
            popped = self._stack.pop()
            self.last_popped = popped
            if self.tracer is not None:
                self.tracer.emit("policy_pop", span, label=label)
            return popped
        return self.base

    # -- enforcement --------------------------------------------------------------
    def check(
        self, permission: str, span: Optional[Span] = None, subject: str = ""
    ) -> None:
        if not self.current.grants(permission):
            if permission == "network":
                raise PolicyViolationError(
                    "INTHON_POLICY_001: Capability 'NETWORK' is required but not permitted. "
                    "Add 'network: true' to your policy block.",
                    span=span,
                )
            raise PolicyViolationError(
                f"INTHON_POLICY_001: Capability '{permission.upper()}' is required but not permitted.",
                span=span,
            )

    def check_tool(self, spec, span: Optional[Span] = None) -> None:
        for permission in spec.permissions:
            self.check(permission, span, subject=spec.path)

    def check_capability(self, cap: object, span: Optional[Span] = None) -> None:
        from .model import Capability

        CAP_TO_PERMISSION = {
            Capability.NETWORK: "network",
            Capability.EMAIL_SEND: "email",
            Capability.SHELL: "shell",
            Capability.PAYMENT_EXECUTE: "payment",
            Capability.MEMORY_WRITE: "memory_persist",
            Capability.FILESYSTEM_WRITE: "filesystem_write",
            Capability.DATABASE_WRITE: "database",
            Capability.FILESYSTEM_READ: "filesystem",
        }
        perm = CAP_TO_PERMISSION.get(
            cap, cap.name.lower() if hasattr(cap, "name") else str(cap)
        )
        if not self.current.grants(perm):
            cap_name = cap.name if hasattr(cap, "name") else str(cap)
            if cap_name == "NETWORK":
                raise PolicyViolationError(
                    "INTHON_POLICY_001: Capability 'NETWORK' is required but not permitted. "
                    "Add 'network: true' to your policy block.",
                    span=span,
                )
            raise PolicyViolationError(
                f"INTHON_POLICY_001: Capability '{cap_name}' is required but not permitted. "
                f"Add '{cap_name.lower()}: true' to your policy block.",
                span=span,
            )

    @property
    def max_tool_calls(self) -> int:
        p = self.last_popped or self.current
        return p.max_tool_calls

    @property
    def max_cost_usd(self) -> float:
        p = self.last_popped or self.current
        return p.max_cost_usd

    @property
    def max_runtime_sec(self) -> float:
        p = self.last_popped or self.current
        return p.max_runtime_sec

    @property
    def active_caps(self) -> set:
        from .model import Capability

        p = self.last_popped or self.current
        caps = set()
        if p.allow_network:
            caps.add(Capability.NETWORK)
        if p.filesystem != "none":
            caps.add(Capability.FILESYSTEM_READ)
        if p.filesystem == "read_write":
            caps.add(Capability.FILESYSTEM_WRITE)
        if p.allow_shell:
            caps.add(Capability.SHELL)
        if p.allow_email:
            caps.add(Capability.EMAIL_SEND)
        if p.allow_payment:
            caps.add(Capability.PAYMENT_EXECUTE)
        if p.allow_database:
            caps.add(Capability.DATABASE_WRITE)
        if p.allow_model:
            caps.add(Capability.MODEL_DOWNLOAD)
        caps.add(Capability.MEMORY_WRITE)
        return PolicyCapsSet(self, caps)


def _hint_for(permission: str) -> str:
    mapping = {
        "network": "Add 'allow_network: true' to the policy block.",
        "email": "Add 'allow_email: true' to the policy block.",
        "filesystem": "Add 'filesystem: read_only' (or read_write) to the policy block.",
        "filesystem_write": "Add 'filesystem: read_write' to the policy block.",
        "shell": "Add 'allow_shell: true' to the policy block.",
        "payment": "Add 'allow_payment: true' to the policy block.",
        "database": "Add 'allow_database: true' to the policy block.",
        "model": "Add 'allow_model: true' to the policy block.",
        "memory_persist": "Add 'allow_memory_persist: true' to the policy block.",
    }
    return mapping.get(permission, "Declare the capability in the policy block.")
