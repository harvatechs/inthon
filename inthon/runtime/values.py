from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class InthonInt:
    v: int

    def __repr__(self) -> str:
        return str(self.v)


@dataclass
class InthonFloat:
    v: float

    def __repr__(self) -> str:
        return str(self.v)


@dataclass
class InthonStr:
    v: str

    def __repr__(self) -> str:
        return repr(self.v)


@dataclass
class InthonBool:
    v: bool

    def __repr__(self) -> str:
        return "true" if self.v else "false"


@dataclass
class InthonNone:
    def __repr__(self) -> str:
        return "none"


@dataclass
class InthonList:
    items: list[InthonValue]

    def __repr__(self) -> str:
        return f"[{', '.join(repr(i) for i in self.items)}]"


@dataclass
class InthonDict:
    pairs: dict[str, InthonValue]

    def __repr__(self) -> str:
        return (
            f"{{{', '.join(f'{repr(k)}: {repr(v)}' for k, v in self.pairs.items())}}}"
        )


@dataclass
class InthonCallable:
    """Represents a user-defined INTHON function."""

    name: str
    params: list[str]
    defaults: dict[str, InthonValue]
    body: Any  # tuple[Statement, ...]
    closure: Any  # ExecutionContext (using Any to avoid circular dependency)

    def __repr__(self) -> str:
        return f"<function {self.name}>"


@dataclass
class InthonToolRef:
    """Reference to a registered tool (not yet called)."""

    tool_path: str

    def __repr__(self) -> str:
        return f"<tool {self.tool_path}>"


@dataclass
class InthonPyObject:
    """Opaque wrapper around an arbitrary Python object."""

    obj: Any
    source_module: str

    def __repr__(self) -> str:
        return f"<IntHon PyObject: {self.source_module}.{type(self.obj).__name__}>"


InthonValue = (
    InthonInt
    | InthonFloat
    | InthonStr
    | InthonBool
    | InthonNone
    | InthonList
    | InthonDict
    | InthonCallable
    | InthonToolRef
    | InthonPyObject
)


def to_python(val: InthonValue) -> Any:
    """Convert an InthonValue to its Python equivalent."""
    match val:
        case InthonInt(v=v):
            return v
        case InthonFloat(v=v):
            return v
        case InthonStr(v=v):
            return v
        case InthonBool(v=v):
            return v
        case InthonNone():
            return None
        case InthonList(items=items):
            return [to_python(i) for i in items]
        case InthonDict(pairs=pairs):
            return {k: to_python(v) for k, v in pairs.items()}
        case InthonPyObject(obj=obj):
            try:
                from ..pybridge.adapters.pandas_adapter import PandasAdapter

                if isinstance(obj, PandasAdapter):
                    return obj.underlying
            except ImportError:
                pass
            return obj
        case InthonCallable():
            return val
        case InthonToolRef():
            return val
        case _:
            raise TypeError(f"Cannot convert {type(val)} to Python")


def from_python(val: Any, source_module: str = "unknown") -> InthonValue:
    """Convert a Python object to an InthonValue."""
    match val:
        case int():
            if type(val) is bool:  # Python bool subclasses int
                return InthonBool(val)
            return InthonInt(val)
        case float():
            return InthonFloat(val)
        case str():
            return InthonStr(val)
        case bool():
            return InthonBool(val)
        case None:
            return InthonNone()
        case list():
            return InthonList([from_python(i, source_module) for i in val])
        case dict():
            return InthonDict(
                {str(k): from_python(v, source_module) for k, v in val.items()}
            )
        case (
            InthonInt()
            | InthonFloat()
            | InthonStr()
            | InthonBool()
            | InthonNone()
            | InthonList()
            | InthonDict()
            | InthonCallable()
            | InthonToolRef()
            | InthonPyObject()
        ):
            return val
        case _:
            if type(val).__name__ == "DataFrame":
                try:
                    from ..pybridge.adapters.pandas_adapter import PandasAdapter

                    return InthonPyObject(PandasAdapter(val), source_module)
                except ImportError:
                    pass
            return InthonPyObject(val, source_module)
