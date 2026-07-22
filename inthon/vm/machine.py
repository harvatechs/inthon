"""
inthon.vm.machine — INTHON Stack-Based Virtual Machine.

InthonVM executes a CodeObject produced by the Compiler. The dispatch loop
is a flat `while ip < n` loop using Python 3.10+ match/case, avoiding all
recursive AST traversal overhead.

Design principles:
- No recursion: function calls push a new Frame and continue the loop.
- Agent primitives are handled directly in the loop alongside the same
  ExecutionContext subsystems used by the tree-walk Interpreter.
- Policy and sandbox checks are enforced at the opcode level (CALL_TOOL,
  AGENT_REMEMBER, AGENT_APPROVE) rather than inside library wrappers.
- The VM is drop-in compatible with ExecutionContext: both the Interpreter
  and InthonVM share the same context, tools, memory, and policy objects.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..runtime.context import ExecutionContext
from ..runtime.errors import (
    IntHonRuntimeError,
    ReturnSignal,
    PolicyViolationError,
    ToolCallError,
)
from ..runtime.values import (
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
from ..policy.model import Capability
from .code_object import CodeObject
from .frame import Frame, RetryState
from .old_opcodes import OpCode

_SENTINEL = object()  # used to detect "no default"


class PauseSignal(Exception):
    """Exception raised to pause execution and serialize the current VM state."""

    def __init__(self, frame: Frame) -> None:
        self.frame = frame


class VMError(IntHonRuntimeError):
    pass


class InthonVM:
    """
    Stack-based virtual machine for INTHON bytecode.

    Usage::

        ctx = ExecutionContext(...)
        register_builtins(ctx.tools)
        vm = InthonVM(ctx)
        result = vm.execute(code_object)
    """

    def __init__(self, ctx: ExecutionContext) -> None:
        self._ctx = ctx
        # Global scope: module-level variables, shared across calls
        self._globals: dict[str, Any] = {}
        from ..policy.loop_guard import LoopGuard

        self._loop_guard = LoopGuard()

    # ── Public API ─────────────────────────────────────────────────────── #

    def dehydrate_state(self, frame: Frame) -> dict:
        """Dehydrate the current frame execution state into a JSON-serializable dictionary."""
        from .serialization import serialize_frame

        return serialize_frame(frame)

    def resume_execution(self, state: dict) -> Any:
        """Rehydrate and resume execution from a dehydrated state."""
        from .serialization import deserialize_frame

        frame = deserialize_frame(state)
        # Reconstruct globals from the root parent's locals
        root = frame
        while root.parent is not None:
            root = root.parent
        self._globals.update(root.locals)
        return self._run_frame(frame)

    def execute(self, code: CodeObject) -> Any:
        """Execute a top-level CodeObject and return the result value."""
        frame = Frame(code=code, locals=self._globals)
        return self._run_frame(frame)

    # ── Core dispatch loop ─────────────────────────────────────────────── #

    def _run_frame(self, frame: Frame) -> Any:  # noqa: C901 (complexity is inherent in a VM)
        """Execute a single Frame until it finishes or returns."""
        instructions = frame.code.instructions
        constants = frame.code.constants
        n = len(instructions)
        ctx = self._ctx

        while frame.ip < n:
            instr = instructions[frame.ip]
            frame.ip += 1
            op = instr.op
            arg = instr.arg

            # ── Stack manipulation ───────────────────────────────────── #
            if op == OpCode.LOAD_CONST:
                frame.push(constants[arg])

            elif op == OpCode.LOAD_FAST:
                val = frame.locals.get(arg, _SENTINEL)
                if val is _SENTINEL:
                    val = self._globals.get(arg, _SENTINEL)
                if val is _SENTINEL:
                    raise VMError(f"INTHON_RUNTIME_001: Undefined variable '{arg}'")
                frame.push(val)

            elif op == OpCode.STORE_FAST:
                frame.locals[arg] = frame.pop()

            elif op == OpCode.LOAD_GLOBAL:
                # Walk scope chain: frame locals → global dict → ctx scope stack
                val = frame.locals.get(arg, _SENTINEL)
                if val is _SENTINEL:
                    val = self._globals.get(arg, _SENTINEL)
                if val is _SENTINEL:
                    # Fallback: try ExecutionContext scope stack
                    try:
                        val = ctx.get_var(arg)
                    except RuntimeError:
                        raise VMError(f"INTHON_RUNTIME_001: Undefined variable '{arg}'")
                frame.push(val)

            elif op == OpCode.STORE_GLOBAL:
                val = frame.pop()
                self._globals[arg] = val
                ctx.assign_var(arg, val)

            elif op == OpCode.POP_TOP:
                frame.pop()

            elif op == OpCode.DUP_TOP:
                frame.push(frame.peek())

            elif op == OpCode.ROT_TWO:
                a = frame.pop()
                b = frame.pop()
                frame.push(a)
                frame.push(b)

            # ── Arithmetic ───────────────────────────────────────────── #
            elif op == OpCode.BINARY_ADD:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) + self._coerce(b))

            elif op == OpCode.BINARY_SUB:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) - self._coerce(b))

            elif op == OpCode.BINARY_MUL:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) * self._coerce(b))

            elif op == OpCode.BINARY_DIV:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) / self._coerce(b))

            elif op == OpCode.BINARY_MOD:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) % self._coerce(b))

            elif op == OpCode.BINARY_POW:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) ** self._coerce(b))

            # ── Comparison ───────────────────────────────────────────── #
            elif op == OpCode.COMPARE_EQ:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) == self._coerce(b))

            elif op == OpCode.COMPARE_NE:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) != self._coerce(b))

            elif op == OpCode.COMPARE_LT:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) < self._coerce(b))

            elif op == OpCode.COMPARE_LE:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) <= self._coerce(b))

            elif op == OpCode.COMPARE_GT:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) > self._coerce(b))

            elif op == OpCode.COMPARE_GE:
                b, a = frame.pop(), frame.pop()
                frame.push(self._coerce(a) >= self._coerce(b))

            elif op == OpCode.LOGICAL_AND:
                b, a = frame.pop(), frame.pop()
                frame.push(self._is_truthy(a) and self._is_truthy(b))

            elif op == OpCode.LOGICAL_OR:
                b, a = frame.pop(), frame.pop()
                frame.push(self._is_truthy(a) or self._is_truthy(b))

            elif op == OpCode.UNARY_NOT:
                frame.push(not self._is_truthy(frame.pop()))

            elif op == OpCode.UNARY_NEG:
                frame.push(-self._coerce(frame.pop()))

            elif op == OpCode.UNARY_POS:
                frame.push(+self._coerce(frame.pop()))

            # ── Collection builders ──────────────────────────────────── #
            elif op == OpCode.BUILD_LIST:
                items = frame.pop_n(arg)
                frame.push(items)

            elif op == OpCode.BUILD_DICT:
                # Items interleaved: k0, v0, k1, v1 ... (bottom to top)
                pairs = frame.pop_n(arg * 2)
                d = {}
                for i in range(0, len(pairs), 2):
                    d[pairs[i]] = pairs[i + 1]
                frame.push(d)

            # ── Attribute / index ────────────────────────────────────── #
            elif op == OpCode.GET_ATTR:
                obj = frame.pop()
                obj = self._unwrap(obj)
                if isinstance(obj, dict):
                    val = obj.get(arg, None)
                elif isinstance(obj, InthonDict):
                    val_opt = obj.pairs.get(arg)
                    val = to_python(val_opt) if val_opt is not None else None
                elif isinstance(obj, InthonToolRef):
                    val = InthonToolRef(obj.tool_path + "." + arg)
                else:
                    from ..pybridge.allowlist import is_safe_attribute_access

                    if not is_safe_attribute_access(obj, arg, getattr(obj, arg, None)):
                        raise VMError(
                            f"INTHON_SANDBOX: Access to attribute '{arg}' is denied."
                        )
                    val = getattr(obj, arg, None)
                frame.push(val)

            elif op == OpCode.SET_ATTR:
                value = frame.pop()
                obj = frame.pop()
                obj = self._unwrap(obj)
                if isinstance(obj, dict):
                    obj[arg] = value
                else:
                    from ..pybridge.allowlist import is_safe_attribute_access

                    if arg.startswith("_") or not is_safe_attribute_access(
                        obj, arg, getattr(obj, arg, None)
                    ):
                        raise VMError(
                            f"INTHON_SANDBOX: Modifying attribute '{arg}' is denied."
                        )
                    setattr(obj, arg, value)

            elif op == OpCode.GET_ITEM:
                idx = frame.pop()
                obj = frame.pop()
                obj = self._unwrap(obj)
                idx = self._coerce(idx)
                if isinstance(obj, list):
                    frame.push(obj[int(idx)])
                elif isinstance(obj, dict):
                    frame.push(obj[idx])
                elif isinstance(obj, InthonList):
                    frame.push(to_python(obj.items[int(idx)]))
                elif isinstance(obj, InthonDict):
                    frame.push(to_python(obj.pairs[str(idx)]))
                elif isinstance(obj, InthonPyObject):
                    frame.push(obj.obj[idx])
                else:
                    raise VMError(f"INTHON_RUNTIME_INDEX: Cannot index {type(obj)}")

            elif op == OpCode.SET_ITEM:
                value = frame.pop()
                idx = frame.pop()
                obj = frame.pop()
                obj = self._unwrap(obj)
                idx = self._coerce(idx)
                if isinstance(obj, list):
                    obj[int(idx)] = self._coerce(value)
                elif isinstance(obj, dict):
                    obj[idx] = self._coerce(value)
                elif isinstance(obj, InthonPyObject):
                    obj.obj[idx] = self._coerce(value)
                else:
                    raise VMError(
                        f"INTHON_RUNTIME_ASSIGN: Cannot set item on {type(obj)}"
                    )

            # ── Control flow ─────────────────────────────────────────── #
            elif op == OpCode.JUMP_ABSOLUTE:
                if arg < frame.ip:
                    self._loop_guard.record_backward_jump(arg)
                frame.ip = arg

            elif op == OpCode.JUMP_IF_FALSE:
                if not self._is_truthy(frame.peek()):
                    if arg < frame.ip:
                        self._loop_guard.record_backward_jump(arg)
                    frame.ip = arg

            elif op == OpCode.JUMP_IF_TRUE:
                if self._is_truthy(frame.peek()):
                    if arg < frame.ip:
                        self._loop_guard.record_backward_jump(arg)
                    frame.ip = arg

            elif op == OpCode.POP_JUMP_IF_FALSE:
                val = frame.pop()
                if not self._is_truthy(val):
                    if arg < frame.ip:
                        self._loop_guard.record_backward_jump(arg)
                    frame.ip = arg

            elif op == OpCode.POP_JUMP_IF_TRUE:
                val = frame.pop()
                if self._is_truthy(val):
                    if arg < frame.ip:
                        self._loop_guard.record_backward_jump(arg)
                    frame.ip = arg

            # ── Iterators ────────────────────────────────────────────── #
            elif op == OpCode.GET_ITER:
                obj = frame.pop()
                obj = self._unwrap(obj)
                from .serialization import InthonIterator

                if isinstance(obj, list):
                    frame.push(InthonIterator(obj))
                elif isinstance(obj, dict):
                    frame.push(InthonIterator(list(obj.keys())))
                elif isinstance(obj, InthonList):
                    frame.push(InthonIterator([to_python(i) for i in obj.items]))
                elif isinstance(obj, InthonDict):
                    frame.push(InthonIterator(list(obj.pairs.keys())))
                elif hasattr(obj, "__iter__"):
                    frame.push(InthonIterator(list(obj)))
                else:
                    raise VMError(
                        f"INTHON_RUNTIME_FOR: '{type(obj).__name__}' is not iterable"
                    )

            elif op == OpCode.FOR_ITER:
                it = frame.peek()  # iterator stays on stack until exhausted
                try:
                    val = next(it)
                    frame.push(val)
                except StopIteration:
                    frame.pop()  # remove the iterator
                    frame.ip = arg  # jump past the loop

            # ── Functions ────────────────────────────────────────────── #
            elif op == OpCode.MAKE_FUNCTION:
                child_co: CodeObject = frame.pop()
                param_names = child_co.param_names
                defaults = child_co.defaults
                closure = {**self._globals, **frame.locals}
                fn = InthonCallable(
                    name=arg,
                    params=param_names,
                    defaults={k: from_python(v) for k, v in defaults.items()},
                    body=child_co,  # store CodeObject in body field
                    closure=closure,
                )
                frame.push(fn)

            elif op == OpCode.CALL_FUNCTION:
                nargs, nkwargs = arg
                # Pop kwargs: interleaved (key, value) pairs, TOS-first
                kwargs: dict[str, Any] = {}
                for _ in range(nkwargs):
                    val = frame.pop()
                    key = frame.pop()
                    kwargs[str(key)] = val
                # Pop positional args (TOS is last arg)
                args = frame.pop_n(nargs)
                # Pop callee
                callee = frame.pop()
                result = self._call(callee, args, kwargs, frame)
                frame.push(result)

            elif op == OpCode.RETURN_VALUE:
                return frame.pop()

            # ── Imports ──────────────────────────────────────────────── #
            elif op == OpCode.IMPORT_TOOL:
                tool_path = arg
                root = tool_path.split(".")[0]
                tool_ref = InthonToolRef(root)
                frame.push(tool_ref)

            elif op == OpCode.IMPORT_PY:
                module_path, alias = arg
                from ..pybridge.importer import SafeModuleImporter

                importer = SafeModuleImporter(ctx=self._ctx)
                wrapper = importer.import_module(module_path, alias)
                frame.push(wrapper)

            # ── Tool calls ───────────────────────────────────────────── #
            elif op == OpCode.CALL_TOOL:
                # Already handled via CALL_FUNCTION → _call() → _call_tool()
                # This opcode is reserved for future direct-dispatch optimization
                tool_path, nargs, nkwargs = arg
                kwargs = {}
                for _ in range(nkwargs):
                    val = frame.pop()
                    key = frame.pop()
                    kwargs[str(key)] = val
                py_args = [self._coerce(frame.pop()) for _ in range(nargs)]
                py_args.reverse()
                result = self._call_tool(tool_path, py_args, kwargs)
                frame.push(result)

            # ── Agent primitives ─────────────────────────────────────── #
            elif op == OpCode.AGENT_ENTER:
                name, goal = arg
                ctx.current_agent = name
                ctx.agent_goal = goal
                ctx.push_scope()
                ctx.tracer.emit("agent_start", {"name": name, "goal": goal})

            elif op == OpCode.AGENT_EXIT:
                name = arg
                ctx.pop_scope()
                ctx.tracer.emit("agent_end", {"name": name})
                ctx.current_agent = None

            elif op == OpCode.APPLY_POLICY:
                from ..policy.model import Policy

                p = Policy(**arg) if isinstance(arg, dict) else arg
                ctx.policy.apply(p)
                ctx.sandbox.max_tool_calls = ctx.policy.current.max_tool_calls
                ctx.sandbox.max_runtime_sec = ctx.policy.current.max_runtime_sec
                ctx.sandbox.max_cost_usd = ctx.policy.current.max_cost_usd

            elif op == OpCode.AGENT_REMEMBER:
                namespace = arg
                ctx.policy.check_capability(Capability.MEMORY_WRITE)
                val = frame.pop()
                key = uuid.uuid4().hex[:8]
                ctx.memory.write(key, self._coerce(val), namespace)
                ctx.tracer.emit("remember", {"key": key, "namespace": namespace})

            elif op == OpCode.AGENT_FORGET:
                namespace = arg
                key_val = self._coerce(frame.pop())
                success = ctx.memory.delete(str(key_val), namespace)
                ctx.tracer.emit("forget", {"key": str(key_val), "success": success})

            elif op == OpCode.AGENT_RECALL:
                query, namespace, varname = arg
                recall_entries = ctx.memory.search(query, namespace)
                if recall_entries:
                    recall_entries.sort(key=lambda e: e.updated_at, reverse=True)
                    res_val = recall_entries[0].value
                else:
                    res_val = None
                frame.locals[varname] = res_val
                self._globals[varname] = res_val
                ctx.assign_var(varname, from_python(res_val))
                ctx.tracer.emit("recall", {"query": query, "var": varname})

            elif op == OpCode.AGENT_APPROVE:
                target, action = arg
                cap = (
                    Capability.PAYMENT_EXECUTE
                    if action == "pay"
                    else Capability.NETWORK
                )
                ctx.policy.check_capability(cap)
                ctx.policy.approval_gate.request(target, action, ctx)
                ctx.tracer.emit("approve", {"target": target, "action": action})

            elif op == OpCode.AGENT_GUARD:
                cond = frame.pop()
                if not self._is_truthy(cond):
                    raise PolicyViolationError(
                        "INTHON_RUNTIME_GUARD: Guard condition failed"
                    )

            elif op == OpCode.AGENT_EVAL:
                subject, rubric, criteria = arg
                ops_map = {
                    "==": lambda a, b: a == b,
                    "!=": lambda a, b: a != b,
                    "<": lambda a, b: a < b,
                    "<=": lambda a, b: a <= b,
                    ">": lambda a, b: a > b,
                    ">=": lambda a, b: a >= b,
                }
                for crit in criteria:
                    metric_val = frame.locals.get(crit["metric"]) or self._globals.get(
                        crit["metric"]
                    )
                    threshold = crit["threshold"]
                    op_fn = ops_map.get(crit["op"])
                    if op_fn and not op_fn(self._coerce(metric_val), threshold):
                        raise IntHonRuntimeError(
                            f"INTHON_RUNTIME_EVAL: Criterion '{crit['metric']}' failed"
                        )
                ctx.tracer.emit("eval", {"subject": subject, "rubric": rubric})

            elif op == OpCode.SETUP_RETRY:
                count, backoff = arg
                frame.retry_stack.append(RetryState(count=count, backoff=backoff))

            elif op == OpCode.END_RETRY:
                if frame.retry_stack:
                    frame.retry_stack.pop()

            elif op == OpCode.LOG_TRACE:
                ctx.tracer.emit("log", {"event": arg})

            else:
                raise VMError(f"Unknown opcode: {op}")

        # If we reach end without RETURN_VALUE, return None
        return None

    # ── Call dispatch ──────────────────────────────────────────────────── #

    def _call(
        self, callee: Any, args: list[Any], kwargs: dict[str, Any], frame: Frame
    ) -> Any:
        """Dispatch a call to a function, tool, or Python callable."""

        if isinstance(callee, InthonCallable):
            return self._call_function(callee, args, kwargs, parent_frame=frame)

        if isinstance(callee, InthonToolRef):
            # Build full tool path from toolref + any chained attrs
            return self._call_tool(
                callee.tool_path,
                [self._coerce(a) for a in args],
                {k: self._coerce(v) for k, v in kwargs.items()},
            )

        if isinstance(callee, InthonPyObject) and callable(callee.obj):
            return self._call_python(callee, args, kwargs)

        # Plain Python callables (from SafeModuleWrapper)
        if callable(callee):
            from ..pybridge.allowlist import is_safe_callable

            if not is_safe_callable(callee):
                raise VMError("INTHON_SANDBOX: Call to dangerous callable is denied.")
            py_args = [self._coerce(a) for a in args]
            py_kwargs = {k: self._coerce(v) for k, v in kwargs.items()}
            result = callee(*py_args, **py_kwargs)
            return self._coerce(result)

        raise VMError(
            f"INTHON_RUNTIME_003: Object of type {type(callee).__name__!r} is not callable"
        )

    def _call_function(
        self,
        fn: InthonCallable,
        args: list[Any],
        kwargs: dict[str, Any],
        parent_frame: Frame | None = None,
    ) -> Any:
        """Execute a user-defined INTHON function (InthonCallable)."""
        body = fn.body

        if isinstance(body, CodeObject):
            # New-style compiled function — create a child Frame
            child_locals: dict[str, Any] = {**fn.closure} if fn.closure else {}

            # Bind parameters
            for i, param in enumerate(fn.params):
                if i < len(args):
                    child_locals[param] = self._coerce(args[i])
                elif param in kwargs:
                    child_locals[param] = self._coerce(kwargs[param])
                elif param in fn.defaults:
                    child_locals[param] = self._coerce(to_python(fn.defaults[param]))
                else:
                    raise VMError(
                        f"INTHON_RUNTIME_004: Missing argument '{param}' for '{fn.name}'"
                    )

            child_frame = Frame(code=body, locals=child_locals, parent=parent_frame)
            return self._run_frame(child_frame)
        else:
            # Legacy AST-body callable — fall back to interpreter
            from ..runtime.interpreter import Interpreter

            interp = Interpreter(self._ctx)
            self._ctx.push_scope()
            try:
                for i, param in enumerate(fn.params):
                    if i < len(args):
                        self._ctx.set_var(param, from_python(self._coerce(args[i])))
                    elif param in kwargs:
                        self._ctx.set_var(
                            param, from_python(self._coerce(kwargs[param]))
                        )
                    elif param in fn.defaults:
                        self._ctx.set_var(param, fn.defaults[param])
                    else:
                        raise VMError(
                            f"INTHON_RUNTIME_004: Missing argument '{param}' for '{fn.name}'"
                        )
                result = InthonNone()
                try:
                    for stmt in fn.body:
                        interp.visit(stmt)
                except ReturnSignal as ret:
                    result = ret.value
                return to_python(result)
            finally:
                self._ctx.pop_scope()

    def _call_tool(
        self, tool_path: str, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:
        """Call a registered tool, enforcing policy/budget checks."""
        self._loop_guard.record_tool_call(tool_path, args, kwargs)
        ctx = self._ctx
        if ctx.dry_run:
            from ..runtime.dryrun import generate_mock_output

            try:
                spec = ctx.tools.get_spec(tool_path)
                return generate_mock_output(spec.output_schema)
            except Exception:
                return {}
        ctx.sandbox.check_budget()
        spec = ctx.tools.get_spec(tool_path)
        ctx.policy.check_tool(spec)
        for eff in spec.side_effects:
            if eff == "network":
                ctx.policy.check_capability(Capability.NETWORK)
            elif eff == "filesystem":
                ctx.policy.check_capability(Capability.FILESYSTEM_WRITE)

        result = ctx.tools.call(tool_path, args, kwargs)
        if not result.success:
            raise ToolCallError(
                f"INTHON_TOOL_004: Tool execution failed: {result.error}"
            )

        ctx.tool_call_count += 1
        ctx.cost_usd += result.cost_usd
        ctx.sandbox.record_tool_call(result.cost_usd)
        ctx.tracer.emit(
            "tool_call",
            {
                "tool": tool_path,
                "args": str(args)[:200],
                "cost_usd": result.cost_usd,
            },
        )
        return result.output

    def _call_python(
        self, callee: InthonPyObject, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:
        """Call a wrapped Python callable."""
        ctx = self._ctx
        ctx.py_call_count += 1
        py_args = [self._coerce(a) for a in args]
        py_kwargs = {k: self._coerce(v) for k, v in kwargs.items()}
        ctx.tracer.emit(
            "py_call",
            {
                "func": getattr(callee.obj, "__name__", str(callee.obj)),
                "args": str(py_args)[:200],
            },
        )
        from ..pybridge.allowlist import is_safe_callable

        if not is_safe_callable(callee.obj):
            raise VMError("INTHON_SANDBOX: Call to dangerous callable is denied.")
        result = callee.obj(*py_args, **py_kwargs)
        return result

    # ── Value helpers ──────────────────────────────────────────────────── #

    @staticmethod
    def _coerce(val: Any) -> Any:
        """Convert InthonValue wrappers to plain Python values."""
        if isinstance(val, (InthonInt, InthonFloat, InthonStr, InthonBool)):
            return val.value
        if isinstance(val, InthonNone):
            return None
        if isinstance(val, InthonList):
            return [InthonVM._coerce(i) for i in val.items]
        if isinstance(val, InthonDict):
            return {k: InthonVM._coerce(v) for k, v in val.pairs.items()}
        if isinstance(val, InthonPyObject):
            return val.obj
        return val  # Already a raw Python value

    @staticmethod
    def _unwrap(val: Any) -> Any:
        """Unwrap one layer of InthonValue (for attribute/index access)."""
        if isinstance(val, (InthonInt, InthonFloat, InthonStr, InthonBool)):
            return val.value
        if isinstance(val, InthonNone):
            return None
        if isinstance(val, InthonPyObject):
            return val.obj
        return val

    @staticmethod
    def _is_truthy(val: Any) -> bool:
        """Evaluate truthiness of any INTHON or Python value."""
        if isinstance(val, InthonBool):
            return val.value
        if isinstance(val, InthonNone):
            return False
        if isinstance(val, InthonInt):
            return val.value != 0
        if isinstance(val, InthonStr):
            return bool(val.value)
        if isinstance(val, InthonList):
            return bool(val.items)
        if isinstance(val, InthonDict):
            return bool(val.pairs)
        # Raw Python
        return bool(val)
