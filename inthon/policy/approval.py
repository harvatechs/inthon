"""Approval gateway: human-in-the-loop gates (spec §approve)."""

from __future__ import annotations

import sys
from typing import Callable, Optional

from ..errors import ApprovalDeniedError, Span


from dataclasses import dataclass

@dataclass
class ApprovalRequest:
    target: str
    action: str
    context_summary: str
    requires_reason: bool = False


class ApprovalGate:
    """Evaluates `approve <subject> before <action>` requests.

    The handler receives (subject, action, details) and returns True/False.
    Host applications inject their own handler (UI prompt, Slack callback,
    auto-approver for tests).  The default handler prompts on the terminal
    when interactive, and denies otherwise (fail-closed).
    """

    def __init__(
        self,
        handler: Optional[Callable] = None,
        tracer=None,
        auto_approve: bool = False,
    ):
        self.handler = handler
        self.tracer = tracer
        self.auto_approve = auto_approve

    def set_handler(self, handler: Callable) -> None:
        self.handler = handler

    def request(self, subject: str, action: str, details: dict, span: Optional[Span] = None) -> bool:
        if self.tracer is not None:
            self.tracer.emit("approval_requested", span, subject=subject, action=action)

        if self.handler is not None:
            import inspect
            try:
                sig = inspect.signature(self.handler)
                params_count = len(sig.parameters)
            except Exception:
                params_count = 3
            if params_count == 1:
                req = ApprovalRequest(
                    target=subject,
                    action=action,
                    context_summary=details.get("summary", f"wants to {action} on {subject}"),
                )
                approved = bool(self.handler(req))
            else:
                approved = bool(self.handler(subject, action, details))
        elif self.auto_approve:
            approved = True
        else:
            approved = self._terminal_prompt(subject, action, details)

        if self.tracer is not None:
            self.tracer.emit(
                "approval_granted" if approved else "approval_denied",
                span,
                subject=subject,
                action=action,
            )
        if not approved:
            raise ApprovalDeniedError(
                f"INTHON_POLICY_002: Human denied approval for '{action}' on '{subject}'",
                span=span,
                hint="Re-run with an approval handler, --yes, or wrap in retry/catch.",
            )
        return True

    def _terminal_prompt(self, subject: str, action: str, details: dict) -> bool:
        if not sys.stdin.isatty():
            return False  # fail-closed when nobody can answer
        print(f"\n[inthon] approval requested: {subject} → {action}")
        for key, value in details.items():
            print(f"    {key}: {value}")
        answer = input("Approve? [y/N] ").strip().lower()
        return answer in ("y", "yes")

