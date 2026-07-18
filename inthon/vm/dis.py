"""InthonVM disassembler (spec VM-19: `inthon dis`)."""

from __future__ import annotations

from .compiler import CodeObject
from .opcodes import CMP_OPS, OPCODE_NAMES, Op

_OPERAND_HINTS = {
    Op.LOAD_CONST: "literals",
    Op.LOAD_META: "meta",
    Op.LOAD_NAME: "names",
    Op.STORE_NAME: "names",
    Op.DECLARE_NAME: "names",
    Op.DECLARE_CONST: "names",
    Op.LOAD_ATTR: "names",
    Op.STORE_ATTR: "names",
    Op.MAKE_FUNCTION: "names",
    Op.MAKE_AGENT: "names",
    Op.FOR_ITER: "names",
}


def disassemble(code: CodeObject, _indent: int = 0) -> str:
    pad = " " * _indent
    lines = [f"{pad}== {code.name} (stacksize={code.stacksize}) =="]
    for addr, instr in enumerate(code.instructions):
        name = OPCODE_NAMES.get(instr.op, f"<{instr.op}>")
        operand = _operand_text(code, instr)
        loc = f"{instr.line}:{instr.col}" if instr.line else ""
        lines.append(f"{pad}{addr:4d}  {name:<22} {operand:<28} {loc}")
    for meta in code.meta:
        if isinstance(meta, dict):
            for key in ("body", "plan"):
                sub = meta.get(key)
                if isinstance(sub, CodeObject):
                    lines.append("")
                    lines.append(disassemble(sub, _indent + 2))
            for sub in meta.get("defaults", {}).values():
                if isinstance(sub, CodeObject):
                    lines.append("")
                    lines.append(disassemble(sub, _indent + 2))
    return "\n".join(lines)


def _operand_text(code: CodeObject, instr) -> str:
    try:
        op = Op(instr.op)
    except ValueError:  # pragma: no cover
        return str(instr.arg)
    arg = instr.arg
    if op == Op.COMPARE_OP:
        return CMP_OPS[arg] if 0 <= arg < len(CMP_OPS) else str(arg)
    hint = _OPERAND_HINTS.get(op)
    if hint == "literals" and 0 <= arg < len(code.literals):
        return repr(code.literals[arg].to_python())[:40]
    if hint == "names" and 0 <= arg < len(code.names):
        return code.names[arg]
    if op in (
        Op.POP_JUMP_IF_FALSE,
        Op.POP_JUMP_IF_TRUE,
        Op.JUMP_FORWARD,
        Op.JUMP_ABSOLUTE,
        Op.JUMP_IF_TRUE_OR_POP,
        Op.JUMP_IF_FALSE_OR_POP,
        Op.FOR_ITER,
    ):
        return f"-> {arg}"
    if op in (Op.CALL_FUNCTION, Op.CALL_FUNCTION_KW, Op.CALL_TOOL):
        n_pos = arg & 0xFF
        n_kw = (arg >> 8) & 0xFF
        return f"pos={n_pos} kw={n_kw}" if n_kw else f"argc={n_pos}"
    if hint == "meta" and 0 <= arg < len(code.meta):
        return _meta_preview(code.meta[arg])
    if op in (Op.BUILD_LIST, Op.BUILD_DICT, Op.BUILD_STRING):
        return f"n={arg}"
    return str(arg) if arg else ""


def _meta_preview(meta) -> str:
    if isinstance(meta, str):
        return repr(meta)[:40]
    if isinstance(meta, tuple):
        return "(" + ", ".join(str(m)[:14] for m in meta) + ")"
    if isinstance(meta, dict):
        return "{" + ", ".join(list(meta.keys())[:4]) + "}"
    return type(meta).__name__
