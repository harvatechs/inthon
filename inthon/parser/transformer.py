from __future__ import annotations
import lark
from typing import Any
from ..ast import nodes as N
from ..lexer.tokens import Span

class InthonTransformer(lark.Transformer):
    def __init__(self, filename: str = "<stdin>") -> None:
        super().__init__()
        self._filename = filename

    def _get_span(self, meta: Any) -> Span | None:
        if meta and hasattr(meta, "line"):
            offset = getattr(meta, "start_pos", 0)
            length = getattr(meta, "end_pos", offset) - offset
            return Span(
                file=self._filename,
                line=meta.line,
                col=meta.column,
                offset=offset,
                length=max(1, length)
            )
        return None

    # Helper to wrap list rules that fold
    def _fold_binary(self, children: list[Any], default_span: Span | None = None) -> Any:
        if len(children) == 1:
            return children[0]
        # children are: [left, op, right, op, right, ...]
        # or [left, op, right]
        left = children[0]
        i = 1
        while i < len(children):
            op = str(children[i])
            right = children[i+1]
            span = getattr(left, "span", default_span)
            left = N.BinaryOp(op=op, left=left, right=right, span=span)
            i += 2
        return left

    # --- Program ---
    def program(self, children: list[Any]) -> N.Program:
        return N.Program(body=tuple(children))

    # --- Imports ---
    def use_tool_stmt(self, children: list[Any]) -> N.UseToolStmt:
        return N.UseToolStmt(tool_path=str(children[0]))

    def use_py_stmt(self, children: list[Any]) -> N.UsePyStmt:
        module_path = str(children[0])
        alias = str(children[1]) if len(children) > 1 else None
        return N.UsePyStmt(module_path=module_path, alias=alias)

    def use_memory_stmt(self, children: list[Any]) -> N.UseMemoryStmt:
        namespace = str(children[0])
        # children[1] is (args, kwargs) returned by call_args
        args = children[1][0] if len(children) > 1 and children[1] is not None else ()
        return N.UseMemoryStmt(namespace=namespace, args=args)

    def import_stmt(self, children: list[Any]) -> Any:
        return children[0]

    # --- Variables ---
    def let_stmt(self, children: list[Any]) -> N.LetStmt:
        name = str(children[0])
        type_ann = children[1] if len(children) == 3 else None
        value = children[-1]
        return N.LetStmt(name=name, type_ann=type_ann, value=value)

    def const_stmt(self, children: list[Any]) -> N.ConstStmt:
        name = str(children[0])
        type_ann = children[1] if len(children) == 3 else None
        value = children[-1]
        return N.ConstStmt(name=name, type_ann=type_ann, value=value)

    def type_annotation(self, children: list[Any]) -> Any:
        return children[0]

    # --- Types ---
    def primitive_type(self, children: list[Any]) -> N.PrimitiveType:
        return N.PrimitiveType(name=str(children[0]))

    def collection_type(self, children: list[Any]) -> Any:
        kind = str(children[0])
        if kind == "list":
            return N.ListType(element=children[1])
        elif kind == "dict":
            return N.DictType(key=children[1], value=children[2])
        elif kind == "tuple":
            return N.TupleType(elements=tuple(children[1:]))
        elif kind == "set":
            return N.AgentSpecificType(name=f"set[{children[1].name}]")
        return N.PrimitiveType(name="any")

    def agent_type(self, children: list[Any]) -> N.AgentSpecificType:
        return N.AgentSpecificType(name=str(children[0]))

    # --- Functions ---
    def fn_decl(self, children: list[Any]) -> N.FnDecl:
        name = str(children[0])
        params = ()
        return_type = None
        body = ()
        
        idx = 1
        if idx < len(children) and isinstance(children[idx], list):
            params = tuple(children[idx])
            idx += 1
        if idx < len(children) and isinstance(children[idx], (N.PrimitiveType, N.ListType, N.DictType, N.TupleType, N.AgentSpecificType)):
            return_type = children[idx]
            idx += 1
        if idx < len(children):
            body = children[idx]
        return N.FnDecl(name=name, params=params, return_type=return_type, body=body)

    def param_list(self, children: list[Any]) -> list[N.Param]:
        return children

    def param(self, children: list[Any]) -> N.Param:
        name = str(children[0])
        type_ann = None
        default = None
        
        idx = 1
        if idx < len(children) and isinstance(children[idx], (N.PrimitiveType, N.ListType, N.DictType, N.TupleType, N.AgentSpecificType)):
            type_ann = children[idx]
            idx += 1
        if idx < len(children):
            default = children[idx]
        return N.Param(name=name, type_ann=type_ann, default=default)

    # --- Agent ---
    def agent_decl(self, children: list[Any]) -> N.AgentDecl:
        name = str(children[0])
        body_node = children[1]
        return N.AgentDecl(
            name=name,
            goal=body_node.get("goal"),
            inputs=body_node.get("inputs", ()),
            outputs=body_node.get("outputs", ()),
            imports=body_node.get("imports", ()),
            policy=body_node.get("policy"),
            plan=body_node.get("plan"),
        )

    def agent_body(self, children: list[Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "goal": None,
            "inputs": (),
            "outputs": (),
            "imports": [],
            "policy": None,
            "plan": None
        }
        for child in children:
            if isinstance(child, tuple) and len(child) > 0 and isinstance(child[0], N.TypedField):
                # inputs/outputs
                pass
            elif isinstance(child, N.PolicyBlock):
                result["policy"] = child
            elif isinstance(child, N.PlanBlock):
                result["plan"] = child
            elif isinstance(child, (N.UseToolStmt, N.UsePyStmt, N.UseMemoryStmt)):
                result["imports"].append(child)
            elif isinstance(child, str):
                result["goal"] = child
            elif isinstance(child, dict):
                # structure of inputs / outputs
                if "inputs" in child:
                    result["inputs"] = child["inputs"]
                if "outputs" in child:
                    result["outputs"] = child["outputs"]
        result["imports"] = tuple(result["imports"])
        return result

    def goal_decl(self, children: list[Any]) -> str:
        return str(children[0]).strip('"\'')

    def inputs_decl(self, children: list[Any]) -> dict[str, Any]:
        return {"inputs": tuple(children)}

    def outputs_decl(self, children: list[Any]) -> dict[str, Any]:
        return {"outputs": tuple(children)}

    def typed_field(self, children: list[Any]) -> N.TypedField:
        return N.TypedField(name=str(children[0]), type_ann=children[1])

    def policy_block(self, children: list[Any]) -> N.PolicyBlock:
        return N.PolicyBlock(entries=tuple(children))

    def policy_entry(self, children: list[Any]) -> N.PolicyEntry:
        key = str(children[0])
        val = children[1]
        if isinstance(val, lark.Token):
            if val.type == 'INT':
                val = int(val)
            elif val.type == 'FLOAT':
                val = float(val)
            elif val.type == 'BOOL_LIT':
                val = True if val.value == 'true' else False
            elif val.type == 'STRING':
                val = val.value.strip('"\'')
            else:
                val = str(val)
        elif isinstance(val, str):
            val = val.strip('"\'')
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
        elif hasattr(val, "value"):
            val = val.value
        return N.PolicyEntry(key=key, value=val)

    def plan_block(self, children: list[Any]) -> N.PlanBlock:
        return N.PlanBlock(body=tuple(children))

    # --- Control Flow ---
    def return_stmt(self, children: list[Any]) -> N.ReturnStmt:
        val = children[0] if children else None
        return N.ReturnStmt(value=val)

    def if_stmt(self, children: list[Any]) -> N.IfStmt:
        condition = children[0]
        then_branch = children[1]
        else_branch = None
        if len(children) > 2:
            eb = children[2]
            if isinstance(eb, N.IfStmt):
                else_branch = (eb,)
            else:
                else_branch = eb
        return N.IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch)

    def for_stmt(self, children: list[Any]) -> N.ForStmt:
        return N.ForStmt(var=str(children[0]), iterable=children[1], body=children[2])

    def while_stmt(self, children: list[Any]) -> N.WhileStmt:
        return N.WhileStmt(condition=children[0], body=children[1])

    # --- Agent Primitives ---
    def approve_stmt(self, children: list[Any]) -> N.ApproveStmt:
        return N.ApproveStmt(target=str(children[0]), action=str(children[1]))

    def remember_stmt(self, children: list[Any]) -> N.RememberStmt:
        return N.RememberStmt(value=children[0], namespace=str(children[1]))

    def forget_stmt(self, children: list[Any]) -> N.ForgetStmt:
        return N.ForgetStmt(key=children[0], namespace=str(children[1]))

    def recall_stmt(self, children: list[Any]) -> N.RecallStmt:
        var_name = self._expr_to_target_str(children[0])
        return N.RecallStmt(var=var_name, query=str(children[1]).strip('"\''), namespace=str(children[2]))

    def guard_stmt(self, children: list[Any]) -> N.GuardStmt:
        return N.GuardStmt(condition=children[0])

    def retry_stmt(self, children: list[Any]) -> N.RetryStmt:
        count = int(children[0])
        backoff = str(children[1])
        body = children[2]
        catch_blk = children[3] if len(children) > 3 else None
        return N.RetryStmt(count=count, backoff=backoff, body=body, catch_block=catch_blk)

    def catch_block(self, children: list[Any]) -> N.CatchBlock:
        return N.CatchBlock(var=str(children[0]), body=children[1])

    def eval_stmt(self, children: list[Any]) -> N.EvalStmt:
        subject = str(children[0])
        rubric = str(children[1])
        criteria = tuple(children[2:])
        return N.EvalStmt(subject=subject, rubric=rubric, criteria=criteria)

    def eval_criterion(self, children: list[Any]) -> N.EvalCriterion:
        return N.EvalCriterion(metric=str(children[0]), op=str(children[1]), threshold=children[2])

    # --- Expressions ---
    def or_expr(self, children: list[Any]) -> Any:
        if len(children) == 1:
            return children[0]
        left = children[0]
        for right in children[1:]:
            span = getattr(left, "span", None)
            left = N.BinaryOp(op="or", left=left, right=right, span=span)
        return left

    def and_expr(self, children: list[Any]) -> Any:
        if len(children) == 1:
            return children[0]
        left = children[0]
        for right in children[1:]:
            span = getattr(left, "span", None)
            left = N.BinaryOp(op="and", left=left, right=right, span=span)
        return left

    def unary_not(self, children: list[Any]) -> N.UnaryOp:
        return N.UnaryOp(op="not", operand=children[0])

    def comparison(self, children: list[Any]) -> Any:
        return self._fold_binary(children)

    def add_expr(self, children: list[Any]) -> Any:
        return self._fold_binary(children)

    def mul_expr(self, children: list[Any]) -> Any:
        return self._fold_binary(children)

    def unary_minus(self, children: list[Any]) -> N.UnaryOp:
        return N.UnaryOp(op=str(children[0]), operand=children[1])

    def power_expr(self, children: list[Any]) -> Any:
        if len(children) == 1:
            return children[0]
        return N.BinaryOp(op="**", left=children[0], right=children[1])

    def call_expr(self, children: list[Any]) -> N.CallExpr:
        callee = children[0]
        args, kwargs = children[1] if len(children) > 1 and children[1] is not None else ((), ())
        return N.CallExpr(callee=callee, args=args, kwargs=kwargs)

    def member_expr(self, children: list[Any]) -> N.MemberExpr:
        return N.MemberExpr(obj=children[0], attr=str(children[1]))

    def index_expr(self, children: list[Any]) -> N.IndexExpr:
        return N.IndexExpr(obj=children[0], index=children[1])

    def method_chain(self, children: list[Any]) -> N.CallExpr:
        obj = children[0]
        method_name = str(children[1])
        args, kwargs = children[2] if len(children) > 2 and children[2] is not None else ((), ())
        return N.CallExpr(callee=N.MemberExpr(obj=obj, attr=method_name), args=args, kwargs=kwargs)

    def arg_list(self, children: list[Any]) -> tuple[tuple[Any, ...], tuple[tuple[str, Any], ...]]:
        args = []
        kwargs = []
        for child in children:
            if isinstance(child, tuple) and len(child) == 2 and isinstance(child[0], str):
                kwargs.append(child)
            else:
                args.append(child)
        return tuple(args), tuple(kwargs)

    def keyword_arg(self, children: list[Any]) -> tuple[str, Any]:
        return str(children[0]), children[1]

    def positional_arg(self, children: list[Any]) -> Any:
        return children[0]

    def int_literal(self, children: list[Any]) -> N.IntLiteral:
        return N.IntLiteral(value=int(children[0]))

    def float_literal(self, children: list[Any]) -> N.FloatLiteral:
        return N.FloatLiteral(value=float(children[0]))

    def string_literal(self, children: list[Any]) -> N.StringLiteral:
        val = str(children[0])
        val = val[1:-1] # strip quote chars
        # Handle escapes simple replacements
        val = val.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n').replace('\\t', '\t')
        return N.StringLiteral(value=val)

    def bool_literal(self, children: list[Any]) -> N.BoolLiteral:
        return N.BoolLiteral(value=True if str(children[0]) == "true" else False)

    def none_literal(self, children: list[Any]) -> N.NoneLiteral:
        return N.NoneLiteral()

    def identifier(self, children: list[Any]) -> N.Identifier:
        return N.Identifier(name=str(children[0]))

    def list_expr(self, children: list[Any]) -> N.ListExpr:
        return N.ListExpr(elements=tuple(children))

    def dict_expr(self, children: list[Any]) -> N.DictExpr:
        return N.DictExpr(pairs=tuple(children))

    def kv_pair(self, children: list[Any]) -> tuple[Any, Any]:
        return children[0], children[1]

    def expr_stmt(self, children: list[Any]) -> Any:
        if isinstance(children[0], N.AssignStmt):
            return children[0]
        return N.ExprStmt(expr=children[0])

    def _expr_to_target_str(self, expr: N.Expr) -> str:
        if isinstance(expr, N.Identifier):
            return expr.name
        if isinstance(expr, N.MemberExpr):
            return f"{self._expr_to_target_str(expr.obj)}.{expr.attr}"
        if isinstance(expr, N.IndexExpr):
            return f"{self._expr_to_target_str(expr.obj)}[{self._expr_to_target_str(expr.index)}]"
        if isinstance(expr, N.IntLiteral):
            return str(expr.value)
        if isinstance(expr, N.FloatLiteral):
            return str(expr.value)
        if isinstance(expr, N.StringLiteral):
            return f'"{expr.value}"'
        if isinstance(expr, N.BoolLiteral):
            return "true" if expr.value else "false"
        if isinstance(expr, N.NoneLiteral):
            return "none"
        raise ValueError(f"Invalid assignment target expression type: {type(expr)}")

    def assignment(self, children: list[Any]) -> N.AssignStmt:
        target_str = self._expr_to_target_str(children[0])
        return N.AssignStmt(target=target_str, value=children[1])

    def dotted_name(self, children: list[Any]) -> str:
        return ".".join(str(c) for c in children)

    def call_args(self, children: list[Any]) -> Any:
        return children[0] if children else ((), ())

    def block(self, children: list[Any]) -> tuple[N.Statement, ...]:
        return tuple(children)
