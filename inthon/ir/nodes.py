from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Union

@dataclass
class IRProgram:
    imports: list[IRImport]
    body: list[IRNode]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class IRImport:
    kind: str  # "tool" | "py" | "memory"
    path: str
    alias: str | None = None

@dataclass
class IRAssign:
    target: str
    value: IRValue

@dataclass
class IRReturn:
    value: IRValue | None

@dataclass
class IRToolCall:
    tool: str  # fully qualified: "web.search"
    args: list[IRValue]
    kwargs: dict[str, IRValue]
    result_var: str | None = None

@dataclass
class IRPyCall:
    module: str  # e.g. "pandas"
    attr_chain: list[str]  # e.g. ["read_csv"]
    args: list[IRValue]
    kwargs: dict[str, IRValue]
    result_var: str | None = None

@dataclass
class IRAgentBlock:
    name: str
    goal: str | None
    policy: dict[str, Any]
    plan: list[IRNode]

@dataclass
class IRApproval:
    target: str
    action: str

@dataclass
class IRConditional:
    condition: IRValue
    then_branch: list[IRNode]
    else_branch: list[IRNode] | None

@dataclass
class IRLoop:
    kind: str  # "for" | "while"
    var: str | None  # for-loop variable
    iterable: IRValue | None
    condition: IRValue | None
    body: list[IRNode]

# ─── IR Values (leaf nodes in expressions) ────────────────────────────────────
@dataclass
class IRLiteral:
    value: int | float | str | bool | None
    type_hint: str

@dataclass
class IRVar:
    name: str

@dataclass
class IRBinaryOp:
    op: str
    left: IRValue
    right: IRValue

@dataclass
class IRList:
    elements: list[IRValue]

@dataclass
class IRDict:
    pairs: list[tuple[IRValue, IRValue]]

@dataclass
class IRCall:
    callee: IRValue
    args: list[IRValue]
    kwargs: dict[str, IRValue]

IRValue = Union[IRLiteral, IRVar, IRBinaryOp, IRList, IRDict, IRToolCall, IRPyCall, IRCall]
IRNode  = Union[IRAssign, IRReturn, IRToolCall, IRPyCall, IRAgentBlock, IRApproval, IRConditional, IRLoop]

def _to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        d = {}
        for f in obj.__dataclass_fields__:
            d[f] = _to_dict(getattr(obj, f))
        d["__ir_type__"] = type(obj).__name__
        return d
    if isinstance(obj, list):
        return [_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [_to_dict(x) for x in obj]
    return obj

def ir_to_json(program: IRProgram, indent: int = 2) -> str:
    """Serialize IR to canonical JSON."""
    return json.dumps(_to_dict(program), indent=indent)

def _from_dict(d: Any) -> Any:
    if isinstance(d, dict):
        if "__ir_type__" in d:
            ir_type = d["__ir_type__"]
            cls = globals()[ir_type]
            kwargs = {}
            for k, v in d.items():
                if k != "__ir_type__":
                    kwargs[k] = _from_dict(v)
            return cls(**kwargs)
        else:
            return {k: _from_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_from_dict(x) for x in d]
    return d

def ir_from_json(raw: str) -> IRProgram:
    """Deserialise canonical JSON back to IR. Round-trip safe."""
    data = json.loads(raw)
    return _from_dict(data)
