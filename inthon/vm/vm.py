"""InthonVM: stack-based bytecode interpreter (spec §InthonVM).

Shares every runtime service with the tree-walking backend (tools, policy,
memory, trace, sandbox, pybridge), so both backends produce identical
results — the differential test-suite proves this on every example program.
"""

from __future__ import annotations

import time

from ..ast import nodes
from ..errors import (
    GuardAssertionError,
    InthonError,
    InthonIndexError,
    InthonSemanticError,
    InthonStackOverflow,
    InthonTypeError_,
    Span,
)
from ..memory import ops as memory_ops
from ..policy.model import Policy
from ..pybridge.calls import py_call, py_index, py_iter
from ..runtime import builtins as builtins_mod
from ..runtime.agents import invoke_agent
from ..runtime.calls import bind_params
from ..runtime.context import ExecutionContext
from ..runtime.environment import Environment
from ..runtime.typecheck import check_value_against_type
from ..runtime.values import (
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
from .compiler import CodeObject, compile_program
from .opcodes import CMP_OPS, Op

MAX_STACK = 1000


class VMFunction(InthonValue):
    """A compiled function: code object + closure environment."""

    type_name = "fn"

    def __init__(
        self,
        name: str,
        decl,
        code: CodeObject,
        closure_env: Environment,
        defaults: dict,
    ):
        self.name = name
        self.decl = decl
        self.code = code
        self.closure_env = closure_env
        self.defaults = defaults

    def to_python(self):
        return f"<fn {self.name}>"

    def display(self) -> str:
        return f"<fn {self.name}>"


class Frame:
    __slots__ = ("code", "env", "stack", "ip", "handlers", "is_fn")

    def __init__(self, code: CodeObject, env: Environment, is_fn: bool = False):
        self.code = code
        self.env = env
        self.stack: list = []
        self.ip = 0
        self.handlers: list[dict] = []
        self.is_fn = is_fn


class InthonVM:
    def __init__(self, ctx: ExecutionContext):
        self.ctx = ctx
        builtins_mod.install_builtins(ctx.env)
        self.frames: list[Frame] = []
        self._interp_helper = None  # lazily-created interpreter for shared helpers

    # ------------------------------------------------------------------
    def run(self, program: nodes.Program) -> InthonValue:
        code = compile_program(program, self.ctx.filename)
        return self.run_code(code, self.ctx.env)

    def run_code(self, code: CodeObject, env: Environment) -> InthonValue:
        frame = Frame(code, env)
        self.frames.append(frame)
        try:
            return self._run_frame(frame)
        finally:
            self.frames.pop()

    # ------------------------------------------------------------------
    # main dispatch loop
    # ------------------------------------------------------------------
    def _run_frame(self, frame: Frame) -> InthonValue:
        code = frame.code
        instrs = code.instructions
        stack = frame.stack
        env = frame.env
        ctx = self.ctx

        while frame.ip < len(instrs):
            instr = instrs[frame.ip]
            frame.ip += 1
            op = instr.op
            try:
                # ---- stack & variables ------------------------------------
                if op == Op.LOAD_CONST:
                    stack.append(code.literals[instr.arg])
                elif op == Op.LOAD_META:
                    stack.append(code.meta[instr.arg])
                elif op == Op.LOAD_NAME:
                    stack.append(env.lookup(code.names[instr.arg], self._span(instr)))
                elif op == Op.DECLARE_NAME:
                    value = stack.pop()
                    mutable = True
                    if env.is_defined_here(code.names[instr.arg]):
                        env.assign(code.names[instr.arg], value, self._span(instr))
                    else:
                        env.define(
                            code.names[instr.arg],
                            value,
                            mutable=mutable,
                            span=self._span(instr),
                        )
                    self._trace_assign(code.names[instr.arg], value, instr)
                elif op == Op.DECLARE_CONST:
                    value = stack.pop()
                    name = code.names[instr.arg]
                    if env.is_defined_here(name):
                        env.assign(name, value, self._span(instr))
                    else:
                        env.define(name, value, mutable=False, span=self._span(instr))
                    self._trace_assign(name, value, instr)
                elif op == Op.STORE_NAME:
                    value = stack.pop()
                    env.assign(code.names[instr.arg], value, self._span(instr))
                    self._trace_assign(code.names[instr.arg], value, instr)
                elif op == Op.LOAD_ATTR:
                    obj = stack.pop()
                    stack.append(self._get_member(obj, code.names[instr.arg], instr))
                elif op == Op.STORE_ATTR:
                    value = stack.pop()
                    obj = stack.pop()
                    self._set_member(obj, code.names[instr.arg], value, instr)
                elif op == Op.POP_TOP:
                    stack.pop()
                elif op == Op.DUP_TOP:
                    stack.append(stack[-1])

                # ---- arithmetic --------------------------------------------
                elif op in (
                    Op.BINARY_ADD,
                    Op.BINARY_SUB,
                    Op.BINARY_MUL,
                    Op.BINARY_DIV,
                    Op.BINARY_MOD,
                    Op.BINARY_POW,
                ):
                    right = stack.pop()
                    left = stack.pop()
                    stack.append(self._arith(left, op, right, instr))
                elif op == Op.COMPARE_OP:
                    right = stack.pop()
                    left = stack.pop()
                    stack.append(self._compare(left, CMP_OPS[instr.arg], right, instr))
                elif op == Op.UNARY_NEG:
                    operand = stack.pop()
                    if isinstance(operand, InthonInt):
                        stack.append(InthonInt(-operand.value))
                    elif isinstance(operand, InthonFloat):
                        stack.append(InthonFloat(-operand.value))
                    else:
                        raise InthonTypeError_(
                            f"Cannot negate {operand.type_name}", span=self._span(instr)
                        )
                elif op == Op.UNARY_NOT:
                    stack.append(bool_value(not truthy(stack.pop())))
                elif op == Op.BINARY_SUBSCR:
                    index = stack.pop()
                    obj = stack.pop()
                    stack.append(self._get_index(obj, index, instr))
                elif op == Op.STORE_SUBSCR:
                    value = stack.pop()
                    index = stack.pop()
                    obj = stack.pop()
                    self._set_index(obj, index, value, instr)

                # ---- control flow -------------------------------------------
                elif op == Op.POP_JUMP_IF_FALSE:
                    if not truthy(stack.pop()):
                        frame.ip = instr.arg
                elif op == Op.POP_JUMP_IF_TRUE:
                    if truthy(stack.pop()):
                        frame.ip = instr.arg
                elif op == Op.JUMP_FORWARD or op == Op.JUMP_ABSOLUTE:
                    frame.ip = instr.arg
                elif op == Op.JUMP_IF_TRUE_OR_POP:
                    if truthy(stack[-1]):
                        frame.ip = instr.arg
                    else:
                        stack.pop()
                elif op == Op.JUMP_IF_FALSE_OR_POP:
                    if not truthy(stack[-1]):
                        frame.ip = instr.arg
                    else:
                        stack.pop()
                elif op == Op.GET_ITER:
                    iterable = stack.pop()
                    stack.append(self._iterate(iterable, instr))
                elif op == Op.FOR_ITER:
                    name_idx, end_target = code.meta[instr.arg]
                    iterator = stack[-1]
                    try:
                        item = next(iterator)
                    except StopIteration:
                        stack.pop()  # discard iterator
                        frame.ip = end_target
                    else:
                        env.set_local(code.names[name_idx], item)
                elif op == Op.RETURN_VALUE:
                    return stack.pop() if stack else NONE
                elif op == Op.TICK:
                    ctx.sandbox.tick(self._span(instr))

                # ---- containers ------------------------------------------------
                elif op == Op.BUILD_LIST:
                    n = instr.arg
                    items = stack[len(stack) - n :] if n else []
                    if n:
                        del stack[len(stack) - n :]
                    stack.append(InthonList(list(items)))
                elif op == Op.BUILD_DICT:
                    n = instr.arg
                    flat = stack[len(stack) - 2 * n :] if n else []
                    if n:
                        del stack[len(stack) - 2 * n :]
                    pairs = {}
                    for i in range(0, len(flat), 2):
                        key = flat[i]
                        if isinstance(key, (InthonList, InthonDict, InthonPyObject)):
                            raise InthonTypeError_(
                                f"Unhashable dict key type '{key.type_name}'",
                                span=self._span(instr),
                            )
                        pairs[key.to_python()] = flat[i + 1]
                    stack.append(InthonDict(pairs))
                elif op == Op.BUILD_STRING:
                    n = instr.arg
                    parts = stack[len(stack) - n :] if n else []
                    if n:
                        del stack[len(stack) - n :]
                    stack.append(InthonString("".join(display(p) for p in parts)))

                # ---- calls -------------------------------------------------------
                elif op in (Op.CALL_FUNCTION, Op.CALL_FUNCTION_KW):
                    n_pos = instr.arg & 0xFF
                    n_kw = (instr.arg >> 8) & 0xFF
                    kwargs = {}
                    if op == Op.CALL_FUNCTION_KW:
                        kw_names = stack.pop()
                        kw_vals = stack[len(stack) - n_kw :]
                        del stack[len(stack) - n_kw :]
                        kwargs = dict(zip(kw_names, kw_vals))
                    args = stack[len(stack) - n_pos :] if n_pos else []
                    if n_pos:
                        del stack[len(stack) - n_pos :]
                    callee = stack.pop()
                    stack.append(self._call(callee, list(args), kwargs, instr))
                elif op == Op.CALL_TOOL:
                    n_pos = instr.arg & 0xFF
                    n_kw = (instr.arg >> 8) & 0xFF
                    kwargs = {}
                    if n_kw:
                        kw_names = stack.pop()
                        kw_vals = stack[len(stack) - n_kw :]
                        del stack[len(stack) - n_kw :]
                        kwargs = dict(zip(kw_names, kw_vals))
                    args = stack[len(stack) - n_pos :] if n_pos else []
                    if n_pos:
                        del stack[len(stack) - n_pos :]
                    path = stack.pop()
                    stack.append(
                        ctx.tools.invoke(
                            ctx, path, list(args), kwargs, self._span(instr)
                        )
                    )
                elif op == Op.MAKE_FUNCTION:
                    meta = stack.pop()
                    decl = meta["decl"]
                    fn = VMFunction(
                        decl.name, decl, meta["body"], env, meta["defaults"]
                    )
                    if env.is_defined_here(fn.name):
                        env.assign(fn.name, fn, self._span(instr))
                    else:
                        env.define(fn.name, fn, mutable=False, span=self._span(instr))
                elif op == Op.MAKE_AGENT:
                    meta = stack.pop()
                    stack.append(self._make_agent(meta, env, instr))

                # ---- agent & policy ------------------------------------------------
                elif op == Op.APPLY_POLICY:
                    policies = code.meta[instr.arg]
                    policy = Policy(**policies) if policies else Policy()
                    ctx.policy.apply(policy, self._span(instr), label="top-level")
                elif op == Op.POP_POLICY:
                    ctx.policy.pop(self._span(instr))
                elif op == Op.APPROVE_GATE:
                    subject, action = code.meta[instr.arg]
                    details = {
                        "agent": ctx.current_agent or "(top level)",
                        "run_id": ctx.tracer.run_id,
                    }
                    ctx.approvals.request(subject, action, details, self._span(instr))
                elif op == Op.AGENT_REMEMBER:
                    ns = code.meta[instr.arg]
                    value = stack.pop()
                    ctx.policy.check(
                        "memory_persist", self._span(instr), subject="remember"
                    )
                    ctx.check_memory_declared(ns, self._span(instr))
                    memory_ops.memory_remember(ctx, ns, value, self._span(instr))
                elif op == Op.AGENT_RECALL:
                    ns = code.meta[instr.arg]
                    query = stack.pop()
                    ctx.policy.check(
                        "memory_persist", self._span(instr), subject="recall"
                    )
                    ctx.check_memory_declared(ns, self._span(instr))
                    stack.append(
                        memory_ops.memory_recall(
                            ctx, ns, display(query), self._span(instr)
                        )
                    )
                elif op == Op.AGENT_FORGET:
                    ns = code.meta[instr.arg]
                    value = stack.pop()
                    ctx.policy.check(
                        "memory_persist", self._span(instr), subject="forget"
                    )
                    ctx.check_memory_declared(ns, self._span(instr))
                    memory_ops.memory_forget(ctx, ns, value, self._span(instr))
                elif op == Op.GUARD_ASSERT:
                    cond = stack.pop()
                    if ctx.tracer is not None:
                        ctx.tracer.emit(
                            "guard", self._span(instr), passed=bool(truthy(cond))
                        )
                    if not truthy(cond):
                        raise GuardAssertionError(
                            "Guard condition failed", span=self._span(instr)
                        )
                elif op == Op.RETRY_BEGIN:
                    handler = dict(code.meta[instr.arg])
                    handler["attempt"] = 0
                    frame.handlers.append(handler)
                elif op == Op.RETRY_END:
                    if frame.handlers:
                        frame.handlers.pop()
                elif op == Op.EVAL_RUBRIC:
                    rubric, count = code.meta[instr.arg]
                    flat = stack[len(stack) - 3 * count :] if count else []
                    if count:
                        del stack[len(stack) - 3 * count :]
                    subject = stack.pop()
                    criteria = [
                        (flat[i], flat[i + 1], flat[i + 2])
                        for i in range(0, len(flat), 3)
                    ]
                    stack.append(self._eval_rubric(subject, criteria, rubric, instr))
                elif op == Op.SELF_EVAL:
                    rubric, rewriter = code.meta[instr.arg]
                    ctx.tracer.emit(
                        "eval",
                        self._span(instr),
                        rubric=rubric,
                        subject="self",
                        passed=True,
                        note="self-eval preview",
                    )
                    stack.append(NONE)

                # ---- imports ----------------------------------------------------------
                elif op == Op.IMPORT_TOOL:
                    path = code.meta[instr.arg]
                    ctx.tools.get(path, self._span(instr))
                    root = path.split(".")[0]
                    if not env.is_defined_here(root):
                        env.define(
                            root,
                            InthonToolNamespace(root, ctx.tools),
                            mutable=False,
                            span=self._span(instr),
                        )
                elif op == Op.IMPORT_PY:
                    module, alias = code.meta[instr.arg]
                    proxy = ctx.importer.import_module(module, self._span(instr))
                    name = alias or module.split(".")[0]
                    if env.is_defined_here(name):
                        env.assign(name, proxy, self._span(instr))
                    else:
                        env.define(name, proxy, mutable=False, span=self._span(instr))
                elif op == Op.USE_MEMORY:
                    ns, args = code.meta[instr.arg]
                    full = ns if not args else f"{ns}." + ".".join(args)
                    ctx.declare_memory(full)
                    ctx.declare_memory(ns)
                elif op == Op.CHECK_TYPE:
                    check_value_against_type(
                        stack[-1], code.meta[instr.arg], self._span(instr)
                    )
                elif op == Op.INTROSPECT_TRACE:
                    stack.append(box(ctx.tracer.to_json()))
                else:  # pragma: no cover
                    raise InthonSemanticError(f"VM: unknown opcode {op}")

                if len(stack) > MAX_STACK:
                    raise InthonStackOverflow(
                        f"VM stack overflow (>{MAX_STACK})", span=self._span(instr)
                    )

            except InthonError as exc:
                if not self._handle_exception(frame, exc, instr):
                    raise
                # handler adjusted ip/stack — continue executing

        return stack.pop() if stack else NONE

    # ------------------------------------------------------------------
    # exception handling (retry/catch)
    # ------------------------------------------------------------------
    def _handle_exception(self, frame: Frame, exc: InthonError, instr) -> bool:
        while frame.handlers:
            handler = frame.handlers[-1]
            handler["attempt"] += 1
            if handler["attempt"] < handler["count"]:
                if self.ctx.tracer is not None:
                    self.ctx.tracer.emit(
                        "retry_failed",
                        self._span(instr),
                        attempt=handler["attempt"],
                        error=exc.code,
                        message=exc.message,
                    )
                time.sleep(_backoff_delay(handler["backoff"], handler["attempt"]))
                frame.ip = handler["body_ip"]
                return True
            # exhausted
            frame.handlers.pop()
            if handler.get("catch_name") and handler["catch_ip"] != handler["end_ip"]:
                err_value = InthonDict(
                    {
                        "message": InthonString(getattr(exc, "message", str(exc))),
                        "code": InthonString(getattr(exc, "code", "INTHON_000")),
                    }
                )
                frame.env.set_local(handler["catch_name"], err_value)
                frame.ip = handler["catch_ip"]
                return True
            return False
        return False

    # ------------------------------------------------------------------
    def _span(self, instr) -> Span:
        return Span(self.ctx.filename, instr.line or 1, instr.col or 1)

    def _trace_assign(self, name: str, value: InthonValue, instr):
        if self.ctx.tracer is not None:
            self.ctx.tracer.emit(
                "assign",
                self._span(instr),
                name=name,
                type=value.type_name,
                preview=display(value)[:120],
            )

    # ------------------------------------------------------------------
    # call dispatch
    # ------------------------------------------------------------------
    def _call(
        self, callee: InthonValue, args: list, kwargs: dict, instr
    ) -> InthonValue:
        span = self._span(instr)
        if isinstance(callee, InthonBuiltin):
            return callee.fn(self.ctx, args, kwargs, span)
        if isinstance(callee, InthonBoundMethod):
            return callee.fn(callee.receiver, args, kwargs, span)
        if isinstance(callee, InthonToolRef):
            return self.ctx.tools.invoke(self.ctx, callee.path, args, kwargs, span)
        if isinstance(callee, VMFunction):
            return self._call_vmfunction(callee, args, kwargs, instr)
        if isinstance(callee, InthonCallable):
            # fn values created by the tree backend (method map/filter interop)
            return self._tree_helper().call_value(callee, args, kwargs, span)
        if isinstance(callee, InthonAgent):
            return self._invoke_agent(callee, kwargs, span)
        if isinstance(callee, InthonPyObject):
            return py_call(self.ctx, callee, args, kwargs, span)
        raise InthonTypeError_(
            f"Value of type {callee.type_name} is not callable",
            span=span,
            hint="Only functions, agents, tools, builtins and Python callables can be called.",
        )

    def _call_vmfunction(
        self, fn: VMFunction, args: list, kwargs: dict, instr
    ) -> InthonValue:
        span = self._span(instr)
        decl = fn.decl

        def eval_default(default_expr):
            dcode = fn.defaults.get(_default_name(decl, default_expr))
            if dcode is None:
                return NONE
            return self.run_code(dcode, fn.closure_env)

        bound = bind_params(decl, args, kwargs, eval_default=eval_default, span=span)
        self.ctx.sandbox.enter_call(fn.name, span)
        try:
            call_env = Environment(fn.closure_env, kind="fn", label=fn.name)
            for param in decl.params:
                value = bound[param.name]
                if param.type_annotation is not None:
                    check_value_against_type(value, param.type_annotation, span)
                call_env.define(param.name, value, mutable=True, span=span)
            frame = Frame(fn.code, call_env, is_fn=True)
            self.frames.append(frame)
            try:
                result = self._run_frame(frame)
            finally:
                self.frames.pop()
        finally:
            self.ctx.sandbox.exit_call()
        if decl.return_type is not None:
            check_value_against_type(result, decl.return_type, span)
        return result

    def _tree_helper(self):
        if self._interp_helper is None:
            from ..runtime.interpreter import Interpreter

            self._interp_helper = Interpreter(self.ctx)
        return self._interp_helper

    # ------------------------------------------------------------------
    # agents
    # ------------------------------------------------------------------
    def _make_agent(self, meta: dict, env: Environment, instr) -> InthonValue:
        decl = meta["decl"]
        agent = InthonAgent(decl, env)
        agent.vm_plan_code = meta["plan"]
        for name, criteria in meta.get("criteria", {}).items():
            self.ctx.criteria_tables[name] = criteria
        if env.is_defined_here(decl.name):
            env.assign(decl.name, agent, self._span(instr))
        else:
            env.define(decl.name, agent, mutable=False, span=self._span(instr))
        return agent

    def _invoke_agent(self, agent: InthonAgent, kwargs: dict, span) -> InthonValue:
        def run_plan(decl, bound_inputs):
            call_env = Environment(
                agent.closure_env, kind="agent-call", label=decl.name
            )
            for name, value in bound_inputs.items():
                call_env.define(name, value, mutable=True, span=span)
            frame = Frame(agent.vm_plan_code, call_env)
            self.frames.append(frame)
            try:
                return self._run_frame(frame)
            finally:
                self.frames.pop()

        return invoke_agent(self.ctx, agent, kwargs, span, run_plan)

    # ------------------------------------------------------------------
    # members & indexing
    # ------------------------------------------------------------------
    def _get_member(self, obj: InthonValue, name: str, instr) -> InthonValue:
        span = self._span(instr)
        if isinstance(obj, InthonToolNamespace):
            path = f"{obj.root}.{name}"
            if self.ctx.tools.has(path):
                return InthonToolRef(path)
            prefix = path + "."
            if any(p.startswith(prefix) for p in self.ctx.tools.paths()):
                return InthonToolNamespace(path, self.ctx.tools)
            from ..errors import ToolNotFoundError

            raise ToolNotFoundError(f"Unknown tool '{path}'", span=span)
        if isinstance(obj, InthonPyObject):
            importer = getattr(obj, "_importer", None) or self.ctx.importer
            return importer.getattr(obj, name, span)
        if isinstance(obj, InthonDict) and name in obj.pairs:
            return obj.pairs[name]
        return builtins_mod.get_method(obj, name, span)

    def _set_member(self, obj: InthonValue, name: str, value: InthonValue, instr):
        span = self._span(instr)
        if isinstance(obj, InthonDict):
            obj.pairs[name] = value
            return
        if isinstance(obj, InthonPyObject):
            raise InthonTypeError_(
                "Attribute assignment on Python objects is blocked by the sandbox",
                span=span,
            )
        raise InthonTypeError_(
            f"Cannot assign member '{name}' on {obj.type_name}", span=span
        )

    def _get_index(self, obj: InthonValue, index: InthonValue, instr) -> InthonValue:
        span = self._span(instr)
        if isinstance(obj, InthonList):
            if not isinstance(index, InthonInt):
                raise InthonTypeError_(
                    f"List index must be an int, got {index.type_name}", span=span
                )
            try:
                return obj.items[index.value]
            except IndexError:
                raise InthonIndexError(
                    f"List index {index.value} out of range (length {len(obj.items)})",
                    span=span,
                ) from None
        if isinstance(obj, InthonString):
            if not isinstance(index, InthonInt):
                raise InthonTypeError_("String index must be an int", span=span)
            try:
                return InthonString(obj.value[index.value])
            except IndexError:
                raise InthonIndexError(
                    f"String index {index.value} out of range (length {len(obj.value)})",
                    span=span,
                ) from None
        if isinstance(obj, InthonDict):
            key = index.to_python()
            if key in obj.pairs:
                return obj.pairs[key]
            available = ", ".join(map(str, list(obj.pairs.keys())[:5]))
            raise InthonIndexError(
                f"Key {key!r} not found in dict",
                span=span,
                hint=f"Available keys: {available}. Use .get(key, default) to avoid the error.",
            )
        if isinstance(obj, InthonPyObject):
            return py_index(self.ctx, obj, index, span)
        raise InthonTypeError_(f"Indexing not supported for {obj.type_name}", span=span)

    def _set_index(
        self, obj: InthonValue, index: InthonValue, value: InthonValue, instr
    ):
        span = self._span(instr)
        if isinstance(obj, InthonList):
            if not isinstance(index, InthonInt):
                raise InthonTypeError_("List index must be an int", span=span)
            i = index.value
            if not -len(obj.items) <= i < len(obj.items):
                raise InthonIndexError(
                    f"List index {i} out of range (length {len(obj.items)})", span=span
                )
            obj.items[i] = value
            return
        if isinstance(obj, InthonDict):
            obj.pairs[index.to_python()] = value
            return
        if isinstance(obj, InthonPyObject):
            raise InthonTypeError_(
                "Item assignment on Python objects is blocked by the sandbox", span=span
            )
        raise InthonTypeError_(
            f"Indexed assignment not supported for {obj.type_name}", span=span
        )

    # ------------------------------------------------------------------
    # operators
    # ------------------------------------------------------------------
    def _arith(
        self, left: InthonValue, op: int, right: InthonValue, instr
    ) -> InthonValue:
        span = self._span(instr)
        op_str = {
            Op.BINARY_ADD: "+",
            Op.BINARY_SUB: "-",
            Op.BINARY_MUL: "*",
            Op.BINARY_DIV: "/",
            Op.BINARY_MOD: "%",
            Op.BINARY_POW: "**",
        }[op]
        if (
            isinstance(left, InthonString)
            and isinstance(right, InthonString)
            and op_str == "+"
        ):
            return InthonString(left.value + right.value)
        if (
            isinstance(left, InthonString)
            and isinstance(right, InthonInt)
            and op_str == "*"
        ):
            return InthonString(left.value * right.value)
        if (
            isinstance(left, InthonList)
            and isinstance(right, InthonList)
            and op_str == "+"
        ):
            return InthonList(left.items + right.items)
        if (
            isinstance(left, InthonList)
            and isinstance(right, InthonInt)
            and op_str == "*"
        ):
            return InthonList(left.items * right.value)
        if isinstance(left, (InthonInt, InthonFloat, InthonBool)) and isinstance(
            right, (InthonInt, InthonFloat, InthonBool)
        ):
            a, b = left.to_python(), right.to_python()
            both_int = isinstance(left, InthonInt) and isinstance(right, InthonInt)
            if op_str == "+":
                return _num_box(a + b, both_int)
            if op_str == "-":
                return _num_box(a - b, both_int)
            if op_str == "*":
                return _num_box(a * b, both_int)
            if op_str == "/":
                if b == 0:
                    raise InthonTypeError_(
                        "Division by zero",
                        span=span,
                        hint="Guard the divisor: guard b != 0",
                    )
                return InthonFloat(a / b)
            if op_str == "%":
                if b == 0:
                    raise InthonTypeError_("Modulo by zero", span=span)
                return _num_box(a % b, both_int)
            if op_str == "**":
                return _num_box(a**b, both_int)
        raise InthonTypeError_(
            f"Operator '{op_str}' not supported for {left.type_name} and {right.type_name}",
            span=span,
        )

    def _compare(
        self, left: InthonValue, op: str, right: InthonValue, instr
    ) -> InthonValue:
        span = self._span(instr)
        if op == "==":
            return bool_value(values_equal(left, right))
        if op == "!=":
            return bool_value(not values_equal(left, right))
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
            )
        return bool_value({"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op])

    # ------------------------------------------------------------------
    def _iterate(self, iterable: InthonValue, instr):
        span = self._span(instr)
        if isinstance(iterable, InthonList):
            return iter(list(iterable.items))
        if isinstance(iterable, InthonString):
            return iter([InthonString(ch) for ch in iterable.value])
        if isinstance(iterable, InthonDict):
            return iter([box(k) for k in iterable.pairs.keys()])
        if isinstance(iterable, InthonPyObject):
            return py_iter(iterable, span)
        raise InthonTypeError_(
            f"Cannot iterate over {iterable.type_name}",
            span=span,
            hint="Iterate a list, string, dict (keys), range(...), or a Python iterable.",
        )

    def _eval_rubric(
        self, subject: InthonValue, criteria: list, rubric: str, instr
    ) -> InthonDict:
        span = self._span(instr)
        details = []
        passed_count = 0
        subject_map = subject.pairs if isinstance(subject, InthonDict) else {}
        for name_v, op_v, expected in criteria:
            name = display(name_v)
            op = display(op_v)
            actual = subject_map.get(name, NONE)
            ok = _criterion_passes(actual, op, expected)
            passed_count += 1 if ok else 0
            details.append(
                InthonDict(
                    {
                        "name": InthonString(name),
                        "op": InthonString(op),
                        "expected": expected,
                        "actual": actual,
                        "passed": bool_value(ok),
                    }
                )
            )
        total = len(criteria)
        report = InthonDict(
            {
                "passed": bool_value(passed_count == total),
                "score": InthonFloat(passed_count / total if total else 1.0),
                "total": InthonInt(total),
                "details": InthonList(details),
            }
        )
        if self.ctx.tracer is not None:
            self.ctx.tracer.emit(
                "eval",
                span,
                rubric=rubric,
                passed=report.pairs["passed"].value,
                score=report.pairs["score"].to_python(),
            )
        return report


def _default_name(decl, default_expr) -> str:
    for param in decl.params:
        if param.default is default_expr:
            return param.name
    return ""


def _num_box(value, both_int: bool) -> InthonValue:
    if both_int:
        return InthonInt(int(value))
    return InthonFloat(float(value))


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


def _backoff_delay(strategy: str, attempt: int) -> float:
    base = 0.05
    if strategy == "exponential":
        return min(0.5, base * (2 ** (attempt - 1)))
    if strategy == "linear":
        return min(0.5, base * attempt)
    return base
