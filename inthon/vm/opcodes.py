"""InthonVM opcode table (spec Appendix B).

Opcodes 0..50 are the canonical set from the language spec.  51+ are v1.0
extensions (short-circuit jumps, string building, imports, declarations)
that the draft reserved for later milestones.
"""

from __future__ import annotations

from enum import IntEnum


class Op(IntEnum):
    # Stack & variables (0-10)
    LOAD_CONST = 0
    LOAD_NAME = 1
    LOAD_FAST = 2            # reserved (locals are name-based in v1.0)
    LOAD_GLOBAL = 3          # reserved
    LOAD_ATTR = 4
    STORE_NAME = 5
    STORE_FAST = 6           # reserved
    STORE_ATTR = 7
    STORE_SUBSCR = 8
    POP_TOP = 9
    DUP_TOP = 10

    # Arithmetic & comparison (11-20)
    BINARY_ADD = 11
    BINARY_SUB = 12
    BINARY_MUL = 13
    BINARY_DIV = 14
    BINARY_MOD = 15
    BINARY_POW = 16
    UNARY_NEG = 17
    UNARY_NOT = 18
    COMPARE_OP = 19
    BINARY_SUBSCR = 20

    # Control flow (21-27)
    POP_JUMP_IF_FALSE = 21
    POP_JUMP_IF_TRUE = 22
    JUMP_FORWARD = 23
    JUMP_ABSOLUTE = 24
    GET_ITER = 25
    FOR_ITER = 26
    RETURN_VALUE = 27

    # Calls & containers (28-35)
    CALL_FUNCTION = 28
    CALL_FUNCTION_KW = 29
    CALL_METHOD = 30         # reserved (methods dispatch via CALL_FUNCTION)
    MAKE_FUNCTION = 31
    BUILD_LIST = 32
    BUILD_TUPLE = 33
    BUILD_DICT = 34
    BUILD_SLICE = 35         # reserved

    # Agent & policy (36-46)
    CALL_TOOL = 36
    APPLY_POLICY = 37
    POP_POLICY = 38
    APPROVE_GATE = 39
    AGENT_REMEMBER = 40
    AGENT_RECALL = 41
    AGENT_FORGET = 42
    GUARD_ASSERT = 43
    RETRY_BEGIN = 44
    RETRY_BACKOFF = 45       # used by the retry handler
    RETRY_END = 46

    # Python interop & introspection (47-50)
    IMPORT_PY = 47
    SELF_EVAL = 48
    INTROSPECT_TRACE = 49
    REWRITE_PLAN = 50

    # v1.0 extensions (51+)
    JUMP_IF_TRUE_OR_POP = 51
    JUMP_IF_FALSE_OR_POP = 52
    BUILD_STRING = 53        # string interpolation
    IMPORT_TOOL = 54
    USE_MEMORY = 55
    DECLARE_NAME = 56        # let (mutable)
    DECLARE_CONST = 57       # const / fn / agent / import bindings
    MAKE_AGENT = 58
    EVAL_RUBRIC = 59
    CHECK_TYPE = 60
    TICK = 61                # loop back-edge budget check
    LOAD_META = 62           # load raw (non-literal) compile-time metadata


CMP_OPS = ["==", "!=", "<", "<=", ">", ">="]

OPCODE_NAMES = {int(op): op.name for op in Op}

OpCode = Op

