"""
inthon.pybridge.sandbox_worker — Isolated subprocess worker for safe Python execution.

This module is designed to be spawned as a SUBPROCESS (not imported as a module).
It receives JSON-RPC-style requests on stdin and returns results on stdout.

Security measures applied:
1. Import allowlist enforced via a custom __import__ hook.
2. All __dunder__ attributes are stripped from return values.
3. Resource limits applied at OS level (rlimit on Unix, JobObject on Windows).
4. No raw Python objects cross the process boundary — everything is JSON.

Protocol:
    Request  (newline-delimited JSON on stdin):
        {"id": 1, "module": "json", "attr_chain": ["loads"], "args": ["\"hello\""], "kwargs": {}}
    Response (newline-delimited JSON on stdout):
        {"id": 1, "result": "hello", "error": null}
        or
        {"id": 1, "result": null, "error": "ErrorType: message"}
"""

from __future__ import annotations

import json
import sys
import importlib
import builtins
import traceback
from pathlib import Path
from inthon.pybridge.allowlist import GLOBAL_EXTRA_ALLOWED

# Add workspace root to sys.path if not present, so we can import allowlist before replacing __import__
_workspace_root = str(Path(__file__).resolve().parents[2])
if _workspace_root not in sys.path:
    sys.path.append(_workspace_root)
from inthon.pybridge.allowlist import is_safe_attribute_access, is_safe_callable  # noqa: E402


# ── Allowlist (kept in sync with pybridge/allowlist.py) ───────────────────────
_ALLOWED_MODULES_SET = {
    "json",
    "re",
    "math",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "string",
    "textwrap",
    "pathlib",
    "io",
    "csv",
    "hashlib",
    "base64",
    "uuid",
    "time",
    "random",
    "statistics",
    "decimal",
    "fractions",
    "struct",
    "calendar",
    "copy",
    # Data science (available if installed)
    "pandas",
    "numpy",
    "polars",
    "pyarrow",
    "sklearn",
    "scipy",
    # HTTP clients
    "requests",
    "httpx",
    "urllib",
    # ML
    "torch",
    "transformers",
}

# Try loading inthon.toml allowed_modules
try:
    import tomllib
    from pathlib import Path

    for path in [Path.cwd(), *Path.cwd().parents]:
        toml_path = path / "inthon.toml"
        if toml_path.is_file():
            with open(toml_path, "rb") as f:
                cfg = tomllib.load(f)
                extra = cfg.get("pybridge", {}).get("allowed_modules", [])
                _ALLOWED_MODULES_SET.update(extra)
            break
except Exception:
    pass

# Parse command line extra allowed modules
_extra_cli = sys.argv[1:]
_ALLOWED_MODULES_SET.update(_extra_cli)

GLOBAL_EXTRA_ALLOWED.update(_extra_cli)

_ALLOWED_MODULES: frozenset[str] = frozenset(_ALLOWED_MODULES_SET)

_BLOCKED_BUILTINS: frozenset[str] = frozenset(
    {
        "exec",
        "eval",
        "compile",
        "__import__",
        "open",
        "breakpoint",
        "input",
    }
)

_BLOCKED_ATTRS: frozenset[str] = frozenset(
    {
        "__class__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__globals__",
        "__builtins__",
        "__code__",
        "__closure__",
        "__dict__",
        "__module__",
        "__qualname__",
    }
)


# ── Import hook ───────────────────────────────────────────────────────────────
_original_import = builtins.__import__


def _safe_import(name: str, *args, **kwargs):
    root = name.split(".")[0]
    if root not in _ALLOWED_MODULES:
        raise ImportError(
            f"INTHON_SANDBOX: Module '{name}' is not permitted in strict sandbox mode."
        )
    return _original_import(name, *args, **kwargs)


builtins.__import__ = _safe_import


# Disable dangerous builtins safely
def _make_blocked_builtin(name: str):
    def _blocked(*args, **kwargs):
        raise PermissionError(
            f"INTHON_SANDBOX: Builtin '{name}' is disabled in strict sandbox mode."
        )

    return _blocked


for _b in _BLOCKED_BUILTINS:
    if _b == "__import__":
        continue
    if hasattr(builtins, _b):
        setattr(builtins, _b, _make_blocked_builtin(_b))


# ── Result sanitisation ──────────────────────────────────────────────────────


def _sanitise(value) -> object:
    """
    Recursively sanitise a value for JSON serialisation.
    Strips dunder attributes, converts objects to repr strings.
    """
    if isinstance(value, (bool, int, float, str, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_sanitise(v) for v in value]
    if isinstance(value, dict):
        return {
            str(k): _sanitise(v)
            for k, v in value.items()
            if not str(k).startswith("__")
        }
    # Convert any other object to its string representation
    return repr(value)


# ── Apply OS-level resource limits ───────────────────────────────────────────


def _apply_resource_limits(max_memory_mb: int = 512, max_cpu_sec: int = 30) -> None:
    """Apply resource limits. Cross-platform (Unix rlimit / Windows JobObject)."""
    if sys.platform != "win32":
        try:
            import resource

            # Max virtual memory
            resource.setrlimit(
                resource.RLIMIT_AS,
                (max_memory_mb * 1024 * 1024, max_memory_mb * 1024 * 1024),
            )
            # Max CPU time
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (max_cpu_sec, max_cpu_sec),
            )
        except Exception:
            pass  # Best-effort on platforms that don't support it
    else:
        # Windows: use ctypes JobObject to set per-process CPU time limit
        try:
            import ctypes
            import ctypes.wintypes

            JOBOBJECT_EXTENDED_LIMIT_INFORMATION = 9
            JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002

            kernel32 = ctypes.windll.kernel32
            job = kernel32.CreateJobObjectW(None, None)
            if job:
                info = (ctypes.c_ulonglong * 32)()
                info[5] = max_cpu_sec * 10_000_000  # 100ns units
                ctypes.c_uint32(JOB_OBJECT_LIMIT_PROCESS_TIME)
                kernel32.SetInformationJobObject(
                    job,
                    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
                kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())
        except Exception:
            pass  # Best-effort


# ── Main dispatch loop ────────────────────────────────────────────────────────


def main() -> None:
    _apply_resource_limits()

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError as e:
            _respond(0, None, f"JSONDecodeError: {e}")
            continue

        req_id = req.get("id", 0)
        try:
            result = _dispatch(req)
            _respond(req_id, _sanitise(result), None)
        except Exception as e:
            tb = traceback.format_exc(limit=5)
            _respond(req_id, None, f"{type(e).__name__}: {e}\n{tb}")


def _dispatch(req: dict) -> object:
    module_path: str = req["module"]
    attr_chain: list[str] = req.get("attr_chain", [])
    args: list = req.get("args", [])
    kwargs: dict = req.get("kwargs", {})

    # Import module (safe_import hook will block non-allowlisted)
    mod = importlib.import_module(module_path)

    # Validate the imported module
    if not is_safe_attribute_access(None, module_path.split(".")[0], mod):
        raise PermissionError(
            f"INTHON_SANDBOX: Module '{module_path}' is not permitted."
        )

    # Traverse attribute chain
    obj = mod
    for attr in attr_chain:
        next_obj = getattr(obj, attr)
        if not is_safe_attribute_access(obj, attr, next_obj):
            raise AttributeError(
                f"INTHON_SANDBOX: Access to attribute '{attr}' is denied."
            )
        obj = next_obj

    # Call if callable; otherwise return attribute value
    if callable(obj):
        if not is_safe_callable(obj):
            raise PermissionError(
                "INTHON_SANDBOX: Call to dangerous callable is denied."
            )
        return obj(*args, **kwargs)
    return obj


def _respond(req_id: int, result: object, error: str | None) -> None:
    line = json.dumps({"id": req_id, "result": result, "error": error})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
