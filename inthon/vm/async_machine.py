"""
inthon.vm.async_machine — Async-cooperative variant of InthonVM.

AsyncInthonVM wraps the synchronous VM dispatch loop in an asyncio-aware
execution model. I/O-bound opcodes (CALL_TOOL, AGENT_APPROVE, AGENT_RECALL)
are executed in a thread pool executor so they don't block the event loop,
allowing multiple agents to make progress concurrently.

Usage::

    async with AsyncInthonVM(ctx) as vm:
        result = await vm.execute(code_object)
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..runtime.context import ExecutionContext
from ..runtime.errors import PolicyViolationError
from ..runtime.values import from_python
from ..policy.model import Capability
from .code_object import CodeObject
from .frame import Frame
from .machine import InthonVM
from .opcodes import OpCode


class AsyncInthonVM(InthonVM):
    """
    Async-cooperative INTHON VM. Inherits the synchronous dispatch loop from
    InthonVM and overrides I/O-heavy opcodes to be non-blocking.

    The async execute() method runs the frame in a thread pool, yielding the
    event loop at every CALL_TOOL / AGENT_APPROVE boundary so other coroutines
    can progress.
    """

    def __init__(
        self, ctx: ExecutionContext, executor: ThreadPoolExecutor | None = None
    ) -> None:
        super().__init__(ctx)
        self._executor = executor or ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="inthon-vm"
        )
        self._loop: asyncio.AbstractEventLoop | None = None

    async def __aenter__(self) -> "AsyncInthonVM":
        self._loop = asyncio.get_running_loop()
        return self

    async def __aexit__(self, *exc_info) -> None:
        self._executor.shutdown(wait=False)

    async def execute(self, code: CodeObject) -> Any:  # type: ignore[override]
        """Execute a CodeObject asynchronously, yielding at I/O boundaries."""
        frame = Frame(code=code, locals=self._globals)
        try:
            return await self._run_frame_async(frame)
        except _ReturnFromAsync as exc:
            return exc.value

    async def _run_frame_async(self, frame: Frame) -> Any:
        """Async variant of the VM dispatch loop."""
        instructions = frame.code.instructions
        constants = frame.code.constants
        n = len(instructions)
        loop = asyncio.get_running_loop()

        while frame.ip < n:
            instr = instructions[frame.ip]
            frame.ip += 1
            op = instr.op
            arg = instr.arg

            # ── I/O-bound opcodes: offload to executor ────────────────────
            if op == OpCode.CALL_FUNCTION:
                # May invoke a tool or Python call — run in executor
                nargs, nkwargs = arg
                kwargs: dict[str, Any] = {}
                for _ in range(nkwargs):
                    val = frame.pop()
                    key = frame.pop()
                    kwargs[str(key)] = val
                args_list = frame.pop_n(nargs)
                callee = frame.pop()

                # Yield control briefly before dispatching I/O
                await asyncio.sleep(0)

                result = await loop.run_in_executor(
                    self._executor,
                    self._call,
                    callee,
                    args_list,
                    kwargs,
                    frame,
                )
                frame.push(result)

            elif op == OpCode.AGENT_REMEMBER:
                namespace = arg
                val = frame.pop()
                await asyncio.sleep(0)
                await loop.run_in_executor(
                    self._executor,
                    self._do_remember,
                    val,
                    namespace,
                )

            elif op == OpCode.AGENT_RECALL:
                query, namespace, varname = arg
                await asyncio.sleep(0)
                result = await loop.run_in_executor(
                    self._executor,
                    self._do_recall,
                    query,
                    namespace,
                    varname,
                    frame,
                )

            elif op == OpCode.AGENT_APPROVE:
                target, action = arg
                await asyncio.sleep(0)
                # Approval gates may wait for human input — run in executor
                await loop.run_in_executor(
                    self._executor,
                    self._do_approve,
                    target,
                    action,
                )

            else:
                # All non-I/O opcodes execute synchronously in the event loop
                # We reuse the parent's _run_frame by executing ONE instruction
                await self._execute_single(frame, op, arg, constants)

        return None

    async def _execute_single(
        self, frame: Frame, op: OpCode, arg: Any, constants: list
    ) -> None:
        """
        Execute a single non-I/O opcode. Dispatches to the synchronous handler
        in the parent class by temporarily setting ip to the instruction's position.
        """
        # We call the synchronous VM dispatch logic for CPU-bound opcodes.
        # Since frame.ip is already advanced by _run_frame_async, we create a
        # minimal one-instruction code and run it.
        # Simpler approach: handle the common non-IO ops here directly.
        # For full correctness, we delegate back to a mini-VM step.
        # Use the parent's _coerce/_is_truthy/_unwrap helpers
        self._dispatch_cpu_op(frame, op, arg, constants)

    def _dispatch_cpu_op(
        self, frame: Frame, op: OpCode, arg: Any, constants: list
    ) -> None:  # noqa: C901
        """Synchronous dispatch for CPU-bound opcodes (no I/O)."""
        _s = InthonVM._coerce
        _t = InthonVM._is_truthy
        _u = InthonVM._unwrap

        if op == OpCode.LOAD_CONST:
            frame.push(constants[arg])
        elif op == OpCode.LOAD_FAST or op == OpCode.LOAD_GLOBAL:
            name = arg
            val = frame.locals.get(name) or self._globals.get(name)
            if val is None:
                try:
                    val = self._ctx.get_var(name)
                except RuntimeError:
                    val = None
            frame.push(val)
        elif op == OpCode.STORE_FAST or op == OpCode.STORE_GLOBAL:
            v = frame.pop()
            frame.locals[arg] = v
            self._globals[arg] = v
        elif op == OpCode.POP_TOP:
            frame.pop()
        elif op == OpCode.DUP_TOP:
            frame.push(frame.peek())
        elif op == OpCode.ROT_TWO:
            a, b = frame.pop(), frame.pop()
            frame.push(a)
            frame.push(b)
        elif op in (
            OpCode.BINARY_ADD,
            OpCode.BINARY_SUB,
            OpCode.BINARY_MUL,
            OpCode.BINARY_DIV,
            OpCode.BINARY_MOD,
            OpCode.BINARY_POW,
        ):
            b, a = _s(frame.pop()), _s(frame.pop())
            op_map = {
                OpCode.BINARY_ADD: lambda x, y: x + y,
                OpCode.BINARY_SUB: lambda x, y: x - y,
                OpCode.BINARY_MUL: lambda x, y: x * y,
                OpCode.BINARY_DIV: lambda x, y: x / y,
                OpCode.BINARY_MOD: lambda x, y: x % y,
                OpCode.BINARY_POW: lambda x, y: x**y,
            }
            frame.push(op_map[op](a, b))
        elif op in (
            OpCode.COMPARE_EQ,
            OpCode.COMPARE_NE,
            OpCode.COMPARE_LT,
            OpCode.COMPARE_LE,
            OpCode.COMPARE_GT,
            OpCode.COMPARE_GE,
        ):
            b, a = _s(frame.pop()), _s(frame.pop())
            cmp_map = {
                OpCode.COMPARE_EQ: lambda x, y: x == y,
                OpCode.COMPARE_NE: lambda x, y: x != y,
                OpCode.COMPARE_LT: lambda x, y: x < y,
                OpCode.COMPARE_LE: lambda x, y: x <= y,
                OpCode.COMPARE_GT: lambda x, y: x > y,
                OpCode.COMPARE_GE: lambda x, y: x >= y,
            }
            frame.push(cmp_map[op](a, b))
        elif op == OpCode.UNARY_NOT:
            frame.push(not _t(frame.pop()))
        elif op == OpCode.UNARY_NEG:
            frame.push(-_s(frame.pop()))
        elif op == OpCode.BUILD_LIST:
            frame.push(frame.pop_n(arg))
        elif op == OpCode.BUILD_DICT:
            pairs = frame.pop_n(arg * 2)
            d = {pairs[i]: pairs[i + 1] for i in range(0, len(pairs), 2)}
            frame.push(d)
        elif op == OpCode.GET_ATTR:
            obj = _u(frame.pop())
            from ..runtime.values import InthonToolRef

            if isinstance(obj, dict):
                val = obj.get(arg)
            elif isinstance(obj, InthonToolRef):
                val = InthonToolRef(obj.tool_path + "." + arg)
            else:
                val = getattr(obj, arg, None)
            frame.push(val)
        elif op == OpCode.GET_ITEM:
            idx = _s(frame.pop())
            obj = _u(frame.pop())
            frame.push(obj[int(idx)] if isinstance(obj, list) else obj[idx])
        elif op == OpCode.JUMP_ABSOLUTE:
            if arg < frame.ip:
                self._loop_guard.record_backward_jump(arg)
            frame.ip = arg
        elif op == OpCode.POP_JUMP_IF_FALSE:
            if not _t(frame.pop()):
                if arg < frame.ip:
                    self._loop_guard.record_backward_jump(arg)
                frame.ip = arg
        elif op == OpCode.POP_JUMP_IF_TRUE:
            if _t(frame.pop()):
                if arg < frame.ip:
                    self._loop_guard.record_backward_jump(arg)
                frame.ip = arg
        elif op == OpCode.GET_ITER:
            obj = _u(frame.pop())
            from .serialization import InthonIterator

            frame.push(
                InthonIterator(list(obj))
                if hasattr(obj, "__iter__")
                else InthonIterator([])
            )
        elif op == OpCode.FOR_ITER:
            it = frame.peek()
            try:
                frame.push(next(it))
            except StopIteration:
                frame.pop()
                frame.ip = arg
        elif op == OpCode.RETURN_VALUE:
            raise _ReturnFromAsync(frame.pop())
        elif op == OpCode.AGENT_ENTER:
            name, goal = arg
            self._ctx.current_agent = name
            self._ctx.agent_goal = goal
            self._ctx.push_scope()
            self._ctx.tracer.emit("agent_start", {"name": name, "goal": goal})
        elif op == OpCode.AGENT_EXIT:
            self._ctx.pop_scope()
            self._ctx.tracer.emit("agent_end", {"name": arg})
            self._ctx.current_agent = None
        elif op == OpCode.AGENT_GUARD:
            cond = frame.pop()
            if not _t(cond):
                raise PolicyViolationError(
                    "INTHON_RUNTIME_GUARD: Guard condition failed"
                )
        elif op == OpCode.APPLY_POLICY:
            from ..ast.nodes import PolicyBlock, PolicyEntry

            entries = tuple(PolicyEntry(key=k, value=v) for k, v in arg.items())
            self._ctx.policy.apply(PolicyBlock(entries=entries))
        elif op == OpCode.MAKE_FUNCTION:
            child_co = frame.pop()
            param_names = child_co.param_names
            defaults = child_co.defaults
            from ..runtime.values import InthonCallable

            fn = InthonCallable(
                name=arg,
                params=param_names,
                defaults={k: from_python(v) for k, v in defaults.items()},
                body=child_co,
                closure={**self._globals, **frame.locals},
            )
            frame.push(fn)
        elif op == OpCode.IMPORT_TOOL:
            from ..runtime.values import InthonToolRef

            frame.push(InthonToolRef(arg.split(".")[0]))
        elif op == OpCode.IMPORT_PY:
            module_path, alias = arg
            from ..pybridge.importer import SafeModuleImporter

            wrapper = SafeModuleImporter(ctx=self._ctx).import_module(
                module_path, alias
            )
            frame.push(wrapper)
        # Skip unknown ops in async mode (log and continue)

    # ── Async I/O helpers ──────────────────────────────────────────────── #

    def _do_remember(self, val: Any, namespace: str) -> None:
        self._ctx.policy.check_capability(Capability.MEMORY_WRITE)
        key = uuid.uuid4().hex[:8]
        self._ctx.memory.write(key, self._coerce(val), namespace)
        self._ctx.tracer.emit("remember", {"key": key, "namespace": namespace})

    def _do_recall(self, query: str, namespace: str, varname: str, frame: Frame) -> Any:
        entries = self._ctx.memory.search(query, namespace)
        result = entries[0].value if entries else None
        frame.locals[varname] = result
        self._globals[varname] = result
        self._ctx.tracer.emit("recall", {"query": query, "var": varname})
        return result

    def _do_approve(self, target: str, action: str) -> None:
        cap = Capability.PAYMENT_EXECUTE if action == "pay" else Capability.NETWORK
        self._ctx.policy.check_capability(cap)
        self._ctx.policy.approval_gate.request(target, action, self._ctx)
        self._ctx.tracer.emit("approve", {"target": target, "action": action})


class _ReturnFromAsync(Exception):
    """Control-flow exception for RETURN_VALUE in async dispatch."""

    def __init__(self, value: Any) -> None:
        self.value = value
