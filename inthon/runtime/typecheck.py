"""Runtime type-annotation enforcement (gradual typing)."""

from __future__ import annotations

from typing import Optional

from ..ast import nodes
from ..errors import InthonTypeError_, Span
from .values import (
    NONE,
    InthonAgent,
    InthonBool,
    InthonCallable,
    InthonDict,
    InthonFloat,
    InthonInt,
    InthonList,
    InthonPyObject,
    InthonString,
    InthonToolRef,
    InthonValue,
)

_PRIMITIVE_CHECKS = {
    "str": lambda v: isinstance(v, InthonString),
    "int": lambda v: isinstance(v, InthonInt),
    "float": lambda v: isinstance(v, (InthonInt, InthonFloat)),
    "bool": lambda v: isinstance(v, InthonBool),
    "bytes": lambda v: isinstance(v, InthonPyObject),
    "none": lambda v: v is NONE,
    "any": lambda v: True,
}

_AGENT_TYPE_CHECKS = {
    "Goal": lambda v: isinstance(v, InthonString),
    "Plan": lambda v: isinstance(v, (InthonString, InthonList)),
    "ToolCall": lambda v: isinstance(v, InthonDict),
    "ToolResult": lambda v: True,
    "Trace": lambda v: isinstance(v, InthonDict),
    "MemoryRef": lambda v: isinstance(v, (InthonString, InthonDict)),
    "Approval": lambda v: isinstance(v, InthonBool),
    "Policy": lambda v: isinstance(v, InthonDict),
    "DataFrame": lambda v: (
        isinstance(v, InthonPyObject) and type(v.wrapped).__name__ == "DataFrame"
    ),
    "Tensor": lambda v: isinstance(v, InthonPyObject),
    "Model": lambda v: isinstance(v, InthonPyObject),
    "Dataset": lambda v: isinstance(v, (InthonPyObject, InthonList)),
    "Embedding": lambda v: isinstance(v, InthonList),
    "Agent": lambda v: isinstance(v, InthonAgent),
    "Tool": lambda v: isinstance(v, InthonToolRef),
    "Fn": lambda v: isinstance(v, InthonCallable),
}


def value_matches(value: InthonValue, type_expr: nodes.TypeExpr) -> bool:
    if isinstance(type_expr, nodes.NamedType):
        name = type_expr.name
        if name in _PRIMITIVE_CHECKS:
            return _PRIMITIVE_CHECKS[name](value)
        if name in _AGENT_TYPE_CHECKS:
            return _AGENT_TYPE_CHECKS[name](value)
        return True
    if isinstance(type_expr, nodes.GenericType):
        name = type_expr.name
        if name == "list":
            if not isinstance(value, InthonList):
                return False
            inner = type_expr.args[0]
            return all(value_matches(v, inner) for v in value.items[:50])
        if name == "set":
            if not isinstance(value, InthonList):
                return False
            inner = type_expr.args[0]
            return all(value_matches(v, inner) for v in value.items[:50])
        if name == "tuple":
            if not isinstance(value, InthonList):
                return False
            if len(type_expr.args) != len(value.items):
                return False
            return all(value_matches(v, t) for v, t in zip(value.items, type_expr.args))
        if name == "dict":
            if not isinstance(value, InthonDict):
                return False
            key_t, val_t = type_expr.args[0], type_expr.args[1]
            sample = list(value.pairs.items())[:50]
            return all(
                value_matches(_box_key(k), key_t) and value_matches(v, val_t)
                for k, v in sample
            )
        return True
    if isinstance(type_expr, nodes.FnType):
        return isinstance(value, InthonCallable)
    return True


def _box_key(k) -> InthonValue:
    from .values import box

    return box(k)


def check_value_against_type(
    value: InthonValue, type_expr: nodes.TypeExpr, span: Optional[Span]
) -> None:
    if not value_matches(value, type_expr):
        raise InthonTypeError_(
            f"Type mismatch: expected {type_expr.render()}, got {value.type_name} "
            f"({value.display()[:60]})",
            span=span,
            hint="Convert explicitly (str(), int(), float()) or fix the annotation.",
        )
