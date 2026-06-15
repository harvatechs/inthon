from __future__ import annotations
from typing import Any, Callable
from .schema import ToolSpec, ToolResult
from .validator import validate_tool_args
import time


class ToolNotFoundError(Exception):
    pass


class ToolValidationError(Exception):
    pass


class ToolRegistry:
    """
    Central registry for all tool implementations.
    Thread-safe for read operations. Write operations (register)
    should only happen during startup, not during execution.
    """

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._impls: dict[str, Callable] = {}
        self._mock_impls: dict[str, Callable] = {}
        self._mock_mode: bool = False

    def register(
        self,
        spec: ToolSpec,
        impl: Callable,
        mock_impl: Callable | None = None,
    ) -> None:
        self._specs[spec.name] = spec
        self._impls[spec.name] = impl
        if mock_impl:
            self._mock_impls[spec.name] = mock_impl

    def use_mocks(self, enabled: bool = True) -> None:
        self._mock_mode = enabled

    def is_mock_mode(self) -> bool:
        return self._mock_mode

    def get_spec(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise ToolNotFoundError(
                f"INTHON_TOOL_001: Tool '{name}' is not registered. "
                f"Add 'use tool {name}' to your program and ensure the tool is available."
            )
        return self._specs[name]

    def call(self, name: str, args: list[Any], kwargs: dict[str, Any]) -> ToolResult:
        spec = self.get_spec(name)
        # Dynamic schema checks via validate_tool_args
        validated_args = validate_tool_args(spec, args, kwargs)

        impl = self._mock_impls.get(name) if self._mock_mode else self._impls.get(name)
        if not impl:
            raise ToolNotFoundError(f"INTHON_TOOL_002: No implementation for '{name}'")

        t0 = time.perf_counter()
        try:
            output = impl(**validated_args)
            duration_ms = (time.perf_counter() - t0) * 1000
            cost = spec.cost_model.base_usd + spec.cost_model.per_call_usd
            return ToolResult(
                tool=name,
                success=True,
                output=output,
                cost_usd=cost,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            return ToolResult(
                tool=name,
                success=False,
                output=None,
                duration_ms=duration_ms,
                error=str(exc),
            )

    def list_tools(self) -> list[str]:
        return sorted(self._specs.keys())
