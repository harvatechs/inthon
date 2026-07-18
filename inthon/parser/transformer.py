"""Parse-tree → AST transformer (engine spec §4.3).

Uses Lark's @v_args(meta=True) so every AST node carries a source span.
Also performs string-interpolation lowering ("Hello, {name}") and type
expression validation.
"""

from __future__ import annotations

from typing import Any, Optional

from lark import Token, Transformer, v_args
from lark.tree import Meta

from ..ast import nodes
from ..errors import InthonParseError, InthonTypeSyntaxError, Span

_PRIMITIVE_TYPES = {"str", "int", "float", "bool", "bytes", "none", "any"}
_AGENT_TYPES = {
    "Goal", "Plan", "ToolCall", "ToolResult", "Trace", "MemoryRef",
    "Approval", "Policy", "DataFrame", "Tensor", "Model", "Dataset", "Embedding",
}
_COLLECTION_TYPES = {"list", "dict", "tuple", "set"}


def _span(meta: Meta, filename: str) -> Span:
    return Span(
        filename=filename,
        line=meta.line,
        col=meta.column,
        end_line=meta.end_line,
        end_col=meta.end_column,
    )


def _tok_text(t: Any) -> str:
    return str(t)


class InthonTransformer(Transformer):
    def __init__(self, filename: str = "<stdin>", expr_parser=None, source: str = ""):
        super().__init__()
        self.filename = filename
        self.expr_parser = expr_parser  # Lark instance with start="expr" for interpolation
        self.source = source

    # -- helpers -------------------------------------------------------------
    def _s(self, meta: Meta) -> Span:
        return _span(meta, self.filename)

    def _type_error(self, name: str, span: Span) -> InthonTypeSyntaxError:
        return InthonTypeSyntaxError(
            f"Unknown type '{name}'",
            span=span,
            source_line=self._line_at(span),
        )

    def _line_at(self, span: Span) -> Optional[str]:
        lines = self.source.splitlines()
        if 1 <= span.line <= len(lines):
            return lines[span.line - 1]
        return None

    # -- program / blocks ------------------------------------------------------
    @v_args(meta=True)
    def program(self, meta: Meta, children):
        return nodes.Program(statements=tuple(children), span=self._s(meta))

    @v_args(meta=True)
    def block(self, meta: Meta, children):
        return nodes.Block(statements=tuple(children), span=self._s(meta))

    # -- imports -----------------------------------------------------------------
    def import_stmt(self, children):
        return children[0]

    @v_args(meta=True)
    def use_tool_stmt(self, meta: Meta, children):
        return nodes.UseTool(path=children[0], span=self._s(meta))

    @v_args(meta=True)
    def use_py_stmt(self, meta: Meta, children):
        module = children[0]
        alias = str(children[1]) if len(children) > 1 else None
        return nodes.UsePy(module=module, alias=alias, span=self._s(meta))

    @v_args(meta=True)
    def use_memory_stmt(self, meta: Meta, children):
        ns = children[0]
        args, kwargs = children[1] if len(children) > 1 else ((), ())
        return nodes.UseMemory(namespace=ns, args=args, kwargs=kwargs, span=self._s(meta))

    @v_args(meta=True)
    def call_args(self, meta: Meta, children):
        args, kwargs = (), ()
        if children:
            for child in children[0]:
                if isinstance(child, tuple) and len(child) == 2 and child[0] == "__kw__":
                    kwargs += ((child[1][0], child[1][1]),)
                else:
                    args += (child,)
        return args, kwargs

    @v_args(meta=True)
    def arg_list(self, meta: Meta, children):
        return children

    def arg(self, children):
        return children[0]

    def keyword_arg(self, children):
        return ("__kw__", (str(children[0]), children[1]))

    def positional_arg(self, children):
        return children[0]

    # -- dotted names --------------------------------------------------------------
    def dotted_name(self, children):
        return ".".join(str(c) for c in children)

    # -- variables -----------------------------------------------------------------
    @v_args(meta=True)
    def let_stmt(self, meta: Meta, children):
        name = str(children[0])
        if len(children) == 3:
            ann, value = children[1], children[2]
        else:
            ann, value = None, children[1]
        return nodes.LetDecl(name=name, type_annotation=ann, value=value, span=self._s(meta))

    @v_args(meta=True)
    def const_stmt(self, meta: Meta, children):
        name = str(children[0])
        if len(children) == 3:
            ann, value = children[1], children[2]
        else:
            ann, value = None, children[1]
        return nodes.ConstDecl(name=name, type_annotation=ann, value=value, span=self._s(meta))

    def type_annotation(self, children):
        return children[0]

    # -- type expressions ------------------------------------------------------------
    @v_args(meta=True)
    def named_type(self, meta: Meta, children):
        name = str(children[0])
        if name not in _PRIMITIVE_TYPES and name not in _AGENT_TYPES:
            raise self._type_error(name, self._s(meta))
        return nodes.NamedType(name=name, span=self._s(meta))

    @v_args(meta=True)
    def generic_type(self, meta: Meta, children):
        name = str(children[0])
        if name not in _COLLECTION_TYPES and name not in _AGENT_TYPES:
            raise self._type_error(name, self._s(meta))
        if name in ("list", "set"):
            pass
        elif name == "tuple":
            pass
        else:
            raise self._type_error(name, self._s(meta))
        return nodes.GenericType(name=name, args=(children[1],), span=self._s(meta))

    @v_args(meta=True)
    def multi_generic_type(self, meta: Meta, children):
        name = str(children[0])
        args = tuple(children[1:])
        if name == "dict":
            if len(args) != 2:
                raise self._type_error(f"{name} expects 2 type arguments", self._s(meta))
        elif name == "tuple":
            pass
        else:
            raise self._type_error(name, self._s(meta))
        return nodes.GenericType(name=name, args=args, span=self._s(meta))

    @v_args(meta=True)
    def fn_type(self, meta: Meta, children):
        *params, ret = children
        return nodes.FnType(params=tuple(params), ret=ret, span=self._s(meta))

    # -- functions --------------------------------------------------------------------
    @v_args(meta=True)
    def fn_decl(self, meta: Meta, children):
        name = str(children[0])
        rest = children[1:]
        params: tuple = ()
        ret = None
        body = None
        if rest and isinstance(rest[0], list):
            params = tuple(rest[0])
            rest = rest[1:]
        if rest and isinstance(rest[0], nodes.TypeExpr):
            ret = rest[0]
            rest = rest[1:]
        if rest:
            body = rest[0]
        return nodes.FnDecl(name=name, params=params, return_type=ret, body=body, span=self._s(meta))

    def param_list(self, children):
        return list(children)

    def param(self, children):
        name = str(children[0])
        ann = None
        default = None
        for child in children[1:]:
            if isinstance(child, nodes.TypeExpr):
                ann = child
            else:
                default = child
        return nodes.Param(name=name, type_annotation=ann, default=default)

    # -- agents -------------------------------------------------------------------------
    @v_args(meta=True)
    def agent_decl(self, meta: Meta, children):
        name = str(children[0])
        body_items = children[1] if len(children) > 1 else []
        goal = None
        inputs: tuple = ()
        outputs: tuple = ()
        imports: list = []
        policies: list = []
        plan = None
        criteria: list = []
        rewriters: list = []
        for item in body_items:
            if isinstance(item, nodes.Statement) and type(item).__name__ == "_GoalDecl":
                goal = item.goal
            elif isinstance(item, _GoalMarker):
                goal = item.goal
            elif isinstance(item, _FieldsMarker):
                if item.kind == "inputs":
                    inputs = tuple(item.fields)
                else:
                    outputs = tuple(item.fields)
            elif isinstance(item, (nodes.UseTool, nodes.UsePy, nodes.UseMemory)):
                imports.append(item)
            elif isinstance(item, nodes.CriteriaDecl):
                criteria.append(item)
            elif isinstance(item, nodes.RewriterDecl):
                rewriters.append(item)
            elif isinstance(item, nodes.PolicyStmt):
                policies.extend(item.entries)
            elif isinstance(item, nodes.Block):
                plan = item
            elif isinstance(item, list):
                # plan_block arrives as list of statements
                plan = nodes.Block(statements=tuple(item), span=self._s(meta))
        return nodes.AgentDecl(
            name=name, goal=goal, inputs=inputs, outputs=outputs,
            imports=tuple(imports), policies=tuple(policies), plan=plan,
            criteria=tuple(criteria), rewriters=tuple(rewriters),
            span=self._s(meta),
        )

    def agent_body(self, children):
        return list(children)

    @v_args(meta=True)
    def goal_decl(self, meta: Meta, children):
        return _GoalMarker(goal=_unquote(str(children[0])))

    @v_args(meta=True)
    def inputs_decl(self, meta: Meta, children):
        return _FieldsMarker(kind="inputs", fields=list(children))

    @v_args(meta=True)
    def outputs_decl(self, meta: Meta, children):
        return _FieldsMarker(kind="outputs", fields=list(children))

    def typed_field(self, children):
        return nodes.TypedField(name=str(children[0]), type_annotation=children[1])

    @v_args(meta=True)
    def criteria_decl(self, meta: Meta, children):
        return nodes.CriteriaDecl(name=str(children[0]), criteria=tuple(children[1:]), span=self._s(meta))

    @v_args(meta=True)
    def rewriter_decl(self, meta: Meta, children):
        return nodes.RewriterDecl(name=str(children[0]), body=children[1], span=self._s(meta))

    @v_args(meta=True)
    def policy_block(self, meta: Meta, children):
        return nodes.PolicyStmt(entries=tuple(children), span=self._s(meta))

    def policy_stmt(self, children):
        return children[0]

    def policy_entry(self, children):
        key = str(children[0])
        raw = children[1]
        if isinstance(raw, Token):
            text = str(raw)
            if raw.type == "STRING":
                value: Any = _unquote(text)
            elif raw.type == "INT":
                value = int(text.replace("_", ""))
            elif raw.type == "FLOAT":
                value = float(text.replace("_", ""))
            elif raw.type == "BOOL_LIT":
                value = text == "true"
            elif raw.type == "NONE_LIT":
                value = None
            else:
                value = text
        else:
            value = raw  # dotted_name string
        return nodes.PolicyEntry(key=key, value=value)

    def plan_block(self, children):
        return list(children)

    # -- control flow ----------------------------------------------------------------------
    @v_args(meta=True)
    def return_stmt(self, meta: Meta, children):
        return nodes.ReturnStmt(value=children[0] if children else None, span=self._s(meta))

    @v_args(meta=True)
    def break_stmt(self, meta: Meta, children):
        return nodes.BreakStmt(span=self._s(meta))

    @v_args(meta=True)
    def continue_stmt(self, meta: Meta, children):
        return nodes.ContinueStmt(span=self._s(meta))

    @v_args(meta=True)
    def if_stmt(self, meta: Meta, children):
        condition = children[0]
        then_block = children[1]
        else_block = children[2] if len(children) > 2 else None
        return nodes.IfStmt(condition=condition, then_block=then_block, else_block=else_block, span=self._s(meta))

    @v_args(meta=True)
    def for_stmt(self, meta: Meta, children):
        return nodes.ForStmt(var=str(children[0]), iterable=children[1], body=children[2], span=self._s(meta))

    @v_args(meta=True)
    def while_stmt(self, meta: Meta, children):
        return nodes.WhileStmt(condition=children[0], body=children[1], span=self._s(meta))

    # -- agent primitives ---------------------------------------------------------------------
    @v_args(meta=True)
    def approve_stmt(self, meta: Meta, children):
        return nodes.ApproveStmt(tool_path=children[0], action=str(children[1]), span=self._s(meta))

    @v_args(meta=True)
    def remember_stmt(self, meta: Meta, children):
        return nodes.RememberStmt(value=children[0], namespace=children[1], span=self._s(meta))

    @v_args(meta=True)
    def forget_stmt(self, meta: Meta, children):
        return nodes.ForgetStmt(value=children[0], namespace=children[1], span=self._s(meta))

    @v_args(meta=True)
    def guard_stmt(self, meta: Meta, children):
        return nodes.GuardStmt(condition=children[0], span=self._s(meta))

    @v_args(meta=True)
    def retry_stmt(self, meta: Meta, children):
        count = int(str(children[0]))
        backoff = str(children[1])
        body = children[2]
        catch_name, catch_body = None, None
        if len(children) > 3:
            catch_name, catch_body = children[3]
        return nodes.RetryStmt(
            count=count, backoff=backoff, body=body,
            catch_name=catch_name, catch_body=catch_body, span=self._s(meta),
        )

    def catch_block(self, children):
        return (str(children[0]), children[1])

    @v_args(meta=True)
    def eval_rubric(self, meta: Meta, children):
        subject = str(children[0])
        rubric = str(children[1])
        criteria = tuple(children[2:])
        return nodes.EvalStmt(subject=subject, rubric=rubric, criteria=criteria, span=self._s(meta))

    @v_args(meta=True)
    def eval_self(self, meta: Meta, children):
        subject = str(children[0])
        rubric = str(children[1])
        rewriter = str(children[2]) if len(children) > 2 else None
        return nodes.EvalStmt(subject=subject, rubric=rubric, criteria=(), rewriter=rewriter, span=self._s(meta))

    @v_args(meta=True)
    def eval_criterion(self, meta: Meta, children):
        name = str(children[0])
        if len(children) == 3:
            op = str(children[1])
            value = children[2]
        else:
            op = ":"
            value = children[1]
        return nodes.EvalCriterion(name=name, op=op, value=value, span=self._s(meta))

    # -- expressions ---------------------------------------------------------------------------
    @v_args(meta=True)
    def or_op(self, meta: Meta, children):
        return nodes.BinaryOp(left=children[0], op="or", right=children[1], span=self._s(meta))

    @v_args(meta=True)
    def and_op(self, meta: Meta, children):
        return nodes.BinaryOp(left=children[0], op="and", right=children[1], span=self._s(meta))

    @v_args(meta=True)
    def unary_not(self, meta: Meta, children):
        return nodes.UnaryOp(op="not", operand=children[0], span=self._s(meta))

    @v_args(meta=True)
    def comparison_op(self, meta: Meta, children):
        return nodes.BinaryOp(left=children[0], op=str(children[1]), right=children[2], span=self._s(meta))

    @v_args(meta=True)
    def add_op(self, meta: Meta, children):
        return nodes.BinaryOp(left=children[0], op=str(children[1]), right=children[2], span=self._s(meta))

    @v_args(meta=True)
    def mul_op(self, meta: Meta, children):
        return nodes.BinaryOp(left=children[0], op=str(children[1]), right=children[2], span=self._s(meta))

    @v_args(meta=True)
    def unary_signed(self, meta: Meta, children):
        return nodes.UnaryOp(op=str(children[0]), operand=children[1], span=self._s(meta))

    def expr_fragment(self, children):
        return children[0]

    @v_args(meta=True)
    def power_expr(self, meta: Meta, children):
        if len(children) == 1:
            return children[0]
        return nodes.BinaryOp(left=children[0], op="**", right=children[1], span=self._s(meta))

    @v_args(meta=True)
    def call_expr(self, meta: Meta, children):
        callee = children[0]
        args: tuple = ()
        kwargs: tuple = ()
        for child in children[1:]:
            if isinstance(child, list):
                for a in child:
                    if isinstance(a, tuple) and len(a) == 2 and a[0] == "__kw__":
                        kwargs += (a[1],)
                    else:
                        args += (a,)
        return nodes.CallExpr(callee=callee, args=args, kwargs=kwargs, span=self._s(meta))

    @v_args(meta=True)
    def member_expr(self, meta: Meta, children):
        return nodes.MemberExpr(object=children[0], name=str(children[1]), span=self._s(meta))

    @v_args(meta=True)
    def index_expr(self, meta: Meta, children):
        return nodes.IndexExpr(object=children[0], index=children[1], span=self._s(meta))

    # -- primaries --------------------------------------------------------------------------------
    @v_args(meta=True)
    def int_literal(self, meta: Meta, children):
        return nodes.IntLiteral(value=int(str(children[0]).replace("_", "")), span=self._s(meta))

    @v_args(meta=True)
    def float_literal(self, meta: Meta, children):
        return nodes.FloatLiteral(value=float(str(children[0]).replace("_", "")), span=self._s(meta))

    @v_args(meta=True)
    def string_literal(self, meta: Meta, children):
        raw = _unquote(str(children[0]))
        parts = self._interpolate(raw, self._s(meta))
        if parts is None:
            val = raw.replace("{{", "{").replace("}}", "}")
            return nodes.StringLiteral(value=val, span=self._s(meta))
        return nodes.InterpString(parts=tuple(parts), span=self._s(meta))

    @v_args(meta=True)
    def bool_literal(self, meta: Meta, children):
        return nodes.BoolLiteral(value=str(children[0]) == "true", span=self._s(meta))

    @v_args(meta=True)
    def none_literal(self, meta: Meta, children):
        return nodes.NoneLiteral(span=self._s(meta))

    @v_args(meta=True)
    def identifier(self, meta: Meta, children):
        return nodes.Identifier(name=str(children[0]), span=self._s(meta))

    @v_args(meta=True)
    def recall_expr(self, meta: Meta, children):
        query = _unquote(str(children[0]))
        return nodes.RecallExpr(query=query, namespace=children[1], span=self._s(meta))

    @v_args(meta=True)
    def list_expr(self, meta: Meta, children):
        return nodes.ListExpr(elements=tuple(children), span=self._s(meta))

    @v_args(meta=True)
    def dict_expr(self, meta: Meta, children):
        pairs = tuple(children)
        return nodes.DictExpr(pairs=pairs, span=self._s(meta))

    def kv_pair(self, children):
        return (children[0], children[1])

    # -- expression statements -----------------------------------------------------------------------
    @v_args(meta=True)
    def expr_stmt(self, meta: Meta, children):
        if len(children) == 1:
            return nodes.ExprStmt(expr=children[0], span=self._s(meta))
        target, value = children[0], children[1]
        if not isinstance(target, (nodes.Identifier, nodes.MemberExpr, nodes.IndexExpr)):
            raise InthonParseError(
                "Invalid assignment target",
                span=self._s(meta),
                hint="Assignment targets must be a name, a member (a.b), or an index (a[i]).",
                source_line=self._line_at(self._s(meta)),
            )
        if isinstance(value, nodes.RecallExpr) and isinstance(target, nodes.Identifier):
            return nodes.RecallStmt(target=target, value=value, span=self._s(meta))
        return nodes.AssignStmt(target=target, value=value, span=self._s(meta))

    # -- string interpolation ---------------------------------------------------------------------------
    def _interpolate(self, raw: str, span: Span) -> Optional[list]:
        """Split *raw* into literal/expr parts; None if no interpolation."""
        if "{" not in raw and "}" not in raw:
            return None
        parts: list = []
        buf: list[str] = []
        i = 0
        found = False
        while i < len(raw):
            ch = raw[i]
            if ch == "{" and i + 1 < len(raw) and raw[i + 1] == "{":
                buf.append("{")
                i += 2
                continue
            if ch == "}" and i + 1 < len(raw) and raw[i + 1] == "}":
                buf.append("}")
                i += 2
                continue
            if ch == "{":
                found = True
                depth = 1
                j = i + 1
                inner: list[str] = []
                in_str: Optional[str] = None
                while j < len(raw) and depth > 0:
                    c = raw[j]
                    if in_str:
                        if c == in_str:
                            in_str = None
                        inner.append(c)
                    elif c in "\"'":
                        in_str = c
                        inner.append(c)
                    elif c == "{":
                        depth += 1
                        inner.append(c)
                    elif c == "}":
                        depth -= 1
                        if depth > 0:
                            inner.append(c)
                    else:
                        inner.append(c)
                    j += 1
                if depth != 0:
                    raise InthonParseError(
                        "Unterminated '{' in string interpolation",
                        span=span,
                        hint="Close the interpolation with '}', or escape a literal brace as '{{'.",
                        source_line=self._line_at(span),
                    )
                if buf:
                    parts.append("".join(buf))
                    buf = []
                expr_src = "".join(inner).strip()
                if not expr_src:
                    raise InthonParseError(
                        "Empty interpolation '{}'",
                        span=span,
                        hint="Put an expression inside the braces, or escape a literal brace as '{{'.",
                        source_line=self._line_at(span),
                    )
                parts.append(self._parse_inner_expr(expr_src, span, i))
                i = j
                continue
            if ch == "}":
                raise InthonParseError(
                    "Unmatched '}' in string literal",
                    span=span,
                    hint="Escape a literal brace as '}}'.",
                    source_line=self._line_at(span),
                )
            buf.append(ch)
            i += 1
        if buf:
            parts.append("".join(buf))
        return parts if found else None

    def _parse_inner_expr(self, src: str, span: Span, offset: int) -> nodes.Expression:
        from .parser import parse_expression_fragment

        try:
            expr = parse_expression_fragment(src, self.filename, span)
            return _rebase_spans(expr, span, offset + 1)
        except InthonParseError as exc:
            raise InthonParseError(
                f"Invalid expression in string interpolation: {exc.message}",
                span=span,
                hint="Interpolations accept any INTHON expression, e.g. \"total: {a + b}\".",
                source_line=self._line_at(span),
            )


def _rebase_spans(node, span: Span, col_base: int):
    """Rebase a fragment AST's spans onto the host string's position."""
    import dataclasses

    if isinstance(node, (list, tuple)):
        return type(node)(_rebase_spans(x, span, col_base) for x in node)
    if not isinstance(node, nodes.Node):
        return node
    updates = {}
    for f in dataclasses.fields(node):
        value = getattr(node, f.name)
        if f.name == "span":
            if value is not None:
                updates[f.name] = Span(
                    filename=span.filename,
                    line=span.line,
                    col=span.col + col_base + (value.col - 1),
                    end_line=span.line,
                    end_col=span.col + col_base + (value.end_col - 1),
                )
        elif isinstance(value, (nodes.Node, list, tuple)):
            updates[f.name] = _rebase_spans(value, span, col_base)
    if updates:
        return dataclasses.replace(node, **updates)
    return node


class _GoalMarker:
    def __init__(self, goal: str):
        self.goal = goal


class _FieldsMarker:
    def __init__(self, kind: str, fields: list):
        self.kind = kind
        self.fields = fields


def _unquote(text: str) -> str:
    """Strip quotes and process escape sequences."""
    if len(text) >= 2 and text[0] in "\"'" and text[-1] == text[0]:
        body = text[1:-1]
    else:
        body = text
    out: list[str] = []
    i = 0
    escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "0": "\0"}
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in escapes:
                out.append(escapes[nxt])
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)
