"""Shared parameter binding for function calls (used by both backends)."""

from __future__ import annotations

from typing import Callable

from ..errors import InthonTypeError_
from .values import InthonValue


def bind_params(
    decl,
    args: list,
    kwargs: dict,
    eval_default: Callable[[object], InthonValue],
    span,
) -> dict:
    """Bind positional/keyword args to declared params; evaluates defaults."""
    params = list(decl.params)
    bound: dict[str, InthonValue] = {}
    if len(args) > len(params):
        raise InthonTypeError_(
            f"fn '{decl.name}' takes {len(params)} argument(s), got {len(args)}",
            span=span,
        )
    for param, value in zip(params, args):
        bound[param.name] = value
    names = [p.name for p in params]
    for key, value in kwargs.items():
        if key in bound:
            raise InthonTypeError_(f"fn '{decl.name}' got '{key}' twice", span=span)
        if key not in names:
            raise InthonTypeError_(
                f"fn '{decl.name}' has no parameter '{key}'", span=span,
                hint=f"Parameters: {', '.join(names)}",
            )
        bound[key] = value
    for param in params:
        if param.name not in bound:
            if param.default is not None:
                bound[param.name] = eval_default(param.default)
            else:
                raise InthonTypeError_(
                    f"fn '{decl.name}' missing required argument '{param.name}'", span=span
                )
    return bound
