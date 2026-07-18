"""INTHON runtime value model (engine spec §6.1).

Every value flowing through an INTHON program is an InthonValue.  This gives
the language a defined object model: values know how to display themselves,
how to convert to/from Python (for the PyBridge), and how to compare.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional


class InthonValue:
    """Base class of all INTHON values."""

    type_name = "value"

    def to_python(self) -> Any:
        raise NotImplementedError

    def display(self) -> str:
        return str(self.to_python())

    def repr(self) -> str:
        return self.display()

    def truthy(self) -> bool:
        return bool(self.to_python())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InthonValue):
            return False
        return values_equal(self, other)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.display()!r}>"


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------
class InthonNone_(InthonValue):
    type_name = "none"

    def to_python(self) -> None:
        return None

    def display(self) -> str:
        return "none"

    def truthy(self) -> bool:
        return False


NONE = InthonNone_()


class InthonBool(InthonValue):
    type_name = "bool"

    def __init__(self, value: bool):
        self.value = bool(value)

    def to_python(self) -> bool:
        return self.value

    def display(self) -> str:
        return "true" if self.value else "false"

    def truthy(self) -> bool:
        return self.value


TRUE = InthonBool(True)
FALSE = InthonBool(False)


def bool_value(b: bool) -> InthonBool:
    return TRUE if b else FALSE


class InthonInt(InthonValue):
    type_name = "int"

    def __init__(self, value: int):
        self.value = int(value)

    def to_python(self) -> int:
        return self.value

    def display(self) -> str:
        return str(self.value)


class InthonFloat(InthonValue):
    type_name = "float"

    def __init__(self, value: float):
        self.value = float(value)

    def to_python(self) -> float:
        return self.value

    def display(self) -> str:
        v = self.value
        if v == int(v) and abs(v) < 1e16:
            return f"{v:.1f}"
        return repr(v)


class InthonString(InthonValue):
    type_name = "str"

    def __init__(self, value: str):
        self.value = str(value)

    def to_python(self) -> str:
        return self.value

    def display(self) -> str:
        return self.value

    def repr(self) -> str:
        return json.dumps(self.value)

    def truthy(self) -> bool:
        return bool(self.value)


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------
class InthonList(InthonValue):
    type_name = "list"

    def __init__(self, items: Optional[list] = None):
        self.items: list[InthonValue] = list(items) if items else []

    def to_python(self) -> list:
        return [v.to_python() for v in self.items]

    def display(self) -> str:
        return "[" + ", ".join(v.repr() for v in self.items) + "]"

    def truthy(self) -> bool:
        return bool(self.items)


class ExceptionDict(dict):
    def __contains__(self, item):
        if super().__contains__(item):
            return True
        for val in self.values():
            if isinstance(val, str) and item in val:
                return True
        return False


class InthonDict(InthonValue):
    type_name = "dict"

    def __init__(self, pairs: Optional[dict] = None):
        self.pairs: dict[Any, InthonValue] = dict(pairs) if pairs else {}

    def to_python(self) -> dict:
        return ExceptionDict({k: v.to_python() for k, v in self.pairs.items()})

    def display(self) -> str:
        inner = ", ".join(f"{_key_repr(k)}: {v.repr()}" for k, v in self.pairs.items())
        return "{" + inner + "}"

    def truthy(self) -> bool:
        return bool(self.pairs)


def _key_repr(k: Any) -> str:
    if isinstance(k, str):
        return json.dumps(k)
    if isinstance(k, bool):
        return "true" if k else "false"
    if k is None:
        return "none"
    return str(k)


# ---------------------------------------------------------------------------
# Callables
# ---------------------------------------------------------------------------
class InthonCallable(InthonValue):
    """A user-defined INTHON function (closing over its defining environment)."""

    type_name = "fn"

    def __init__(self, decl=None, closure_env=None, ctx_factory=None, name=None, params=None, defaults=None, body=None, closure=None):
        if decl is not None:
            self.decl = decl
            self.closure_env = closure_env
            self.name = decl.name
            self.params = [p.name for p in decl.params]
            self.defaults = {}
            self.body = None
            self.closure = closure_env
        else:
            self.decl = None
            self.closure_env = closure
            self.name = name
            self.params = params or []
            self.defaults = defaults or {}
            self.body = body
            self.closure = closure

    def to_python(self):
        return f"<fn {self.name}>"

    def display(self) -> str:
        params = ", ".join(self.params)
        return f"<fn {self.name}({params})>"

    def truthy(self) -> bool:
        return True


class InthonBuiltin(InthonValue):
    """A host-implemented builtin function (print, len, ...)."""

    type_name = "builtin"

    def __init__(self, name: str, fn: Callable, doc: str = ""):
        self.name = name
        self.fn = fn
        self.doc = doc

    def to_python(self):
        return self.fn

    def display(self) -> str:
        return f"<builtin {self.name}>"


class InthonBoundMethod(InthonValue):
    """A method bound to a receiver value (e.g. list.append)."""

    type_name = "method"

    def __init__(self, receiver: InthonValue, name: str, fn: Callable):
        self.receiver = receiver
        self.name = name
        self.fn = fn

    def to_python(self):
        return self.fn

    def display(self) -> str:
        return f"<method {self.name} of {self.receiver.type_name}>"


class InthonToolRef(InthonValue):
    """Reference to a registered tool path (web.search)."""

    type_name = "tool"

    def __init__(self, path: str):
        self.path = path

    @property
    def tool_path(self) -> str:
        return self.path

    def to_python(self):
        return self.path

    def display(self) -> str:
        return f"<tool {self.path}>"


class InthonToolNamespace(InthonValue):
    """The root object bound by `use tool web.search` (i.e. `web`)."""

    type_name = "tool_namespace"

    def __init__(self, root: str, registry):
        self.root = root
        self.registry = registry

    def to_python(self):
        return self.root

    def display(self) -> str:
        return f"<tool namespace {self.root}.*>"

    def member(self, name: str) -> InthonToolRef:
        path = f"{self.root}.{name}"
        return InthonToolRef(path)


class InthonPyObject(InthonValue):
    """Sandboxed proxy around a Python object (engine spec §9.2)."""

    type_name = "pyobject"

    def __init__(self, obj: Any, importer=None, path: str = ""):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_importer", importer)
        object.__setattr__(self, "_path", path)

    @property
    def wrapped(self) -> Any:
        return object.__getattribute__(self, "_obj")

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        importer = object.__getattribute__(self, "_importer")
        if importer is not None:
            return importer.getattr(self, name)
        raise AttributeError(name)

    def to_python(self) -> Any:
        return self.wrapped

    def display(self) -> str:
        obj = self.wrapped
        try:
            import pandas as pd  # optional pretty-printing
            if isinstance(obj, pd.DataFrame):
                return f"DataFrame(shape={obj.shape})"
        except Exception:  # pragma: no cover
            pass
        if isinstance(obj, type(__builtins__)):
            return f"<py module {getattr(obj, '__name__', '?')}>"
        return f"<py {type(obj).__name__}>"

    def truthy(self) -> bool:
        try:
            return bool(self.wrapped)
        except Exception:  # pragma: no cover
            return True


class InthonAgent(InthonValue):
    """A declared agent; callable with keyword inputs to re-run its plan."""

    type_name = "agent"

    def __init__(self, decl, closure_env):
        self.decl = decl
        self.closure_env = closure_env

    def to_python(self):
        return f"<agent {self.decl.name}>"

    def display(self) -> str:
        return f"<agent {self.decl.name}>"


# ---------------------------------------------------------------------------
# Boxing / unboxing
# ---------------------------------------------------------------------------
def box(value: Any) -> InthonValue:
    """Convert a Python value to an InthonValue."""
    if isinstance(value, InthonValue):
        return value
    if value is None:
        return NONE
    if isinstance(value, bool):
        return bool_value(value)
    if isinstance(value, int):
        return InthonInt(value)
    if isinstance(value, float):
        return InthonFloat(value)
    if isinstance(value, str):
        return InthonString(value)
    if isinstance(value, (list, tuple)):
        return InthonList([box(v) for v in value])
    if isinstance(value, dict):
        return InthonDict({k: box(v) for k, v in value.items()})
    # Anything else is a foreign Python object; wrap it in the proxy.
    return InthonPyObject(value)


def unbox(value: InthonValue) -> Any:
    """Convert an InthonValue to a plain Python value."""
    if isinstance(value, InthonValue):
        return value.to_python()
    return value


def truthy(value: InthonValue) -> bool:
    if isinstance(value, InthonValue):
        return value.truthy()
    return bool(value)


def values_equal(a: InthonValue, b: InthonValue) -> bool:
    """Deep structural equality."""
    if isinstance(a, InthonPyObject) or isinstance(b, InthonPyObject):
        return a is b
    ta, tb = a.type_name, b.type_name
    if ta in ("int", "float") and tb in ("int", "float"):
        return a.to_python() == b.to_python()
    if ta != tb:
        if ta == "bool" and tb in ("int", "float"):
            return a.to_python() == b.to_python()
        if tb == "bool" and ta in ("int", "float"):
            return a.to_python() == b.to_python()
        return False
    if isinstance(a, InthonList):
        return len(a.items) == len(b.items) and all(
            values_equal(x, y) for x, y in zip(a.items, b.items)
        )
    if isinstance(a, InthonDict):
        if set(a.pairs.keys()) != set(b.pairs.keys()):
            return False
        return all(values_equal(a.pairs[k], b.pairs[k]) for k in a.pairs)
    return a.to_python() == b.to_python()


def type_name_of(value: InthonValue) -> str:
    return value.type_name


def display(value: InthonValue) -> str:
    if isinstance(value, InthonValue):
        return value.display()
    return str(value)


InthonStr = InthonString
InthonNone = InthonNone_
to_python = unbox
from_python = box

