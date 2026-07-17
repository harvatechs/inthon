"""Tool argument validation against ToolSpec schemas."""

from __future__ import annotations

from typing import Any

from ..errors import Span, ToolValidationError
from ..runtime.values import InthonValue, unbox
from .schema import ToolSpec

_TYPE_CHECKS = {
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "num": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
    "dict": lambda v: isinstance(v, dict),
    "any": lambda v: True,
    "none": lambda v: v is None,
}


def _type_matches(decl: str, value: Any) -> bool:
    for alt in decl.split("|"):
        alt = alt.strip()
        check = _TYPE_CHECKS.get(alt)
        if check is not None and check(value):
            return True
    return False


def validate_call(spec: ToolSpec, args: list, kwargs: dict, span: Span = None) -> dict:
    """Validate a call against the spec; returns a normalized kwargs dict of
    plain Python values (defaults filled, types coerced)."""
    params = list(spec.params)
    normalized: dict[str, Any] = {}

    arg_values = [unbox(a) for a in args]
    kw_values = {k: unbox(v) for k, v in kwargs.items()}

    if len(arg_values) > len(params):
        raise ToolValidationError(
            f"Tool '{spec.path}' takes at most {len(params)} positional argument(s), got {len(arg_values)}",
            span=span,
            hint=f"Signature: {_signature(spec)}",
        )

    for param, value in zip(params, arg_values):
        normalized[param.name] = value

    for key, value in kw_values.items():
        if key in normalized:
            raise ToolValidationError(
                f"Tool '{spec.path}' got '{key}' both positionally and by keyword",
                span=span,
                hint=f"Signature: {_signature(spec)}",
            )
        if key not in spec.param_names():
            raise ToolValidationError(
                f"Tool '{spec.path}' has no parameter '{key}'",
                span=span,
                hint=f"Valid parameters: {', '.join(spec.param_names()) or '(none)'}",
            )
        normalized[key] = value

    for param in params:
        if param.name not in normalized:
            if param.required:
                raise ToolValidationError(
                    f"Tool '{spec.path}' is missing required argument '{param.name}'",
                    span=span,
                    hint=f"Signature: {_signature(spec)}",
                )
            normalized[param.name] = param.default

    for param in params:
        value = normalized[param.name]
        if value is None and not param.required:
            continue
        if not _type_matches(param.type, value):
            raise ToolValidationError(
                f"Tool '{spec.path}' argument '{param.name}' expects {param.type}, got {type(value).__name__}",
                span=span,
                hint=f"Signature: {_signature(spec)}",
            )

    return normalized


def _signature(spec: ToolSpec) -> str:
    parts = []
    for p in spec.params:
        if p.required:
            parts.append(f"{p.name}: {p.type}")
        else:
            parts.append(f"{p.name}: {p.type} = {p.default!r}")
    return f"{spec.path}({', '.join(parts)})"
