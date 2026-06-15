from __future__ import annotations
from ..runtime.errors import IntHonRuntimeError


class PyBridgeError(IntHonRuntimeError):
    pass


def wrap_python_exception(exc: Exception, source: str, func_name: str) -> Exception:
    return PyBridgeError(
        f"INTHON_PYBRIDGE_005: Exception in {source}.{func_name}: {exc}"
    )
