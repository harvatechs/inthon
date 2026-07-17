"""Audit helpers over the run trace.

The trace is the audit log; this module adds query conveniences used by
`inthon trace` and by hosts that need to answer "what did the agent do?"
"""

from __future__ import annotations

from typing import Any


class AuditLog:
    def __init__(self, trace_json: dict):
        self.trace = trace_json

    @property
    def events(self) -> list[dict]:
        return self.trace.get("events", [])

    def by_type(self, event_type: str) -> list[dict]:
        return [e for e in self.events if e.get("type") == event_type]

    def tool_calls(self) -> list[dict]:
        return self.by_type("tool_call")

    def approvals(self) -> list[dict]:
        return [e for e in self.events if e.get("type", "").startswith("approval")]

    def policy_changes(self) -> list[dict]:
        return [e for e in self.events if e.get("type", "").startswith("policy_")]

    def total_cost_usd(self) -> float:
        return float(self.trace.get("cost", {}).get("usd", 0.0))

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.trace.get("run_id"),
            "events": len(self.events),
            "tool_calls": len(self.tool_calls()),
            "errors": len(self.trace.get("errors", [])),
            "cost_usd": self.total_cost_usd(),
            "duration_ms": self.trace.get("duration_ms"),
        }
