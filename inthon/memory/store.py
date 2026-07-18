"""Memory store interface + in-memory implementation with rollback journaling."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..runtime.values import (
    NONE,
    InthonDict,
    InthonList,
    InthonString,
    InthonValue,
    bool_value,
)
from .embed import cosine, embed


@dataclass
class MemoryEntry:
    key: str
    _value: InthonValue
    text: str
    embedding: list[float]
    namespace: str = ""
    ts: float = field(default_factory=time.time)

    @property
    def value(self) -> Any:
        from ..runtime.values import to_python
        return to_python(self._value)

    def to_json(self) -> dict:
        return {
            "key": self.key,
            "text": self.text[:200],
            "ts": self.ts,
            "value": value_to_json(self._value),
        }


# ---------------------------------------------------------------------------
# Value (de)serialization
# ---------------------------------------------------------------------------
def value_to_json(value: InthonValue) -> Any:
    from ..runtime.values import InthonPyObject

    if value is NONE or value is None:
        return None
    tname = value.type_name
    if tname in ("int", "float", "str", "bool"):
        return {"__t__": tname, "v": value.to_python()}
    if isinstance(value, InthonList):
        return {"__t__": "list", "v": [value_to_json(v) for v in value.items]}
    if isinstance(value, InthonDict):
        return {
            "__t__": "dict",
            "v": [[k, value_to_json(v)] for k, v in value.pairs.items()],
        }
    if isinstance(value, InthonPyObject):
        return {"__t__": "py_repr", "v": value.display()}
    return {"__t__": "repr", "v": value.display()}


def value_from_json(data: Any) -> InthonValue:
    from ..runtime.values import InthonFloat, InthonInt

    if data is None:
        return NONE
    tag = data.get("__t__") if isinstance(data, dict) else None
    if tag == "int":
        return InthonInt(data["v"])
    if tag == "float":
        return InthonFloat(data["v"])
    if tag == "str":
        return InthonString(data["v"])
    if tag == "bool":
        return bool_value(data["v"])
    if tag == "list":
        return InthonList([value_from_json(v) for v in data["v"]])
    if tag == "dict":
        return InthonDict({k: value_from_json(v) for k, v in data["v"]})
    if tag in ("py_repr", "repr"):
        return InthonString(data["v"])
    return InthonString(str(data))


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------
class MemoryStore:
    """Abstract episodic memory store."""

    @classmethod
    def in_memory(cls) -> InMemoryStore:
        return InMemoryStore()

    @classmethod
    def persistent(cls, db_path: str = ".inthon/memory.db", use_embeddings: bool = True) -> MemoryStore:
        from pathlib import Path
        try:
            from .sqlite_store import SQLiteMemoryStore
            if db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            return SQLiteMemoryStore(db_path=db_path, use_embeddings=use_embeddings)
        except Exception:
            return InMemoryStore()

    def remember(self, namespace: str, key: str, value: InthonValue, text: str) -> MemoryEntry:
        raise NotImplementedError

    def recall(self, namespace: str, query: str, limit: int = 1) -> list[MemoryEntry]:
        raise NotImplementedError

    def forget(self, namespace: str, text: str) -> int:
        raise NotImplementedError

    def all(self, namespace: str) -> list[MemoryEntry]:
        raise NotImplementedError

    def namespaces(self) -> list[str]:
        raise NotImplementedError

    def write(self, key: str, value: Any, namespace: str) -> MemoryEntry:
        from ..runtime.values import from_python
        val_wrapped = from_python(value)
        entry = self.remember(namespace, key, val_wrapped, str(value))
        entry.namespace = namespace
        return entry

    def read(self, key: str, namespace: str) -> Optional[MemoryEntry]:
        for entry in self.all(namespace):
            if entry.key == key:
                return entry
        return None

    def delete(self, key: str, namespace: str) -> bool:
        return self.forget(namespace, key) > 0

    def search(self, query: str, namespace: str, limit: int = 10) -> list[MemoryEntry]:
        return self.recall(namespace, query, limit)

    def stats(self, namespace: str | None = None) -> dict:
        total = 0
        if namespace:
            total = len(self.all(namespace))
        else:
            for ns in self.namespaces():
                total += len(self.all(ns))
        return {
            "total_entries": total,
            "db_path": getattr(self, "db_path", ":memory:"),
            "embeddings_enabled": getattr(self, "use_embeddings", False),
            "using_ml_embeddings": False,
        }

    # -- journaling (SB-14: rollback on policy violation) ------------------------
    def begin(self):
        raise NotImplementedError

    def rollback(self, token) -> None:
        raise NotImplementedError

    def commit(self, token) -> None:
        pass


class InMemoryStore(MemoryStore):
    """Process-local store; the default for session namespaces."""

    persistent = False

    def __init__(self):
        self._data: dict[str, dict[str, MemoryEntry]] = {}

    def _ns(self, namespace: str) -> dict[str, MemoryEntry]:
        return self._data.setdefault(namespace, {})

    def remember(self, namespace: str, key: str, value: InthonValue, text: str) -> MemoryEntry:
        entry = MemoryEntry(key=key, _value=value, text=text, embedding=embed(text), namespace=namespace)
        self._ns(namespace)[key] = entry
        return entry

    def recall(self, namespace: str, query: str, limit: int = 1) -> list[MemoryEntry]:
        entries = self._ns(namespace)
        if not entries:
            return []
        q = embed(query)
        scored = sorted(
            ((cosine(q, e.embedding), e) for e in entries.values()),
            key=lambda pair: pair[0],
            reverse=True,
        )
        return [e for score, e in scored[: max(1, limit)]]

    def forget(self, namespace: str, text: str) -> int:
        entries = self._ns(namespace)
        removed = 0
        # exact text match first
        for key, entry in list(entries.items()):
            if entry.text == text or key == text:
                del entries[key]
                removed += 1
        if removed:
            return removed
        # otherwise: best semantic match
        best = self.recall(namespace, text, limit=1)
        if best and best[0].key in entries:
            del entries[best[0].key]
            removed += 1
        return removed

    def all(self, namespace: str) -> list[MemoryEntry]:
        return list(self._ns(namespace).values())

    def namespaces(self) -> list[str]:
        return sorted(self._data)

    # -- journaling ------------------------------------------------------------------
    def begin(self):
        return {ns: dict(entries) for ns, entries in self._data.items()}

    def rollback(self, token) -> None:
        self._data = {ns: dict(entries) for ns, entries in token.items()}
