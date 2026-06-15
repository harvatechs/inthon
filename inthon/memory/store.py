from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class MemoryEntry:
    key: str
    value: Any
    namespace: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)


class MemoryStore(ABC):
    @abstractmethod
    def write(self, key: str, value: Any, namespace: str) -> MemoryEntry: ...
    @abstractmethod
    def read(self, key: str, namespace: str) -> MemoryEntry | None: ...
    @abstractmethod
    def delete(self, key: str, namespace: str) -> bool: ...
    @abstractmethod
    def search(
        self, query: str, namespace: str, limit: int = 10
    ) -> list[MemoryEntry]: ...

    @classmethod
    def in_memory(cls) -> "InMemoryStore":
        """Return a volatile in-memory store (data lost on process exit)."""
        return InMemoryStore()

    @classmethod
    def persistent(
        cls, db_path: str = ".inthon/memory.db", use_embeddings: bool = True
    ) -> "MemoryStore":
        """
        Return a persistent SQLite-backed store that survives restarts.
        Falls back to InMemoryStore if SQLite is unavailable (unlikely).
        """
        from pathlib import Path

        try:
            from .sqlite_store import SQLiteMemoryStore

            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            return SQLiteMemoryStore(db_path=db_path, use_embeddings=use_embeddings)
        except Exception:
            return InMemoryStore()


class InMemoryStore(MemoryStore):
    """
    Volatile in-process store for v0.1.
    Namespaces are isolated; cross-namespace reads require explicit
    namespace specification.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, MemoryEntry]] = {}

    def write(self, key: str, value: Any, namespace: str = "session") -> MemoryEntry:
        ns = self._store.setdefault(namespace, {})
        if key in ns:
            entry = ns[key]
            ns[key] = MemoryEntry(
                key=key,
                value=value,
                namespace=namespace,
                created_at=entry.created_at,
                updated_at=time.time(),
                tags=entry.tags,
            )
        else:
            ns[key] = MemoryEntry(key=key, value=value, namespace=namespace)
        return ns[key]

    def read(self, key: str, namespace: str = "session") -> MemoryEntry | None:
        return self._store.get(namespace, {}).get(key)

    def delete(self, key: str, namespace: str = "session") -> bool:
        ns = self._store.get(namespace, {})
        if key in ns:
            del ns[key]
            return True
        return False

    def search(
        self, query: str, namespace: str = "session", limit: int = 10
    ) -> list[MemoryEntry]:
        ns = self._store.get(namespace, {})
        results = [
            entry for entry in ns.values() if query.lower() in str(entry.value).lower()
        ]
        return results[:limit]
