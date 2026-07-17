"""
tests/unit/test_async_scheduler.py — Unit tests for cooperative async scheduler (Phase 4).
"""

import pytest
from inthon.runtime.context import ExecutionContext
from inthon.runtime.scheduler import AgentScheduler
from inthon.vm.old_parser import parse
from inthon.vm.old_compiler import compile_program


@pytest.mark.anyio
async def test_async_scheduler_concurrent_execution():
    """Verify that multiple agents can be run concurrently and finish successfully."""
    ctx = ExecutionContext()

    src1 = """
agent BotA {
    goal "Task A"
    plan {
        let x = 10
        // Wait or yield is implicit in async loop
        return x
    }
}
"""
    src2 = """
agent BotB {
    goal "Task B"
    plan {
        let y = 20
        return y
    }
}
"""

    prog1 = parse(src1, "<test1>")
    prog2 = parse(src2, "<test2>")
    code1 = compile_program(prog1, "<test1>")
    code2 = compile_program(prog2, "<test2>")

    async with AgentScheduler(ctx) as scheduler:
        id1 = await scheduler.spawn("BotA", code1)
        id2 = await scheduler.spawn("BotB", code2)

        results = await scheduler.wait_all(timeout=5.0)

        # Verify both executed successfully
        assert results[id1] == 10
        assert results[id2] == 20

        summary = scheduler.summary()
        assert summary[id1]["name"] == "BotA"
        assert summary[id2]["name"] == "BotB"
        assert summary[id1]["error"] is None
        assert summary[id2]["error"] is None
