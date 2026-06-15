from __future__ import annotations
from typing import Any
from enum import Enum
from pydantic import BaseModel, Field


class ToolArgSchema(BaseModel):
    type: str  # e.g., "str", "int", "list[str]"
    description: str = ""
    required: bool = True
    default: Any = None


class ToolCostModel(BaseModel):
    base_usd: float = 0.0
    per_call_usd: float = 0.001
    per_token_usd: float = 0.0


class ToolSideEffect(str, Enum):
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    SHELL = "shell"
    EMAIL = "email"
    PAYMENT = "payment"
    DATABASE = "database"
    CALENDAR = "calendar"
    MEMORY = "memory"


class ToolSpec(BaseModel):
    name: str  # fully qualified: "web.search"
    description: str
    input_schema: dict[str, ToolArgSchema]
    output_schema: dict[str, Any]
    side_effects: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    cost_model: ToolCostModel = Field(default_factory=ToolCostModel)
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    tool: str
    success: bool
    output: Any
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
