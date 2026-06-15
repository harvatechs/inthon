from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Union
from ..lexer.tokens import Span

# ─── Root ─────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Program:
    body: tuple[Statement, ...]
    span: Span | None = None

# ─── Type Expressions ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class PrimitiveType:
    name: str  # "str" | "int" | "float" | "bool" | "bytes" | "none" | "any"
    span: Span | None = None

@dataclass(frozen=True)
class ListType:
    element: TypeExpr
    span: Span | None = None

@dataclass(frozen=True)
class DictType:
    key: TypeExpr
    value: TypeExpr
    span: Span | None = None

@dataclass(frozen=True)
class TupleType:
    elements: tuple[TypeExpr, ...]
    span: Span | None = None

@dataclass(frozen=True)
class AgentSpecificType:
    name: str  # "DataFrame" | "Tensor" | "Model" etc.
    span: Span | None = None

TypeExpr = Union[PrimitiveType, ListType, DictType, TupleType, AgentSpecificType]

# ─── Expressions ──────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class IntLiteral:
    value: int
    span: Span | None = None

@dataclass(frozen=True)
class FloatLiteral:
    value: float
    span: Span | None = None

@dataclass(frozen=True)
class StringLiteral:
    value: str
    span: Span | None = None

@dataclass(frozen=True)
class BoolLiteral:
    value: bool
    span: Span | None = None

@dataclass(frozen=True)
class NoneLiteral:
    span: Span | None = None

@dataclass(frozen=True)
class Identifier:
    name: str
    span: Span | None = None

@dataclass(frozen=True)
class BinaryOp:
    op: str
    left: Expr
    right: Expr
    span: Span | None = None

@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: Expr
    span: Span | None = None

@dataclass(frozen=True)
class CallExpr:
    callee: Expr
    args: tuple[Expr, ...]
    kwargs: tuple[tuple[str, Expr], ...]
    span: Span | None = None

@dataclass(frozen=True)
class MemberExpr:
    obj: Expr
    attr: str
    span: Span | None = None

@dataclass(frozen=True)
class IndexExpr:
    obj: Expr
    index: Expr
    span: Span | None = None

@dataclass(frozen=True)
class ListExpr:
    elements: tuple[Expr, ...]
    span: Span | None = None

@dataclass(frozen=True)
class DictExpr:
    pairs: tuple[tuple[Expr, Expr], ...]
    span: Span | None = None

Expr = Union[
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral, NoneLiteral,
    Identifier, BinaryOp, UnaryOp, CallExpr, MemberExpr,
    IndexExpr, ListExpr, DictExpr
]

# ─── Statements ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class LetStmt:
    name: str
    type_ann: TypeExpr | None
    value: Expr
    span: Span | None = None

@dataclass(frozen=True)
class ConstStmt:
    name: str
    type_ann: TypeExpr | None
    value: Expr
    span: Span | None = None

@dataclass(frozen=True)
class Param:
    name: str
    type_ann: TypeExpr | None
    default: Expr | None
    span: Span | None = None

@dataclass(frozen=True)
class FnDecl:
    name: str
    params: tuple[Param, ...]
    return_type: TypeExpr | None
    body: tuple[Statement, ...]
    span: Span | None = None

@dataclass(frozen=True)
class TypedField:
    name: str
    type_ann: TypeExpr
    span: Span | None = None

@dataclass(frozen=True)
class PolicyEntry:
    key: str
    value: Union[bool, int, float, str]
    span: Span | None = None

@dataclass(frozen=True)
class PolicyBlock:
    entries: tuple[PolicyEntry, ...]
    span: Span | None = None

@dataclass(frozen=True)
class PlanBlock:
    body: tuple[Statement, ...]
    span: Span | None = None

@dataclass(frozen=True)
class AgentDecl:
    name: str
    goal: str | None
    inputs: tuple[TypedField, ...]
    outputs: tuple[TypedField, ...]
    imports: tuple[Union[UseToolStmt, UsePyStmt], ...]
    policy: PolicyBlock | None
    plan: PlanBlock
    span: Span | None = None

@dataclass(frozen=True)
class ReturnStmt:
    value: Expr | None
    span: Span | None = None

@dataclass(frozen=True)
class ExprStmt:
    expr: Expr
    span: Span | None = None

@dataclass(frozen=True)
class AssignStmt:
    target: str
    value: Expr
    span: Span | None = None

@dataclass(frozen=True)
class IfStmt:
    condition: Expr
    then_branch: tuple[Statement, ...]
    else_branch: tuple[Statement, ...] | None
    span: Span | None = None

@dataclass(frozen=True)
class ForStmt:
    var: str
    iterable: Expr
    body: tuple[Statement, ...]
    span: Span | None = None

@dataclass(frozen=True)
class WhileStmt:
    condition: Expr
    body: tuple[Statement, ...]
    span: Span | None = None

# ─── Import Statements ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class UseToolStmt:
    tool_path: str
    span: Span | None = None

@dataclass(frozen=True)
class UsePyStmt:
    module_path: str
    alias: str | None
    span: Span | None = None

@dataclass(frozen=True)
class UseMemoryStmt:
    namespace: str
    args: tuple[Expr, ...]
    span: Span | None = None

# ─── Agent Primitives ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ApproveStmt:
    target: str
    action: str
    span: Span | None = None

@dataclass(frozen=True)
class RememberStmt:
    value: Expr
    namespace: str
    span: Span | None = None

@dataclass(frozen=True)
class ForgetStmt:
    key: Expr
    namespace: str
    span: Span | None = None

@dataclass(frozen=True)
class RecallStmt:
    var: str
    query: str
    namespace: str
    span: Span | None = None

@dataclass(frozen=True)
class GuardStmt:
    condition: Expr
    span: Span | None = None

@dataclass(frozen=True)
class CatchBlock:
    var: str
    body: tuple[Statement, ...]
    span: Span | None = None

@dataclass(frozen=True)
class RetryStmt:
    count: int
    backoff: str  # "exponential" | "linear" | "fixed"
    body: tuple[Statement, ...]
    catch_block: CatchBlock | None
    span: Span | None = None

@dataclass(frozen=True)
class EvalCriterion:
    metric: str
    op: str
    threshold: Expr
    span: Span | None = None

@dataclass(frozen=True)
class EvalStmt:
    subject: str
    rubric: str
    criteria: tuple[EvalCriterion, ...]
    span: Span | None = None

Statement = Union[
    LetStmt, ConstStmt, FnDecl, AgentDecl, ReturnStmt,
    ExprStmt, AssignStmt, IfStmt, ForStmt, WhileStmt,
    UseToolStmt, UsePyStmt, UseMemoryStmt, ApproveStmt,
    RememberStmt, ForgetStmt, RecallStmt, GuardStmt,
    RetryStmt, EvalStmt
]
