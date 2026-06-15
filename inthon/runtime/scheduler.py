"""
inthon.runtime.scheduler — Multi-agent cooperative async scheduler.

The AgentScheduler manages a pool of AsyncInthonVM tasks, allowing multiple
agent declarations to execute concurrently on the same event loop. Each agent
runs as an asyncio Task, with shared ExecutionContext subsystems (memory, tools,
policy, tracer) that are thread-safe by design.

Usage::

    scheduler = AgentScheduler(ctx)
    await scheduler.spawn("alice", alice_code_object)
    await scheduler.spawn("bob", bob_code_object)
    results = await scheduler.wait_all()
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from ..runtime.context import ExecutionContext
from ..vm.code_object import CodeObject
from ..vm.async_machine import AsyncInthonVM


@dataclass
class AgentTask:
    """Tracks a single agent's execution task."""

    agent_id: str
    name: str
    task: asyncio.Task
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    result: Any = None
    error: Exception | None = None


class AgentScheduler:
    """
    Cooperative multi-agent scheduler built on asyncio.

    Each call to `spawn()` creates an asyncio Task running an AsyncInthonVM.
    All agents share the same ExecutionContext (memory, tools, policy) but run
    in separate VM frames.

    Call `wait_all()` to await all spawned agents and collect their results.
    """

    def __init__(self, ctx: ExecutionContext) -> None:
        self._ctx = ctx
        self._tasks: dict[str, AgentTask] = {}
        self._vm = AsyncInthonVM(ctx)

    async def __aenter__(self) -> "AgentScheduler":
        await self._vm.__aenter__()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._vm.__aexit__(*exc_info)

    async def spawn(self, name: str, code: CodeObject) -> str:
        """
        Spawn an agent task. Returns the agent_id used to track it.
        Multiple agents with the same name are allowed (different IDs).
        """
        import uuid

        agent_id = f"{name}_{uuid.uuid4().hex[:6]}"

        async def _run() -> Any:
            return await self._vm.execute(code)

        task = asyncio.create_task(_run(), name=agent_id)
        agent_task = AgentTask(agent_id=agent_id, name=name, task=task)
        self._tasks[agent_id] = agent_task

        # Attach completion callback
        def _on_done(t: asyncio.Task) -> None:
            at = self._tasks.get(agent_id)
            if at:
                at.finished_at = time.time()
                if t.cancelled():
                    at.error = asyncio.CancelledError()
                elif t.exception():
                    at.error = t.exception()
                else:
                    at.result = t.result()

        task.add_done_callback(_on_done)
        return agent_id

    async def wait_all(self, timeout: float | None = None) -> dict[str, Any]:
        """
        Await all spawned agent tasks. Returns a dict mapping agent_id → result.
        Agents that errored have their result set to None and error in agent_results.
        """
        if not self._tasks:
            return {}

        all_tasks = [at.task for at in self._tasks.values()]
        done, pending = await asyncio.wait(
            all_tasks,
            timeout=timeout,
            return_when=asyncio.ALL_COMPLETED,
        )

        if pending:
            for task in pending:
                task.cancel()
            # Wait for cancellation to complete
            await asyncio.gather(*pending, return_exceptions=True)

        return self.get_results()

    async def cancel(self, agent_id: str) -> None:
        """Cancel a specific agent task."""
        at = self._tasks.get(agent_id)
        if at and not at.task.done():
            at.task.cancel()
            try:
                await at.task
            except asyncio.CancelledError:
                pass

    def get_results(self) -> dict[str, Any]:
        """
        Return completed results as a dict of agent_id → value.
        Errors are stored in agent metadata, not raised here.
        """
        return {agent_id: at.result for agent_id, at in self._tasks.items()}

    def get_errors(self) -> dict[str, Exception | None]:
        """Return per-agent errors, if any."""
        return {
            agent_id: at.error
            for agent_id, at in self._tasks.items()
            if at.error is not None
        }

    def summary(self) -> dict:
        """Return a summary of all agent executions."""
        return {
            at.agent_id: {
                "name": at.name,
                "started_at": at.started_at,
                "finished_at": at.finished_at,
                "duration_ms": round((at.finished_at - at.started_at) * 1000, 2)
                if at.finished_at
                else None,
                "result": at.result,
                "error": str(at.error) if at.error else None,
            }
            for at in self._tasks.values()
        }


async def run_agents_concurrently(
    code_objects: dict[str, CodeObject],
    ctx: ExecutionContext,
    timeout: float | None = 300.0,
) -> dict[str, Any]:
    """
    Convenience function: run multiple named agents concurrently
    and return their results.

    Args:
        code_objects: dict of agent_name → CodeObject to execute.
        ctx: shared ExecutionContext.
        timeout: overall timeout in seconds (None = no limit).

    Returns:
        dict of agent_name → result value.
    """
    async with AgentScheduler(ctx) as scheduler:
        for name, code in code_objects.items():
            await scheduler.spawn(name, code)
        return await scheduler.wait_all(timeout=timeout)
