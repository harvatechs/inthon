from __future__ import annotations
from typing import Any
from ..ast import nodes as N
from .scope import ScopeChain

def _type_expr_to_str(type_ann: N.TypeExpr | None) -> str:
    if type_ann is None:
        return "any"
    if isinstance(type_ann, N.PrimitiveType):
        return type_ann.name
    if isinstance(type_ann, N.ListType):
        return f"list[{_type_expr_to_str(type_ann.element)}]"
    if isinstance(type_ann, N.DictType):
        return f"dict[{_type_expr_to_str(type_ann.key)}, {_type_expr_to_str(type_ann.value)}]"
    if isinstance(type_ann, N.TupleType):
        elements_str = ", ".join(_type_expr_to_str(e) for e in type_ann.elements)
        return f"tuple[{elements_str}]"
    if isinstance(type_ann, N.AgentSpecificType):
        return type_ann.name
    return "any"

def infer_type(expr: N.Expr, scope: ScopeChain) -> str:
    if isinstance(expr, N.IntLiteral):
        return "int"
    if isinstance(expr, N.FloatLiteral):
        return "float"
    if isinstance(expr, N.StringLiteral):
        return "str"
    if isinstance(expr, N.BoolLiteral):
        return "bool"
    if isinstance(expr, N.NoneLiteral):
        return "none"
    if isinstance(expr, N.ListExpr):
        if not expr.elements:
            return "list[any]"
        elem_types = {infer_type(e, scope) for e in expr.elements}
        inner = elem_types.pop() if len(elem_types) == 1 else "any"
        return f"list[{inner}]"
    if isinstance(expr, N.DictExpr):
        if not expr.pairs:
            return "dict[any, any]"
        key_types = {infer_type(p[0], scope) for p in expr.pairs}
        val_types = {infer_type(p[1], scope) for p in expr.pairs}
        kt = key_types.pop() if len(key_types) == 1 else "any"
        vt = val_types.pop() if len(val_types) == 1 else "any"
        return f"dict[{kt}, {vt}]"
    if isinstance(expr, N.BinaryOp):
        if expr.op in ("+", "-", "*", "/", "%", "**"):
            lt = infer_type(expr.left, scope)
            rt = infer_type(expr.right, scope)
            if lt == rt == "int":
                return "int"
            if lt == "float" or rt == "float":
                return "float"
            if lt == rt == "str" and expr.op == "+":
                return "str"
            return "any"
        if expr.op in ("==", "!=", "<", "<=", ">", ">=", "and", "or"):
            return "bool"
    if isinstance(expr, N.UnaryOp):
        if expr.op == "not":
            return "bool"
        if expr.op in ("-", "+"):
            return infer_type(expr.operand, scope)
    if isinstance(expr, N.Identifier):
        sym = scope.lookup(expr.name)
        if sym and sym.type_ann:
            return _type_expr_to_str(sym.type_ann)
        return "any"
    if isinstance(expr, N.CallExpr):
        return "any"
    return "any"

def is_subtype(sub: str, sup: str) -> bool:
    if sup == "any":
        return True
    if sub == sup:
        return True
    if sub == "int" and sup == "float":
        return True
    return False
