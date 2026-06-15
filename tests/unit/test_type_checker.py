from inthon.semantic.scope import ScopeChain
from inthon.semantic.type_checker import infer_type, is_subtype
from inthon.ast import nodes as N


def test_type_inference_literals():
    scope = ScopeChain()
    assert infer_type(N.IntLiteral(10), scope) == "int"
    assert infer_type(N.FloatLiteral(3.14), scope) == "float"
    assert infer_type(N.StringLiteral("hello"), scope) == "str"
    assert infer_type(N.BoolLiteral(True), scope) == "bool"
    assert infer_type(N.NoneLiteral(), scope) == "none"


def test_type_inference_lists_dicts():
    scope = ScopeChain()
    list_expr = N.ListExpr(elements=(N.IntLiteral(10), N.IntLiteral(20)))
    assert infer_type(list_expr, scope) == "list[int]"

    dict_expr = N.DictExpr(pairs=((N.StringLiteral("key"), N.IntLiteral(10)),))
    assert infer_type(dict_expr, scope) == "dict[str, int]"


def test_type_inference_bin_ops():
    scope = ScopeChain()
    op = N.BinaryOp(op="+", left=N.IntLiteral(10), right=N.IntLiteral(20))
    assert infer_type(op, scope) == "int"

    op_float = N.BinaryOp(op="+", left=N.IntLiteral(10), right=N.FloatLiteral(3.14))
    assert infer_type(op_float, scope) == "float"

    op_str = N.BinaryOp(op="+", left=N.StringLiteral("a"), right=N.StringLiteral("b"))
    assert infer_type(op_str, scope) == "str"


def test_subtype_relations():
    assert is_subtype("int", "float") is True
    assert is_subtype("int", "int") is True
    assert is_subtype("float", "int") is False
    assert is_subtype("str", "any") is True
