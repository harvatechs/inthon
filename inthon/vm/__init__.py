"""
inthon.vm — Bytecode compiler and stack-based virtual machine for INTHON.

The VM pipeline:
  AST (from parser)
    → Compiler (inthon.vm.compiler)
    → CodeObject (inthon.vm.code_object)
    → InthonVM (inthon.vm.machine)

This backend replaces the tree-walk Interpreter for production use and provides
significantly better performance on loops and repeated function calls by eliminating
recursive AST traversal at execution time.
"""

from .opcodes import OpCode
from .code_object import CodeObject, Instruction
from .compiler import Compiler
from .frame import Frame
from .machine import InthonVM

__all__ = [
    "OpCode",
    "CodeObject",
    "Instruction",
    "Compiler",
    "Frame",
    "InthonVM",
]
