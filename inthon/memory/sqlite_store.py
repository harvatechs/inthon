"""SQLite-backed episodic memory (spec §29.1, MT-01..MT-05).

One table per namespace (MT-04), embeddings stored as JSON (MT-01), brute-
force cosine retrieval in Python (MT-02), persistence across runs at
.inthon/memory.db (MT-05).  Rollback uses SQLite SAVEPOINTs (SB-14).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from pathlib import Path

from ..errors import InthonMemoryError_
from ..runtime.values import InthonValue
from .embed import cosine, embed
from .store import MemoryEntry, MemoryStore, value_from_json, value_to_json

_SCHEMA = """
CREATE TABLE IF NOT EXISTS "{table}" (
    key TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    value TEXT NOT NULL,
    embedding TEXT NOT NULL,
    ts REAL NOT NULL
)
"""


def _table_name(namespace: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", namespace)
    return f"mem_{safe}"


class SQLiteMemoryStore(MemoryStore):
    persistent = True

    def __init__(self, db_path: str, use_embeddings: bool = True):
        self.db_path = db_path
        self.use_embeddings = use_embeddings
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path)
        except Exception as exc:
            raise InthonMemoryError_(
                f"Cannot open memory database at {db_path}: {exc}"
            ) from exc
        self._savepoints: list[str] = []

    def _ensure(self, namespace: str) -> str:
        table = _table_name(namespace)
        self._conn.execute(_SCHEMA.format(table=table))
        return table

    # -- operations -------------------------------------------------------------------
    def remember(self, namespace: str, key: str, value: InthonValue, text: str) -> MemoryEntry:
        table = self._ensure(namespace)
        entry = MemoryEntry(key=key, _value=value, text=text, embedding=embed(text))
        self._conn.execute(
            f'INSERT OR REPLACE INTO "{table}" (key, text, value, embedding, ts) VALUES (?, ?, ?, ?, ?)',
            (key, text, json.dumps(value_to_json(value)), json.dumps(entry.embedding), time.time()),
        )
        self._conn.commit()
        return entry

    def recall(self, namespace: str, query: str, limit: int = 1) -> list[MemoryEntry]:
        table = self._ensure(namespace)
        rows = self._conn.execute(
            f'SELECT key, text, value, embedding, ts FROM "{table}"'
        ).fetchall()
        if not rows:
            return []
        q = embed(query)
        entries = [
            (
                cosine(q, json.loads(row[3])),
                MemoryEntry(
                    key=row[0],
                    _value=value_from_json(json.loads(row[2])),
                    text=row[1],
                    embedding=json.loads(row[3]),
                    namespace=namespace,
                    ts=row[4],
                ),
            )
            for row in rows
        ]
        entries.sort(key=lambda pair: pair[0], reverse=True)
        return [e for _, e in entries[: max(1, limit)]]

    def forget(self, namespace: str, text: str) -> int:
        table = self._ensure(namespace)
        cur = self._conn.execute(
            f'DELETE FROM "{table}" WHERE key = ? OR text = ?', (text, text)
        )
        removed = cur.rowcount
        if removed == 0:
            best = self.recall(namespace, text, limit=1)
            if best:
                cur = self._conn.execute(f'DELETE FROM "{table}" WHERE key = ?', (best[0].key,))
                removed = cur.rowcount
        self._conn.commit()
        return removed

    def all(self, namespace: str) -> list[MemoryEntry]:
        table = self._ensure(namespace)
        rows = self._conn.execute(
            f'SELECT key, text, value, embedding, ts FROM "{table}" ORDER BY ts'
        ).fetchall()
        return [
            MemoryEntry(
                key=row[0],
                _value=value_from_json(json.loads(row[2])),
                text=row[1],
                embedding=json.loads(row[3]),
                namespace=namespace,
                ts=row[4],
            )
            for row in rows
        ]

    def namespaces(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mem_%'"
        ).fetchall()
        return sorted(row[0][4:] for row in rows)

    # -- journaling -----------------------------------------------------------------------
    def begin(self):
        name = f"sp_{uuid.uuid4().hex[:8]}"
        self._conn.execute(f"SAVEPOINT {name}")
        self._savepoints.append(name)
        return name

    def rollback(self, token) -> None:
        if token in self._savepoints:
            self._conn.execute(f"ROLLBACK TO SAVEPOINT {token}")
            self._conn.execute(f"RELEASE SAVEPOINT {token}")
            self._savepoints.remove(token)

    def commit(self, token) -> None:
        if token in self._savepoints:
            self._conn.execute(f"RELEASE SAVEPOINT {token}")
            self._savepoints.remove(token)
        self._conn.commit()

    def close(self):
        self._conn.close()
