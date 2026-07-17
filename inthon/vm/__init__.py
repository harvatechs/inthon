"""INTHON bytecode VM package."""

from .compiler import CodeObject, compile_program
from .dis import disassemble
from .opcodes import CMP_OPS, Op
from .vm import InthonVM, VMFunction

__all__ = ["CodeObject", "compile_program", "disassemble", "Op", "CMP_OPS", "InthonVM", "VMFunction"]
