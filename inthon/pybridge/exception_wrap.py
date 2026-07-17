"""Wrap Python exceptions as INTHON errors (spec §pybridge-errors)."""

from __future__ import annotations

from typing import Optional

from ..errors import InthonPyRuntimeError, Span


def wrap_python_exception(exc: BaseException, where: str, span: Optional[Span] = None) -> InthonPyRuntimeError:
    name = type(exc).__name__
    message = str(exc) or name
    hint = None
    if isinstance(exc, (FileNotFoundError,)):
        hint = "Check the path; filesystem access also requires the filesystem capability."
    elif isinstance(exc, (ValueError, TypeError)):
        hint = "Check argument types; use type(...) to inspect values."
    return InthonPyRuntimeError(
        f"Python {name} in {where}: {message}",
        span=span,
        hint=hint,
    )
