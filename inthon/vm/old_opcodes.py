"""
inthon.vm.opcodes â€” Instruction set for the INTHON stack-based virtual machine.

Design principles:
- Agent-first: tool calls, memory ops, approval gates are first-class opcodes,
  not library calls. This lets the VM enforce policy and budgets at the opcode
  level rather than burying it inside function wrappers.
- Flat: no recursive dispatch. Every opcode is a single integer looked up in a
  match statement inside InthonVM.execute().
- Compact: each instruction is (opcode: int, arg: Any). The arg is typed per
  opcode (see docstrings on each member).
"""

from __future__ import annotations
from enum import IntEnum, auto


class OpCode(IntEnum):
    # â”€â”€ Stack manipulation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    LOAD_CONST = auto()
    """Push constants[arg] onto the stack. arg = int index into CodeObject.constants."""

    LOAD_FAST = auto()
    """Push frame.locals[arg] onto the stack. arg = str variable name."""

    STORE_FAST = auto()
    """Pop TOS and store in frame.locals[arg]. arg = str variable name."""

    LOAD_GLOBAL = auto()
    """Push value from the global scope chain. arg = str variable name."""

    STORE_GLOBAL = auto()
    """Pop TOS and store in global scope. arg = str variable name."""

    POP_TOP = auto()
    """Discard the top-of-stack value. arg = None."""

    DUP_TOP = auto()
    """Duplicate TOS. arg = None."""

    ROT_TWO = auto()
    """Swap TOS and TOS1. arg = None."""

    # â”€â”€ Arithmetic & logic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    BINARY_ADD = auto()
    """Pop TOS1 and TOS, push TOS1 + TOS. arg = None."""

    BINARY_SUB = auto()
    BINARY_MUL = auto()
    BINARY_DIV = auto()
    BINARY_MOD = auto()
    BINARY_POW = auto()

    COMPARE_EQ = auto()
    """Pop TOS1 and TOS, push TOS1 == TOS as bool. arg = None."""

    COMPARE_NE = auto()
    COMPARE_LT = auto()
    COMPARE_LE = auto()
    COMPARE_GT = auto()
    COMPARE_GE = auto()

    LOGICAL_AND = auto()
    """Short-circuit AND. Pops two values, pushes bool result. arg = None."""

    LOGICAL_OR = auto()
    """Short-circuit OR. Pops two values, pushes bool result. arg = None."""

    UNARY_NOT = auto()
    """Push not TOS. arg = None."""

    UNARY_NEG = auto()
    """Push -TOS. arg = None."""

    UNARY_POS = auto()
    """Push +TOS. arg = None."""

    # â”€â”€ Collection builders â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    BUILD_LIST = auto()
    """Pop arg items from stack (bottom to top), push a list. arg = int count."""

    BUILD_DICT = auto()
    """Pop arg*2 items (key, value pairs interleaved TOS-first), push dict. arg = int pair count."""

    # â”€â”€ Attribute / index access â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    GET_ATTR = auto()
    """Pop obj from stack, push getattr(obj, arg). arg = str attribute name."""

    SET_ATTR = auto()
    """Pop value then obj; setattr(obj, arg, value). arg = str attribute name."""

    GET_ITEM = auto()
    """Pop index then obj; push obj[index]. arg = None."""

    SET_ITEM = auto()
    """Pop value, index, obj; obj[index] = value. arg = None."""

    # â”€â”€ Control flow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    JUMP_ABSOLUTE = auto()
    """Set ip = arg unconditionally. arg = int instruction index."""

    JUMP_IF_FALSE = auto()
    """If TOS is falsy, set ip = arg (TOS not popped). arg = int instruction index."""

    JUMP_IF_TRUE = auto()
    """If TOS is truthy, set ip = arg (TOS not popped). arg = int instruction index."""

    POP_JUMP_IF_FALSE = auto()
    """Pop TOS; if falsy, set ip = arg. arg = int instruction index."""

    POP_JUMP_IF_TRUE = auto()
    """Pop TOS; if truthy, set ip = arg. arg = int instruction index."""

    # â”€â”€ Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    MAKE_FUNCTION = auto()
    """
    Pop a CodeObject from stack, wrap it with current scope as closure,
    push an InthonCallable. arg = str function name.
    """

    CALL_FUNCTION = auto()
    """
    Pop nkwargs*(key+value) pairs, then nargs positional args, then callee.
    Push return value. arg = (nargs: int, nkwargs: int) tuple.
    """

    RETURN_VALUE = auto()
    """Pop TOS and set it as the return value of the current frame. arg = None."""

    # â”€â”€ Tool & Python bridge â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    CALL_TOOL = auto()
    """
    Pop nkwargs*(key+value) pairs then nargs args from stack.
    Call the registered tool at path `arg`.
    arg = (tool_path: str, nargs: int, nkwargs: int) tuple.
    """

    IMPORT_TOOL = auto()
    """Register tool_path in context and push an InthonToolRef. arg = str tool_path."""

    IMPORT_PY = auto()
    """Import a Python module through the safe bridge, push a wrapper. arg = (module_path: str, alias: str|None)."""

    CALL_PYTHON = auto()
    """
    Pop nkwargs*(key+value) pairs then nargs args then a callable PyObject.
    Call it, push result. arg = (nargs: int, nkwargs: int) tuple.
    """

    # â”€â”€ Agent-native memory primitives â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    AGENT_REMEMBER = auto()
    """
    Pop value from stack; write to memory store under namespace.
    arg = str namespace.
    """

    AGENT_FORGET = auto()
    """
    Pop key from stack; delete from memory store.
    arg = str namespace.
    """

    AGENT_RECALL = auto()
    """
    Perform a semantic / keyword search; push the best match value or None.
    arg = (query: str, namespace: str, varname: str) tuple.
    """

    # â”€â”€ Agent control & policy â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    AGENT_ENTER = auto()
    """
    Set up an agent scope: apply policy, set current_agent, push scope.
    arg = (name: str, goal: str | None) tuple.
    """

    AGENT_EXIT = auto()
    """Tear down agent scope. arg = str agent_name."""

    AGENT_APPROVE = auto()
    """
    Request human or automated approval gate before proceeding.
    arg = (target: str, action: str) tuple.
    """

    AGENT_GUARD = auto()
    """
    Pop condition from stack; raise PolicyViolationError if falsy.
    arg = None.
    """

    AGENT_EVAL = auto()
    """
    Evaluate agent output quality against rubric and criteria.
    arg = (subject: str, rubric: str, criteria: list[dict]) tuple.
    """

    APPLY_POLICY = auto()
    """
    Apply a serialized policy dict to the policy engine.
    arg = dict of policy entries.
    """

    # â”€â”€ Loop support â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    GET_ITER = auto()
    """Pop TOS, push an iterator over it. arg = None."""

    FOR_ITER = auto()
    """
    Advance the iterator on TOS. If exhausted, jump to arg and pop iter.
    Otherwise push the next value. arg = int jump target (past loop body).
    """

    # â”€â”€ Misc â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    SETUP_RETRY = auto()
    """
    Begin a retry block. arg = (count: int, backoff: str) tuple.
    The VM tracks retry state in the frame's retry stack.
    """

    END_RETRY = auto()
    """End a retry block. arg = None."""

    LOG_TRACE = auto()
    """Emit a trace event without affecting the stack. arg = str event_name."""
