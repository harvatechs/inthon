from __future__ import annotations
from dataclasses import dataclass, field
import types
import builtins


DEFAULT_ALLOWED_MODULES = frozenset(
    {
        "inthon",
        "pandas",
        "numpy",
        "torch",
        "transformers",
        "sklearn",
        "scipy",
        "matplotlib",
        "seaborn",
        "plotly",
        "polars",
        "pyarrow",
        "json",
        "math",
        "datetime",
        "collections",
        "itertools",
        "functools",
        "string",
        "re",
        "pathlib",
        "typing",
        "dataclasses",
        "enum",
        "abc",
        "copy",
        "textwrap",
        "base64",
        "hashlib",
        "hmac",
        "uuid",
        "urllib.parse",
    }
)

HARD_DENIED_MODULES = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "shutil",
        "socket",
        "asyncio",
        "threading",
        "multiprocessing",
        "ctypes",
        "cffi",
        "importlib",
        "builtins",
        "code",
        "codeop",
        "inspect",
        "ast",
        "pickle",
        "shelve",
        "marshal",
        "compileall",
        "dis",
        "gc",
        "weakref",
        "signal",
        "mmap",
        "pty",
        "tty",
        "termios",
    }
)

BLOCKED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "pandas": frozenset({"eval", "read_clipboard"}),
    "numpy": frozenset({"frompyfunc"}),
    "io": frozenset({"open", "FileIO", "open_code"}),
}


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
        if root in HARD_DENIED_MODULES:
            return False
        if root in self.extra_denied:
            return False
        if root in DEFAULT_ALLOWED_MODULES or root in self.extra_allowed:
            return True
        return False


def is_safe_attribute_access(parent: object, attr_name: str, value: object) -> bool:
    """
    Validate that accessing attr_name on parent, resulting in value, is safe.
    """
    if attr_name.startswith("_"):
        return False

    # 1. Check parent module's BLOCKED_ATTRIBUTES
    if parent is not None:
        parent_mod = None
        if type(parent).__name__ == "SafeModuleWrapper":
            try:
                parent_mod = object.__getattribute__(parent, "_path")
            except AttributeError:
                pass
        else:
            try:
                parent_mod = object.__getattribute__(parent, "__name__")
            except AttributeError:
                pass

        if isinstance(parent_mod, str):
            parent_root = parent_mod.split(".")[0]
            blocked = BLOCKED_ATTRIBUTES.get(parent_root, frozenset())
            if attr_name in blocked:
                return False

    # Check if value is a module
    if isinstance(value, types.ModuleType):
        mod_name = value.__name__.split(".")[0]
        # Include nt, posix, _thread as denied implementation modules
        if mod_name in HARD_DENIED_MODULES or mod_name in ("nt", "posix", "_thread"):
            return False

    # Check if value itself is a dangerous builtin function
    blocked_builtins = {
        "exec",
        "eval",
        "compile",
        "__import__",
        "open",
        "breakpoint",
        "input",
    }
    for b_name in blocked_builtins:
        if hasattr(builtins, b_name):
            if value is getattr(builtins, b_name):
                return False

    # Check if value is a builtin function with a blocked name (like io.open)
    if type(value).__name__ in (
        "builtin_function_or_method",
        "wrapper_descriptor",
        "method-wrapper",
    ):
        val_name = getattr(value, "__name__", None)
        if val_name in blocked_builtins:
            return False

    # Check __module__ attribute if present
    val_mod = getattr(value, "__module__", None)
    if isinstance(val_mod, str):
        val_mod_root = val_mod.split(".")[0]
        if val_mod_root in HARD_DENIED_MODULES or val_mod_root in (
            "nt",
            "posix",
            "_thread",
        ):
            if val_mod_root == "builtins":
                # For builtins module, check if the function name is in blocked_builtins
                val_name = getattr(value, "__name__", None)
                if val_name in blocked_builtins:
                    return False
            else:
                return False

    return True


def is_safe_callable(obj: object) -> bool:
    """
    Validate that calling obj is safe.
    """
    blocked_builtins = {
        "exec",
        "eval",
        "compile",
        "__import__",
        "open",
        "breakpoint",
        "input",
    }
    if obj in blocked_builtins:
        return False
    for b_name in blocked_builtins:
        if hasattr(builtins, b_name):
            if obj is getattr(builtins, b_name):
                return False

    # Check if obj is a builtin function with a blocked name
    if type(obj).__name__ in (
        "builtin_function_or_method",
        "wrapper_descriptor",
        "method-wrapper",
    ):
        val_name = getattr(obj, "__name__", None)
        if val_name in blocked_builtins:
            return False

    # Check __module__ attribute if present
    val_mod = getattr(obj, "__module__", None)
    if isinstance(val_mod, str):
        val_mod_root = val_mod.split(".")[0]
        if val_mod_root in HARD_DENIED_MODULES or val_mod_root in (
            "nt",
            "posix",
            "_thread",
        ):
            if val_mod_root == "builtins":
                # For builtins module, check if the function name is in blocked_builtins
                val_name = getattr(obj, "__name__", None)
                if val_name in blocked_builtins:
                    return False
            else:
                return False

    # Check if it is a module
    if isinstance(obj, types.ModuleType):
        return False

    return True
