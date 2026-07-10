"""
tests/unit/test_loop_guard.py — Unit tests for the Metacognitive Loop Guard.
"""

from __future__ import annotations
import pytest
from inthon.runtime.context import ExecutionContext
from inthon.parser.parser import parse
from inthon.vm.compiler import compile_program
from inthon.vm.machine import InthonVM
from inthon.policy.loop_guard import LoopDetectedError


def test_vm_infinite_loop_detection():
    ctx = ExecutionContext()
    # Set VM threshold low to speed up the test
    vm = InthonVM(ctx)
    vm._loop_guard.max_vm_iterations = 20

    src = """
let x = 0
while x < 100 {
    // infinite loop because we don't increment x
}
"""
    prog = parse(src, "<test>")
    code = compile_program(prog, "<test>")

    with pytest.raises(LoopDetectedError) as exc_info:
        vm.execute(code)

    assert "Infinite control flow loop detected" in str(exc_info.value)


def test_tool_repetition_loop_detection():
    ctx = ExecutionContext()
    # Authorize network capability for web.search
    from inthon.policy.model import Capability

    ctx.policy.active_caps.add(Capability.NETWORK)

    vm = InthonVM(ctx)
    vm._loop_guard.max_tool_repetitions = 2

    # Register a mock tool in execution context
    from inthon.tools.builtin_tools import register_builtins

    register_builtins(ctx.tools, mock=True)

    src = """
use tool web.search
let i = 0
while i < 10 {
    web.search("AI")
    i = i + 1
}
"""
    prog = parse(src, "<test>")
    code = compile_program(prog, "<test>")

    with pytest.raises(LoopDetectedError) as exc_info:
        vm.execute(code)

    assert "Tool loop detected" in str(exc_info.value)


def test_tool_cycle_loop_detection():
    ctx = ExecutionContext()
    # Authorize network and payment capability
    from inthon.policy.model import Capability

    ctx.policy.active_caps.add(Capability.NETWORK)
    ctx.policy.active_caps.add(Capability.PAYMENT_EXECUTE)

    vm = InthonVM(ctx)
    vm._loop_guard.max_tool_repetitions = 5  # don't trigger simple repetition

    from inthon.tools.builtin_tools import register_builtins

    register_builtins(ctx.tools, mock=True)

    # Let's call web.search and web.read alternatively in a loop
    src = """
use tool web.search
use tool web.read
let i = 0
while i < 10 {
    web.search("test")
    web.read("https://example.com")
    i = i + 1
}
"""
    prog = parse(src, "<test>")
    code = compile_program(prog, "<test>")

    with pytest.raises(LoopDetectedError) as exc_info:
        vm.execute(code)

    assert "Multi-tool cycle loop detected" in str(exc_info.value)
