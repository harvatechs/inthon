"""Value conversion between INTHON and Python (spec §pybridge-conversion).

from_python is deep-but-bounded: primitives and plain containers convert
structurally; anything else (modules, functions, DataFrames, numpy arrays)
stays wrapped in an InthonPyObject proxy so attribute policy still applies.
"""

from __future__ import annotations

from typing import Any

from ..errors import InthonConversionError, Span
from ..runtime.values import (
    NONE,
    InthonDict,
    InthonFloat,
    InthonInt,
    InthonList,
    InthonPyObject,
    InthonString,
    InthonValue,
    bool_value,
)

_MAX_DEPTH = 50
_MAX_ITEMS = 100_000


def from_python(obj: Any, importer=None, path: str = "", _depth: int = 0) -> InthonValue:
    if obj is None:
        return NONE
    if isinstance(obj, bool):
        return bool_value(obj)
    if isinstance(obj, InthonValue):
        return obj
    if isinstance(obj, int):
        return InthonInt(obj)
    if isinstance(obj, float):
        return InthonFloat(obj)
    if isinstance(obj, str):
        return InthonString(obj)
    # numpy scalars → native numbers (duck-typed to avoid a hard numpy dep)
    if type(obj).__module__ == "numpy" and type(obj).__name__ in (
        "int64", "int32", "float64", "float32", "int_", "float_",
    ):
        return InthonFloat(float(obj)) if "float" in type(obj).__name__ else InthonInt(int(obj))
    if isinstance(obj, (list, tuple, set, frozenset)):
        if _depth > _MAX_DEPTH:
            raise InthonConversionError("Value too deep to convert from Python")
        items = list(obj)
        if len(items) > _MAX_ITEMS:
            raise InthonConversionError("Collection too large to convert from Python")
        return InthonList([from_python(v, importer, path, _depth + 1) for v in items])
    if isinstance(obj, dict):
        if _depth > _MAX_DEPTH:
            raise InthonConversionError("Value too deep to convert from Python")
        if len(obj) > _MAX_ITEMS:
            raise InthonConversionError("Dict too large to convert from Python")
        return InthonDict({k: from_python(v, importer, path, _depth + 1) for k, v in obj.items()})
    # everything else stays proxied
    return InthonPyObject(obj, importer=importer, path=path)


def to_python(value: InthonValue, _depth: int = 0) -> Any:
    if _depth > _MAX_DEPTH:
        raise InthonConversionError("Value too deep to convert to Python")
    if isinstance(value, InthonPyObject):
        return value.wrapped
    if isinstance(value, InthonList):
        return [to_python(v, _depth + 1) for v in value.items]
    if isinstance(value, InthonDict):
        return {k: to_python(v, _depth + 1) for k, v in value.pairs.items()}
    if isinstance(value, InthonValue):
        return value.to_python()
    return value
