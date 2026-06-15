from __future__ import annotations
import importlib
from typing import Any
from .allowlist import AllowlistConfig, BLOCKED_ATTRIBUTES
from ..runtime.errors import IntHonRuntimeError
from .exception_wrap import wrap_python_exception


class PyBridgeError(IntHonRuntimeError):
    pass


class SafeModuleImporter:
    """
    Safe module importer enforcing allowlists and attribute blocks.
    """

    def __init__(self, config: AllowlistConfig | None = None, ctx: Any = None) -> None:
        self._config = config or AllowlistConfig()
        self._cache: dict[str, Any] = {}
        self._ctx = ctx

        # Determine sandbox mode
        sandbox_mode = "soft"
        if ctx and hasattr(ctx, "config") and ctx.config:
            sandbox_mode = ctx.config.get("pybridge", {}).get("sandbox", "soft")
        else:
            # Fallback: load directly
            try:
                import tomllib
                from pathlib import Path

                for path in [Path.cwd(), *Path.cwd().parents]:
                    toml_path = path / "inthon.toml"
                    if toml_path.is_file():
                        with open(toml_path, "rb") as f:
                            cfg = tomllib.load(f)
                            sandbox_mode = cfg.get("pybridge", {}).get(
                                "sandbox", "soft"
                            )
                        break
            except Exception:
                pass

        self._sandbox_mode = sandbox_mode
        self._subprocess_bridge = None
        if sandbox_mode == "strict":
            from .subprocess_bridge import SubprocessPyBridge

            self._subprocess_bridge = SubprocessPyBridge()

    def import_module(self, module_path: str, alias: str | None = None) -> Any:
        if not self._config.is_allowed(module_path):
            raise PyBridgeError(
                f"INTHON_PYBRIDGE_001: Module '{module_path}' is not permitted under the active policy. "
                f"If you need this module, add it to [pybridge] allowed_modules."
            )

        if self._sandbox_mode == "strict":
            return self._subprocess_bridge.import_module(module_path, alias)
        if module_path in self._cache:
            return self._cache[module_path]
        try:
            mod = importlib.import_module(module_path)
        except ImportError as exc:
            raise PyBridgeError(
                f"INTHON_PYBRIDGE_002: Module '{module_path}' could not be imported. "
                f"Install it with: pip install {module_path.split('.')[0]}"
            ) from exc
        blocked = BLOCKED_ATTRIBUTES.get(module_path.split(".")[0], frozenset())
        wrapper = SafeModuleWrapper(mod, module_path, blocked)
        self._cache[module_path] = wrapper
        return wrapper


class SafeModuleWrapper:
    """
    Thin proxy around a Python module that blocks access to
    denied attributes and wraps all return values as InthonValue.
    """

    def __init__(self, module: Any, path: str, blocked_attrs: frozenset[str]) -> None:
        self._module = module
        self._path = path
        self._blocked = blocked_attrs

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise PyBridgeError(
                f"INTHON_PYBRIDGE_003: Access to private attribute '{name}' is denied."
            )
        if name in self._blocked:
            raise PyBridgeError(
                f"INTHON_PYBRIDGE_004: Attribute '{self._path}.{name}' is blocked."
            )
        attr = getattr(self._module, name)
        if callable(attr):
            return _wrap_callable(attr, self._path)
        from ..runtime.values import from_python

        return from_python(attr, self._path)

    def __repr__(self) -> str:
        return f"<IntHon PyModule: {self._path}>"


def _wrap_callable(fn: Any, source: str) -> Any:
    """Returns a wrapper that converts return values to InthonValue."""
    from ..runtime.values import from_python

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Unpack InthonValue arguments to Python equivalents before calling
        from ..runtime.values import to_python, InthonValue

        unpacked_args = [
            to_python(a) if isinstance(a, InthonValue) else a for a in args
        ]
        unpacked_kwargs = {
            k: (to_python(v) if isinstance(v, InthonValue) else v)
            for k, v in kwargs.items()
        }
        try:
            result = fn(*unpacked_args, **unpacked_kwargs)
            return from_python(result, source)
        except Exception as exc:
            raise wrap_python_exception(exc, source, fn.__name__)

    wrapper.__name__ = fn.__name__
    return wrapper
