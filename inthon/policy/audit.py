from __future__ import annotations
from typing import Any

class AuditLog:
    """Append-only audit log for capabilities and policy decisions."""
    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def log(self, event_type: str, data: dict[str, Any]) -> None:
        self._entries.append({
            "event": event_type,
            "data": data
        })

    def get_entries(self) -> list[dict[str, Any]]:
        return self._entries
