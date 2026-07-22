from __future__ import annotations
from typing import Any
from ..ast import nodes as N
from ..ast.visitor import ASTVisitor
from ..runtime.context import ExecutionContext
from ..runtime.values import (
    from_python,
    to_python,
    InthonValue,
    InthonCallable,
    InthonToolRef,
    InthonNone,
)
from ..runtime.errors import IntHonRuntimeError, ReturnSignal
from .. import RunResult


class Transpiler(ASTVisitor):
    def __init__(self) -> None:
        super().__init__()
        self._indent = 0

    def _target_to_str(self, node: Any) -> str:
        if isinstance(node, N.Identifier):
            return node.name
        if isinstance(node, N.MemberExpr):
            return f"{self._target_to_str(node.object)}.{node.name}"
        if isinstance(node, N.IndexExpr):
            idx_str = str(node.index.value) if hasattr(node.index, "value") else ""
            return f"{self._target_to_str(node.object)}[{idx_str}]"
        return str(node)

    def transpile(self, program: N.Program) -> str:
        lines = [
            "def run_inthon(ctx):",
            "    import time",
            "    from inthon.runtime.values import from_python, to_python, InthonNone, InthonCallable, InthonToolRef",
            "    from inthon.runtime.errors import IntHonRuntimeError, ReturnSignal, PolicyViolationError",
            "    _last_val = InthonNone()",
            "    ",
        ]
        self._indent = 1
        for stmt in program.statements:
            stmt_code = self._visit_stmt(stmt)
            if stmt_code:
                lines.extend(self._add_indent(stmt_code))
        lines.extend(
            [
                "    return _last_val",
            ]
        )
        return "\n".join(lines)

    def _add_indent(self, code: str) -> list[str]:
        indent_str = "    " * self._indent
        return [indent_str + line for line in code.splitlines()]

    def _visit_stmt(self, stmt: Any) -> str:
        code = self.visit(stmt)
        if not code:
            return ""
        # Prefix value-producing statements with _last_val assignment
        if isinstance(stmt, (N.ExprStmt, N.LetDecl, N.ConstDecl, N.AssignStmt)):
            if not code.strip().startswith("_last_val ="):
                return f"_last_val = {code}"
        return code

    # ─── Expressions ───────────────────────────────────────────────────────── #

    def visit_IntLiteral(self, node: N.IntLiteral) -> str:
        return f"from_python({node.value})"

    def visit_FloatLiteral(self, node: N.FloatLiteral) -> str:
        return f"from_python({node.value})"

    def visit_StringLiteral(self, node: N.StringLiteral) -> str:
        return f"from_python({repr(node.value)})"

    def visit_BoolLiteral(self, node: N.BoolLiteral) -> str:
        return "from_python(True)" if node.value else "from_python(False)"

    def visit_NoneLiteral(self, node: N.NoneLiteral) -> str:
        return "InthonNone()"

    def visit_Identifier(self, node: N.Identifier) -> str:
        return f"ctx.get_var('{node.name}')"

    def visit_ListExpr(self, node: N.ListExpr) -> str:
        elems = ", ".join(self.visit(e) for e in node.elements)
        return f"from_python([{elems}])"

    def visit_DictExpr(self, node: N.DictExpr) -> str:
        pairs = ", ".join(
            f"to_python({self.visit(k)}): {self.visit(v)}" for k, v in node.pairs
        )
        return f"from_python({{{pairs}}})"

    def visit_BinaryOp(self, node: N.BinaryOp) -> str:
        left = f"to_python({self.visit(node.left)})"
        right = f"to_python({self.visit(node.right)})"
        if node.op in ("and", "or"):
            return f"from_python({left} {node.op} {right})"
        return f"from_python({left} {node.op} {right})"

    def visit_UnaryOp(self, node: N.UnaryOp) -> str:
        operand = f"to_python({self.visit(node.operand)})"
        return f"from_python({node.op} {operand})"

    def visit_MemberExpr(self, node: N.MemberExpr) -> str:
        obj = self.visit(node.object)
        return f"ctx.safe_getattr({obj}, '{node.name}')"

    def visit_IndexExpr(self, node: N.IndexExpr) -> str:
        obj = self.visit(node.object)
        idx = self.visit(node.index)
        return f"ctx.safe_getitem({obj}, {idx})"

    def visit_CallExpr(self, node: N.CallExpr) -> str:
        callee = self.visit(node.callee)
        args_str = ", ".join(self.visit(a) for a in node.args)
        kwargs_str = ", ".join(f"'{k}': {self.visit(v)}" for k, v in node.kwargs)
        return f"ctx.safe_call({callee}, [{args_str}], {{{kwargs_str}}})"

    # ─── Statements ────────────────────────────────────────────────────────── #

    def visit_LetDecl(self, node: N.LetDecl) -> str:
        val = self.visit(node.value)
        return f"ctx.set_var('{node.name}', {val})"

    def visit_ConstDecl(self, node: N.ConstDecl) -> str:
        val = self.visit(node.value)
        return f"ctx.set_var('{node.name}', {val})"

    def visit_AssignStmt(self, node: N.AssignStmt) -> str:
        val = self.visit(node.value)
        target_str = self._target_to_str(node.target)
        if "." in target_str or "[" in target_str:
            return f"ctx.assign_target_expression('{target_str}', {val})"
        return f"ctx.assign_var('{target_str}', {val})"

    def visit_ExprStmt(self, node: N.ExprStmt) -> str:
        return self.visit(node.expr)

    def visit_ReturnStmt(self, node: N.ReturnStmt) -> str:
        val = self.visit(node.value) if node.value is not None else "InthonNone()"
        return f"raise ReturnSignal({val})"

    def visit_IfStmt(self, node: N.IfStmt) -> str:
        cond = f"to_python({self.visit(node.condition)})"
        lines = [f"if {cond}:"]
        self._indent += 1
        then_stmts = node.then_block.statements if hasattr(node.then_block, "statements") else []
        for stmt in then_stmts:
            stmt_code = self._visit_stmt(stmt)
            if stmt_code:
                lines.extend(self._add_indent(stmt_code))
        self._indent -= 1

        if node.else_block:
            lines.append("else:")
            self._indent += 1
            else_stmts = node.else_block.statements if hasattr(node.else_block, "statements") else ([node.else_block] if isinstance(node.else_block, N.IfStmt) else [])
            for stmt in else_stmts:
                stmt_code = self._visit_stmt(stmt)
                if stmt_code:
                    lines.extend(self._add_indent(stmt_code))
            self._indent -= 1
        return "\n".join(lines)


    def visit_WhileStmt(self, node: N.WhileStmt) -> str:
        cond = f"to_python({self.visit(node.condition)})"
        lines = [f"while {cond}:"]
        self._indent += 1
        for stmt in node.body.statements if node.body else []:
            stmt_code = self._visit_stmt(stmt)
            if stmt_code:
                lines.extend(self._add_indent(stmt_code))
        self._indent -= 1
        return "\n".join(lines)

    def visit_ForStmt(self, node: N.ForStmt) -> str:
        iter_expr = f"to_python({self.visit(node.iterable)})"
        lines = [f"for loop_val_{node.var} in {iter_expr}:"]
        self._indent += 1
        lines.extend(
            self._add_indent(
                f"ctx.assign_var('{node.var}', from_python(loop_val_{node.var}))"
            )
        )
        for stmt in node.body.statements if node.body else []:
            stmt_code = self._visit_stmt(stmt)
            if stmt_code:
                lines.extend(self._add_indent(stmt_code))
        self._indent -= 1
        return "\n".join(lines)

    # ─── Agent & Primitives ────────────────────────────────────────────────── #

    def visit_FnDecl(self, node: N.FnDecl) -> str:
        fn_lines = [
            f"def user_fn_{node.name}():",
        ]
        self._indent += 1
        for stmt in node.body.statements if node.body else []:
            stmt_code = self._visit_stmt(stmt)
            if stmt_code:
                fn_lines.extend(self._add_indent(stmt_code))
        self._indent -= 1

        fn_lines.extend(
            [
                f"ctx.assign_var('{node.name}', InthonCallable(name='{node.name}', params={[p.name for p in node.params]}, defaults={{}}, body=user_fn_{node.name}, closure=ctx))",
            ]
        )
        return "\n".join(fn_lines)

    def visit_AgentDecl(self, node: N.AgentDecl) -> str:
        lines = [
            f"ctx.current_agent = '{node.name}'",
            f"ctx.agent_goal = {repr(node.goal)}",
            f"ctx.tracer.emit('agent_start', {{'name': '{node.name}', 'goal': {repr(node.goal)}}})",
            "ctx.push_scope()",
            "try:",
        ]
        self._indent += 1
        for imp in node.imports:
            stmt_code = self._visit_stmt(imp)
            if stmt_code:
                lines.extend(self._add_indent(stmt_code))
        for stmt in node.plan.statements if node.plan else []:
            stmt_code = self._visit_stmt(stmt)
            if stmt_code:
                lines.extend(self._add_indent(stmt_code))
        self._indent -= 1
        lines.extend(
            [
                "finally:",
                "    ctx.pop_scope()",
                f"    ctx.tracer.emit('agent_end', {{'name': '{node.name}'}})",
                "    ctx.current_agent = None",
            ]
        )
        return "\n".join(lines)

    def visit_UseTool(self, node: N.UseTool) -> str:
        pkg = node.path.split(".")[0]
        return f"ctx.assign_var('{pkg}', InthonToolRef('{node.path}'))"

    def visit_UsePy(self, node: N.UsePy) -> str:
        alias = node.alias or node.module.split(".")[-1]
        return f"ctx.assign_var('{alias}', ctx.importer.import_module('{node.module}', '{node.alias}'))"

    def visit_UseMemory(self, node: N.UseMemory) -> str:
        return ""

    def visit_RememberStmt(self, node: N.RememberStmt) -> str:
        val = self.visit(node.value)
        return f"ctx.memory.remember(to_python({val}), '{node.namespace}')"

    def visit_RecallExpr(self, node: N.RecallExpr) -> str:
        return f"from_python(ctx.memory.recall('{node.query}', '{node.namespace}'))"

    def visit_ForgetStmt(self, node: N.ForgetStmt) -> str:
        val = self.visit(node.key)
        return f"ctx.memory.forget(to_python({val}), '{node.namespace}')"

    def visit_ApproveStmt(self, node: N.ApproveStmt) -> str:
        return (
            f"ctx.policy.approval_gate.request('{node.target}', '{node.action}', ctx)"
        )

    def visit_GuardStmt(self, node: N.GuardStmt) -> str:
        cond = f"to_python({self.visit(node.condition)})"
        return f"if not {cond}: raise PolicyViolationError('Guard condition failed')"

    def visit_EvalStmt(self, node: N.EvalStmt) -> str:
        eval_lines = []
        for crit in node.criteria:
            expected = f"to_python({self.visit(crit.threshold)})"
            eval_lines.append(
                f"if not to_python(ctx.get_var('{crit.metric}')) {crit.op} {expected}: raise PolicyViolationError('Criterion failed')"
            )
        return "\n".join(eval_lines)


def run_transpiled(
    source: str, filename: str = "<stdin>", mock_tools: bool = True
) -> RunResult:
    """Transpile and run INTHON code at native Python speed."""
    from ..parser.parser import parse
    from ..semantic.analyzer import SemanticAnalyzer
    from ..tools.builtin_tools import register_builtins

    program = parse(source, filename=filename)
    SemanticAnalyzer().analyze(program)

    ctx = ExecutionContext(filename=filename)
    register_builtins(ctx.tools, mock=mock_tools)

    def safe_getattr(obj: Any, attr: str) -> Any:
        from ..pybridge.allowlist import is_safe_attribute_access

        if isinstance(obj, InthonToolRef):
            return InthonToolRef(obj.tool_path + "." + attr)
        unwrapped = to_python(obj) if isinstance(obj, InthonValue) else obj
        if not is_safe_attribute_access(
            unwrapped, attr, getattr(unwrapped, attr, None)
        ):
            raise IntHonRuntimeError(
                f"INTHON_SANDBOX: Access to attribute '{attr}' is denied."
            )
        return from_python(getattr(unwrapped, attr))

    def safe_getitem(obj: Any, idx: Any) -> Any:
        unwrapped_obj = to_python(obj) if isinstance(obj, InthonValue) else obj
        unwrapped_idx = to_python(idx) if isinstance(idx, InthonValue) else idx
        return from_python(unwrapped_obj[unwrapped_idx])

    def safe_call(callee: Any, args: list[Any], kwargs: dict[str, Any]) -> Any:
        if isinstance(callee, InthonCallable):
            ctx.push_scope()
            try:
                for i, p_name in enumerate(callee.params):
                    if i < len(args):
                        ctx.set_var(p_name, args[i])
                for k, v in kwargs.items():
                    ctx.set_var(k, v)
                return callee.body()
            except ReturnSignal as ret:
                return ret.value
            finally:
                ctx.pop_scope()

        if isinstance(callee, InthonToolRef):
            res = ctx.tools.call(
                callee.tool_path,
                [to_python(a) for a in args],
                {k: to_python(v) for k, v in kwargs.items()},
            )
            if not res.success:
                raise IntHonRuntimeError(f"Tool call failed: {res.error}")
            return from_python(res.output)

        unwrapped = to_python(callee) if isinstance(callee, InthonValue) else callee
        if callable(unwrapped):
            unpacked_args = [to_python(a) for a in args]
            unpacked_kwargs = {k: to_python(v) for k, v in kwargs.items()}
            return from_python(unwrapped(*unpacked_args, **unpacked_kwargs))

        raise IntHonRuntimeError(f"Object is not callable: {callee}")

    setattr(ctx, "safe_getattr", safe_getattr)
    setattr(ctx, "safe_getitem", safe_getitem)
    setattr(ctx, "safe_call", safe_call)
    setattr(ctx, "assign_const", ctx.set_var)
    setattr(ctx, "assign_target_expression", lambda target, val: None)


    transpiler = Transpiler()
    py_code = transpiler.transpile(program)

    global_env = {"ctx": ctx}
    exec(py_code, global_env)
    run_inthon = global_env["run_inthon"]

    result_val = InthonNone()
    try:
        result_val = run_inthon(ctx)
    except ReturnSignal as ret:
        result_val = ret.value

    trace_data = ctx.tracer.finish(
        result_type=type(result_val).__name__,
        result_preview=repr(to_python(result_val)),
    )
    return RunResult(
        ok=True,
        result=result_val,
        result_python=to_python(result_val),
        result_display=str(to_python(result_val)),
        trace=trace_data,
        stdout="",
        error=None,
        backend="transpile",
    )
