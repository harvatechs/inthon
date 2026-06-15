from __future__ import annotations
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


IRValue = Union[
    IRLiteral, IRVar, IRBinaryOp, IRList, IRDict, IRToolCall, IRPyCall, IRCall
]
IRNode = Union[
    IRAssign,
    IRReturn,
    IRToolCall,
    IRPyCall,
    IRAgentBlock,
    IRApproval,
    IRConditional,
    IRLoop,
    IRCall,
]
