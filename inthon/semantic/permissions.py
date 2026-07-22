from __future__ import annotations
from ..ast.visitor import ASTVisitor
from ..ast import nodes as N


class PermissionAnalyzer(ASTVisitor):
    """
    Static permission analyzer that walks the AST to find all
    imported tools and python modules, verifying if the capability
    set covers them.
    """

    def __init__(self) -> None:
        self.used_tools: set[str] = set()
        self.used_py_modules: set[str] = set()

    def analyze(self, program: N.Program) -> None:
        self.visit(program)

    def visit_UseTool(self, node: N.UseTool) -> None:
        self.used_tools.add(node.path)

    def visit_UsePy(self, node: N.UsePy) -> None:
        self.used_py_modules.add(node.module)

