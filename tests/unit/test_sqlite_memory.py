"""
tests/unit/test_sqlite_memory.py — Tests for the persistent SQLite memory store.
"""

from __future__ import annotations
import tempfile
import os
from inthon.memory.sqlite_store import SQLiteMemoryStore
from inthon.memory.store import MemoryStore


class TestSQLiteMemoryStore:
    def setup_method(self):
        """Use a temporary in-memory SQLite for each test."""
        self.store = SQLiteMemoryStore(db_path=":memory:", use_embeddings=False)

    def test_write_and_read(self):
        self.store.write("key1", "hello world", "test")
        entry = self.store.read("key1", "test")
        assert entry is not None
        assert entry.value == "hello world"
        assert entry.namespace == "test"

    def test_write_updates_existing(self):
        self.store.write("key1", "original", "test")
        self.store.write("key1", "updated", "test")
        entry = self.store.read("key1", "test")
        assert entry.value == "updated"

    def test_delete(self):
        self.store.write("key1", "value", "test")
        success = self.store.delete("key1", "test")
        assert success is True
        assert self.store.read("key1", "test") is None

    def test_delete_nonexistent(self):
        result = self.store.delete("nonexistent", "test")
        assert result is False

    def test_keyword_search(self):
        self.store.write("k1", "python is great", "ns")
        self.store.write("k2", "inthon is fast", "ns")
        self.store.write("k3", "unrelated entry", "ns")

        results = self.store.search("inthon", "ns")
        assert len(results) >= 1
        assert any("inthon" in str(r.value) for r in results)

    def test_namespace_isolation(self):
        self.store.write("key1", "value-ns1", "namespace1")
        self.store.write("key1", "value-ns2", "namespace2")

        entry1 = self.store.read("key1", "namespace1")
        entry2 = self.store.read("key1", "namespace2")
        assert entry1.value == "value-ns1"
        assert entry2.value == "value-ns2"

    def test_write_complex_value(self):
        self.store.write(
            "complex", {"key": "value", "num": 42, "list": [1, 2, 3]}, "test"
        )
        entry = self.store.read("complex", "test")
        assert entry is not None
        assert entry.value["num"] == 42

    def test_stats(self):
        self.store.write("k1", "v1", "ns")
        self.store.write("k2", "v2", "ns")
        stats = self.store.stats()
        assert stats["total_entries"] == 2
        assert stats["embeddings_enabled"] is False

    def test_persistence_across_instances(self):
        """Data should survive closing and reopening the store."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            store1 = SQLiteMemoryStore(db_path=db_path, use_embeddings=False)
            store1.write("persistent_key", "persistent_value", "session")
            store1.close()

            store2 = SQLiteMemoryStore(db_path=db_path, use_embeddings=False)
            entry = store2.read("persistent_key", "session")
            store2.close()

            assert entry is not None
            assert entry.value == "persistent_value"
        finally:
            os.unlink(db_path)


class TestMemoryStoreFactory:
    def test_in_memory_factory(self):
        store = MemoryStore.in_memory()
        store.write("k", "v", "ns")
        assert store.read("k", "ns").value == "v"

    def test_persistent_factory(self):
        store = MemoryStore.persistent(db_path=":memory:", use_embeddings=False)
        store.write("k", "v", "ns")
        assert store.read("k", "ns").value == "v"
        # Should be an SQLiteMemoryStore
        from inthon.memory.sqlite_store import SQLiteMemoryStore

        assert isinstance(store, SQLiteMemoryStore)


class TestEmbedder:
    def test_trigram_embedder(self):
        from inthon.memory.embedder import LocalEmbedder

        embedder = LocalEmbedder.__new__(LocalEmbedder)
        embedder._use_ml = False
        embedder._dim = 512
        embedder._model = None
        embedder._model_name = "test"

        vec = embedder._trigram_embed("hello world")
        assert len(vec) == 512
        # Should be unit-normalised
        import math

        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 0.01 or norm == 0.0

    def test_cosine_similarity_identical(self):
        from inthon.memory.embedder import LocalEmbedder

        vec = [1.0, 0.0, 0.0]
        sim = LocalEmbedder.cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        from inthon.memory.embedder import LocalEmbedder

        a = [1.0, 0.0]
        b = [0.0, 1.0]
        sim = LocalEmbedder.cosine_similarity(a, b)
        assert abs(sim - 0.0) < 0.001
