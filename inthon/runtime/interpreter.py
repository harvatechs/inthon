"""INTHON tree-walking interpreter (backend: "tree").

Executes the AST directly against an ExecutionContext.  Shares all runtime
services (tools, policy, memory, trace, sandbox, pybridge) with the
bytecode VM, so both backends produce identical results and traces.
"""

from __future__ import annotations

import time
from typing import Optional

from ..ast import nodes
from ..errors import (
    GuardAssertionError,
    InthonError,
    InthonIndexError,
    InthonSemanticError,
    InthonTypeError_,
    Span,
)
from ..memory import ops as memory_ops
from ..policy.model import Policy
from ..pybridge.calls import py_call, py_index, py_iter
from . import builtins as builtins_mod
from .context import ExecutionContext
from .environment import Environment
from .typecheck import check_value_against_type
from .values import (
    NONE,
    InthonAgent,
    InthonBool,
    InthonBoundMethod,
    InthonBuiltin,
    InthonCallable,
    InthonDict,
    InthonFloat,
    InthonInt,
    InthonList,
    InthonPyObject,
    InthonString,
    InthonToolNamespace,
    InthonToolRef,
    InthonValue,
    bool_value,
    box,
    display,
    truthy,
    values_equal,
)


class ReturnSignal(Exception):
    def __init__(self, value: InthonValue):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


_RETRYABLE = (GuardAssertionError,)


class Interpreter:
    def __init__(self, ctx: ExecutionContext):
        self.ctx = ctx
        builtins_mod.install_builtins(ctx.env)
        builtins_mod.set_active_interpreter(self)

    # -----------------------------------------------------------------------
    # entry point
    # -----------------------------------------------------------------------
    def run(self, program: nodes.Program) -> InthonValue:
        try:
            result = self.exec_block(program.statements, self.ctx.env, capture=True)
        except ReturnSignal as ret:
            result = ret.value
        return result

    # -----------------------------------------------------------------------
    # blocks & statements
    # -----------------------------------------------------------------------
    def exec_block(
        self, statements, env: Environment, capture: bool = False
    ) -> InthonValue:
        """Execute a statement list.  With capture=True the block's value is
        its last statement's value (declarations/assignments yield none)."""
        last: InthonValue = NONE
        for stmt in statements:
            value = self.exec_stmt(stmt, env)
            if capture:
                last = value
        return last

    def exec_stmt(self, stmt: nodes.Statement, env: Environment) -> InthonValue:
        handler = getattr(self, f"stmt_{type(stmt).__name__}", None)
        if handler is None:  # pragma: no cover - defensive
            raise InthonSemanticError(
                f"Unsupported statement {type(stmt).__name__}", span=stmt.span
            )
        return handler(stmt, env)

    # -- imports ------------------------------------------------------------
    def stmt_UseTool(self, stmt: nodes.UseTool, env: Environment):
        path = stmt.path
        self.ctx.tools.get(path, stmt.span)  # validates existence
        root = path.split(".")[0]
        if not env.is_defined_here(root):
            env.define(
                root,
                InthonToolNamespace(root, self.ctx.tools),
                mutable=False,
                span=stmt.span,
            )
        return NONE

    def stmt_UsePy(self, stmt: nodes.UsePy, env: Environment):
        proxy = self.ctx.importer.import_module(stmt.module, stmt.span)
        name = stmt.alias or stmt.module.split(".")[0]
        if env.is_defined_here(name):
            env.assign(name, proxy, stmt.span)
        else:
            env.define(name, proxy, mutable=False, span=stmt.span)
        return NONE

    def stmt_UseMemory(self, stmt: nodes.UseMemory, env: Environment):
        ns = stmt.namespace
        if stmt.args:
            suffix = ".".join(display(self.eval_expr(a, env)) for a in stmt.args)
            ns = f"{ns}.{suffix}"
        self.ctx.declare_memory(ns)
        # also register the plain root so remember/recall resolve
        self.ctx.declare_memory(stmt.namespace)
        return NONE

    # -- declarations ------------------------------------------------------------
    def stmt_LetDecl(self, stmt: nodes.LetDecl, env: Environment):
        value = self.eval_expr(stmt.value, env)
        if stmt.type_annotation is not None:
            check_value_against_type(value, stmt.type_annotation, stmt.span)
        env.define(stmt.name, value, mutable=True, span=stmt.span)
        self._trace_assign(stmt.name, value, stmt.span)
        return NONE

    def stmt_ConstDecl(self, stmt: nodes.ConstDecl, env: Environment):
        value = self.eval_expr(stmt.value, env)
        if stmt.type_annotation is not None:
            check_value_against_type(value, stmt.type_annotation, stmt.span)
        env.define(stmt.name, value, mutable=False, span=stmt.span)
        self._trace_assign(stmt.name, value, stmt.span)
        return NONE

    def _trace_assign(self, name: str, value: InthonValue, span: Optional[Span]):
        if self.ctx.tracer is not None:
            self.ctx.tracer.emit(
                "assign",
                span,
                name=name,
                type=value.type_name,
                preview=display(value)[:120],
            )

    def stmt_FnDecl(self, stmt: nodes.FnDecl, env: Environment):
        fn = InthonCallable(stmt, env)
        env.define(stmt.name, fn, mutable=False, span=stmt.span)
        return NONE

    # -- control flow ------------------------------------------------------------------
    def stmt_IfStmt(self, stmt: nodes.IfStmt, env: Environment):
        if truthy(self.eval_expr(stmt.condition, env)):
            return self.exec_block(
                stmt.then_block.statements, Environment(env), capture=True
            )
        if stmt.else_block is not None:
            if isinstance(stmt.else_block, nodes.IfStmt):
                return self.stmt_IfStmt(stmt.else_block, env)
            return self.exec_block(
                stmt.else_block.statements, Environment(env), capture=True
            )
        return NONE

    def stmt_ForStmt(self, stmt: nodes.ForStmt, env: Environment):
        iterable = self.eval_expr(stmt.iterable, env)
        items = self._iterate(iterable, stmt.span)
        loop_env = Environment(env, kind="loop")
        result = NONE
        for item in items:
            self.ctx.sandbox.tick(stmt.span)
            loop_env.set_local(stmt.var, item)
            try:
                value = self.exec_block(stmt.body.statements, loop_env, capture=True)
                if value is not NONE:
                    result = value
            except ContinueSignal:
                continue
            except BreakSignal:
                break
        return result

    def stmt_WhileStmt(self, stmt: nodes.WhileStmt, env: Environment):
        result = NONE
        while truthy(self.eval_expr(stmt.condition, env)):
            self.ctx.sandbox.tick(stmt.span)
            try:
                value = self.exec_block(
                    stmt.body.statements, Environment(env), capture=True
                )
                if value is not NONE:
                    result = value
            except ContinueSignal:
                continue
            except BreakSignal:
                break
        return result

    def stmt_ReturnStmt(self, stmt: nodes.ReturnStmt, env: Environment):
        value = self.eval_expr(stmt.value, env) if stmt.value is not None else NONE
        raise ReturnSignal(value)

    def stmt_BreakStmt(self, stmt: nodes.BreakStmt, env: Environment):
        raise BreakSignal()

    def stmt_ContinueStmt(self, stmt: nodes.ContinueStmt, env: Environment):
        raise ContinueSignal()

    # -- expressions as statements --------------------------------------------------------
    def stmt_ExprStmt(self, stmt: nodes.ExprStmt, env: Environment) -> InthonValue:
        return self.eval_expr(stmt.expr, env)

    def stmt_AssignStmt(self, stmt: nodes.AssignStmt, env: Environment):
        value = self.eval_expr(stmt.value, env)
        target = stmt.target
        if isinstance(target, nodes.Identifier):
            env.assign(target.name, value, stmt.span)
            self._trace_assign(target.name, value, stmt.span)
            return NONE
        if isinstance(target, nodes.IndexExpr):
            container = self.eval_expr(target.object, env)
            index = self.eval_expr(target.index, env)
            self._set_index(container, index, value, stmt.span)
            return NONE
        if isinstance(target, nodes.MemberExpr):
            obj = self.eval_expr(target.object, env)
            if isinstance(obj, InthonDict):
                obj.pairs[target.name] = value
                return NONE
            raise InthonTypeError_(
                f"Cannot assign member '{target.name}' on {obj.type_name}",
                span=stmt.span,
                hint="Member assignment is supported on dicts only.",
            )
        raise InthonSemanticError("Invalid assignment target", span=stmt.span)

    # -- agent primitives --------------------------------------------------------------------
    def stmt_ApproveStmt(self, stmt: nodes.ApproveStmt, env: Environment):
        details = {
            "agent": self.ctx.current_agent or "(top level)",
            "run_id": self.ctx.tracer.run_id,
        }
        self.ctx.approvals.request(stmt.tool_path, stmt.action, details, stmt.span)
        return NONE

    def stmt_RememberStmt(self, stmt: nodes.RememberStmt, env: Environment):
        self.ctx.policy.check("memory_persist", stmt.span, subject="remember")
        self.ctx.check_memory_declared(stmt.namespace, stmt.span)
        value = self.eval_expr(stmt.value, env)
        memory_ops.memory_remember(self.ctx, stmt.namespace, value, stmt.span)
        return NONE

    def stmt_ForgetStmt(self, stmt: nodes.ForgetStmt, env: Environment):
        self.ctx.policy.check("memory_persist", stmt.span, subject="forget")
        self.ctx.check_memory_declared(stmt.namespace, stmt.span)
        value = self.eval_expr(stmt.value, env)
        memory_ops.memory_forget(self.ctx, stmt.namespace, value, stmt.span)
        return NONE

    def stmt_GuardStmt(self, stmt: nodes.GuardStmt, env: Environment):
        value = self.eval_expr(stmt.condition, env)
        if self.ctx.tracer is not None:
            self.ctx.tracer.emit("guard", stmt.span, passed=bool(truthy(value)))
        if not truthy(value):
            raise GuardAssertionError(
                "Guard condition failed",
                span=stmt.span,
                hint="The guard expression evaluated to a falsy value; inside retry this triggers a retry.",
            )
        return NONE

    def stmt_RetryStmt(self, stmt: nodes.RetryStmt, env: Environment):
        attempts = max(1, stmt.count)
        last_error: Optional[BaseException] = None
        for attempt in range(1, attempts + 1):
            try:
                if self.ctx.tracer is not None:
                    self.ctx.tracer.emit(
                        "retry",
                        stmt.span,
                        attempt=attempt,
                        max_attempts=attempts,
                        backoff=stmt.backoff,
                    )
                return self.exec_block(
                    stmt.body.statements, Environment(env), capture=True
                )
            except (BreakSignal, ContinueSignal, ReturnSignal):
                raise
            except InthonError as exc:
                last_error = exc
                if self.ctx.tracer is not None:
                    self.ctx.tracer.emit(
                        "retry_failed",
                        stmt.span,
                        attempt=attempt,
                        error=exc.code,
                        message=exc.message,
                    )
                if attempt < attempts:
                    time.sleep(self._backoff_delay(stmt.backoff, attempt))
        if stmt.catch_body is not None:
            catch_env = Environment(env, kind="catch")
            err_value = InthonDict(
                {
                    "message": InthonString(
                        getattr(last_error, "message", str(last_error))
                    ),
                    "code": InthonString(getattr(last_error, "code", "INTHON_000")),
                }
            )
            catch_env.define(
                stmt.catch_name or "err", err_value, mutable=True, span=stmt.span
            )
            return self.exec_block(stmt.catch_body.statements, catch_env, capture=True)
        assert last_error is not None
        raise last_error

    @staticmethod
    def _backoff_delay(strategy: str, attempt: int) -> float:
        base = 0.05
        if strategy == "exponential":
            return min(0.5, base * (2 ** (attempt - 1)))
        if strategy == "linear":
            return min(0.5, base * attempt)
        return base  # fixed (and any unknown strategy)

    def stmt_EvalStmt(self, stmt: nodes.EvalStmt, env: Environment):
        criteria = stmt.criteria
        if not criteria:
            table = self.ctx.criteria_tables.get(stmt.rubric)
            if table is None:
                if stmt.subject == "self":
                    # self-eval preview: no rubric registered → record and pass
                    if self.ctx.tracer is not None:
                        self.ctx.tracer.emit(
                            "eval",
                            stmt.span,
                            rubric=stmt.rubric,
                            subject="self",
                            passed=True,
                            note="self-eval preview",
                        )
                    return NONE
                raise InthonSemanticError(
                    f"Unknown rubric '{stmt.rubric}'",
                    span=stmt.span,
                    hint="Declare it inside the agent: criteria "
                    + stmt.rubric
                    + " { ... }, "
                    "or pass criteria inline: eval x against "
                    + stmt.rubric
                    + " { ... }.",
                )
            criteria = table
        if stmt.subject == "self":
            subject_value = NONE
        else:
            subject_value = env.lookup(stmt.subject, stmt.span)
        report = self._evaluate_criteria(subject_value, criteria, stmt, env)
        if self.ctx.tracer is not None:
            self.ctx.tracer.emit(
                "eval",
                stmt.span,
                rubric=stmt.rubric,
                subject=stmt.subject,
                passed=report.pairs["passed"].value,
                score=report.pairs["score"].to_python(),
            )
        if not report.pairs["passed"].value:
            failed_msg = "Rubric evaluation failed"
            for detail in report.pairs["details"].items:
                if not detail.pairs["passed"].value:
                    name = detail.pairs["name"].value
                    op = detail.pairs["op"].value
                    expected = detail.pairs["expected"].to_python()
                    actual = detail.pairs["actual"].to_python()
                    failed_msg = f"INTHON_RUNTIME_EVAL: Criterion '{name}' failed: expected {op} {expected}, got {actual}"
                    break
            raise InthonTypeError_(failed_msg, span=stmt.span)
        return report

    def _evaluate_criteria(
        self, subject: InthonValue, criteria, stmt, env: Environment
    ) -> InthonDict:
        details = []
        passed_count = 0
        subject_map = subject.pairs if isinstance(subject, InthonDict) else {}
        for criterion in criteria:
            expected = self.eval_expr(criterion.value, env)
            actual = subject_map.get(criterion.name, NONE)
            if actual is NONE and env.is_defined(criterion.name):
                actual = env.lookup(criterion.name, stmt.span)
            ok = self._criterion_passes(actual, criterion.op, expected)
            passed_count += 1 if ok else 0
            details.append(
                InthonDict(
                    {
                        "name": InthonString(criterion.name),
                        "op": InthonString(criterion.op),
                        "expected": expected,
                        "actual": actual,
                        "passed": bool_value(ok),
                    }
                )
            )
        total = len(criteria)
        return InthonDict(
            {
                "passed": bool_value(passed_count == total),
                "score": InthonFloat(passed_count / total if total else 1.0),
                "total": InthonInt(total),
                "details": InthonList(details),
            }
        )

    @staticmethod
    def _criterion_passes(actual: InthonValue, op: str, expected: InthonValue) -> bool:
        if op == ":":
            op = "=="
        try:
            if op == "==":
                return values_equal(actual, expected)
            if op == "!=":
                return not values_equal(actual, expected)
            a, b = actual.to_python(), expected.to_python()
            if op == "<":
                return a < b
            if op == "<=":
                return a <= b
            if op == ">":
                return a > b
            if op == ">=":
                return a >= b
        except TypeError:
            return False
        return False

    def stmt_PolicyStmt(self, stmt: nodes.PolicyStmt, env: Environment):
        policy = Policy.from_entries(stmt.entries, span=stmt.span)
        self.ctx.policy.apply(policy, stmt.span, label="top-level")
        return NONE

    # -- agents ---------------------------------------------------------------------------------
    def stmt_AgentDecl(self, stmt: nodes.AgentDecl, env: Environment):
        # imports inside the agent body are capabilities: process them first
        agent_env = Environment(env, kind="agent", label=stmt.name)
        for imp in stmt.imports:
            self.exec_stmt(imp, agent_env)

        # typed inputs/outputs metadata; criteria & rewriters registered for eval
        for criteria_decl in stmt.criteria:
            self.ctx.criteria_tables[criteria_decl.name] = criteria_decl.criteria

        agent_value = InthonAgent(stmt, agent_env)
        env.define(stmt.name, agent_value, mutable=False, span=stmt.span)

        # Semantics: a bare declaration with no required inputs executes the
        # plan immediately; otherwise it waits to be invoked like a function.
        if not stmt.inputs and stmt.plan is not None:
            return self._invoke_agent(agent_value, {}, stmt.span)
        return NONE

    def _invoke_agent(
        self, agent: InthonAgent, kwargs: dict, span: Optional[Span]
    ) -> InthonValue:
        from .agents import invoke_agent

        def run_plan(decl, bound_inputs):
            call_env = Environment(
                agent.closure_env, kind="agent-call", label=decl.name
            )
            for name, value in bound_inputs.items():
                call_env.define(name, value, mutable=True, span=span)
            try:
                return self.exec_block(decl.plan.statements, call_env, capture=True)
            except ReturnSignal as ret:
                return ret.value

        return invoke_agent(self.ctx, agent, kwargs, span, run_plan)

    # ---------------------------------------------------------------------------
    # expressions
    # ---------------------------------------------------------------------------
    def eval_expr(
        self, expr: Optional[nodes.Expression], env: Environment
    ) -> InthonValue:
        if expr is None:
            return NONE
        handler = getattr(self, f"expr_{type(expr).__name__}", None)
        if handler is None:  # pragma: no cover - defensive
            raise InthonSemanticError(
                f"Unsupported expression {type(expr).__name__}", span=expr.span
            )
        return handler(expr, env)

    # -- literals --------------------------------------------------------------
    def expr_IntLiteral(self, expr: nodes.IntLiteral, env) -> InthonValue:
        return InthonInt(expr.value)

    def expr_FloatLiteral(self, expr: nodes.FloatLiteral, env) -> InthonValue:
        return InthonFloat(expr.value)

    def expr_StringLiteral(self, expr: nodes.StringLiteral, env) -> InthonValue:
        return InthonString(expr.value)

    def expr_BoolLiteral(self, expr: nodes.BoolLiteral, env) -> InthonValue:
        return bool_value(expr.value)

    def expr_NoneLiteral(self, expr: nodes.NoneLiteral, env) -> InthonValue:
        return NONE

    def expr_InterpString(self, expr: nodes.InterpString, env) -> InthonValue:
        out = []
        for part in expr.parts:
            if isinstance(part, str):
                out.append(part)
            else:
                out.append(display(self.eval_expr(part, env)))
        return InthonString("".join(out))

    def expr_ListExpr(self, expr: nodes.ListExpr, env) -> InthonValue:
        return InthonList([self.eval_expr(e, env) for e in expr.elements])

    def expr_DictExpr(self, expr: nodes.DictExpr, env) -> InthonValue:
        pairs = {}
        for key_expr, value_expr in expr.pairs:
            key = self.eval_expr(key_expr, env)
            value = self.eval_expr(value_expr, env)
            if isinstance(key, (InthonList, InthonDict, InthonPyObject)):
                raise InthonTypeError_(
                    f"Unhashable dict key type '{key.type_name}'", span=key_expr.span
                )
            pairs[key.to_python()] = value
        return InthonDict(pairs)

    def expr_Identifier(self, expr: nodes.Identifier, env) -> InthonValue:
        return env.lookup(expr.name, expr.span)

    def expr_RecallExpr(self, expr: nodes.RecallExpr, env) -> InthonValue:
        self.ctx.policy.check("memory_persist", expr.span, subject="recall")
        self.ctx.check_memory_declared(expr.namespace, expr.span)
        return memory_ops.memory_recall(self.ctx, expr.namespace, expr.query, expr.span)

    # -- operators ------------------------------------------------------------------
    def expr_UnaryOp(self, expr: nodes.UnaryOp, env) -> InthonValue:
        operand = self.eval_expr(expr.operand, env)
        if expr.op == "not":
            return bool_value(not truthy(operand))
        if expr.op == "-":
            if isinstance(operand, InthonInt):
                return InthonInt(-operand.value)
            if isinstance(operand, InthonFloat):
                return InthonFloat(-operand.value)
            raise InthonTypeError_(f"Cannot negate {operand.type_name}", span=expr.span)
        if expr.op == "+":
            if isinstance(operand, (InthonInt, InthonFloat)):
                return operand
            raise InthonTypeError_(
                f"Unary + not supported for {operand.type_name}", span=expr.span
            )
        raise InthonSemanticError(f"Unknown unary operator '{expr.op}'", span=expr.span)

    def expr_BinaryOp(self, expr: nodes.BinaryOp, env) -> InthonValue:
        op = expr.op
        if op == "and":
            left = self.eval_expr(expr.left, env)
            if not truthy(left):
                return left
            return self.eval_expr(expr.right, env)
        if op == "or":
            left = self.eval_expr(expr.left, env)
            if truthy(left):
                return left
            return self.eval_expr(expr.right, env)

        left = self.eval_expr(expr.left, env)
        right = self.eval_expr(expr.right, env)

        if op == "==":
            return bool_value(values_equal(left, right))
        if op == "!=":
            return bool_value(not values_equal(left, right))

        if op in ("+", "-", "*", "/", "%", "**"):
            return self._arith(left, op, right, expr.span)
        if op in ("<", "<=", ">", ">="):
            return self._compare(left, op, right, expr.span)
        raise InthonSemanticError(f"Unknown operator '{op}'", span=expr.span)

    def _arith(
        self, left: InthonValue, op: str, right: InthonValue, span
    ) -> InthonValue:
        # strings
        if (
            isinstance(left, InthonString)
            and isinstance(right, InthonString)
            and op == "+"
        ):
            return InthonString(left.value + right.value)
        if (
            isinstance(left, InthonString)
            and isinstance(right, InthonInt)
            and op == "*"
        ):
            return InthonString(left.value * right.value)
        if isinstance(left, InthonList) and isinstance(right, InthonList) and op == "+":
            return InthonList(left.items + right.items)
        if isinstance(left, InthonList) and isinstance(right, InthonInt) and op == "*":
            return InthonList(left.items * right.value)
        # numbers
        if isinstance(left, (InthonInt, InthonFloat, InthonBool)) and isinstance(
            right, (InthonInt, InthonFloat, InthonBool)
        ):
            a, b = left.to_python(), right.to_python()
            both_int = isinstance(left, InthonInt) and isinstance(right, InthonInt)
            if op == "+":
                return _num_box(a + b, both_int)
            if op == "-":
                return _num_box(a - b, both_int)
            if op == "*":
                return _num_box(a * b, both_int)
            if op == "/":
                if b == 0:
                    raise InthonTypeError_(
                        "Division by zero",
                        span=span,
                        hint="Guard the divisor: guard b != 0",
                    )
                return InthonFloat(a / b)
            if op == "%":
                if b == 0:
                    raise InthonTypeError_("Modulo by zero", span=span)
                return _num_box(a % b, both_int)
            if op == "**":
                return _num_box(a**b, both_int)
        raise InthonTypeError_(
            f"Operator '{op}' not supported for {left.type_name} and {right.type_name}",
            span=span,
            hint=f"Got {left.display()!r} {op} {right.display()!r}. Convert with str(), int() or float().",
        )

    def _compare(
        self, left: InthonValue, op: str, right: InthonValue, span
    ) -> InthonValue:
        if isinstance(left, (InthonInt, InthonFloat, InthonBool)) and isinstance(
            right, (InthonInt, InthonFloat, InthonBool)
        ):
            a, b = left.to_python(), right.to_python()
        elif isinstance(left, InthonString) and isinstance(right, InthonString):
            a, b = left.value, right.value
        else:
            raise InthonTypeError_(
                f"Cannot compare {left.type_name} with {right.type_name} using '{op}'",
                span=span,
                hint="Ordering comparisons work on numbers and strings; use ==/!= for deep equality.",
            )
        return bool_value({"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op])

    # -- postfix ----------------------------------------------------------------------
    def expr_MemberExpr(self, expr: nodes.MemberExpr, env) -> InthonValue:
        obj = self.eval_expr(expr.object, env)
        return self._get_member(obj, expr.name, expr.span)

    def _get_member(self, obj: InthonValue, name: str, span) -> InthonValue:
        if isinstance(obj, InthonToolNamespace):
            path = f"{obj.root}.{name}"
            if self.ctx.tools.has(path):
                return InthonToolRef(path)
            # allow deeper namespaces: web.sub.tool
            prefix = path + "."
            if any(p.startswith(prefix) for p in self.ctx.tools.paths()):
                return InthonToolNamespace(path, self.ctx.tools)
            from ..errors import ToolNotFoundError

            raise ToolNotFoundError(
                f"Unknown tool '{path}'",
                span=span,
                hint=f"Did you declare it? Add 'use tool {path}'. Registered: {', '.join(self.ctx.tools.paths())}",
            )
        if isinstance(obj, InthonPyObject):
            importer = getattr(obj, "_importer", None) or self.ctx.importer
            return importer.getattr(obj, name, span)
        if isinstance(obj, InthonDict):
            if name in obj.pairs:
                return obj.pairs[name]
        return builtins_mod.get_method(obj, name, span)

    def expr_IndexExpr(self, expr: nodes.IndexExpr, env) -> InthonValue:
        obj = self.eval_expr(expr.object, env)
        index = self.eval_expr(expr.index, env)
        if isinstance(obj, InthonList):
            if not isinstance(index, InthonInt):
                raise InthonTypeError_(
                    f"List index must be an int, got {index.type_name}", span=expr.span
                )
            i = index.value
            try:
                return obj.items[i]
            except IndexError:
                raise InthonIndexError(
                    f"List index {i} out of range (length {len(obj.items)})",
                    span=expr.span,
                ) from None
        if isinstance(obj, InthonString):
            if not isinstance(index, InthonInt):
                raise InthonTypeError_("String index must be an int", span=expr.span)
            i = index.value
            try:
                return InthonString(obj.value[i])
            except IndexError:
                raise InthonIndexError(
                    f"String index {i} out of range (length {len(obj.value)})",
                    span=expr.span,
                ) from None
        if isinstance(obj, InthonDict):
            key = index.to_python()
            if key in obj.pairs:
                return obj.pairs[key]
            available = ", ".join(map(str, list(obj.pairs.keys())[:5]))
            raise InthonIndexError(
                f"Key {key!r} not found in dict",
                span=expr.span,
                hint=f"Available keys: {available}{'…' if len(obj.pairs) > 5 else ''}. "
                f"Use .get(key, default) to avoid the error.",
            )
        if isinstance(obj, InthonPyObject):
            return py_index(self.ctx, obj, index, expr.span)
        raise InthonTypeError_(
            f"Indexing not supported for {obj.type_name}", span=expr.span
        )

    def _set_index(
        self, container: InthonValue, index: InthonValue, value: InthonValue, span
    ):
        if isinstance(container, InthonList):
            if not isinstance(index, InthonInt):
                raise InthonTypeError_("List index must be an int", span=span)
            i = index.value
            if not -len(container.items) <= i < len(container.items):
                raise InthonIndexError(
                    f"List index {i} out of range (length {len(container.items)})",
                    span=span,
                )
            container.items[i] = value
            return
        if isinstance(container, InthonDict):
            container.pairs[index.to_python()] = value
            return
        if isinstance(container, InthonPyObject):
            raise InthonTypeError_(
                "Item assignment on Python objects is blocked by the sandbox", span=span
            )
        raise InthonTypeError_(
            f"Indexed assignment not supported for {container.type_name}", span=span
        )

    def expr_CallExpr(self, expr: nodes.CallExpr, env) -> InthonValue:
        callee = self.eval_expr(expr.callee, env)
        args = [self.eval_expr(a, env) for a in expr.args]
        kwargs = {name: self.eval_expr(v, env) for name, v in expr.kwargs}
        return self.call_value(callee, args, kwargs, expr.span)

    # ---------------------------------------------------------------------------
    # call dispatch (shared with method map/filter)
    # ---------------------------------------------------------------------------
    def call_value(
        self, callee: InthonValue, args: list, kwargs: dict, span
    ) -> InthonValue:
        if isinstance(callee, InthonBuiltin):
            return callee.fn(self.ctx, args, kwargs, span)
        if isinstance(callee, InthonBoundMethod):
            return callee.fn(callee.receiver, args, kwargs, span)
        if isinstance(callee, InthonToolRef):
            return self.ctx.tools.invoke(self.ctx, callee.path, args, kwargs, span)
        if isinstance(callee, InthonCallable):
            return self._call_function(callee, args, kwargs, span)
        if isinstance(callee, InthonAgent):
            return self._invoke_agent(callee, kwargs, span)
        if isinstance(callee, InthonPyObject):
            return py_call(self.ctx, callee, args, kwargs, span)
        raise InthonTypeError_(
            f"Value of type {callee.type_name} is not callable",
            span=span,
            hint="Only functions, agents, tools, builtins and Python callables can be called.",
        )

    def _call_function(
        self, fn: InthonCallable, args: list, kwargs: dict, span
    ) -> InthonValue:
        from .calls import bind_params

        decl = fn.decl
        params = list(decl.params)
        bound = bind_params(
            decl,
            args,
            kwargs,
            eval_default=lambda default: self.eval_expr(default, fn.closure_env),
            span=span,
        )

        self.ctx.sandbox.enter_call(decl.name, span)
        call_env = Environment(fn.closure_env, kind="fn", label=decl.name)
        for param in params:
            value = bound[param.name]
            if param.type_annotation is not None:
                check_value_against_type(value, param.type_annotation, span)
            call_env.define(param.name, value, mutable=True, span=span)
        try:
            result = self.exec_block(decl.body.statements, call_env, capture=True)
        except ReturnSignal as ret:
            result = ret.value
        finally:
            self.ctx.sandbox.exit_call()
        if decl.return_type is not None:
            check_value_against_type(result, decl.return_type, span)
        return result

    # ---------------------------------------------------------------------------
    # iteration
    # ---------------------------------------------------------------------------
    def _iterate(self, iterable: InthonValue, span):
        if isinstance(iterable, InthonList):
            return list(iterable.items)
        if isinstance(iterable, InthonString):
            return [InthonString(ch) for ch in iterable.value]
        if isinstance(iterable, InthonDict):
            return [box(k) for k in iterable.pairs.keys()]
        if isinstance(iterable, InthonPyObject):
            return list(py_iter(iterable, span))
        raise InthonTypeError_(
            f"Cannot iterate over {iterable.type_name}",
            span=span,
            hint="Iterate a list, string, dict (keys), range(...), or a Python iterable.",
        )


def _num_box(value, both_int: bool) -> InthonValue:
    if both_int:
        return InthonInt(int(value))
    return InthonFloat(float(value))


def run_program(program: nodes.Program, ctx: ExecutionContext) -> InthonValue:
    return Interpreter(ctx).run(program)
