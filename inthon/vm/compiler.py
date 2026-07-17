"""INTHON bytecode compiler: AST → CodeObject (spec §InthonVM).

Two constant pools per code object:
  * literals — pre-boxed immutable InthonValues (scalars only; list/dict
    literals are built fresh at runtime by BUILD_LIST/BUILD_DICT)
  * meta — raw compile-time artifacts (CodeObjects, TypeExprs, tuples)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..ast import nodes
from ..errors import InthonSemanticError
from ..runtime.values import FALSE, NONE, TRUE, InthonFloat, InthonInt, InthonString
from .opcodes import CMP_OPS, Op


@dataclass
class Instr:
    op: int
    arg: int = 0
    line: int = 0
    col: int = 0


@dataclass
class CodeObject:
    name: str
    instructions: list = field(default_factory=list)
    literals: list = field(default_factory=list)   # InthonValue scalars
    meta: list = field(default_factory=list)       # raw artifacts
    names: list = field(default_factory=list)      # identifier pool
    stacksize: int = 0

    @property
    def constants(self) -> list:
        return self.literals

    @constants.setter
    def constants(self, val: list):
        self.literals = val

    def disassemble(self) -> str:
        from .dis import disassemble

        return disassemble(self)


class _LoopCtx:
    def __init__(self):
        self.break_patches: list[int] = []
        self.continue_target: int = 0


class Compiler:
    def __init__(self, filename: str = "<stdin>"):
        self.filename = filename
        self.declared_tools: set[str] = set()
        self._depth = 0
        self._max_depth = 0
        self._loops: list[_LoopCtx] = []

    # -- entry ------------------------------------------------------------------
    def compile(self, program: nodes.Program) -> CodeObject:
        code = CodeObject(name="<module>")
        self.code = code
        self._compile_statements(program.statements, capture=True)
        self._emit(Op.RETURN_VALUE, 0, 0, 0)
        code.stacksize = self._max_depth
        return code

    # -- emit helpers ---------------------------------------------------------------
    def _emit(self, op: int, arg: int = 0, line: int = 0, col: int = 0) -> int:
        self.code.instructions.append(Instr(int(op), arg, line, col))
        return len(self.code.instructions) - 1

    def _push(self, n: int = 1):
        self._depth += n
        self._max_depth = max(self._max_depth, self._depth)

    def _pop(self, n: int = 1):
        self._depth -= n

    def _lit(self, value) -> int:
        self.code.literals.append(value)
        return len(self.code.literals) - 1

    def _meta(self, value: Any) -> int:
        self.code.meta.append(value)
        return len(self.code.meta) - 1

    def _name(self, name: str) -> int:
        if name in self.code.names:
            return self.code.names.index(name)
        self.code.names.append(name)
        return len(self.code.names) - 1

    def _line(self, node) -> tuple:
        if getattr(node, "span", None) is not None:
            return node.span.line, node.span.col
        return 0, 0

    def _patch(self, idx: int, target: int):
        self.code.instructions[idx].arg = target

    # -- statements ---------------------------------------------------------------------
    def _compile_statements(self, statements, capture: bool):
        stmts = list(statements)
        for i, stmt in enumerate(stmts):
            last = i == len(stmts) - 1
            self._compile_statement(stmt, capture=capture and last)
        if capture and not stmts:
            self._emit_load_none()

    def _emit_load_none(self):
        idx = self._lit(NONE)
        self._emit(Op.LOAD_CONST, idx)
        self._push()

    def _compile_statement(self, stmt, capture: bool):
        method = getattr(self, f"_st_{type(stmt).__name__}", None)
        if method is None:
            raise InthonSemanticError(
                f"VM: unsupported statement {type(stmt).__name__}", span=stmt.span
            )
        method(stmt, capture)

    # -- declarations ------------------------------------------------------------
    def _st_LetDecl(self, stmt: nodes.LetDecl, capture: bool):
        line, col = self._line(stmt)
        self._compile_expr(stmt.value)
        self._pop()
        if stmt.type_annotation is not None:
            midx = self._meta(stmt.type_annotation)
            self._emit(Op.CHECK_TYPE, midx, line, col)
        self._emit(Op.DECLARE_NAME, self._name(stmt.name), line, col)
        if capture:
            self._emit_load_none()

    def _st_ConstDecl(self, stmt: nodes.ConstDecl, capture: bool):
        line, col = self._line(stmt)
        self._compile_expr(stmt.value)
        self._pop()
        if stmt.type_annotation is not None:
            midx = self._meta(stmt.type_annotation)
            self._emit(Op.CHECK_TYPE, midx, line, col)
        self._emit(Op.DECLARE_CONST, self._name(stmt.name), line, col)
        if capture:
            self._emit_load_none()

    def _st_FnDecl(self, stmt: nodes.FnDecl, capture: bool):
        line, col = self._line(stmt)
        body = CodeObject(name=stmt.name)
        saved = self.code
        self.code = body
        saved_depth, saved_max = self._depth, self._max_depth
        self._depth = self._max_depth = 0
        saved_loops = self._loops
        self._loops = []
        self._compile_statements(stmt.body.statements, capture=True)
        self._emit(Op.RETURN_VALUE, 0, *self._line(stmt))
        body.stacksize = self._max_depth
        self.code = saved
        self._loops = saved_loops
        self._depth, self._max_depth = saved_depth, saved_max

        defaults = {}
        for param in stmt.params:
            if param.default is not None:
                dcode = CodeObject(name=f"{stmt.name}.default.{param.name}")
                saved2 = self.code
                self.code = dcode
                saved_depth, saved_max = self._depth, self._max_depth
                self._depth = self._max_depth = 0
                self._compile_expr(param.default)
                self._emit(Op.RETURN_VALUE)
                self.code = saved2
                self._depth, self._max_depth = saved_depth, saved_max
                defaults[param.name] = dcode

        meta_idx = self._meta({"decl": stmt, "body": body, "defaults": defaults})
        self._emit(Op.LOAD_META, meta_idx, line, col)
        self._push()
        self._emit(Op.MAKE_FUNCTION, self._name(stmt.name), line, col)
        self._pop()
        if capture:
            self._emit_load_none()

    def _st_AgentDecl(self, stmt: nodes.AgentDecl, capture: bool):
        line, col = self._line(stmt)
        for imp in stmt.imports:
            self._compile_statement(imp, capture=False)

        plan_code = None
        if stmt.plan is not None:
            plan_code = CodeObject(name=f"agent:{stmt.name}")
            saved = self.code
            self.code = plan_code
            saved_depth, saved_max = self._depth, self._max_depth
            self._depth = self._max_depth = 0
            saved_loops = self._loops
            self._loops = []
            self._compile_statements(stmt.plan.statements, capture=True)
            self._emit(Op.RETURN_VALUE)
            plan_code.stacksize = self._max_depth
            self.code = saved
            self._loops = saved_loops
            self._depth, self._max_depth = saved_depth, saved_max

        policies = {entry.key: entry.value for entry in stmt.policies}
        meta_idx = self._meta(
            {
                "decl": stmt,
                "plan": plan_code,
                "policies": policies,
                "criteria": {c.name: c.criteria for c in stmt.criteria},
            }
        )
        self._emit(Op.LOAD_META, meta_idx, line, col)
        self._push()
        self._emit(Op.MAKE_AGENT, self._name(stmt.name), line, col)
        self._pop()
        # bare agent with no required inputs auto-executes
        if not stmt.inputs and stmt.plan is not None:
            self._emit(Op.LOAD_NAME, self._name(stmt.name), line, col)
            self._push()
            self._emit(Op.CALL_FUNCTION, 0, line, col)
            if not capture:
                self._emit(Op.POP_TOP, 0, line, col)
        elif capture:
            self._emit_load_none()

    # -- imports ----------------------------------------------------------------------
    def _st_UseTool(self, stmt: nodes.UseTool, capture: bool):
        line, col = self._line(stmt)
        self.declared_tools.add(stmt.path)
        midx = self._meta(stmt.path)
        self._emit(Op.IMPORT_TOOL, midx, line, col)
        if capture:
            self._emit_load_none()

    def _st_UsePy(self, stmt: nodes.UsePy, capture: bool):
        line, col = self._line(stmt)
        midx = self._meta((stmt.module, stmt.alias))
        self._emit(Op.IMPORT_PY, midx, line, col)
        if capture:
            self._emit_load_none()

    def _st_UseMemory(self, stmt: nodes.UseMemory, capture: bool):
        line, col = self._line(stmt)
        args = []
        for a in stmt.args:
            if isinstance(a, nodes.StringLiteral):
                args.append(a.value)
        midx = self._meta((stmt.namespace, tuple(args)))
        self._emit(Op.USE_MEMORY, midx, line, col)
        if capture:
            self._emit_load_none()

    # -- control flow ----------------------------------------------------------------------
    def _st_IfStmt(self, stmt: nodes.IfStmt, capture: bool):
        line, col = self._line(stmt)
        self._compile_expr(stmt.condition)
        self._pop()
        j_else = self._emit(Op.POP_JUMP_IF_FALSE, 0, line, col)
        self._compile_statements(stmt.then_block.statements, capture=capture)
        j_end = self._emit(Op.JUMP_FORWARD, 0, line, col)
        self._patch(j_else, len(self.code.instructions))
        if stmt.else_block is not None:
            if isinstance(stmt.else_block, nodes.IfStmt):
                self._st_IfStmt(stmt.else_block, capture)
            else:
                self._compile_statements(stmt.else_block.statements, capture=capture)
        elif capture:
            self._emit_load_none()
        self._patch(j_end, len(self.code.instructions))

    def _st_ForStmt(self, stmt: nodes.ForStmt, capture: bool):
        line, col = self._line(stmt)
        tmp = f"__loopval_{len(self.code.instructions)}"
        if capture:
            self._emit_load_none()
            self._emit(Op.DECLARE_NAME, self._name(tmp), line, col)
            self._pop()
        self._compile_expr(stmt.iterable)
        self._pop()
        self._emit(Op.GET_ITER, 0, line, col)
        self._push()
        ctx = _LoopCtx()
        self._loops.append(ctx)
        ctx.continue_target = len(self.code.instructions)
        self._emit(Op.TICK, 0, line, col)
        fidx = self._meta([self._name(stmt.var), 0])  # [name_idx, end_target] (patched)
        self._emit(Op.FOR_ITER, fidx, line, col)
        self._compile_statements(stmt.body.statements, capture=capture)
        if capture:
            self._emit(Op.STORE_NAME, self._name(tmp), line, col)
            self._pop()
        self._emit(Op.JUMP_ABSOLUTE, ctx.continue_target, line, col)
        end = len(self.code.instructions)
        self.code.meta[fidx][1] = end
        for patch in ctx.break_patches:
            self._patch(patch, end)
        self._loops.pop()
        self._pop()  # iterator
        if capture:
            self._emit(Op.LOAD_NAME, self._name(tmp), line, col)
            self._push()

    def _st_WhileStmt(self, stmt: nodes.WhileStmt, capture: bool):
        line, col = self._line(stmt)
        tmp = f"__loopval_{len(self.code.instructions)}"
        if capture:
            self._emit_load_none()
            self._emit(Op.DECLARE_NAME, self._name(tmp), line, col)
            self._pop()
        ctx = _LoopCtx()
        self._loops.append(ctx)
        ctx.continue_target = len(self.code.instructions)
        self._compile_expr(stmt.condition)
        self._pop()
        j_end = self._emit(Op.POP_JUMP_IF_FALSE, 0, line, col)
        self._emit(Op.TICK, 0, line, col)
        self._compile_statements(stmt.body.statements, capture=capture)
        if capture:
            self._emit(Op.STORE_NAME, self._name(tmp), line, col)
            self._pop()
        self._emit(Op.JUMP_ABSOLUTE, ctx.continue_target, line, col)
        end = len(self.code.instructions)
        self._patch(j_end, end)
        for patch in ctx.break_patches:
            self._patch(patch, end)
        self._loops.pop()
        if capture:
            self._emit(Op.LOAD_NAME, self._name(tmp), line, col)
            self._push()

    def _st_ReturnStmt(self, stmt: nodes.ReturnStmt, capture: bool):
        line, col = self._line(stmt)
        if stmt.value is not None:
            self._compile_expr(stmt.value)
            self._pop()
        else:
            self._emit_load_none()
            self._pop()
        self._emit(Op.RETURN_VALUE, 0, line, col)

    def _st_BreakStmt(self, stmt: nodes.BreakStmt, capture: bool):
        line, col = self._line(stmt)
        if not self._loops:
            raise InthonSemanticError("'break' outside of a loop", span=stmt.span)
        idx = self._emit(Op.JUMP_ABSOLUTE, 0, line, col)
        self._loops[-1].break_patches.append(idx)
        if capture:
            self._emit_load_none()

    def _st_ContinueStmt(self, stmt: nodes.ContinueStmt, capture: bool):
        line, col = self._line(stmt)
        if not self._loops:
            raise InthonSemanticError("'continue' outside of a loop", span=stmt.span)
        self._emit(Op.JUMP_ABSOLUTE, self._loops[-1].continue_target, line, col)
        if capture:
            self._emit_load_none()

    # -- agent primitives ----------------------------------------------------------------------
    def _st_ApproveStmt(self, stmt: nodes.ApproveStmt, capture: bool):
        line, col = self._line(stmt)
        midx = self._meta((stmt.tool_path, stmt.action))
        self._emit(Op.APPROVE_GATE, midx, line, col)
        if capture:
            self._emit_load_none()

    def _st_RememberStmt(self, stmt: nodes.RememberStmt, capture: bool):
        line, col = self._line(stmt)
        self._compile_expr(stmt.value)
        self._pop()
        midx = self._meta(stmt.namespace)
        self._emit(Op.AGENT_REMEMBER, midx, line, col)
        if capture:
            self._emit_load_none()

    def _st_ForgetStmt(self, stmt: nodes.ForgetStmt, capture: bool):
        line, col = self._line(stmt)
        self._compile_expr(stmt.value)
        self._pop()
        midx = self._meta(stmt.namespace)
        self._emit(Op.AGENT_FORGET, midx, line, col)
        if capture:
            self._emit_load_none()

    def _st_GuardStmt(self, stmt: nodes.GuardStmt, capture: bool):
        line, col = self._line(stmt)
        self._compile_expr(stmt.condition)
        self._pop()
        self._emit(Op.GUARD_ASSERT, 0, line, col)
        if capture:
            self._emit_load_none()

    def _st_RetryStmt(self, stmt: nodes.RetryStmt, capture: bool):
        line, col = self._line(stmt)
        handler = {"count": stmt.count, "backoff": stmt.backoff, "catch_name": stmt.catch_name}
        handler["body_ip"] = len(self.code.instructions) + 1
        midx = self._meta(handler)
        self._emit(Op.RETRY_BEGIN, midx, line, col)
        self._compile_statements(stmt.body.statements, capture=capture)
        if capture:
            self._pop()
        self._emit(Op.RETRY_END, 0, line, col)
        j_end = self._emit(Op.JUMP_FORWARD, 0, line, col)
        handler["catch_ip"] = len(self.code.instructions)
        if stmt.catch_body is not None:
            self._compile_statements(stmt.catch_body.statements, capture=capture)
            if capture:
                self._pop()
        handler["end_ip"] = len(self.code.instructions)
        self.code.meta[midx] = handler
        self._patch(j_end, len(self.code.instructions))

    def _st_EvalStmt(self, stmt: nodes.EvalStmt, capture: bool):
        line, col = self._line(stmt)
        if stmt.subject == "self":
            midx = self._meta((stmt.rubric, stmt.rewriter))
            self._emit(Op.SELF_EVAL, midx, line, col)
            self._push()
            if not capture:
                self._emit(Op.POP_TOP, 0, line, col)
                self._pop()
            return
        self._emit(Op.LOAD_NAME, self._name(stmt.subject), line, col)
        self._push()
        count = 0
        for criterion in stmt.criteria:
            self._emit(Op.LOAD_CONST, self._lit(InthonString(criterion.name)), line, col)
            self._emit(Op.LOAD_CONST, self._lit(InthonString(criterion.op)), line, col)
            self._compile_expr(criterion.value)
            self._push(2)
            count += 1
        midx = self._meta((stmt.rubric, count))
        self._emit(Op.EVAL_RUBRIC, midx, line, col)
        self._pop(3 * count)
        if not capture:
            self._emit(Op.POP_TOP, 0, line, col)
            self._pop()

    def _st_PolicyStmt(self, stmt: nodes.PolicyStmt, capture: bool):
        line, col = self._line(stmt)
        policies = {entry.key: entry.value for entry in stmt.entries}
        midx = self._meta(policies)
        self._emit(Op.APPLY_POLICY, midx, line, col)
        if capture:
            self._emit_load_none()

    def _st_ExprStmt(self, stmt: nodes.ExprStmt, capture: bool):
        self._compile_expr(stmt.expr)
        self._pop()
        if not capture:
            self._emit(Op.POP_TOP, 0, *self._line(stmt))

    def _st_AssignStmt(self, stmt: nodes.AssignStmt, capture: bool):
        line, col = self._line(stmt)
        target = stmt.target
        if isinstance(target, nodes.Identifier):
            self._compile_expr(stmt.value)
            self._pop()
            self._emit(Op.STORE_NAME, self._name(target.name), line, col)
        elif isinstance(target, nodes.IndexExpr):
            self._compile_expr(target.object)
            self._compile_expr(target.index)
            self._compile_expr(stmt.value)
            self._pop(3)
            self._emit(Op.STORE_SUBSCR, 0, line, col)
        elif isinstance(target, nodes.MemberExpr):
            self._compile_expr(target.object)
            self._compile_expr(stmt.value)
            self._pop(2)
            self._emit(Op.STORE_ATTR, self._name(target.name), line, col)
        if capture:
            self._emit_load_none()

    # -- expressions --------------------------------------------------------------------------------
    def _compile_expr(self, expr):
        method = getattr(self, f"_ex_{type(expr).__name__}", None)
        if method is None:
            raise InthonSemanticError(
                f"VM: unsupported expression {type(expr).__name__}", span=expr.span
            )
        method(expr)
        self._push()

    def _ex_IntLiteral(self, expr):
        self._emit(Op.LOAD_CONST, self._lit(InthonInt(expr.value)), *self._line(expr))

    def _ex_FloatLiteral(self, expr):
        self._emit(Op.LOAD_CONST, self._lit(InthonFloat(expr.value)), *self._line(expr))

    def _ex_StringLiteral(self, expr):
        self._emit(Op.LOAD_CONST, self._lit(InthonString(expr.value)), *self._line(expr))

    def _ex_BoolLiteral(self, expr):
        self._emit(Op.LOAD_CONST, self._lit(TRUE if expr.value else FALSE), *self._line(expr))

    def _ex_NoneLiteral(self, expr):
        self._emit(Op.LOAD_CONST, self._lit(NONE), *self._line(expr))

    def _ex_InterpString(self, expr):
        n = 0
        for part in expr.parts:
            if isinstance(part, str):
                self._emit(Op.LOAD_CONST, self._lit(InthonString(part)), *self._line(expr))
                self._push()
            else:
                self._compile_expr(part)
            n += 1
        self._emit(Op.BUILD_STRING, n, *self._line(expr))
        self._pop(n)

    def _ex_ListExpr(self, expr):
        for el in expr.elements:
            self._compile_expr(el)
        self._emit(Op.BUILD_LIST, len(expr.elements), *self._line(expr))
        self._pop(len(expr.elements))

    def _ex_DictExpr(self, expr):
        for k, v in expr.pairs:
            self._compile_expr(k)
            self._compile_expr(v)
        self._emit(Op.BUILD_DICT, len(expr.pairs), *self._line(expr))
        self._pop(2 * len(expr.pairs))

    def _ex_Identifier(self, expr):
        self._emit(Op.LOAD_NAME, self._name(expr.name), *self._line(expr))

    def _ex_RecallExpr(self, expr):
        q = self._lit(InthonString(expr.query))
        self._emit(Op.LOAD_CONST, q, *self._line(expr))
        self._push()
        midx = self._meta(expr.namespace)
        self._emit(Op.AGENT_RECALL, midx, *self._line(expr))
        self._pop()

    def _ex_UnaryOp(self, expr):
        if expr.op == "not":
            self._compile_expr(expr.operand)
            self._pop()
            self._emit(Op.UNARY_NOT, 0, *self._line(expr))
        elif expr.op == "-":
            self._compile_expr(expr.operand)
            self._pop()
            self._emit(Op.UNARY_NEG, 0, *self._line(expr))
        else:  # unary + : operand only (no-op)
            self._compile_expr(expr.operand)
            self._pop()

    def _ex_BinaryOp(self, expr):
        line, col = self._line(expr)
        op = expr.op
        if op == "and":
            self._compile_expr(expr.left)
            j = self._emit(Op.JUMP_IF_FALSE_OR_POP, 0, line, col)
            self._pop()
            self._compile_expr(expr.right)
            self._patch(j, len(self.code.instructions))
            self._pop(2)
            return
        if op == "or":
            self._compile_expr(expr.left)
            j = self._emit(Op.JUMP_IF_TRUE_OR_POP, 0, line, col)
            self._pop()
            self._compile_expr(expr.right)
            self._patch(j, len(self.code.instructions))
            self._pop(2)
            return
        self._compile_expr(expr.left)
        self._compile_expr(expr.right)
        if op == "+":
            self._emit(Op.BINARY_ADD, 0, line, col)
        elif op == "-":
            self._emit(Op.BINARY_SUB, 0, line, col)
        elif op == "*":
            self._emit(Op.BINARY_MUL, 0, line, col)
        elif op == "/":
            self._emit(Op.BINARY_DIV, 0, line, col)
        elif op == "%":
            self._emit(Op.BINARY_MOD, 0, line, col)
        elif op == "**":
            self._emit(Op.BINARY_POW, 0, line, col)
        elif op in CMP_OPS:
            self._emit(Op.COMPARE_OP, CMP_OPS.index(op), line, col)
        self._pop(2)

    def _ex_MemberExpr(self, expr):
        self._compile_expr(expr.object)
        self._pop()
        self._emit(Op.LOAD_ATTR, self._name(expr.name), *self._line(expr))

    def _ex_IndexExpr(self, expr):
        self._compile_expr(expr.object)
        self._compile_expr(expr.index)
        self._pop(2)
        self._emit(Op.BINARY_SUBSCR, 0, *self._line(expr))

    def _ex_CallExpr(self, expr):
        line, col = self._line(expr)
        tool_path = self._tool_path(expr.callee)
        if tool_path is not None:
            midx = self._meta(tool_path)
            self._emit(Op.LOAD_META, midx, line, col)
            self._push()
        else:
            self._compile_expr(expr.callee)
        for a in expr.args:
            self._compile_expr(a)
        n_pos = len(expr.args)
        n_kw = len(expr.kwargs)
        if n_kw:
            kw_names = tuple(name for name, _ in expr.kwargs)
            kidx = self._meta(kw_names)
            for _, v in expr.kwargs:
                self._compile_expr(v)
            self._emit(Op.LOAD_META, kidx, line, col)
            self._push()
            op = Op.CALL_TOOL if tool_path is not None else Op.CALL_FUNCTION_KW
            self._emit(op, n_pos | (n_kw << 8), line, col)
            self._pop(n_pos + n_kw + 2)
        else:
            op = Op.CALL_TOOL if tool_path is not None else Op.CALL_FUNCTION
            self._emit(op, n_pos, line, col)
            self._pop(n_pos + 1)

    def _tool_path(self, callee) -> Optional[str]:
        parts = []
        node = callee
        while isinstance(node, nodes.MemberExpr):
            parts.append(node.name)
            node = node.object
        if not isinstance(node, nodes.Identifier):
            return None
        parts.append(node.name)
        path = ".".join(reversed(parts))
        if path in self.declared_tools:
            return path
        return None


def compile_program(program: nodes.Program, filename: str = "<stdin>") -> CodeObject:
    return Compiler(filename).compile(program)
