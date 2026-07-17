"""PyBridge allowlist / denylist (spec §pybridge, SB-06..SB-10)."""

from __future__ import annotations

#: Modules that may be imported via `use py.<name>` by default.
#: Configurable via [pybridge] allowed_modules in inthon.toml.
DEFAULT_ALLOWLIST: frozenset[str] = frozenset(
    {
        # stdlib — pure computation, no I/O escapes
        "math",
        "statistics",
        "json",
        "re",
        "datetime",
        "time",
        "random",
        "string",
        "textwrap",
        "itertools",
        "functools",
        "collections",
        "operator",
        "decimal",
        "fractions",
        "csv",
        "io",
        "hashlib",
        "base64",
        "urllib.parse",
        "html",
        "unicodedata",
        # data / ML ecosystem (optional, resolved at import time)
        "pandas",
        "numpy",
    }
)

#: Hardcoded denylist — never importable, even if added to the allowlist
#: (SB-07: not configurable).  These are process/machine escape hatches.
HARD_DENYLIST: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "ctypes",
        "socket",
        "pickle",
        "importlib",
        "builtins",
        "shutil",
        "pathlib",
        "signal",
        "multiprocessing",
        "threading",
        "asyncio",
        "runpy",
        "code",
        "codeop",
        "pty",
        "fcntl",
        "mmap",
        "resource",
        "gc",
        "inspect",
        "traceback",
        "linecache",
        "marshal",
        "shelve",
        "dbm",
        "sqlite3",
        "requests",
        "urllib.request",
        "http",
        "ftplib",
        "smtplib",
        "telnetlib",
        "webbrowser",
        "tempfile",
    }
)

GLOBAL_EXTRA_ALLOWED: set[str] = set()

#: Attribute names blocked on every proxied object.  Dunder traversal is
#: blocked separately by the `__x__` pattern rule.
BLOCKED_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "__import__",
        "compile",
        "system",
        "popen",
        "spawnl",
        "spawnv",
        "fork",
        "kill",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "breakpoint",
        "exit",
        "quit",
    }
)


def is_dunder(name: str) -> bool:
    return len(name) >= 4 and name.startswith("__") and name.endswith("__")


import builtins
import types
from dataclasses import dataclass, field

@dataclass
class AllowlistConfig:
    extra_allowed: set[str] = field(default_factory=set)
    extra_denied: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        try:
            import tomllib
            from pathlib import Path

            for path in [Path.cwd(), *Path.cwd().parents]:
                toml_path = path / "inthon.toml"
                if toml_path.is_file():
                    with open(toml_path, "rb") as f:
                        cfg = tomllib.load(f)
                        extra = cfg.get("pybridge", {}).get("allowed_modules", [])
                        self.extra_allowed.update(extra)
                    break
        except Exception:
            pass

    def is_allowed(self, module_path: str) -> bool:
        root = module_path.split(".")[0]
        if root in self.extra_allowed:
            return True
        if root in HARD_DENYLIST:
            return False
        if root in self.extra_denied:
            return False
        if root in DEFAULT_ALLOWLIST:
            return True
        return False


def is_safe_attribute_access(parent: object, attr_name: str, value: object) -> bool:
    if attr_name.startswith("_"):
        return False
    if attr_name in BLOCKED_ATTRIBUTES:
        return False

    # Check if value is a module
    if isinstance(value, types.ModuleType):
        mod_name = value.__name__.split(".")[0]
        if mod_name in GLOBAL_EXTRA_ALLOWED:
            pass
        elif mod_name in HARD_DENYLIST or mod_name in ("nt", "posix", "_thread"):
            return False

    # Check if value itself is a dangerous builtin function
    blocked_builtins = {"exec", "eval", "compile", "__import__", "open", "breakpoint", "input"}
    if value in blocked_builtins:
        return False
    for b_name in blocked_builtins:
        if hasattr(builtins, b_name):
            if value is getattr(builtins, b_name):
                return False

    # Check if value is a builtin function with a blocked name (like io.open)
    if type(value).__name__ in ("builtin_function_or_method", "wrapper_descriptor", "method-wrapper"):
        val_name = getattr(value, "__name__", None)
        if val_name in blocked_builtins:
            return False

    # Check __module__ attribute if present
    val_mod = getattr(value, "__module__", None)
    if isinstance(val_mod, str):
        val_mod_root = val_mod.split(".")[0]
        if val_mod_root in HARD_DENYLIST or val_mod_root in ("nt", "posix", "_thread"):
            if val_mod_root == "builtins":
                val_name = getattr(value, "__name__", None)
                if val_name in blocked_builtins:
                    return False
            else:
                return False
    return True


def is_safe_callable(obj: object) -> bool:
    blocked_builtins = {"exec", "eval", "compile", "__import__", "open", "breakpoint", "input"}
    if obj in blocked_builtins:
        return False
    for b_name in blocked_builtins:
        if hasattr(builtins, b_name):
            if obj is getattr(builtins, b_name):
                return False
    if type(obj).__name__ in ("builtin_function_or_method", "wrapper_descriptor", "method-wrapper"):
        val_name = getattr(obj, "__name__", None)
        if val_name in blocked_builtins:
            return False
    val_mod = getattr(obj, "__module__", None)
    if isinstance(val_mod, str):
        val_mod_root = val_mod.split(".")[0]
        if val_mod_root in HARD_DENYLIST or val_mod_root in ("nt", "posix", "_thread"):
            if val_mod_root == "builtins":
                val_name = getattr(obj, "__name__", None)
                if val_name in blocked_builtins:
                    return False
            else:
                return False
    if isinstance(obj, types.ModuleType):
        return False
    return True

