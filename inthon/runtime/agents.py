"""Shared agent invocation choreography (used by both backends).

Handles: input binding + type checks, policy frame push/pop, memory
journaling with rollback on policy violation (SB-14), and trace events.
The actual plan execution is injected by the backend.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..errors import InthonSemanticError, InthonTypeError_, PolicyViolationError, Span
from ..policy.model import Policy
from .typecheck import check_value_against_type
from .values import NONE, InthonValue, display


def invoke_agent(
    ctx,
    agent,
    kwargs: dict,
    span: Optional[Span],
    run_plan: Callable[[object, dict], InthonValue],
) -> InthonValue:
    decl = agent.decl
    if decl.plan is None:
        raise InthonSemanticError(
            f"Agent '{decl.name}' has no plan block", span=span or decl.span,
            hint="Every agent needs a plan { ... } body.",
        )

    input_names = [f.name for f in decl.inputs]
    for key in kwargs:
        if key not in input_names:
            raise InthonTypeError_(
                f"Agent '{decl.name}' has no input '{key}'", span=span,
                hint=f"Declared inputs: {', '.join(input_names) or '(none)'}",
            )
    bound_inputs: dict[str, InthonValue] = {}
    for field in decl.inputs:
        if field.name in kwargs:
            value = kwargs[field.name]
            if field.type_annotation is not None:
                check_value_against_type(value, field.type_annotation, span or decl.span)
            bound_inputs[field.name] = value
        else:
            bound_inputs[field.name] = NONE

    policy = Policy.from_entries(decl.policies, span=decl.span) if decl.policies else Policy()
    ctx.policy.apply(policy, decl.span, label=decl.name)

    store = None
    mem_token = None
    try:
        store = ctx.memory_store_for("session")
        mem_token = store.begin()
    except Exception:  # pragma: no cover - defensive
        pass

    ctx.agent_stack.append(decl.name)
    prev_agent = ctx.tracer.agent
    ctx.tracer.agent = decl.name
    ctx.tracer.emit("agent_start", decl.span, agent=decl.name, goal=decl.goal or "")
    try:
        result = run_plan(decl, bound_inputs)
        ctx.tracer.emit("agent_end", decl.span, agent=decl.name,
                        result_type=result.type_name, preview=display(result)[:120])
        if store is not None and mem_token is not None:
            store.commit(mem_token)
        return result
    except PolicyViolationError:
        if store is not None and mem_token is not None:
            store.rollback(mem_token)
            ctx.tracer.emit("memory_rollback", decl.span, agent=decl.name)
        raise
    finally:
        ctx.agent_stack.pop()
        ctx.tracer.agent = prev_agent
        ctx.policy.pop(decl.span, label=decl.name)
