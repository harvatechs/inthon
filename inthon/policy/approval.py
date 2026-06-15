from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
from ..runtime.errors import ApprovalDeniedError


@dataclass
class ApprovalRequest:
    target: str
    action: str
    context_summary: str
    requires_reason: bool = False


class ApprovalGate:
    """
    Synchronous approval gate for v0.1.
    For headless execution (such as testing), an auto-approve callback handler can be registered.
    """

    def __init__(self) -> None:
        self._handler: Callable[[ApprovalRequest], bool] | None = None

    def set_handler(self, handler: Callable[[ApprovalRequest], bool]) -> None:
        """Register a custom approval handler (e.g. web UI, CLI prompt, API call)."""
        self._handler = handler

    def request(self, target: str, action: str, context: Any) -> None:
        req = ApprovalRequest(
            target=target,
            action=action,
            context_summary=f"Agent '{context.current_agent}' wants to {action} on {target}",
        )
        if self._handler is None:
            approved = self._cli_prompt(req)
        else:
            approved = self._handler(req)
        if not approved:
            raise ApprovalDeniedError(
                f"INTHON_POLICY_002: Human denied approval for '{action}' on '{target}'"
            )

    def _cli_prompt(self, req: ApprovalRequest) -> bool:
        print("\n[INTHON APPROVAL REQUIRED]")
        print(f"  Action: {req.action} -> {req.target}")
        print(f"  Context: {req.context_summary}")
        try:
            response = input("  Approve? [y/N]: ").strip().lower()
            return response in ("y", "yes")
        except (IOError, EOFError):
            # Fallback for headless environments without stdin
            return False
