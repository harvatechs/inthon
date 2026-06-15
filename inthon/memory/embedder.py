"""
inthon.memory.embedder — Optional local text embedder for semantic memory search.

Provides a simple interface to generate vector embeddings for text. Uses
sentence-transformers if installed; falls back to a TF-IDF-style keyword
representation that still enables ranked retrieval without the 500MB model download.

The fallback is not "fake" — it produces a real sparse vector over character
n-grams, enabling genuine ranked recall even without ML dependencies.
"""

from __future__ import annotations
import hashlib
import math
from typing import Optional


class LocalEmbedder:
    """
    Unified embedding interface. Tries sentence-transformers first, then
    falls back to a character-trigram sparse vector for zero-dependency setups.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model = None
        self._model_name = model_name
        self._use_ml = False
        self._dim = 384  # MiniLM output dimension; trigram fallback uses 512

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(model_name)
            self._use_ml = True
            self._dim = self._model.get_sentence_embedding_dimension()
        except ImportError:
            # Graceful degradation: sparse trigram vectors
            self._dim = 512

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def using_ml(self) -> bool:
        return self._use_ml

    def embed(self, text: str) -> list[float]:
        """Return a unit-normalised embedding vector for text."""
        if self._use_ml and self._model is not None:
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        return self._trigram_embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._use_ml and self._model is not None:
            vecs = self._model.encode(texts, normalize_embeddings=True)
            return [v.tolist() for v in vecs]
        return [self._trigram_embed(t) for t in texts]

    # ── Sparse trigram fallback ───────────────────────────────────────── #

    def _trigram_embed(self, text: str) -> list[float]:
        """
        Produce a 512-dim sparse vector from character trigrams.
        Each trigram is hashed to a bucket; values are log(1+freq).
        The result is L2-normalised.
        """
        text = text.lower()
        counts: dict[int, float] = {}
        # Extract trigrams
        for i in range(len(text) - 2):
            gram = text[i : i + 3]
            bucket = int(hashlib.md5(gram.encode()).hexdigest(), 16) % self._dim
            counts[bucket] = counts.get(bucket, 0) + 1
        # Apply log(1+freq) weighting
        vec = [0.0] * self._dim
        for bucket, freq in counts.items():
            vec[bucket] = math.log1p(freq)
        # L2 normalise
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two pre-normalised vectors."""
        if len(a) != len(b):
            return 0.0
        return sum(x * y for x, y in zip(a, b))


# Module-level singleton — instantiated lazily
_embedder: Optional[LocalEmbedder] = None


def get_embedder() -> LocalEmbedder:
    """Return the shared embedder instance (lazy init)."""
    global _embedder
    if _embedder is None:
        _embedder = LocalEmbedder()
    return _embedder
