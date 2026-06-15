from __future__ import annotations
import uuid
import re
from typing import Any
from ..ast import nodes as N
from ..ast.visitor import ASTVisitor
from .context import ExecutionContext
from .values import (
    InthonValue,
    InthonInt,
    InthonFloat,
    InthonStr,
    InthonBool,
    InthonNone,
    InthonList,
    InthonDict,
    InthonCallable,
    InthonToolRef,
    InthonPyObject,
    from_python,
    to_python,
)
from .errors import IntHonRuntimeError, ToolCallError, ReturnSignal
from ..policy.model import Capability


class Interpreter(ASTVisitor):
    def __init__(self, ctx: ExecutionContext) -> None:
        self._ctx = ctx

    def run(self, program: N.Program) -> InthonValue:
        result: InthonValue = InthonNone()
        try:
            for stmt in program.body:
                val = self.visit(stmt)
                if val is not None:
                    result = val
        except ReturnSignal as ret:
            result = ret.value
        return result

    # ─── Helper: Dynamic Target Assignment ─────────────────────────────────── #
    def _assign_target(self, target_str: str, val: InthonValue) -> None:
        # Scan root identifier
        root_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)", target_str)
        if not root_match:
            raise IntHonRuntimeError(
                f"INTHON_RUNTIME_ASSIGN: Invalid assignment target root '{target_str}'"
            )
        root_name = root_match.group(1)
        pos = root_match.end()

        parts = []
        # Scan member or index operations
        while pos < len(target_str):
            if target_str[pos] == ".":
                pos += 1
                member_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)", target_str[pos:])
                if not member_match:
                    raise IntHonRuntimeError(
                        f"INTHON_RUNTIME_ASSIGN: Invalid member in target '{target_str}' at pos {pos}"
                    )
                parts.append(("attr", member_match.group(1)))
                pos += member_match.end()
            elif target_str[pos] == "[":
                pos += 1
                bracket_count = 1
                start_idx = pos
                while pos < len(target_str) and bracket_count > 0:
                    if target_str[pos] == "[":
                        bracket_count += 1
                    elif target_str[pos] == "]":
                        bracket_count -= 1
                    pos += 1
                if bracket_count > 0:
                    raise IntHonRuntimeError(
                        f"INTHON_RUNTIME_ASSIGN: Unmatched brackets in target '{target_str}'"
                    )
                inner = target_str[start_idx : pos - 1]

                idx_val: Any
                # Resolve bracket index value
                if inner.isdigit():
                    idx_val = int(inner)
                elif (inner.startswith("'") and inner.endswith("'")) or (
                    inner.startswith('"') and inner.endswith('"')
                ):
                    idx_val = inner[1:-1]
                elif inner == "true":
                    idx_val = True
                elif inner == "false":
                    idx_val = False
                elif inner == "none":
                    idx_val = None
                else:
                    if self._ctx.has_var(inner):
                        idx_val = to_python(self._ctx.get_var(inner))
                    else:
                        raise IntHonRuntimeError(
                            f"INTHON_RUNTIME_ASSIGN: Undefined variable '{inner}' in bracket index"
                        )
                parts.append(("index", idx_val))
            else:
                raise IntHonRuntimeError(
                    f"INTHON_RUNTIME_ASSIGN: Invalid character '{target_str[pos]}' in target '{target_str}'"
                )

        if not parts:
            self._ctx.assign_var(root_name, val)
            return

        obj = self._ctx.get_var(root_name)
        for i, (kind, key) in enumerate(parts[:-1]):
            if kind == "attr":
                if isinstance(obj, InthonPyObject):
                    obj = from_python(getattr(obj.obj, key))
                elif isinstance(obj, InthonDict) and key in obj.pairs:
                    obj = obj.pairs[key]
                else:
                    raise IntHonRuntimeError(
                        f"INTHON_RUNTIME_ASSIGN: Attribute '{key}' not found on '{type(obj)}'"
                    )
            elif kind == "index":
                if isinstance(obj, InthonList):
                    obj = obj.items[int(key)]
                elif isinstance(obj, InthonDict):
                    obj = obj.pairs[str(key)]
                elif isinstance(obj, InthonPyObject):
                    obj = from_python(obj.obj[key])
                else:
                    raise IntHonRuntimeError(
                        f"INTHON_RUNTIME_ASSIGN: Subscript lookup failed on '{type(obj)}'"
                    )

        last_kind, last_key = parts[-1]
        if last_kind == "attr":
            if isinstance(obj, InthonPyObject):
                setattr(obj.obj, last_key, to_python(val))
            elif isinstance(obj, InthonDict):
                obj.pairs[last_key] = val
            else:
                raise IntHonRuntimeError(
                    f"INTHON_RUNTIME_ASSIGN: Cannot set attribute on '{type(obj)}'"
                )
        elif last_kind == "index":
            if isinstance(obj, InthonList):
                obj.items[int(last_key)] = val
            elif isinstance(obj, InthonDict):
                obj.pairs[str(last_key)] = val
            elif isinstance(obj, InthonPyObject):
                obj.obj[last_key] = to_python(val)
            else:
                raise IntHonRuntimeError(
                    f"INTHON_RUNTIME_ASSIGN: Cannot set subscript on '{type(obj)}'"
                )

    # ─── Statement Visitors ────────────────────────────────────────────────── #
    def visit_LetStmt(self, node: N.LetStmt) -> None:
        val = self.visit(node.value)
        self._ctx.set_var(node.name, val)
        self._ctx.tracer.emit("assign", {"name": node.name})

    def visit_ConstStmt(self, node: N.ConstStmt) -> None:
        val = self.visit(node.value)
        self._ctx.set_var(node.name, val)
        self._ctx.tracer.emit("assign", {"name": node.name})

    def visit_AssignStmt(self, node: N.AssignStmt) -> None:
        val = self.visit(node.value)
        self._assign_target(node.target, val)
        self._ctx.tracer.emit("assign", {"name": node.target})

    def visit_ReturnStmt(self, node: N.ReturnStmt) -> None:
        val = self.visit(node.value) if node.value else InthonNone()
        raise ReturnSignal(val)

    def visit_FnDecl(self, node: N.FnDecl) -> None:
        fn = InthonCallable(
            name=node.name,
            params=[p.name for p in node.params],
            defaults={
                p.name: self.visit(p.default)
                for p in node.params
                if p.default is not None
            },
            body=node.body,
            closure=self._ctx,
        )
        self._ctx.set_var(node.name, fn)

    def visit_AgentDecl(self, node: N.AgentDecl) -> InthonValue:
        if node.policy:
            self._ctx.policy.apply(node.policy)
            # Link policy engine settings to active sandbox
            self._ctx.sandbox.max_tool_calls = self._ctx.policy.max_tool_calls
            self._ctx.sandbox.max_runtime_sec = self._ctx.policy.max_runtime_sec
            self._ctx.sandbox.max_cost_usd = self._ctx.policy.max_cost_usd

        self._ctx.current_agent = node.name
        self._ctx.agent_goal = node.goal
        self._ctx.tracer.emit("agent_start", {"name": node.name, "goal": node.goal})

        self._ctx.push_scope()
        try:
            # Execute imports in agent block
            for imp in node.imports:
                self.visit(imp)

            result: InthonValue = InthonNone()
            try:
                for stmt in node.plan.body:
                    val = self.visit(stmt)
                    if val is not None:
                        result = val
            except ReturnSignal as ret:
                result = ret.value
            return result
        finally:
            self._ctx.pop_scope()
            self._ctx.tracer.emit("agent_end", {"name": node.name})
            self._ctx.current_agent = None

    def visit_IfStmt(self, node: N.IfStmt) -> InthonValue:
        cond = self.visit(node.condition)
        self._ctx.push_scope()
        try:
            branch = (
                node.then_branch if self._is_truthy(cond) else (node.else_branch or ())
            )
            result: InthonValue = InthonNone()
            for stmt in branch:
                val = self.visit(stmt)
                if val is not None:
                    result = val
            return result
        finally:
            self._ctx.pop_scope()

    def visit_ForStmt(self, node: N.ForStmt) -> InthonValue:
        iterable_val = self.visit(node.iterable)

        items = []
        if isinstance(iterable_val, InthonList):
            items = iterable_val.items
        elif isinstance(iterable_val, InthonPyObject) and hasattr(
            iterable_val.obj, "__iter__"
        ):
            items = [from_python(i) for i in iterable_val.obj]
        elif isinstance(iterable_val, InthonDict):
            items = [InthonStr(k) for k in iterable_val.pairs.keys()]
        else:
            raise IntHonRuntimeError(
                f"INTHON_RUNTIME_FOR: Object '{type(iterable_val)}' is not iterable"
            )

        result: InthonValue = InthonNone()
        for item in items:
            self._ctx.push_scope()
            try:
                self._ctx.set_var(node.var, item)
                for stmt in node.body:
                    val = self.visit(stmt)
                    if val is not None:
                        result = val
            finally:
                self._ctx.pop_scope()
        return result

    def visit_WhileStmt(self, node: N.WhileStmt) -> InthonValue:
        result: InthonValue = InthonNone()
        while True:
            cond = self.visit(node.condition)
            if not self._is_truthy(cond):
                break
            self._ctx.push_scope()
            try:
                for stmt in node.body:
                    val = self.visit(stmt)
                    if val is not None:
                        result = val
            finally:
                self._ctx.pop_scope()
        return result

    def visit_ExprStmt(self, node: N.ExprStmt) -> InthonValue:
        return self.visit(node.expr)

    # ─── Agent Primitive Visitors ─────────────────────────────────────────── #
    def visit_UseToolStmt(self, node: N.UseToolStmt) -> None:
        root = node.tool_path.split(".")[0]
        self._ctx.set_var(root, InthonToolRef(root))

    def visit_UsePyStmt(self, node: N.UsePyStmt) -> None:
        from ..pybridge.importer import SafeModuleImporter

        importer = SafeModuleImporter()
        wrapper = importer.import_module(node.module_path, node.alias)
        alias = node.alias or node.module_path.split(".")[-1]
        self._ctx.set_var(alias, wrapper)

    def visit_UseMemoryStmt(self, node: N.UseMemoryStmt) -> None:
        # Initialise / ensure memory store works
        pass

    def visit_ApproveStmt(self, node: N.ApproveStmt) -> None:
        self._ctx.policy.check_capability(
            Capability.PAYMENT_EXECUTE if node.action == "pay" else Capability.NETWORK
        )
        self._ctx.policy.approval_gate.request(node.target, node.action, self._ctx)
        self._ctx.tracer.emit("approve", {"target": node.target, "action": node.action})

    def visit_RememberStmt(self, node: N.RememberStmt) -> None:
        self._ctx.policy.check_capability(Capability.MEMORY_WRITE)
        val = self.visit(node.value)
        key = uuid.uuid4().hex[:8]
        self._ctx.memory.write(key, to_python(val), node.namespace)
        self._ctx.tracer.emit("remember", {"key": key, "namespace": node.namespace})

    def visit_ForgetStmt(self, node: N.ForgetStmt) -> None:
        key_val = to_python(self.visit(node.key))
        success = self._ctx.memory.delete(str(key_val), node.namespace)
        self._ctx.tracer.emit(
            "forget",
            {"key": str(key_val), "namespace": node.namespace, "success": success},
        )

    def visit_RecallStmt(self, node: N.RecallStmt) -> None:
        entries = self._ctx.memory.search(node.query, node.namespace)
        if entries:
            entries.sort(key=lambda e: e.updated_at, reverse=True)
            res_val = from_python(entries[0].value)
        else:
            res_val = InthonNone()
        self._ctx.set_var(node.var, res_val)
        self._ctx.tracer.emit("recall", {"query": node.query, "var": node.var})

    def visit_GuardStmt(self, node: N.GuardStmt) -> None:
        cond = self.visit(node.condition)
        if not self._is_truthy(cond):
            raise IntHonRuntimeError(
                "INTHON_RUNTIME_GUARD: Guard condition failed", node.span
            )

    def visit_RetryStmt(self, node: N.RetryStmt) -> InthonValue:
        last_error: Exception | None = None
        for attempt in range(node.count):
            try:
                self._ctx.push_scope()
                try:
                    for stmt in node.body:
                        self.visit(stmt)
                    return InthonNone()
                finally:
                    self._ctx.pop_scope()
            except IntHonRuntimeError as e:
                last_error = e
                # Wait based on backoff
                import time

                wait = 2**attempt if node.backoff == "exponential" else 1
                self._ctx.tracer.emit(
                    "retry", {"attempt": attempt + 1, "wait_sec": wait, "error": str(e)}
                )
                time.sleep(wait)

        if node.catch_block:
            self._ctx.push_scope()
            try:
                self._ctx.set_var(node.catch_block.var, from_python(str(last_error)))
                for stmt in node.catch_block.body:
                    self.visit(stmt)
            finally:
                self._ctx.pop_scope()
        else:
            if last_error:
                raise last_error
        return InthonNone()

    def visit_EvalStmt(self, node: N.EvalStmt) -> None:
        for crit in node.criteria:
            metric_val = self._ctx.get_var(crit.metric)
            threshold_val = self.visit(crit.threshold)
            lhs = to_python(metric_val)
            rhs = to_python(threshold_val)
            ops = {
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
                "<": lambda a, b: a < b,
                "<=": lambda a, b: a <= b,
                ">": lambda a, b: a > b,
                ">=": lambda a, b: a >= b,
            }
            if crit.op not in ops:
                raise IntHonRuntimeError(
                    f"INTHON_RUNTIME_EVAL: Unknown operator '{crit.op}'"
                )
            if not ops[crit.op](lhs, rhs):
                raise IntHonRuntimeError(
                    f"INTHON_RUNTIME_EVAL: Criterion '{crit.metric}' failed: expected {crit.op} {rhs}, got {lhs}"
                )
        self._ctx.tracer.emit("eval", {"subject": node.subject, "rubric": node.rubric})

    # ─── Expression Visitors ───────────────────────────────────────────────── #
    def visit_IntLiteral(self, node: N.IntLiteral) -> InthonInt:
        return InthonInt(node.value)

    def visit_FloatLiteral(self, node: N.FloatLiteral) -> InthonFloat:
        return InthonFloat(node.value)

    def visit_StringLiteral(self, node: N.StringLiteral) -> InthonStr:
        return InthonStr(node.value)

    def visit_BoolLiteral(self, node: N.BoolLiteral) -> InthonBool:
        return InthonBool(node.value)

    def visit_NoneLiteral(self, node: N.NoneLiteral) -> InthonNone:
        return InthonNone()

    def visit_Identifier(self, node: N.Identifier) -> InthonValue:
        return self._ctx.get_var(node.name)

    def visit_ListExpr(self, node: N.ListExpr) -> InthonList:
        return InthonList([self.visit(e) for e in node.elements])

    def visit_DictExpr(self, node: N.DictExpr) -> InthonDict:
        return InthonDict(
            {to_python(self.visit(k)): self.visit(v) for k, v in node.pairs}
        )

    def visit_BinaryOp(self, node: N.BinaryOp) -> InthonValue:
        lhs = to_python(self.visit(node.left))
        rhs = to_python(self.visit(node.right))

        ops = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b,
            "%": lambda a, b: a % b,
            "**": lambda a, b: a**b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
            "and": lambda a, b: a and b,
            "or": lambda a, b: a or b,
        }
        if node.op not in ops:
            raise IntHonRuntimeError(
                f"INTHON_RUNTIME_002: Unknown operator '{node.op}'"
            )
        return from_python(ops[node.op](lhs, rhs))

    def visit_UnaryOp(self, node: N.UnaryOp) -> InthonValue:
        val = to_python(self.visit(node.operand))
        if node.op == "-":
            return from_python(-val)
        if node.op == "+":
            return from_python(+val)
        if node.op == "not":
            return from_python(not val)
        raise IntHonRuntimeError(
            f"INTHON_RUNTIME_002: Unknown unary operator '{node.op}'"
        )

    def visit_CallExpr(self, node: N.CallExpr) -> InthonValue:
        callee = self.visit(node.callee)
        args = [self.visit(a) for a in node.args]
        kwargs = {k: self.visit(v) for k, v in node.kwargs}

        if isinstance(callee, InthonCallable):
            return self._call_function(callee, args, kwargs)
        if isinstance(callee, InthonToolRef):
            return self._call_tool(callee.tool_path, args, kwargs)
        if isinstance(callee, InthonPyObject) and callable(callee.obj):
            return self._call_python(callee, args, kwargs)

        raise IntHonRuntimeError(f"INTHON_RUNTIME_003: '{node.callee}' is not callable")

    def visit_MemberExpr(self, node: N.MemberExpr) -> InthonValue:
        obj = self.visit(node.obj)
        if isinstance(obj, InthonToolRef):
            return InthonToolRef(obj.tool_path + "." + node.attr)
        if isinstance(obj, InthonPyObject):
            attr = getattr(obj.obj, node.attr)
            return from_python(attr, obj.source_module)
        if isinstance(obj, InthonDict) and node.attr in obj.pairs:
            return obj.pairs[node.attr]

        # Support python modules wrapper from import stmt
        from ..pybridge.importer import SafeModuleWrapper

        if isinstance(obj, SafeModuleWrapper):
            attr = getattr(obj, node.attr)
            # SafeModuleWrapper returns already wrapped or callable InthonPyObject
            return from_python(attr)

        raise IntHonRuntimeError(
            f"INTHON_RUNTIME_MEMBER: Member '{node.attr}' not found on '{type(obj)}'"
        )

    def visit_IndexExpr(self, node: N.IndexExpr) -> InthonValue:
        obj = self.visit(node.obj)
        idx = to_python(self.visit(node.index))

        if isinstance(obj, InthonList):
            return obj.items[int(idx)]
        if isinstance(obj, InthonDict):
            return obj.pairs[str(idx)]
        if isinstance(obj, InthonPyObject):
            return from_python(obj.obj[idx], obj.source_module)

        raise IntHonRuntimeError(
            f"INTHON_RUNTIME_INDEX: Index lookup failed on '{type(obj)}'"
        )

    # ─── Private Call Methods ──────────────────────────────────────────────── #
    def _call_function(
        self,
        fn: InthonCallable,
        args: list[InthonValue],
        kwargs: dict[str, InthonValue],
    ) -> InthonValue:
        self._ctx.push_scope()
        for i, param in enumerate(fn.params):
            if i < len(args):
                self._ctx.set_var(param, args[i])
            elif param in kwargs:
                self._ctx.set_var(param, kwargs[param])
            elif param in fn.defaults:
                self._ctx.set_var(param, fn.defaults[param])
            else:
                raise IntHonRuntimeError(
                    f"INTHON_RUNTIME_004: Missing argument '{param}' for function '{fn.name}'"
                )

        result: InthonValue = InthonNone()
        try:
            for stmt in fn.body:
                self.visit(stmt)
        except ReturnSignal as ret:
            result = ret.value
        finally:
            self._ctx.pop_scope()
        return result

    def _call_tool(
        self, tool_path: str, args: list[InthonValue], kwargs: dict[str, InthonValue]
    ) -> InthonValue:
        # Check budget limits first
        self._ctx.sandbox.check_budget()

        # Verify tool registry check
        self._ctx.policy.check_tool(tool_path)

        # side_effects checks (web.search side effects etc.)
        spec = self._ctx.tools.get_spec(tool_path)
        for eff in spec.side_effects:
            if eff == "network":
                self._ctx.policy.check_capability(Capability.NETWORK)
            elif eff == "filesystem":
                self._ctx.policy.check_capability(Capability.FILESYSTEM_WRITE)

        py_args = [to_python(a) for a in args]
        py_kwargs = {k: to_python(v) for k, v in kwargs.items()}

        result = self._ctx.tools.call(tool_path, py_args, py_kwargs)
        if not result.success:
            raise ToolCallError(
                f"INTHON_TOOL_004: Tool execution failed: {result.error}"
            )

        self._ctx.tool_call_count += 1
        self._ctx.cost_usd += result.cost_usd
        self._ctx.sandbox.record_tool_call(result.cost_usd)

        self._ctx.tracer.emit(
            "tool_call",
            {
                "tool": tool_path,
                "args": str(py_args)[:200],
                "cost_usd": result.cost_usd,
            },
        )
        return from_python(result.output)

    def _call_python(
        self,
        callee: InthonPyObject,
        args: list[InthonValue],
        kwargs: dict[str, InthonValue],
    ) -> InthonValue:
        self._ctx.py_call_count += 1
        self._ctx.tracer.emit(
            "py_call",
            {
                "module": callee.source_module,
                "func": callee.obj.__name__
                if hasattr(callee.obj, "__name__")
                else str(callee.obj),
                "args": str([to_python(a) for a in args])[:200],
            },
        )
        # SafeModuleWrapper wrapped functions are callable and expect unpacked args,
        # but our _wrap_callable already unpacks them. If callee.obj is the wrapper,
        # we call it directly.
        res = callee.obj(*args, **kwargs)
        return from_python(res)

    @staticmethod
    def _is_truthy(val: InthonValue) -> bool:
        if isinstance(val, InthonBool):
            return val.v
        if isinstance(val, InthonNone):
            return False
        if isinstance(val, InthonInt):
            return val.v != 0
        if isinstance(val, InthonStr):
            return bool(val.v)
        return True
