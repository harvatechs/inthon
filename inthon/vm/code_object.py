"""
inthon.vm.code_object — Compiled bytecode representation.

A CodeObject is the output of the Compiler and the input to InthonVM.
It mirrors the structure of CPython's `code` object but is pure Python
dataclasses for portability.

Key design decisions:
- Constants are pooled: identical literal values share one entry.
- Instructions reference constants by index, not by value, keeping the
  instruction stream compact and cache-friendly.
- Nested functions / agent plans produce child CodeObjects stored in the
  parent's constant pool, so the entire program is one serialisable tree.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .old_opcodes import OpCode


@dataclass
class Instruction:
    """A single bytecode instruction."""

    op: OpCode
    arg: Any = None
    # Source location for error messages (line, col from original span)
    lineno: int = 0
    colno: int = 0

    def __repr__(self) -> str:
        if self.arg is not None:
            return f"{self.op.name:<22} {self.arg!r}"
        return self.op.name


@dataclass
class CodeObject:
    """
    Compiled representation of a function, agent plan, or top-level program.

    Attributes:
        name:        Human-readable name (function name, agent name, or '<module>').
        filename:    Source file path for error messages.
        constants:   Immutable pool of literal values (int, float, str, bool,
                     None, CodeObject for nested functions/agents).
        varnames:    Ordered list of local variable names referenced by
                     LOAD_FAST / STORE_FAST. Index into this list is used as arg.
        instructions: Flat list of Instruction objects; the VM iterates these
                      sequentially, modifying ip for jumps.
    """

    name: str
    filename: str
    constants: list[Any] = field(default_factory=list)
    varnames: list[str] = field(default_factory=list)
    instructions: list[Instruction] = field(default_factory=list)
    param_names: list[str] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)

    # ── Constant pool management ────────────────────────────────────────── #

    def add_const(self, value: Any) -> int:
        """Add value to constant pool (deduplicating scalars). Returns index."""
        # Dedup for immutable scalars. CodeObjects are always unique.
        if not isinstance(value, CodeObject):
            for i, existing in enumerate(self.constants):
                if type(existing) is type(value) and existing == value:
                    return i
        self.constants.append(value)
        return len(self.constants) - 1

    # ── Variable name management ────────────────────────────────────────── #

    def add_varname(self, name: str) -> int:
        """Register a local variable name. Returns index (for LOAD/STORE_FAST)."""
        if name not in self.varnames:
            self.varnames.append(name)
        return self.varnames.index(name)

    # ── Instruction emission ────────────────────────────────────────────── #

    def emit(self, op: OpCode, arg: Any = None, lineno: int = 0, colno: int = 0) -> int:
        """Append an instruction. Returns its index (for jump-target patching)."""
        self.instructions.append(
            Instruction(op=op, arg=arg, lineno=lineno, colno=colno)
        )
        return len(self.instructions) - 1

    def patch_jump(self, instr_index: int, target: int) -> None:
        """Backpatch a previously emitted jump instruction's arg to target."""
        self.instructions[instr_index].arg = target

    def next_index(self) -> int:
        """Return the index of the NEXT instruction to be emitted."""
        return len(self.instructions)

    # ── Disassembler ────────────────────────────────────────────────────── #

    def disassemble(self) -> str:
        """Return a human-readable disassembly of this code object."""
        lines = [f"CodeObject <{self.name}> in {self.filename}"]
        lines.append(f"  constants ({len(self.constants)}): {self.constants!r}")
        lines.append(f"  varnames  ({len(self.varnames)}): {self.varnames!r}")
        lines.append("  instructions:")
        for i, instr in enumerate(self.instructions):
            lines.append(f"    {i:>4}  {instr!r}  (line {instr.lineno})")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<CodeObject '{self.name}' at {id(self):#x}>"
