"""Safe module importer + proxy attribute rules (spec §pybridge)."""

from __future__ import annotations

import importlib
from typing import Optional, Any

from ..errors import InthonImportError_, InthonPyAttributeError, Span, PyBridgeError
from ..runtime.values import InthonPyObject
from .allowlist import (
    BLOCKED_ATTRIBUTES,
    DEFAULT_ALLOWLIST,
    HARD_DENYLIST,
    is_dunder,
    AllowlistConfig,
)


class SafeModuleImporter:
    """Imports Python modules on behalf of INTHON programs, enforcing the
    allowlist/denylist and wrapping every result in an InthonPyObject proxy."""

    def __init__(
        self,
        allowlist: Optional[set] = None,
        tracer=None,
        config: Optional[AllowlistConfig] = None,
        ctx=None,
    ):
        self.allowlist = (
            set(allowlist) if allowlist is not None else set(DEFAULT_ALLOWLIST)
        )
        self.tracer = tracer
        self._config = config or AllowlistConfig()
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

        # Update global bypass allowed set
        from .allowlist import GLOBAL_EXTRA_ALLOWED

        GLOBAL_EXTRA_ALLOWED.update(self._config.extra_allowed)

        self._sandbox_mode = sandbox_mode
        self._subprocess_bridge = None
        if sandbox_mode == "strict":
            from .subprocess_bridge import SubprocessPyBridge

            self._subprocess_bridge = SubprocessPyBridge(
                extra_allowed=self._config.extra_allowed
            )

    # -- module import -------------------------------------------------------------
    def import_module(self, dotted: str, span: Optional[Span] = None) -> Any:
        if not self._config.is_allowed(dotted):
            raise PyBridgeError(
                f"INTHON_PYBRIDGE_001: Module '{dotted}' is not permitted under the active policy. "
                f"If you need this module, add it to [pybridge] allowed_modules."
            )

        if self._sandbox_mode == "strict":
            if self._subprocess_bridge is None:
                raise PyBridgeError(
                    "INTHON_PYBRIDGE_004: Strict sandbox mode active but SubprocessPyBridge is not initialized."
                )
            return self._subprocess_bridge.import_module(dotted)
        top = dotted.split(".")[0]
        if top in HARD_DENYLIST or dotted in HARD_DENYLIST:
            raise InthonImportError_(
                f"Python module '{dotted}' is blocked by the sandbox",
                span=span,
                hint=f"'{top}' is on the hardcoded denylist and cannot be enabled.",
            )
        if top not in self.allowlist and dotted not in self.allowlist:
            raise InthonImportError_(
                f"Python module '{dotted}' is not in the PyBridge allowlist",
                span=span,
                hint=(
                    f"Add it to [pybridge] allowed_modules in inthon.toml if it is safe. "
                    f"Currently allowed: {', '.join(sorted(self.allowlist))}"
                ),
            )
        try:
            module = importlib.import_module(dotted)
        except ImportError as exc:
            raise InthonImportError_(
                f"Python module '{dotted}' is not installed: {exc}",
                span=span,
                hint=f"Install it with: pip install {top}",
            ) from exc
        if self.tracer is not None:
            self.tracer.emit("import_py", span, module=dotted)
        return InthonPyObject(module, importer=self, path=dotted)

    # -- attribute policy -------------------------------------------------------------
    def check_attribute(
        self, name: str, span: Optional[Span] = None, owner_path: str = ""
    ) -> None:
        if is_dunder(name):
            raise InthonPyAttributeError(
                f"Access to attribute '{name}' is denied (is blocked)",
                span=span,
                hint="Dunder traversal (e.g. __class__.__bases__) is a sandbox escape vector.",
            )
        if name in BLOCKED_ATTRIBUTES:
            raise InthonPyAttributeError(
                f"Access to attribute '{name}' is denied (is blocked)",
                span=span,
                hint=f"'{name}' is on the PyBridge blocked-attribute list.",
            )

    def getattr(
        self, proxy: InthonPyObject, name: str, span: Optional[Span] = None
    ) -> InthonPyObject:
        self.check_attribute(name, span, getattr(proxy, "_path", ""))
        obj = proxy.wrapped
        try:
            attr = getattr(obj, name)
        except AttributeError:
            raise InthonPyAttributeError(
                f"Python object {type(obj).__name__!r} has no attribute '{name}'",
                span=span,
            ) from None

        from .allowlist import is_safe_attribute_access

        if not is_safe_attribute_access(obj, name, attr):
            raise InthonPyAttributeError(
                f"Access to attribute '{name}' is denied (is blocked)",
                span=span,
                hint="Attribute value is considered unsafe under PyBridge security policy.",
            )

        path = getattr(proxy, "_path", "")
        child_path = f"{path}.{name}" if path else name
        return InthonPyObject(attr, importer=self, path=child_path)


_default_importer: Optional[SafeModuleImporter] = None


def default_importer() -> SafeModuleImporter:
    global _default_importer
    if _default_importer is None:
        _default_importer = SafeModuleImporter()
    return _default_importer
