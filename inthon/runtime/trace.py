from __future__ import annotations
import time
import uuid
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceEvent:
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    kind: str = ""  # "assign" | "tool_call" | "py_call" | "agent_start" | "agent_end" | "approve" | "remember" | "eval"
    data: dict[str, Any] = field(default_factory=dict)
    span_line: int | None = None
    duration_ms: float | None = None


class TraceLogger:
    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def emit(
        self,
        kind: str,
        data: dict[str, Any],
        span_line: int | None = None,
        duration_ms: float | None = None,
    ) -> None:
        self._events.append(
            TraceEvent(
                kind=kind, data=data, span_line=span_line, duration_ms=duration_ms
            )
        )

    def tool_events(self) -> list[dict]:
        return [e.data for e in self._events if e.kind == "tool_call"]

    def py_events(self) -> list[dict]:
        return [e.data for e in self._events if e.kind == "py_call"]

    def all_events(self) -> list[dict]:
        return [
            {
                "id": e.event_id,
                "ts": e.timestamp,
                "kind": e.kind,
                "data": e.data,
                "line": e.span_line,
                "duration_ms": e.duration_ms,
            }
            for e in self._events
        ]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.all_events(), indent=indent, default=str)
