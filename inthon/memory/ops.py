"""remember / recall / forget execution helpers shared by both backends."""

from __future__ import annotations

from typing import Optional

from ..errors import Span
from ..runtime.values import NONE, InthonValue, display


def memory_remember(ctx, namespace: str, value: InthonValue, span: Optional[Span] = None):
    store = ctx.memory_store_for(namespace)
    text = display(value)
    key = f"{namespace}:{abs(hash(text)) % (10 ** 10)}:{len(text)}"
    entry = store.remember(namespace, key, value, text)
    if ctx.tracer is not None:
        ctx.tracer.emit("remember", span, namespace=namespace, key=key, preview=text[:120])
    return entry


def memory_recall(ctx, namespace: str, query: str, span: Optional[Span] = None) -> InthonValue:
    store = ctx.memory_store_for(namespace)
    results = store.recall(namespace, query, limit=1)
    if ctx.tracer is not None:
        ctx.tracer.emit(
            "recall", span, namespace=namespace, query=query,
            found=bool(results), preview=(results[0].text[:120] if results else ""),
        )
    if not results:
        return NONE
    return results[0]._value


def memory_forget(ctx, namespace: str, value: InthonValue, span: Optional[Span] = None) -> int:
    store = ctx.memory_store_for(namespace)
    removed = store.forget(namespace, display(value))
    if ctx.tracer is not None:
        ctx.tracer.emit("forget", span, namespace=namespace, removed=removed)
    return removed
