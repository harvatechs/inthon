"""Tool specification model (spec: tool-spec)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class ToolParam:
    name: str
    type: str = "any"           # str|int|float|bool|list|dict|any|str|list (union via '|')
    required: bool = True
    default: Any = None
    description: str = ""


@dataclass
class ToolArgSchema:
    type: str  # e.g., "str", "int", "list[str]"
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class ToolCostModel:
    base_usd: float = 0.0
    per_call_usd: float = 0.002
    per_token_usd: float = 0.0


@dataclass
class ToolResult:
    tool: str
    success: bool
    output: Any
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolSpec:
    """A registered tool: schema + handlers + cost model + side effects."""

    path: str
    description: str = ""
    params: tuple = ()                    # tuple[ToolParam]
    returns: str = "any"
    side_effects: tuple = ()              # e.g. ("network",), ("email_send",)
    permissions: tuple = ()               # capabilities required, e.g. ("network",)
    cost_usd: float = 0.0                 # charged per call
    latency_ms: float = 0.0               # simulated latency recorded in trace
    handler: Optional[Callable] = None    # real implementation
    mock: Optional[Callable] = None       # deterministic offline implementation
    version: str = "1.0"
    requires_approval: bool = False

    @property
    def name(self) -> str:
        return self.path

    @property
    def input_schema(self) -> dict[str, ToolArgSchema]:
        return {
            p.name: ToolArgSchema(
                type=p.type,
                description=p.description,
                required=p.required,
                default=p.default
            )
            for p in self.params
        }

    @property
    def pure(self) -> bool:
        return not self.side_effects

    @property
    def output_schema(self) -> dict[str, str]:
        if self.path == "web.search":
            return {"results": "list[dict]"}
        return {"result": self.returns}

    def param_names(self) -> list[str]:
        return [p.name for p in self.params]

    def required_params(self) -> list[str]:
        return [p.name for p in self.params if p.required]

    def to_json(self) -> dict:
        return {
            "path": self.path,
            "description": self.description,
            "params": [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "description": p.description,
                }
                for p in self.params
            ],
            "returns": self.returns,
            "side_effects": list(self.side_effects),
            "permissions": list(self.permissions),
            "cost_usd": self.cost_usd,
            "version": self.version,
        }
