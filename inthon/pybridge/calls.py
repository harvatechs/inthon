"""Calling proxied Python callables from INTHON."""

from __future__ import annotations

from typing import Optional

from ..errors import InthonPyAttributeError, Span
from ..runtime.values import InthonPyObject, InthonValue
from .converter import from_python, to_python
from .exception_wrap import wrap_python_exception


def py_call(ctx, fn_proxy: InthonPyObject, args: list, kwargs: dict, span: Optional[Span] = None) -> InthonValue:
    """Invoke a proxied Python callable with budget checks and tracing."""
    target = fn_proxy.wrapped
    path = getattr(fn_proxy, "_path", "") or type(target).__name__
    importer = getattr(fn_proxy, "_importer", None)

    if not callable(target):
        raise InthonPyAttributeError(
            f"Python object at '{path}' is not callable", span=span
        )

    if ctx is not None and ctx.sandbox is not None:
        ctx.sandbox.before_py_call(path, span)

    py_args = [to_python(a) for a in args]
    py_kwargs = {k: to_python(v) for k, v in kwargs.items()}
    try:
        result = target(*py_args, **py_kwargs)
    except Exception as exc:
        raise wrap_python_exception(exc, path, span) from exc

    if ctx is not None:
        if ctx.sandbox is not None:
            ctx.sandbox.after_py_call(path)
        if ctx.tracer is not None:
            ctx.tracer.emit(
                "py_call",
                span,
                path=path,
                args=repr(py_args)[:120],
                kwargs=repr(py_kwargs)[:120],
                result=repr(result)[:120],
            )
    return from_python(result, importer=importer, path=path + "()")


def py_index(ctx, proxy: InthonPyObject, index: InthonValue, span: Optional[Span] = None) -> InthonValue:
    """obj[key] on a proxied Python object."""
    target = proxy.wrapped
    importer = getattr(proxy, "_importer", None)
    path = getattr(proxy, "_path", "")
    try:
        result = target[to_python(index)]
    except Exception as exc:
        raise wrap_python_exception(exc, f"{path}[...]", span) from exc
    return from_python(result, importer=importer, path=f"{path}[...]")


def py_iter(proxy: InthonPyObject, span: Optional[Span] = None):
    """Iterate a proxied Python iterable, yielding wrapped items."""
    target = proxy.wrapped
    importer = getattr(proxy, "_importer", None)
    path = getattr(proxy, "_path", "")
    try:
        iterator = iter(target)
    except TypeError as exc:
        raise wrap_python_exception(exc, f"iter({path})", span) from exc
    for item in iterator:
        yield from_python(item, importer=importer, path=f"{path}[*]")
