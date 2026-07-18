"""Semantic analyzer (spec §semantic): scope resolution, capability
validation, type warnings, multi-error collection (AS-16)."""

from __future__ import annotations

import difflib
from typing import Optional

from ..ast import nodes
from ..errors import (
    InthonCapabilityError,
    InthonConstError,
    InthonDuplicateError,
    InthonNameError,
    InthonSemanticError,
    InthonStaticTypeError,
    Span,
    ToolNotFoundError,
    PyBridgeError,
)
from ..lexer.keywords import NOT_KEYWORDS
from ..runtime.builtins import BUILTINS
from ..runtime.context import ExecutionContext
from .scope import Scope, Symbol
from .type_checker import TypeEnv, compatible, infer_expr_type, type_of_typeexpr


class AnalysisFailure(InthonSemanticError):
    """Raised when analysis completes with ≥1 error; carries all of them."""

    code = "INTHON_SEM_000"

    def __init__(self, errors: list):
        self.errors_list = errors
        first = errors[0]
        summary = "\n\n".join(e.formatted() for e in errors)
        super().__init__(
            f"{len(errors)} semantic error(s):\n\n{summary}",
            span=first.span,
            hint=first.hint,
        )


class SemanticAnalyzer:
    def __init__(self, ctx: Optional[ExecutionContext] = None):
        if ctx is None:
            from ..runtime.context import ExecutionContext
            ctx = ExecutionContext()
        self.ctx = ctx
        self.errors: list = []
        self.warnings: list = []
        self.fn_returns: dict[str, str] = {}
        self.fn_params: dict[str, list[tuple[str, str]]] = {}
        self.memory_namespaces: set[str] = set()
        self.tool_paths: set[str] = set()
        self.strict = bool(getattr(ctx.options, "strict_types", False))

    @property
    def _errors(self) -> list:
        return self.errors

    @_errors.setter
    def _errors(self, val: list) -> None:
        self.errors = val

    # ------------------------------------------------------------------
    def analyze(self, program: nodes.Program) -> nodes.Program:
        global_scope = Scope(kind="global", label="global")
        for name in BUILTINS:
            global_scope.declare(Symbol(name, "builtin"))
        tenv = TypeEnv()
        for name in BUILTINS:
            tenv.set(name, "fn")
        if self.ctx and hasattr(self.ctx, "env") and self.ctx.env:
            for name in self.ctx.env.names():
                if name not in BUILTINS:
                    is_const = name in self.ctx.env.consts
                    global_scope.declare(Symbol(name, "const" if is_const else "let"))
                    tenv.set(name, "any")
        self._walk_statements(program.statements, global_scope, tenv, in_loop=False, in_fn=False)
        if self.errors:
            for err in self.errors:
                if isinstance(err, PyBridgeError):
                    raise err
            raise AnalysisFailure(self.errors)
        return program

    # ------------------------------------------------------------------
    # statements
    # ------------------------------------------------------------------
    def _walk_statements(self, statements, scope: Scope, tenv: TypeEnv, in_loop: bool, in_fn: bool):
        for stmt in statements:
            self._walk_statement(stmt, scope, tenv, in_loop, in_fn)

    def _child(self, scope: Scope, kind: str, label: str = "") -> Scope:
        child = Scope(scope, kind=kind, label=label)
        scope.children.append(child)
        return child

    def _walk_statement(self, stmt, scope: Scope, tenv: TypeEnv, in_loop: bool, in_fn: bool):
        method = getattr(self, f"_st_{type(stmt).__name__}", None)
        if method is None:  # pragma: no cover
            return
        method(stmt, scope, tenv, in_loop, in_fn)

    # -- imports -------------------------------------------------------------
    def _st_UseTool(self, stmt: nodes.UseTool, scope, tenv, *_):
        path = stmt.path
        if not self.ctx.tools.has(path):
            known = self.ctx.tools.paths()
            close = difflib.get_close_matches(path, known, n=1, cutoff=0.6)
            hint = f"Did you mean '{close[0]}'?" if close else f"Registered tools: {', '.join(known)}"
            self._error(ToolNotFoundError(f"Unknown tool '{path}'", span=stmt.span, hint=hint))
            return
        root = path.split(".")[0]
        scope.declare(Symbol(root, "tool", stmt.span))
        tenv.set(root, "tool")
        self.tool_paths.add(path)

    def _st_UsePy(self, stmt: nodes.UsePy, scope, tenv, *_):
        top = stmt.module.split(".")[0]
        from ..pybridge.allowlist import HARD_DENYLIST

        if top in HARD_DENYLIST or stmt.module in HARD_DENYLIST or (
            top not in self.ctx.importer.allowlist and stmt.module not in self.ctx.importer.allowlist
        ):
            self._error(
                PyBridgeError(
                    f"Python module '{stmt.module}' is not permitted under the active policy. "
                    f"If you need this module, add it to [pybridge] allowed_modules.",
                    span=stmt.span,
                )
            )
        name = stmt.alias or top
        scope.declare(Symbol(name, "py", stmt.span))
        tenv.set(name, "py")

    def _st_UseMemory(self, stmt: nodes.UseMemory, scope, tenv, *_):
        ns = stmt.namespace
        if stmt.args:
            suffix = ".".join(self._const_string(a, scope, tenv) for a in stmt.args)
            ns = f"{ns}.{suffix}"
        self.memory_namespaces.add(ns)
        self.memory_namespaces.add(stmt.namespace)
        self.ctx.declare_memory(stmt.namespace)

    def _const_string(self, expr, scope, tenv) -> str:
        if isinstance(expr, nodes.StringLiteral):
            return expr.value
        return "_"

    # -- declarations -------------------------------------------------------------
    def _st_LetDecl(self, stmt: nodes.LetDecl, scope, tenv, *_):
        value_type = infer_expr_type(stmt.value, tenv, self.fn_returns)
        self._walk_expr(stmt.value, scope, tenv, False, False)
        if stmt.type_annotation is not None:
            declared = type_of_typeexpr(stmt.type_annotation)
            if not compatible(declared, value_type):
                self._type_warning(
                    f"Type mismatch: variable '{stmt.name}' declared as {stmt.type_annotation.render()} "
                    f"but assigned {value_type}",
                    stmt.span,
                )
            tenv.set(stmt.name, declared)
        else:
            tenv.set(stmt.name, value_type)
        self._declare(scope, Symbol(stmt.name, "let", stmt.span, stmt.type_annotation))

    def _st_ConstDecl(self, stmt: nodes.ConstDecl, scope, tenv, *_):
        value_type = infer_expr_type(stmt.value, tenv, self.fn_returns)
        self._walk_expr(stmt.value, scope, tenv, False, False)
        if stmt.type_annotation is not None:
            declared = type_of_typeexpr(stmt.type_annotation)
            if not compatible(declared, value_type):
                self._type_warning(
                    f"Type mismatch: constant '{stmt.name}' declared as {stmt.type_annotation.render()} "
                    f"but assigned {value_type}",
                    stmt.span,
                )
            tenv.set(stmt.name, declared)
        else:
            tenv.set(stmt.name, value_type)
        self._declare(scope, Symbol(stmt.name, "const", stmt.span, stmt.type_annotation))

    def _st_FnDecl(self, stmt: nodes.FnDecl, scope, tenv, *_):
        self._declare(scope, Symbol(stmt.name, "fn", stmt.span))
        if stmt.return_type is not None:
            self.fn_returns[stmt.name] = type_of_typeexpr(stmt.return_type)
        tenv.set(stmt.name, "fn")
        params_info = []
        for param in stmt.params:
            ptype = type_of_typeexpr(param.type_annotation) if param.type_annotation else "any"
            params_info.append((param.name, ptype))
        self.fn_params[stmt.name] = params_info
        fn_scope = self._child(scope, "fn", stmt.name)
        fn_tenv = TypeEnv(tenv)
        for param in stmt.params:
            if fn_scope.lookup_here(param.name):
                self._error(
                    InthonDuplicateError(
                        f"Duplicate parameter '{param.name}'", span=param.span
                    )
                )
            fn_scope.declare(Symbol(param.name, "param", param.span, param.type_annotation))
            fn_tenv.set(
                param.name,
                type_of_typeexpr(param.type_annotation) if param.type_annotation else "any",
            )
            if param.default is not None:
                self._walk_expr(param.default, scope, tenv, False, False)
        self._walk_statements(stmt.body.statements, fn_scope, fn_tenv, in_loop=False, in_fn=stmt.name)

    def _st_AgentDecl(self, stmt: nodes.AgentDecl, scope, tenv, *_):
        self._declare(scope, Symbol(stmt.name, "agent", stmt.span))
        tenv.set(stmt.name, "agent")
        agent_scope = self._child(scope, "agent", stmt.name)
        agent_tenv = TypeEnv(tenv)
        for imp in stmt.imports:
            self._walk_statement(imp, agent_scope, agent_tenv, False, False)
        seen_inputs = set()
        for field in stmt.inputs:
            if field.name in seen_inputs:
                self._error(
                    InthonDuplicateError(f"Duplicate input '{field.name}'", span=field.span)
                )
            seen_inputs.add(field.name)
            agent_scope.declare(Symbol(field.name, "param", field.span, field.type_annotation))
            agent_tenv.set(
                field.name,
                type_of_typeexpr(field.type_annotation) if field.type_annotation else "any",
            )
        # static policy/tool permission pre-check
        self._check_agent_permissions(stmt)
        if stmt.plan is None:
            self._error(
                InthonSemanticError(
                    f"Agent '{stmt.name}' has no plan block",
                    span=stmt.span,
                    hint="Add a plan { ... } body — it is the executable core of the agent.",
                )
            )
        else:
            self._walk_statements(stmt.plan.statements, agent_scope, agent_tenv, False, False)
        # rewriters are bodies with access to the eval context
        for rw in stmt.rewriters:
            rw_scope = self._child(agent_scope, "fn", f"rewriter:{rw.name}")
            rw_scope.declare(Symbol("ctx", "param"))
            self._walk_statements(rw.body.statements, rw_scope, TypeEnv(agent_tenv), False, True)

    def _check_agent_permissions(self, stmt: nodes.AgentDecl):
        from ..policy.model import Policy

        try:
            policy = Policy.from_entries(stmt.policies, span=stmt.span)
        except InthonSemanticError as exc:
            self._error(exc)
            return
        declared_tools = {imp.path for imp in stmt.imports if isinstance(imp, nodes.UseTool)}
        for path in declared_tools:
            if not self.ctx.tools.has(path):
                continue
            spec = self.ctx.tools.get(path)
            for permission in spec.permissions:
                if not policy.grants(permission):
                    self._warning(
                        f"Agent '{stmt.name}' calls {path} (requires '{permission}') but its "
                        f"policy does not grant it — the call will fail at runtime.",
                        stmt.span,
                    )

    # -- control flow ----------------------------------------------------------------------
    def _st_IfStmt(self, stmt: nodes.IfStmt, scope, tenv, in_loop, in_fn):
        self._walk_expr(stmt.condition, scope, tenv, in_loop, in_fn)
        self._walk_statements(
            stmt.then_block.statements, self._child(scope, "block"), TypeEnv(tenv), in_loop, in_fn
        )
        if stmt.else_block is not None:
            if isinstance(stmt.else_block, nodes.IfStmt):
                self._st_IfStmt(stmt.else_block, scope, tenv, in_loop, in_fn)
            else:
                self._walk_statements(
                    stmt.else_block.statements, self._child(scope, "block"), TypeEnv(tenv), in_loop, in_fn
                )

    def _st_ForStmt(self, stmt: nodes.ForStmt, scope, tenv, in_loop, in_fn):
        self._walk_expr(stmt.iterable, scope, tenv, in_loop, in_fn)
        loop_scope = self._child(scope, "loop")
        loop_scope.declare(Symbol(stmt.var, "loop", stmt.span))
        loop_tenv = TypeEnv(tenv)
        loop_tenv.set(stmt.var, "any")
        self._walk_statements(stmt.body.statements, loop_scope, loop_tenv, True, in_fn)

    def _st_WhileStmt(self, stmt: nodes.WhileStmt, scope, tenv, in_loop, in_fn):
        self._walk_expr(stmt.condition, scope, tenv, in_loop, in_fn)
        self._walk_statements(
            stmt.body.statements, self._child(scope, "loop"), TypeEnv(tenv), True, in_fn
        )

    def _st_ReturnStmt(self, stmt: nodes.ReturnStmt, scope, tenv, in_loop, in_fn):
        if stmt.value is not None:
            self._walk_expr(stmt.value, scope, tenv, in_loop, in_fn)
            if isinstance(in_fn, str):
                expected = self.fn_returns.get(in_fn, "any")
                value_type = infer_expr_type(stmt.value, tenv, self.fn_returns)
                if not compatible(expected, value_type):
                    self._type_warning(
                        f"Type mismatch: function return type must be {expected}, got {value_type} (in function '{in_fn}')",
                        stmt.span,
                    )

    def _st_BreakStmt(self, stmt, scope, tenv, in_loop, in_fn):
        if not in_loop:
            self._error(
                InthonSemanticError("'break' outside of a loop", span=stmt.span,
                                    hint="break/continue are only valid inside for/while bodies.")
            )

    def _st_ContinueStmt(self, stmt, scope, tenv, in_loop, in_fn):
        if not in_loop:
            self._error(
                InthonSemanticError("'continue' outside of a loop", span=stmt.span,
                                    hint="break/continue are only valid inside for/while bodies.")
            )

    # -- agent primitives ---------------------------------------------------------------------
    def _st_ApproveStmt(self, stmt: nodes.ApproveStmt, scope, tenv, *_):
        root = stmt.tool_path.split(".")[0]
        if scope.lookup(root) is None:
            self._error(
                InthonCapabilityError(
                    f"approve references undeclared tool '{stmt.tool_path}'",
                    span=stmt.span,
                    hint=f"Add 'use tool {stmt.tool_path}' first.",
                )
            )

    def _st_RememberStmt(self, stmt: nodes.RememberStmt, scope, tenv, in_loop, in_fn):
        self._walk_expr(stmt.value, scope, tenv, in_loop, in_fn)
        self._check_memory_ns(stmt.namespace, stmt.span)

    def _st_ForgetStmt(self, stmt: nodes.ForgetStmt, scope, tenv, in_loop, in_fn):
        self._walk_expr(stmt.value, scope, tenv, in_loop, in_fn)
        self._check_memory_ns(stmt.namespace, stmt.span)

    def _st_GuardStmt(self, stmt: nodes.GuardStmt, scope, tenv, in_loop, in_fn):
        self._walk_expr(stmt.condition, scope, tenv, in_loop, in_fn)

    def _st_RetryStmt(self, stmt: nodes.RetryStmt, scope, tenv, in_loop, in_fn):
        if stmt.backoff not in ("exponential", "linear", "fixed"):
            self._error(
                InthonSemanticError(
                    f"Unknown backoff strategy '{stmt.backoff}'",
                    span=stmt.span,
                    hint="Use exponential, linear, or fixed.",
                )
            )
        self._walk_statements(stmt.body.statements, self._child(scope, "block"), TypeEnv(tenv), in_loop, in_fn)
        if stmt.catch_body is not None:
            catch_scope = self._child(scope, "catch")
            catch_scope.declare(Symbol(stmt.catch_name or "err", "catch", stmt.span))
            self._walk_statements(stmt.catch_body.statements, catch_scope, TypeEnv(tenv), in_loop, in_fn)

    def _st_EvalStmt(self, stmt: nodes.EvalStmt, scope, tenv, *_):
        if stmt.subject != "self" and scope.lookup(stmt.subject) is None:
            self._error(self._undefined_error(stmt.subject, scope, stmt.span))
        for criterion in stmt.criteria:
            self._walk_expr(criterion.value, scope, tenv, False, False)

    def _st_PolicyStmt(self, stmt: nodes.PolicyStmt, scope, tenv, *_):
        from ..policy.model import Policy

        try:
            Policy.from_entries(stmt.entries, span=stmt.span)
        except InthonSemanticError as exc:
            self._error(exc)

    # -- expressions ---------------------------------------------------------------------------
    def _st_ExprStmt(self, stmt: nodes.ExprStmt, scope, tenv, in_loop, in_fn):
        self._walk_expr(stmt.expr, scope, tenv, in_loop, in_fn)

    def _st_AssignStmt(self, stmt: nodes.AssignStmt, scope, tenv, in_loop, in_fn):
        self._walk_expr(stmt.value, scope, tenv, in_loop, in_fn)
        target = stmt.target
        if isinstance(target, nodes.Identifier):
            symbol = scope.lookup(target.name)
            if symbol is None:
                self._error(self._undefined_error(target.name, scope, target.span))
                return
            if symbol.kind == "const":
                self._error(
                    InthonConstError(
                        f"Reassignment to constant '{target.name}'", span=target.span
                    )
                )
            if symbol.kind in ("builtin", "tool", "fn", "agent", "py"):
                self._error(
                    InthonSemanticError(
                        f"Cannot assign to {symbol.kind} '{target.name}'", span=target.span
                    )
                )
            value_type = infer_expr_type(stmt.value, tenv, self.fn_returns)
            declared = tenv.get(target.name)
            if not compatible(declared, value_type):
                self._type_warning(
                    f"Type mismatch: '{target.name}' is {declared} but assigned {value_type}",
                    stmt.span,
                )
        elif isinstance(target, nodes.IndexExpr):
            self._walk_expr(target.object, scope, tenv, in_loop, in_fn)
            self._walk_expr(target.index, scope, tenv, in_loop, in_fn)
        elif isinstance(target, nodes.MemberExpr):
            self._walk_expr(target.object, scope, tenv, in_loop, in_fn)

    def _walk_expr(self, expr, scope: Scope, tenv: TypeEnv, in_loop: bool, in_fn: bool):
        if expr is None:
            return
        if isinstance(expr, nodes.Identifier):
            if scope.lookup(expr.name) is None:
                self._error(self._undefined_error(expr.name, scope, expr.span))
            return
        if isinstance(expr, (nodes.IntLiteral, nodes.FloatLiteral, nodes.StringLiteral,
                             nodes.BoolLiteral, nodes.NoneLiteral)):
            return
        if isinstance(expr, nodes.InterpString):
            for part in expr.parts:
                if not isinstance(part, str):
                    self._walk_expr(part, scope, tenv, in_loop, in_fn)
            return
        if isinstance(expr, nodes.ListExpr):
            for el in expr.elements:
                self._walk_expr(el, scope, tenv, in_loop, in_fn)
            return
        if isinstance(expr, nodes.DictExpr):
            for k, v in expr.pairs:
                self._walk_expr(k, scope, tenv, in_loop, in_fn)
                self._walk_expr(v, scope, tenv, in_loop, in_fn)
            return
        if isinstance(expr, nodes.UnaryOp):
            self._walk_expr(expr.operand, scope, tenv, in_loop, in_fn)
            return
        if isinstance(expr, nodes.BinaryOp):
            self._walk_expr(expr.left, scope, tenv, in_loop, in_fn)
            self._walk_expr(expr.right, scope, tenv, in_loop, in_fn)
            return
        if isinstance(expr, nodes.CallExpr):
            self._walk_expr(expr.callee, scope, tenv, in_loop, in_fn)
            for a in expr.args:
                self._walk_expr(a, scope, tenv, in_loop, in_fn)
            for _, v in expr.kwargs:
                self._walk_expr(v, scope, tenv, in_loop, in_fn)
            if isinstance(expr.callee, nodes.Identifier):
                fn_name = expr.callee.name
                if fn_name in self.fn_params:
                    params_info = self.fn_params[fn_name]
                    for i, arg in enumerate(expr.args):
                        if i < len(params_info):
                            param_name, param_type = params_info[i]
                            arg_type = infer_expr_type(arg, tenv, self.fn_returns)
                            if not compatible(param_type, arg_type):
                                self._type_warning(
                                    f"Type mismatch: argument '{param_name}' of function '{fn_name}' "
                                    f"expected {param_type}, got {arg_type}",
                                    arg.span or expr.span,
                                )
            return
        if isinstance(expr, nodes.MemberExpr):
            self._walk_expr(expr.object, scope, tenv, in_loop, in_fn)
            return
        if isinstance(expr, nodes.IndexExpr):
            self._walk_expr(expr.object, scope, tenv, in_loop, in_fn)
            self._walk_expr(expr.index, scope, tenv, in_loop, in_fn)
            return
        if isinstance(expr, nodes.RecallExpr):
            self._check_memory_ns(expr.namespace, expr.span)
            return

    # ------------------------------------------------------------------
    def _check_memory_ns(self, namespace: str, span: Optional[Span]):
        if namespace not in self.memory_namespaces:
            self._error(
                InthonCapabilityError(
                    f"Memory namespace '{namespace}' used without declaration",
                    span=span,
                    hint=f"Add 'use memory.{namespace}' before remember/recall/forget.",
                )
            )

    def _declare(self, scope: Scope, symbol: Symbol):
        prev = scope.declare(symbol)
        if prev is not None and prev.kind != "builtin":
            self._error(
                InthonDuplicateError(
                    f"Name '{symbol.name}' is already declared in this scope",
                    span=symbol.span,
                    hint=f"First declared as '{prev.kind}'. Rename one of them.",
                )
            )
        # shadowing warning (AS-08)
        if scope.parent is not None and scope.parent.lookup(symbol.name) is not None:
            outer = scope.parent.lookup(symbol.name)
            if outer.kind != "builtin":
                self._warning(
                    f"shadow name '{symbol.name}': '{symbol.name}' shadows a {outer.kind} from an outer scope",
                    symbol.span,
                )

    def _undefined_error(self, name: str, scope: Scope, span: Optional[Span]):
        if name in NOT_KEYWORDS:
            suggestion = NOT_KEYWORDS[name]
            hint = f"'{name}' is not an INTHON keyword — use {suggestion}."
        else:
            close = difflib.get_close_matches(name, scope.all_names(), n=1, cutoff=0.7)
            if close:
                hint = f"Did you mean '{close[0]}'?"
            else:
                tool_roots = {p.split(".")[0] for p in self.ctx.tools.paths()}
                if name in tool_roots:
                    matches = [p for p in self.ctx.tools.paths() if p.startswith(name + ".")]
                    return InthonCapabilityError(
                        f"Tool namespace '{name}' used but not imported",
                        span=span,
                        hint="Add one of: " + ", ".join(f"use tool {p}" for p in matches[:3]),
                    )
                hint = "Declare it first with 'let' or 'const', or import it with 'use'."
        return InthonNameError(f"Undefined name '{name}'", span=span, hint=hint)

    def _error(self, exc):
        self.errors.append(exc)

    def _warning(self, message: str, span: Optional[Span]):
        self.warnings.append(str(InthonSemanticError(message, span=span)))

    def _type_warning(self, message: str, span: Optional[Span]):
        exc = InthonStaticTypeError(message, span=span)
        if self.strict:
            self.errors.append(exc)
        else:
            self.warnings.append(str(exc))
