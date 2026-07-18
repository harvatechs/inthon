"""INTHON AST node catalog.

Every grammar production has a corresponding frozen dataclass here.
Nodes carry a source Span for error reporting and support JSON
round-tripping (to_json / from_json).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from typing import Any, Optional

from ..errors import Span


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Node:
    span: Optional[Span] = field(default=None, kw_only=True, compare=False)

    def to_json(self) -> dict:
        out: dict[str, Any] = {"type": type(self).__name__}
        for f in fields(self):
            if f.name == "span":
                continue
            out[f.name] = _json_value(getattr(self, f.name))
        return out

    def to_json_str(self, indent: int = 2) -> str:
        return json.dumps(self.to_json(), indent=indent)


def _json_value(v: Any) -> Any:
    if isinstance(v, Node):
        return v.to_json()
    if isinstance(v, (list, tuple)):
        return [_json_value(x) for x in v]
    if isinstance(v, Span):
        return {"line": v.line, "col": v.col}
    return v


_NODE_REGISTRY: dict[str, type] = {}


def _register(cls):
    _NODE_REGISTRY[cls.__name__] = cls
    return cls


def node_from_json(data: dict) -> "Node":
    cls = _NODE_REGISTRY[data["type"]]
    kwargs = {}
    for f in fields(cls):
        if f.name == "span":
            continue
        kwargs[f.name] = _node_value(getattr(cls, "__dataclass_fields__")[f.name], data.get(f.name))
    return cls(**kwargs)


def _node_value(f, v):
    if v is None:
        return None
    if isinstance(v, dict) and "type" in v:
        return node_from_json(v)
    if isinstance(v, list):
        return [_node_value(f, x) for x in v]
    if isinstance(v, tuple):
        return tuple(_node_value(f, x) for x in v)
    return v


def ast_from_json_str(s: str) -> "Node":
    return node_from_json(json.loads(s))


# ---------------------------------------------------------------------------
# Type expressions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TypeExpr(Node):
    def render(self) -> str:
        raise NotImplementedError


@_register
@dataclass(frozen=True)
class NamedType(TypeExpr):
    name: str = ""

    def render(self) -> str:
        return self.name


@_register
@dataclass(frozen=True)
class GenericType(TypeExpr):
    name: str = ""
    args: tuple = ()

    def render(self) -> str:
        return f"{self.name}[{', '.join(a.render() for a in self.args)}]"


@_register
@dataclass(frozen=True)
class FnType(TypeExpr):
    params: tuple = ()
    ret: Optional[TypeExpr] = None

    def render(self) -> str:
        inner = ", ".join(p.render() for p in self.params)
        return f"fn({inner}) -> {self.ret.render() if self.ret else 'any'}"


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------
@_register
@dataclass(frozen=True)
class Program(Node):
    statements: tuple = ()

    def __init__(self, statements: tuple = (), body: Optional[tuple] = None, span: Optional[Span] = None):
        if body is not None:
            statements = body
        object.__setattr__(self, "statements", tuple(statements))
        object.__setattr__(self, "span", span)

    @property
    def body(self) -> tuple:
        return self.statements


@dataclass(frozen=True)
class Statement(Node):
    pass


@dataclass(frozen=True)
class Expression(Node):
    pass


@_register
@dataclass(frozen=True)
class Block(Node):
    statements: tuple = ()

    @property
    def body(self) -> tuple:
        return self.statements

    def __len__(self) -> int:
        return len(self.statements)

    def __getitem__(self, index: int) -> Any:
        return self.statements[index]

    def __iter__(self) -> Any:
        return iter(self.statements)


# ---------------------------------------------------------------------------
# Imports / capability declarations
# ---------------------------------------------------------------------------
@_register
@dataclass(frozen=True)
class UseTool(Statement):
    path: str = ""

    @property
    def tool_path(self) -> str:
        return self.path


@_register
@dataclass(frozen=True)
class UsePy(Statement):
    module: str = ""
    alias: Optional[str] = None

    @property
    def module_path(self) -> str:
        return self.module


@_register
@dataclass(frozen=True)
class UseMemory(Statement):
    namespace: str = ""
    args: tuple = ()
    kwargs: tuple = ()  # tuple[(name, expr)]


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------
@_register
@dataclass(frozen=True)
class LetDecl(Statement):
    name: str = ""
    type_annotation: Optional[TypeExpr] = None
    value: Optional[Expression] = None

    @property
    def type_ann(self) -> Optional[TypeExpr]:
        return self.type_annotation


@_register
@dataclass(frozen=True)
class ConstDecl(Statement):
    name: str = ""
    type_annotation: Optional[TypeExpr] = None
    value: Optional[Expression] = None

    @property
    def type_ann(self) -> Optional[TypeExpr]:
        return self.type_annotation


@_register
@dataclass(frozen=True)
class Param(Node):
    name: str = ""
    type_annotation: Optional[TypeExpr] = None
    default: Optional[Expression] = None

    @property
    def type_ann(self) -> Optional[TypeExpr]:
        return self.type_annotation


@_register
@dataclass(frozen=True)
class FnDecl(Statement):
    name: str = ""
    params: tuple = ()
    return_type: Optional[TypeExpr] = None
    body: Optional[Block] = None


@_register
@dataclass(frozen=True)
class TypedField(Node):
    name: str = ""
    type_annotation: Optional[TypeExpr] = None


@_register
@dataclass(frozen=True)
class PolicyEntry(Node):
    key: str = ""
    value: Any = None  # literal: str | int | float | bool | None


@_register
@dataclass(frozen=True)
class EvalCriterion(Node):
    name: str = ""
    op: str = ":"  # one of ==, !=, <, <=, >, >=, ':'
    value: Optional[Expression] = None


@_register
@dataclass(frozen=True)
class CriteriaDecl(Statement):
    name: str = ""
    criteria: tuple = ()


@_register
@dataclass(frozen=True)
class RewriterDecl(Statement):
    name: str = ""
    body: Optional[Block] = None


@_register
@dataclass(frozen=True)
class AgentDecl(Statement):
    name: str = ""
    goal: Optional[str] = None
    inputs: tuple = ()      # tuple[TypedField]
    outputs: tuple = ()     # tuple[TypedField]
    imports: tuple = ()     # tuple[UseTool|UsePy|UseMemory]
    policies: tuple = ()    # tuple[PolicyEntry]
    plan: Optional[Block] = None
    criteria: tuple = ()    # tuple[CriteriaDecl]
    rewriters: tuple = ()   # tuple[RewriterDecl]

    @property
    def policy(self) -> Optional[PolicyCompatibilityWrapper]:
        if not self.policies:
            return None
        return PolicyCompatibilityWrapper(self.policies)


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------
@_register
@dataclass(frozen=True)
class IfStmt(Statement):
    condition: Optional[Expression] = None
    then_block: Optional[Block] = None
    else_block: Optional[Node] = None  # Block | IfStmt | None


@_register
@dataclass(frozen=True)
class ForStmt(Statement):
    var: str = ""
    iterable: Optional[Expression] = None
    body: Optional[Block] = None


@_register
@dataclass(frozen=True)
class WhileStmt(Statement):
    condition: Optional[Expression] = None
    body: Optional[Block] = None


@_register
@dataclass(frozen=True)
class ReturnStmt(Statement):
    value: Optional[Expression] = None


@_register
@dataclass(frozen=True)
class BreakStmt(Statement):
    pass


@_register
@dataclass(frozen=True)
class ContinueStmt(Statement):
    pass


@_register
@dataclass(frozen=True)
class ApproveStmt(Statement):
    tool_path: str = ""
    action: str = ""

    @property
    def target(self) -> str:
        return self.tool_path


@_register
@dataclass(frozen=True)
class RememberStmt(Statement):
    value: Optional[Expression] = None
    namespace: str = ""


@_register
@dataclass(frozen=True)
class ForgetStmt(Statement):
    value: Optional[Expression] = None
    namespace: str = ""

    @property
    def key(self) -> Optional[Expression]:
        return self.value


@_register
@dataclass(frozen=True)
class GuardStmt(Statement):
    condition: Optional[Expression] = None


@_register
@dataclass(frozen=True)
class RetryStmt(Statement):
    count: int = 1
    backoff: str = "exponential"  # exponential | linear | fixed
    body: Optional[Block] = None
    catch_name: Optional[str] = None
    catch_body: Optional[Block] = None

    @property
    def catch_block(self) -> Optional[CatchBlockCompatibilityWrapper]:
        if self.catch_name is None and self.catch_body is None:
            return None
        return CatchBlockCompatibilityWrapper(self.catch_name, self.catch_body)


@_register
@dataclass(frozen=True)
class EvalStmt(Statement):
    subject: str = ""               # variable name or 'self'
    rubric: str = ""
    criteria: tuple = ()            # tuple[EvalCriterion]; empty for self-eval form
    rewriter: Optional[str] = None  # for `eval self ... on fail rewrite with X`


@_register
@dataclass(frozen=True)
class PolicyStmt(Statement):
    entries: tuple = ()


@_register
@dataclass(frozen=True)
class ExprStmt(Statement):
    expr: Optional[Expression] = None


@_register
@dataclass(frozen=True)
class AssignStmt(Statement):
    target: Optional[Expression] = None  # Identifier | MemberExpr | IndexExpr
    value: Optional[Expression] = None


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------
@_register
@dataclass(frozen=True)
class IntLiteral(Expression):
    value: int = 0


@_register
@dataclass(frozen=True)
class FloatLiteral(Expression):
    value: float = 0.0


@_register
@dataclass(frozen=True)
class StringLiteral(Expression):
    value: str = ""


@_register
@dataclass(frozen=True)
class InterpString(Expression):
    """String with {expr} interpolations; parts alternate str | Expression."""

    parts: tuple = ()


@_register
@dataclass(frozen=True)
class BoolLiteral(Expression):
    value: bool = False


@_register
@dataclass(frozen=True)
class NoneLiteral(Expression):
    pass


@_register
@dataclass(frozen=True)
class Identifier(Expression):
    name: str = ""

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, Identifier):
            return self.name == other.name
        return super().__eq__(other)


@_register
@dataclass(frozen=True)
class ListExpr(Expression):
    elements: tuple = ()


@_register
@dataclass(frozen=True)
class DictExpr(Expression):
    pairs: tuple = ()  # tuple[(key_expr, value_expr)]


@_register
@dataclass(frozen=True)
class BinaryOp(Expression):
    left: Optional[Expression] = None
    op: str = ""
    right: Optional[Expression] = None


@_register
@dataclass(frozen=True)
class UnaryOp(Expression):
    op: str = ""
    operand: Optional[Expression] = None


@_register
@dataclass(frozen=True)
class CallExpr(Expression):
    callee: Optional[Expression] = None
    args: tuple = ()
    kwargs: tuple = ()  # tuple[(name, expr)]


@_register
@dataclass(frozen=True)
class MemberExpr(Expression):
    object: Optional[Expression] = None
    name: str = ""


@_register
@dataclass(frozen=True)
class IndexExpr(Expression):
    object: Optional[Expression] = None
    index: Optional[Expression] = None


@_register
@dataclass(frozen=True)
class RecallExpr(Expression):
    query: str = ""
    namespace: str = ""


@_register
@dataclass(frozen=True)
class RecallStmt(AssignStmt):
    @property
    def var(self) -> str:
        return self.target.name if self.target else ""

    @property
    def query(self) -> str:
        return self.value.query if self.value else ""

    @property
    def namespace(self) -> str:
        return self.value.namespace if self.value else ""


LetStmt = LetDecl
ConstStmt = ConstDecl
UseToolStmt = UseTool
UsePyStmt = UsePy
UseMemoryStmt = UseMemory


class PolicyCompatibilityWrapper:
    def __init__(self, entries: tuple):
        self.entries = entries
        self._entries = {e.key: e.value for e in entries}

    def __getattr__(self, name: str) -> Any:
        return self._entries.get(name)


class CatchBlockCompatibilityWrapper:
    def __init__(self, name: Optional[str], body: Optional[Block]):
        self.var = name
        self.body = body


PrimitiveType = NamedType
