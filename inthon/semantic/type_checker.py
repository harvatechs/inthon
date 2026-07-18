"""Conservative static type inference for warnings (AS-09..AS-12).

Gradual typing contract:
  * annotations are always enforced at runtime (hard errors)
  * the static checker only reports when both sides are *known* and clearly
    incompatible; anything unknown passes silently
  * warnings become errors under strict_types
"""

from __future__ import annotations

from typing import Optional
from .scope import Scope

from ..ast import nodes

#: canonical type tags: int | float | str | bool | none | list | dict | fn | agent | tool | py | any
NUM = {"int", "float"}

_BUILTIN_RETURNS = {
    "len": "int",
    "int": "int",
    "float": "float",
    "str": "str",
    "bool": "bool",
    "type": "str",
    "range": "list",
    "abs": "num",
    "sum": "num",
    "round": "num",
    "floor": "int",
    "ceil": "int",
    "sqrt": "float",
    "sorted": "list",
    "keys": "list",
    "values": "list",
    "items": "list",
    "append": "list",
    "push": "list",
    "join": "str",
    "split": "list",
    "upper": "str",
    "lower": "str",
    "strip": "str",
    "replace": "str",
    "starts_with": "bool",
    "ends_with": "bool",
    "contains": "bool",
    "json_encode": "str",
    "json_decode": "any",
    "now": "float",
    "min": "num",
    "max": "num",
}


def type_of_typeexpr(t: nodes.TypeExpr) -> str:
    if isinstance(t, nodes.NamedType):
        if t.name in ("int", "float"):
            return t.name
        if t.name in ("str", "bool"):
            return t.name
        if t.name == "none":
            return "none"
        return "any"
    if isinstance(t, nodes.GenericType):
        return t.name if t.name in ("list", "dict", "tuple", "set") else "any"
    if isinstance(t, nodes.FnType):
        return "fn"
    return "any"


def compatible(declared: str, actual: str) -> bool:
    if declared == "any" or actual == "any":
        return True
    if declared == actual:
        return True
    if declared == "float" and actual == "int":
        return True
    if declared == "num" and actual in NUM:
        return True
    if declared in ("list", "tuple", "set") and actual == "list":
        return True
    return False


class TypeEnv:
    """Flow-sensitive-ish name→type map layered over scopes."""

    def __init__(self, parent: Optional["TypeEnv"] = None):
        self.parent = parent
        self.types: dict[str, str] = {}

    def set(self, name: str, t: str):
        self.types[name] = t

    def get(self, name: str) -> str:
        env: Optional[TypeEnv] = self
        while env is not None:
            if name in env.types:
                return env.types[name]
            env = env.parent
        return "any"


def infer_expr_type(expr: nodes.Expression, tenv: TypeEnv, fn_returns: dict) -> str:
    if isinstance(expr, nodes.IntLiteral):
        return "int"
    if isinstance(expr, nodes.FloatLiteral):
        return "float"
    if isinstance(expr, (nodes.StringLiteral, nodes.InterpString)):
        return "str"
    if isinstance(expr, nodes.BoolLiteral):
        return "bool"
    if isinstance(expr, nodes.NoneLiteral):
        return "none"
    if isinstance(expr, nodes.ListExpr):
        return "list"
    if isinstance(expr, nodes.DictExpr):
        return "dict"
    if isinstance(expr, nodes.Identifier):
        return tenv.get(expr.name)
    if isinstance(expr, nodes.UnaryOp):
        if expr.op == "not":
            return "bool"
        return infer_expr_type(expr.operand, tenv, fn_returns)
    if isinstance(expr, nodes.BinaryOp):
        if expr.op in ("==", "!=", "<", "<=", ">", ">=", "and", "or", "not"):
            return "bool"
        lt = infer_expr_type(expr.left, tenv, fn_returns)
        rt = infer_expr_type(expr.right, tenv, fn_returns)
        if expr.op == "+" and (lt == "str" and rt == "str"):
            return "str"
        if expr.op == "+" and lt == "list" and rt == "list":
            return "list"
        if lt == "float" or rt == "float" or expr.op == "/":
            return "float"
        if lt in NUM and rt in NUM:
            return "int"
        return "any"
    if isinstance(expr, nodes.CallExpr):
        callee = expr.callee
        if isinstance(callee, nodes.Identifier):
            if callee.name in _BUILTIN_RETURNS:
                return _BUILTIN_RETURNS[callee.name]
            if callee.name in fn_returns:
                return fn_returns[callee.name]
        if isinstance(callee, nodes.MemberExpr):
            # tool returns like "list[dict]" → "list"
            root = _root_name(callee)
            if root is not None:
                return "any"
        return "any"
    if isinstance(expr, nodes.RecallExpr):
        return "any"
    if isinstance(expr, nodes.MemberExpr):
        return "any"
    if isinstance(expr, nodes.IndexExpr):
        return "any"
    return "any"


def _root_name(member: nodes.MemberExpr) -> Optional[str]:
    node = member.object
    while isinstance(node, nodes.MemberExpr):
        node = node.object
    if isinstance(node, nodes.Identifier):
        return node.name
    return None


def infer_type(expr: nodes.Expression, scope: Scope) -> str:
    # Handle list and dict nested typing
    if isinstance(expr, nodes.ListExpr):
        if not expr.elements:
            return "list[any]"
        elem_types = {infer_type(e, scope) for e in expr.elements}
        inner = elem_types.pop() if len(elem_types) == 1 else "any"
        return f"list[{inner}]"
    if isinstance(expr, nodes.DictExpr):
        if not expr.pairs:
            return "dict[any, any]"
        key_types = {infer_type(p[0], scope) for p in expr.pairs}
        val_types = {infer_type(p[1], scope) for p in expr.pairs}
        kt = key_types.pop() if len(key_types) == 1 else "any"
        vt = val_types.pop() if len(val_types) == 1 else "any"
        return f"dict[{kt}, {vt}]"

    # For other expressions, map scope variables to TypeEnv
    tenv = TypeEnv()
    curr_scope = scope
    curr_env = tenv
    while curr_scope is not None:
        for name, sym in curr_scope.symbols.items():
            if sym.type_annotation is not None:
                t_str = type_of_typeexpr(sym.type_annotation)
                curr_env.set(name, t_str)
        if curr_scope.parent is not None:
            curr_env.parent = TypeEnv()
            curr_env = curr_env.parent
        curr_scope = curr_scope.parent
        
    return infer_expr_type(expr, tenv, {})


def is_subtype(sub: str, sup: str) -> bool:
    return compatible(sup, sub)
