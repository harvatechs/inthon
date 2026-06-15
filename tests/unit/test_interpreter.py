import pytest
from inthon import run, parse
from inthon.runtime.context import ExecutionContext
from inthon.runtime.interpreter import Interpreter
from inthon.runtime.values import to_python
from inthon.runtime.errors import (
    IntHonRuntimeError,
    SandboxViolationError,
    ApprovalDeniedError,
    PolicyViolationError,
)
from inthon.policy.approval import ApprovalRequest


def test_eval_basic_arithmetic():
    src = "let x = 10 + 20 * 2 - 5\nx"
    res = run(src)
    assert res.output == 45


def test_eval_boolean_operators():
    src = "let a = true\nlet b = false\nlet c = a or b\nlet d = a and b\nlet e = not a"
    # We can run an interpreter manually to inspect all values in scope
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("c")) is True
    assert to_python(ctx.get_var("d")) is False
    assert to_python(ctx.get_var("e")) is False


def test_variable_reassignment():
    src = "let x = 10\nx = 20\nx"
    res = run(src)
    assert res.output == 20


def test_if_else_statement():
    src = """
    let x = 10
    let res = 0
    if x > 5 {
        res = 1
    } else {
        res = 2
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("res")) == 1


def test_while_loop():
    src = """
    let i = 0
    let sum = 0
    while i < 5 {
        sum = sum + i
        i = i + 1
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("sum")) == 10


def test_for_loop():
    src = """
    let sum = 0
    for x in [1, 2, 3, 4] {
        sum = sum + x
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("sum")) == 10


def test_function_call():
    src = """
    fn add(x, y = 5) {
        return x + y
    }
    let a = add(10)
    let b = add(10, y: 20)
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("a")) == 15
    assert to_python(ctx.get_var("b")) == 30


def test_agent_policy_and_sandbox_limits():
    src = """
    agent MyAgent {
        goal "Test agent goal"
        policy {
            allow_network: true
            max_tool_calls: 3
            max_cost_usd: 0.05
        }
        plan {
            let x = 1
        }
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert ctx.policy.max_tool_calls == 3
    assert ctx.policy.max_cost_usd == 0.05
    # allow_network is in active capabilities
    from inthon.policy.model import Capability

    assert Capability.NETWORK in ctx.policy.active_caps


def test_sandbox_tool_calls_quota_violation():
    src = """
    agent MyAgent {
        policy {
            max_tool_calls: 1
            allow_network: true
        }
        plan {
            use tool web.search
            web.search("first")
            web.search("second")
        }
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    from inthon.tools.builtin_tools import register_builtins

    register_builtins(ctx.tools, mock=True)
    interp = Interpreter(ctx)
    with pytest.raises(SandboxViolationError) as exc:
        interp.run(prog)
    assert "limit of 1 exceeded" in str(exc.value)


def test_sandbox_cost_quota_violation():
    src = """
    agent MyAgent {
        policy {
            max_cost_usd: 0.001
            allow_network: true
        }
        plan {
            use tool web.search
            web.search("query") // cost is 0.005
        }
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    from inthon.tools.builtin_tools import register_builtins

    register_builtins(ctx.tools, mock=True)
    interp = Interpreter(ctx)
    # The first call estimates the budget beforehand or budget is exceeded.
    with pytest.raises(SandboxViolationError) as exc:
        interp.run(prog)
    assert "exceeded $0.001" in str(exc.value)


def test_policy_capability_denied():
    src = """
    agent MyAgent {
        policy {
            allow_network: false
        }
        plan {
            use tool web.search
            web.search("query")
        }
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    from inthon.tools.builtin_tools import register_builtins

    register_builtins(ctx.tools, mock=True)
    interp = Interpreter(ctx)
    with pytest.raises(PolicyViolationError) as exc:
        interp.run(prog)
    assert "Capability 'NETWORK' is required" in str(exc.value)


def test_interactive_approval_gate_auto_approve():
    src = """
    agent GuardAgent {
        policy {
            allow_network: true
        }
        plan {
            approve my_server before send
        }
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()

    # Register an auto-approve handler
    def auto_approve(req: ApprovalRequest) -> bool:
        return req.action == "send"

    ctx.policy.approval_gate.set_handler(auto_approve)
    interp = Interpreter(ctx)
    interp.run(prog)  # should pass without error


def test_interactive_approval_gate_denied():
    src = """
    agent GuardAgent {
        policy {
            allow_network: true
        }
        plan {
            approve my_server before send
        }
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()

    # Register a denial handler
    def deny_all(req: ApprovalRequest) -> bool:
        return False

    ctx.policy.approval_gate.set_handler(deny_all)
    interp = Interpreter(ctx)
    with pytest.raises(ApprovalDeniedError) as exc:
        interp.run(prog)
    assert "Human denied approval" in str(exc.value)


def test_memory_actions_remember_recall_forget():
    src = """
    agent MemAgent {
        policy {
            allow_network: true
            allow_memory_persist: true
        }
        plan {
            remember "INTHON rules" in session
            x = recall "rules" from session
            forget "rules" from session
            return x
        }
    }
    """
    res = run(src)
    assert res.output == "INTHON rules"


def test_retry_statement_success():
    src = """
    let x = 0
    retry 3 with backoff fixed {
        x = x + 1
        if x < 2 {
            guard false
        }
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("x")) == 2


def test_retry_statement_failure_and_catch():
    src = """
    let x = 0
    let caught_msg = ""
    retry 2 with backoff fixed {
        x = x + 1
        guard false
    } catch err {
        caught_msg = err
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("x")) == 2
    assert "Guard condition failed" in to_python(ctx.get_var("caught_msg"))


def test_guard_statement():
    src = "guard 10 > 5"
    res = run(src)
    assert res.output is None

    src_fail = "guard 10 < 5"
    with pytest.raises(IntHonRuntimeError) as exc:
        run(src_fail)
    assert "Guard condition failed" in str(exc.value)


def test_eval_statement():
    src = """
    let score = 0.95
    eval score against rubric {
        score >= 0.9
    }
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)  # passes without error

    src_fail = """
    let score = 0.85
    eval score against rubric {
        score >= 0.9
    }
    """
    prog_fail = parse(src_fail)
    ctx_fail = ExecutionContext()
    interp_fail = Interpreter(ctx_fail)
    with pytest.raises(IntHonRuntimeError) as exc:
        interp_fail.run(prog_fail)
    assert "expected >= 0.9, got 0.85" in str(exc.value)


def test_dynamic_target_assignment_nested():
    src = """
    use py.json as js
    // Parse json to dict
    let data = js.loads("{\\"a\\": {\\"b\\": 10}}")
    data.a.b = 20
    let val = data.a.b
    """
    # Let's run this test. Note that `use py.json` requires allowlist permission,
    # and "json" is in DEFAULT_ALLOWED_MODULES.
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("val")) == 20


def test_dict_subscript_assignment():
    src = """
    let d = {"key": "old"}
    d["key"] = "new"
    let val = d["key"]
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("val")) == "new"


def test_list_subscript_assignment():
    src = """
    let lst = [1, 2, 3]
    lst[1] = 99
    let val = lst[1]
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("val")) == 99


def test_nested_subscript_assignment():
    src = """
    let data = {"a": {"b": 10}}
    data["a"]["b"] = 100
    let val = data["a"]["b"]
    """
    prog = parse(src)
    ctx = ExecutionContext()
    interp = Interpreter(ctx)
    interp.run(prog)
    assert to_python(ctx.get_var("val")) == 100


def test_top_level_return():
    src = """
    let val = 42
    return val + 8
    """
    res = run(src)
    assert res.output == 50
