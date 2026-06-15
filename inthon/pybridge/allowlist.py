from __future__ import annotations
from dataclasses import dataclass, field

DEFAULT_ALLOWED_MODULES = frozenset({
    "pandas", "numpy", "torch", "transformers", "sklearn",
    "scipy", "matplotlib", "seaborn", "plotly", "polars",
    "pyarrow", "json", "math", "datetime", "collections",
    "itertools", "functools", "string", "re", "pathlib",
    "typing", "dataclasses", "enum", "abc", "copy",
    "textwrap", "base64", "hashlib", "hmac", "uuid",
    "urllib.parse",
})

HARD_DENIED_MODULES = frozenset({
    "os", "sys", "subprocess", "shutil", "socket", "asyncio",
    "threading", "multiprocessing", "ctypes", "cffi",
    "importlib", "builtins", "code", "codeop", "inspect",
    "ast", "pickle", "shelve", "marshal", "compileall",
    "dis", "gc", "weakref", "signal", "mmap", "pty",
    "tty", "termios",
})

BLOCKED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "pandas": frozenset({"eval", "read_clipboard"}),
    "numpy":  frozenset({"frompyfunc"}),
}

@dataclass
class AllowlistConfig:
    extra_allowed: set[str] = field(default_factory=set)
    extra_denied: set[str] = field(default_factory=set)

    def is_allowed(self, module_path: str) -> bool:
        root = module_path.split(".")[0]
        if root in HARD_DENIED_MODULES:
            return False
        if root in self.extra_denied:
            return False
        if root in DEFAULT_ALLOWED_MODULES or root in self.extra_allowed:
            return True
        return False
