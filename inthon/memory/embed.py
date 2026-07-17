"""Deterministic hash-based text embeddings (spec MT-03).

The default embedding model (MiniLM) requires network downloads; this
fallback is fully offline and deterministic, which keeps traces replayable.
The interface is pluggable — any callable str -> list[float] works.
"""

from __future__ import annotations

import hashlib
import math
import re

DEFAULT_DIMS = 128

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def embed(text: str, dims: int = DEFAULT_DIMS) -> list[float]:
    """Map text to an L2-normalized vector via feature hashing.

    Unigrams and bigrams are hashed into `dims` buckets with signed counts —
    a classic hashing trick that preserves cosine similarity structure.
    """
    tokens = tokenize(text)
    vec = [0.0] * dims
    features: list[str] = list(tokens)
    features.extend(f"{a} {b}" for a, b in zip(tokens, tokens[1:]))
    for feat in features:
        digest = hashlib.sha256(feat.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "little") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[bucket] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
