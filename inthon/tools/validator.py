from __future__ import annotations
from typing import Any
from pydantic import create_model
from .schema import ToolSpec
from ..runtime.errors import ToolCallError


def map_type_string(t_str: str) -> Any:
    t_str = t_str.strip()
    if t_str == "int":
        return int
    if t_str == "float":
        return float
    if t_str == "str":
        return str
    if t_str == "bool":
        return bool
    if t_str == "none":
        return type(None)
    if t_str.startswith("list"):
        return list
    if t_str.startswith("dict"):
        return dict
    return Any


def validate_tool_args(
    spec: ToolSpec, args: list[Any], kwargs: dict[str, Any]
) -> dict[str, Any]:
    param_names = list(spec.input_schema.keys())
    merged_kwargs = {}

    if len(args) > len(param_names):
        raise ToolCallError(
            f"INTHON_TOOL_003: Too many positional arguments for tool '{spec.name}' "
            f"(expected at most {len(param_names)}, got {len(args)})"
        )

    for i, arg_val in enumerate(args):
        name = param_names[i]
        merged_kwargs[name] = arg_val

    for k, v in kwargs.items():
        if k in merged_kwargs:
            raise ToolCallError(
                f"INTHON_TOOL_003: Multiple values for argument '{k}' in tool '{spec.name}'"
            )
        if k not in param_names:
            raise ToolCallError(
                f"INTHON_TOOL_003: Unexpected argument '{k}' for tool '{spec.name}'"
            )
        merged_kwargs[k] = v

    fields: dict[str, Any] = {}
    for name, schema in spec.input_schema.items():
        py_type = map_type_string(schema.type)
        if schema.required and schema.default is None:
            fields[name] = (py_type, ...)
        else:
            fields[name] = (py_type, schema.default)

    DynamicModel = create_model(f"ToolArgs_{spec.name.replace('.', '_')}", **fields)

    try:
        validated = DynamicModel(**merged_kwargs)
        return validated.model_dump()
    except Exception as e:
        raise ToolCallError(
            f"INTHON_TOOL_003: Schema validation failed for tool '{spec.name}': {e}"
        )
