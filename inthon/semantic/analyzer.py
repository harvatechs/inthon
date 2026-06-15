from __future__ import annotations
from typing import Any
from ..ast.visitor import ASTVisitor
from ..ast import nodes as N
from .scope import ScopeChain, Symbol, SymbolKind, SemanticError

class SemanticAnalyzer(ASTVisitor):
    def __init__(self) -> None:
        self._scope = ScopeChain()  # global scope
        self._imported_tools: set[str] = set()
        self._imported_py: dict[str, str] = {}  # alias -> module
        self._errors: list[SemanticError] = []
        self.warnings: list[str] = []

    def analyze(self, program: N.Program) -> None:
        for stmt in program.body:
            self.visit(stmt)
        if self._errors:
            raise self._errors[0]

    def _get_root_name(self, expr: N.Expr) -> str | None:
        if isinstance(expr, N.Identifier):
            return expr.name
        if isinstance(expr, N.MemberExpr):
            return self._get_root_name(expr.obj)
        return None

    def visit_UseToolStmt(self, node: N.UseToolStmt) -> None:
        self._imported_tools.add(node.tool_path)
        root = node.tool_path.split(".")[0]
        # Check if already defined in the current scope
        if self._scope.lookup(root) is None:
            self._scope.define(Symbol(
                name=root,
                kind=SymbolKind.TOOL,
                type_ann=None,
                source_span=node.span,
            ))

    def visit_UsePyStmt(self, node: N.UsePyStmt) -> None:
        alias = node.alias or node.module_path.split(".")[-1]
        self._imported_py[alias] = node.module_path
        try:
            self._scope.define(Symbol(
                name=alias,
                kind=SymbolKind.PY_MODULE,
                type_ann=None,
                source_span=node.span,
            ))
        except SemanticError as e:
            self._errors.append(e)

    def visit_UseMemoryStmt(self, node: N.UseMemoryStmt) -> None:
        # Define memory namespace in the scope
        try:
            self._scope.define(Symbol(
                name=node.namespace,
                kind=SymbolKind.VARIABLE,
                type_ann=None,
                source_span=node.span,
            ))
        except SemanticError as e:
            self._errors.append(e)
        self.generic_visit(node)

    def visit_LetStmt(self, node: N.LetStmt) -> None:
        self.visit(node.value)
        try:
            self._scope.define(Symbol(
                name=node.name,
                kind=SymbolKind.VARIABLE,
                type_ann=node.type_ann,
                mutable=True,
                source_span=node.span,
            ))
            if node.type_ann:
                from .type_checker import infer_type, is_subtype, _type_expr_to_str
                inferred = infer_type(node.value, self._scope)
                expected = _type_expr_to_str(node.type_ann)
                if inferred != "any" and expected != "any" and not is_subtype(inferred, expected):
                    loc = f" at line {node.span.line}" if node.span else ""
                    self.warnings.append(
                        f"Type mismatch{loc}: variable '{node.name}' declared as {expected} but assigned {inferred}"
                    )
        except SemanticError as e:
            self._errors.append(e)

    def visit_ConstStmt(self, node: N.ConstStmt) -> None:
        self.visit(node.value)
        try:
            self._scope.define(Symbol(
                name=node.name,
                kind=SymbolKind.CONSTANT,
                type_ann=node.type_ann,
                mutable=False,
                source_span=node.span,
            ))
            if node.type_ann:
                from .type_checker import infer_type, is_subtype, _type_expr_to_str
                inferred = infer_type(node.value, self._scope)
                expected = _type_expr_to_str(node.type_ann)
                if inferred != "any" and expected != "any" and not is_subtype(inferred, expected):
                    loc = f" at line {node.span.line}" if node.span else ""
                    self.warnings.append(
                        f"Type mismatch{loc}: constant '{node.name}' declared as {expected} but assigned {inferred}"
                    )
        except SemanticError as e:
            self._errors.append(e)

    def visit_AssignStmt(self, node: N.AssignStmt) -> None:
        self.visit(node.value)
        # Parse the root target name (e.g. x in x.y or x[0])
        target_root = node.target.split(".")[0].split("[")[0]
        sym = self._scope.lookup(target_root)
        if sym is None:
            self._errors.append(SemanticError(
                f"INTHON_SEM_002: Undefined name '{target_root}'",
                node.span,
            ))
        elif not sym.mutable:
            self._errors.append(SemanticError(
                f"INTHON_SEM_001: Reassignment to constant '{target_root}' is not allowed",
                node.span,
            ))
        elif sym.type_ann:
            from .type_checker import infer_type, is_subtype, _type_expr_to_str
            inferred = infer_type(node.value, self._scope)
            expected = _type_expr_to_str(sym.type_ann)
            if inferred != "any" and expected != "any" and not is_subtype(inferred, expected):
                loc = f" at line {node.span.line}" if node.span else ""
                self.warnings.append(
                    f"Type mismatch{loc}: variable '{target_root}' is type {expected} but assigned {inferred}"
                )

    def visit_Identifier(self, node: N.Identifier) -> None:
        if self._scope.lookup(node.name) is None:
            self._errors.append(SemanticError(
                f"INTHON_SEM_002: Undefined name '{node.name}'",
                node.span,
            ))

    def visit_MemberExpr(self, node: N.MemberExpr) -> None:
        root = self._get_root_name(node)
        if root and self._scope.lookup(root) is None:
            self._errors.append(SemanticError(
                f"INTHON_SEM_003: Tool or module '{root}' used but not imported",
                node.span,
            ))
        self.generic_visit(node)

    def visit_CallExpr(self, node: N.CallExpr) -> None:
        if isinstance(node.callee, N.MemberExpr):
            root = self._get_root_name(node.callee)
            if root and self._scope.lookup(root) is None:
                self._errors.append(SemanticError(
                    f"INTHON_SEM_003: Tool or module '{root}' used but not imported",
                    node.span,
                ))
        self.generic_visit(node)

    def visit_FnDecl(self, node: N.FnDecl) -> None:
        try:
            self._scope.define(Symbol(
                name=node.name,
                kind=SymbolKind.FUNCTION,
                type_ann=node.return_type,
                mutable=False,
                source_span=node.span,
            ))
        except SemanticError as e:
            self._errors.append(e)

        outer_scope = self._scope
        self._scope = outer_scope.child()
        
        for p in node.params:
            try:
                self._scope.define(Symbol(
                    name=p.name,
                    kind=SymbolKind.PARAM,
                    type_ann=p.type_ann,
                    mutable=True,
                    source_span=p.span,
                ))
            except SemanticError as e:
                self._errors.append(e)
            if p.default:
                self.visit(p.default)

        for stmt in node.body:
            self.visit(stmt)

        self._scope = outer_scope

    def visit_AgentDecl(self, node: N.AgentDecl) -> None:
        try:
            self._scope.define(Symbol(
                name=node.name,
                kind=SymbolKind.AGENT,
                type_ann=None,
                mutable=False,
                source_span=node.span,
            ))
        except SemanticError as e:
            self._errors.append(e)

        outer_scope = self._scope
        self._scope = outer_scope.child()
        self._scope.define(Symbol("self", SymbolKind.AGENT, None))

        for imp in node.imports:
            self.visit(imp)

        if node.policy:
            self.visit(node.policy)

        self.visit(node.plan)

        self._scope = outer_scope

    def visit_ForStmt(self, node: N.ForStmt) -> None:
        self.visit(node.iterable)
        outer_scope = self._scope
        self._scope = outer_scope.child()
        
        self._scope.define(Symbol(
            name=node.var,
            kind=SymbolKind.VARIABLE,
            type_ann=None,
            mutable=True,
            source_span=node.span,
        ))
        
        for stmt in node.body:
            self.visit(stmt)
            
        self._scope = outer_scope

    def visit_RecallStmt(self, node: N.RecallStmt) -> None:
        try:
            self._scope.define(Symbol(
                name=node.var,
                kind=SymbolKind.VARIABLE,
                type_ann=None,
                mutable=True,
                source_span=node.span,
            ))
        except SemanticError as e:
            self._errors.append(e)

    def visit_RetryStmt(self, node: N.RetryStmt) -> None:
        for stmt in node.body:
            self.visit(stmt)
        if node.catch_block:
            outer_scope = self._scope
            self._scope = outer_scope.child()
            self._scope.define(Symbol(
                name=node.catch_block.var,
                kind=SymbolKind.VARIABLE,
                type_ann=None,
                mutable=True,
                source_span=node.catch_block.span,
            ))
            for stmt in node.catch_block.body:
                self.visit(stmt)
            self._scope = outer_scope
