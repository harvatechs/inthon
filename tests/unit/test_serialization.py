"""
tests/unit/test_serialization.py — Unit tests for INTHON VM state dehydration/hydration.
"""

from __future__ import annotations
from inthon.runtime.context import ExecutionContext
from inthon.parser.parser import parse
from inthon.vm.compiler import compile_program
from inthon.vm.machine import InthonVM, PauseSignal
from inthon.vm.serialization import (
    serialize_value,
    deserialize_value,
)

class PauseHelper:
    def __init__(self):
        self.frame = None

    def __call__(self):
        raise PauseSignal(self.frame)


def test_value_serialization():
    from inthon.runtime.values import InthonInt, InthonStr, InthonList

    # Primitives
    assert serialize_value(10) == 10
    assert serialize_value("hello") == "hello"

    # Inthon wrappers
    assert serialize_value(InthonInt(42)) == {"__type__": "inthon_int", "v": 42}
    assert serialize_value(InthonStr("test")) == {"__type__": "inthon_str", "v": "test"}

    # Collections
    lst = InthonList([InthonInt(1), InthonInt(2)])
    ser_lst = serialize_value(lst)
    assert ser_lst == {
        "__type__": "inthon_list",
        "items": [{"__type__": "inthon_int", "v": 1}, {"__type__": "inthon_int", "v": 2}],
    }
    assert deserialize_value(ser_lst) == lst


def test_execution_pause_and_resume():
    ctx = ExecutionContext()
    vm = InthonVM(ctx)

    src = """
let x = 5
let y = pause()
let z = x + y
"""

    pauser = PauseHelper()
    vm._globals["pause"] = pauser

    prog = parse(src, "<test>")
    code = compile_program(prog, "<test>")

    # Intercept Pauser in VM._call for the test
    original_call = vm._call
    def mock_call(callee, args, kwargs, frame):
        if callee is pauser:
            pauser.frame = frame
        return original_call(callee, args, kwargs, frame)
    vm._call = mock_call

    # Run the VM. It should raise PauseSignal when it hits pause()
    state = None
    try:
        vm.execute(code)
        assert False, "Should have raised PauseSignal"
    except PauseSignal as sig:
        state = vm.dehydrate_state(sig.frame)

    assert state is not None
    assert state["ip"] > 0
    assert state["ip"] > 0
    assert state["locals"]["x"] == 5

    # Now, resume the VM. We need to feed the return value of pause() onto the stack.
    # In INTHON, when a call finishes, the return value is pushed onto the stack.
    # In the dehydrated state, the ip has advanced past CALL_FUNCTION, but it expects
    # the result to be on the stack because the next instructions use it.
    # Let's verify: we can push the result onto the rehydrated frame's stack.
    # Or, we can just push it before we serialize.
    # Let's push 15 onto the stack to act as the return value from pause().
    state["stack"].append(serialize_value(15))

    # Re-run from the serialized state
    vm2 = InthonVM(ctx)
    vm2.resume_execution(state)

    # After resuming, let's verify z's value in vm2 globals
    assert vm2._globals["z"] == 20
