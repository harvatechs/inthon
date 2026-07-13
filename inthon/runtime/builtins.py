from __future__ import annotations

import builtins as py_builtins
from collections.abc import Callable
from typing import Any


SAFE_BUILTIN_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "print": py_builtins.print,
    "range": lambda *args: list(py_builtins.range(*args)),
    "len": py_builtins.len,
    "str": py_builtins.str,
    "int": py_builtins.int,
    "float": py_builtins.float,
    "bool": py_builtins.bool,
    "abs": py_builtins.abs,
    "min": py_builtins.min,
    "max": py_builtins.max,
    "sum": py_builtins.sum,
    "round": py_builtins.round,
}

SAFE_BUILTIN_NAMES = tuple(SAFE_BUILTIN_FUNCTIONS)


def make_builtin_wrapper(name: str, fn: Callable[..., Any]) -> Any:
    from .values import InthonPyObject, InthonValue, to_python

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        py_args = [
            to_python(arg) if isinstance(arg, InthonValue) else arg for arg in args
        ]
        py_kwargs = {
            key: to_python(value) if isinstance(value, InthonValue) else value
            for key, value in kwargs.items()
        }
        return fn(*py_args, **py_kwargs)

    wrapper.__name__ = name
    return InthonPyObject(wrapper, "builtins")


def builtin_values() -> dict[str, Any]:
    return {
        name: make_builtin_wrapper(name, fn)
        for name, fn in SAFE_BUILTIN_FUNCTIONS.items()
    }
