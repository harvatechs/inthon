"""Structured trace logging (engine spec §6.3).

Every observable event in an INTHON run is recorded in a versioned JSON
trace: tool calls, Python calls, approvals, memory operations, guards,
retries, policy changes, assignments and errors.  The trace is
deterministic given the same source and tool responses (VM-13).
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from ..errors import Span
from ..version import TRACE_SCHEMA_VERSION


class TraceLogger:
    """Accumulates trace events for one run."""

    def __init__(
        self,
        run_id: Optional[str] = None,
        program: str = "",
        filename: str = "<stdin>",
        backend: str = "tree",
        enabled: bool = True,
    ):
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        self.filename = filename
        self.backend = backend
        self.enabled = enabled
        self.started_at = time.time()
        self.ended_at: Optional[float] = None
        self.events: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self._seq = 0
        self._program_hash = _program_hash(program)
        self.agent: Optional[str] = None

    # -- event emission --------------------------------------------------------
    def emit(self, event_type: str, span: Optional[Span] = None, **payload) -> dict:
        if not self.enabled:
            return {}
        self._seq += 1
        event = {
            "seq": self._seq,
            "t_ms": round((time.time() - self.started_at) * 1000.0, 3),
            "type": event_type,
        }
        if span is not None:
            if hasattr(span, "line"):
                event["src"] = {"line": span.line, "col": span.col}
            elif isinstance(span, dict):
                payload.update(span)
        if self.agent:
            event["agent"] = self.agent
        event.update(payload)
        self.events.append(event)
        return event

    def emit_error(self, code: str, message: str, span: Optional[Span] = None):
        entry = {"code": code, "message": message}
        if span is not None:
            entry["src"] = {"line": span.line, "col": span.col}
        self.errors.append(entry)
        self.emit("error", span, code=code, message=message)

    # -- finalization ------------------------------------------------------------
    def finish(self, result_type: str = "none", result_preview: str = "") -> dict:
        self.ended_at = time.time()
        return self.to_json(result_type=result_type, result_preview=result_preview)

    def to_json(self, result_type: str = "none", result_preview: str = "") -> dict:
        ended = self.ended_at or time.time()
        tool_calls = [e for e in self.events if e.get("type") == "tool_call"]
        py_calls = [e for e in self.events if e.get("type") == "py_call"]
        total_cost = round(sum(e.get("cost_usd", 0.0) for e in tool_calls), 6)
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "program_hash": self._program_hash,
            "filename": self.filename,
            "backend": self.backend,
            "started_at": _iso(self.started_at),
            "ended_at": _iso(ended),
            "duration_ms": round((ended - self.started_at) * 1000.0, 3),
            "agent": self.agent,
            "events": self.events,
            "tool_calls": tool_calls,
            "py_calls": py_calls,
            "errors": self.errors,
            "cost": {"usd": total_cost, "tool_calls": len(tool_calls), "py_calls": len(py_calls)},
            "result_type": result_type,
            "result_preview": result_preview[:200],
        }

    def to_json_str(self, **kwargs) -> str:
        return json.dumps(self.to_json(**kwargs), indent=2)


def _iso(ts: float) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()


def _program_hash(program: str) -> str:
    import hashlib

    return hashlib.sha256(program.encode("utf-8")).hexdigest()[:16]
