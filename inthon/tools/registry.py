"""Tool registry: name → ToolSpec, plus the invocation pipeline.

The invocation pipeline is where a tool call crosses the trust boundary:
policy check → budget check → schema validation → execution → cost
accounting → trace emission.  Both execution backends (tree-walker and
InthonVM) share this pipeline, which is what makes their behavior identical.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from dataclasses import dataclass
from ..errors import Span, ToolExecutionError, ToolNotFoundError
from ..runtime.values import box
from .builtin_tools import builtin_tool_specs
from .schema import ToolParam, ToolSpec
from .validator import validate_call


class ToolRegistry:
    def __init__(self):
        self._specs: dict[str, ToolSpec] = {}
        self._lock = threading.Lock()
        self.mock_mode = True

    # -- registration ---------------------------------------------------------
    def register(self, spec: ToolSpec) -> None:
        with self._lock:
            self._specs[spec.path] = spec

    def register_function(
        self,
        path: str,
        fn: Callable,
        *,
        description: str = "",
        params: tuple = (),
        returns: str = "any",
        side_effects: tuple = (),
        permissions: tuple = (),
        cost_usd: float = 0.0,
        mock: Optional[Callable] = None,
    ) -> None:
        """Convenience API for host applications embedding INTHON."""
        self.register(
            ToolSpec(
                path=path,
                description=description,
                params=params,
                returns=returns,
                side_effects=side_effects,
                permissions=permissions,
                cost_usd=cost_usd,
                handler=fn,
                mock=mock or fn,
            )
        )

    # -- lookup -----------------------------------------------------------------
    def has(self, path: str) -> bool:
        return path in self._specs

    def get(self, path: str, span: Optional[Span] = None) -> ToolSpec:
        try:
            return self._specs[path]
        except KeyError:
            known = ", ".join(sorted(self._specs))
            raise ToolNotFoundError(
                f"Unknown tool '{path}'",
                span=span,
                hint=f"Registered tools: {known}",
            ) from None

    def paths(self) -> list[str]:
        return sorted(self._specs)

    def specs(self) -> list[ToolSpec]:
        return [self._specs[p] for p in self.paths()]

    def list_tools(self) -> list[str]:
        return self.paths()

    def get_spec(self, name: str) -> ToolSpec:
        return self.get(name)

    def use_mocks(self, enable: bool) -> None:
        self.mock_mode = enable

    def call(self, path: str, args: list, kwargs: dict) -> ToolResult:
        from ..runtime.context import ExecutionContext
        ctx = ExecutionContext()
        ctx.tools = self
        try:
            res_val = self.invoke(ctx, path, args, kwargs)
            from ..runtime.values import to_python
            return ToolResult(
                tool=path,
                success=True,
                output=to_python(res_val),
            )
        except Exception as e:
            return ToolResult(
                tool=path,
                success=False,
                output=None,
                error=str(e),
            )

    # -- invocation ----------------------------------------------------------------
    def invoke(self, ctx, path: str, args: list, kwargs: dict, span: Optional[Span] = None) -> Any:
        """Full tool-call pipeline.  Returns a boxed INTHON value."""
        spec = self.get(path, span)

        # 1. Policy: is this tool's side effect permitted right now?
        if ctx.policy is not None:
            ctx.policy.check_tool(spec, span)

        # 2. Budget: call count + projected cost.
        if ctx.sandbox is not None:
            ctx.sandbox.before_tool_call(spec, span)

        # 3. Schema validation.
        normalized = validate_call(spec, args, kwargs, span)

        # 4. Execute (mock by default).
        impl = spec.mock if getattr(ctx, "mock", True) else (spec.handler or spec.mock)
        if impl is None:
            raise ToolExecutionError(
                f"Tool '{path}' has no implementation available", span=span
            )
        try:
            result = impl(**normalized)
        except Exception as exc:
            raise ToolExecutionError(
                f"Tool '{path}' failed: {exc}", span=span,
                hint="Wrap the call in retry/catch to handle transient tool failures.",
            ) from exc

        # 5. Accounting + trace.
        if ctx.sandbox is not None:
            ctx.sandbox.after_tool_call(spec)
        if ctx.tracer is not None:
            ctx.tracer.emit(
                "tool_call",
                span,
                tool=path,
                args=_preview(normalized),
                result=_preview(result),
                cost_usd=spec.cost_usd,
                latency_ms=spec.latency_ms,
                mock=bool(getattr(ctx, "mock", True)),
            )
        return box(result)

    def get_spec(self, name: str) -> ToolSpec:
        return self.get(name)

    def call(self, name: str, args: list, kwargs: dict) -> ToolResult:
        import time
        spec = self.get(name)
        mock_mode = getattr(self, "mock_mode", True)
        impl = spec.mock if mock_mode else (spec.handler or spec.mock)
        t0 = time.perf_counter()
        try:
            from .validator import validate_call
            normalized = validate_call(spec, args, kwargs, None)
            output = impl(**normalized) if impl else None
            duration_ms = (time.perf_counter() - t0) * 1000
            return ToolResult(
                tool=name,
                success=True,
                output=output,
                cost_usd=spec.cost_usd,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            return ToolResult(
                tool=name,
                success=False,
                output=None,
                cost_usd=spec.cost_usd,
                duration_ms=duration_ms,
                error=str(exc),
            )



def _preview(value: Any, limit: int = 120) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


_default_registry: Optional[ToolRegistry] = None


def default_registry() -> ToolRegistry:
    """Process-wide registry preloaded with the builtin tool set."""
    global _default_registry
    if _default_registry is None:
        reg = ToolRegistry()
        for spec in builtin_tool_specs():
            reg.register(spec)
        _default_registry = reg
    return _default_registry


@dataclass
class ToolResult:
    tool: str
    success: bool
    output: Any = None
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error: Optional[str] = None

