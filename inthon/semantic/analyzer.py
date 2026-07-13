from typing import Any
from ..lexer.tokens import Span
from ..ast.visitor import ASTVisitor
from ..ast import nodes as N
from .scope import ScopeChain, Symbol, SymbolKind, SemanticError
from ..runtime.builtins import SAFE_BUILTIN_NAMES


class SemanticAnalyzer(ASTVisitor):
    def __init__(self) -> None:
        self._scope = ScopeChain()  # global scope
        for name in SAFE_BUILTIN_NAMES:
            self._scope.define(
                Symbol(name=name, kind=SymbolKind.FUNCTION, mutable=False)
            )
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

    def _check_shadow(self, name: str, span: Any) -> None:
        if self._scope._parent is not None:
            existing = self._scope._parent.lookup(name)
            if existing is not None:
                loc = f" at line {span.line}" if span else ""
                self.warnings.append(
                    f"Warning: shadow name '{name}'{loc} shadows a definition from an outer scope"
                )

    def visit_UseToolStmt(self, node: N.UseToolStmt) -> None:
        self._imported_tools.add(node.tool_path)
        root = node.tool_path.split(".")[0]
        self._check_shadow(root, node.span)
        # Check if already defined in the current scope
        if self._scope.lookup(root) is None:
            self._scope.define(
                Symbol(
                    name=root,
                    kind=SymbolKind.TOOL,
                    type_ann=None,
                    source_span=node.span,
                )
            )

    def visit_UsePyStmt(self, node: N.UsePyStmt) -> None:
        alias = node.alias or node.module_path.split(".")[-1]
        self._imported_py[alias] = node.module_path
        self._check_shadow(alias, node.span)
        try:
            self._scope.define(
                Symbol(
                    name=alias,
                    kind=SymbolKind.PY_MODULE,
                    type_ann=None,
                    source_span=node.span,
                )
            )
        except SemanticError as e:
            self._errors.append(e)

    def visit_UseMemoryStmt(self, node: N.UseMemoryStmt) -> None:
        self._check_shadow(node.namespace, node.span)
        # Define memory namespace in the scope
        try:
            self._scope.define(
                Symbol(
                    name=node.namespace,
                    kind=SymbolKind.VARIABLE,
                    type_ann=None,
                    source_span=node.span,
                )
            )
        except SemanticError as e:
            self._errors.append(e)
        self.generic_visit(node)

    def visit_LetStmt(self, node: N.LetStmt) -> None:
        self.visit(node.value)
        try:
            from .type_checker import infer_type, is_subtype, _type_expr_to_str

            type_ann = node.type_ann
            if type_ann is None:
                type_ann = infer_type(node.value, self._scope)

            self._check_shadow(node.name, node.span)
            self._scope.define(
                Symbol(
                    name=node.name,
                    kind=SymbolKind.VARIABLE,
                    type_ann=type_ann,
                    mutable=True,
                    source_span=node.span,
                )
            )
            if node.type_ann:
                inferred = infer_type(node.value, self._scope)
                expected = _type_expr_to_str(node.type_ann)
                if (
                    inferred != "any"
                    and expected != "any"
                    and not is_subtype(inferred, expected)
                ):
                    self._errors.append(
                        SemanticError(
                            f"INTHON_SEM_004: Type mismatch: variable '{node.name}' declared as {expected} but assigned {inferred}",
                            node.span,
                        )
                    )
        except SemanticError as e:
            self._errors.append(e)

    def visit_ConstStmt(self, node: N.ConstStmt) -> None:
        self.visit(node.value)
        try:
            from .type_checker import infer_type, is_subtype, _type_expr_to_str

            type_ann = node.type_ann
            if type_ann is None:
                type_ann = infer_type(node.value, self._scope)

            self._check_shadow(node.name, node.span)
            self._scope.define(
                Symbol(
                    name=node.name,
                    kind=SymbolKind.CONSTANT,
                    type_ann=type_ann,
                    mutable=False,
                    source_span=node.span,
                )
            )
            if node.type_ann:
                inferred = infer_type(node.value, self._scope)
                expected = _type_expr_to_str(node.type_ann)
                if (
                    inferred != "any"
                    and expected != "any"
                    and not is_subtype(inferred, expected)
                ):
                    self._errors.append(
                        SemanticError(
                            f"INTHON_SEM_004: Type mismatch: constant '{node.name}' declared as {expected} but assigned {inferred}",
                            node.span,
                        )
                    )
        except SemanticError as e:
            self._errors.append(e)

    def visit_AssignStmt(self, node: N.AssignStmt) -> None:
        self.visit(node.value)
        # Parse the root target name (e.g. x in x.y or x[0])
        target_root = node.target.split(".")[0].split("[")[0]
        sym = self._scope.lookup(target_root)
        if sym is None:
            self._errors.append(
                SemanticError(
                    f"INTHON_SEM_002: Undefined name '{target_root}'",
                    node.span,
                )
            )
        elif not sym.mutable:
            self._errors.append(
                SemanticError(
                    f"INTHON_SEM_001: Reassignment to constant '{target_root}' is not allowed",
                    node.span,
                )
            )
        elif sym.type_ann:
            from .type_checker import infer_type, is_subtype, _type_expr_to_str

            inferred = infer_type(node.value, self._scope)
            expected = _type_expr_to_str(sym.type_ann)
            if (
                inferred != "any"
                and expected != "any"
                and not is_subtype(inferred, expected)
            ):
                self._errors.append(
                    SemanticError(
                        f"INTHON_SEM_004: Type mismatch: variable '{target_root}' is type {expected} but assigned {inferred}",
                        node.span,
                    )
                )

    def visit_Identifier(self, node: N.Identifier) -> None:
        if self._scope.lookup(node.name) is None:
            self._errors.append(
                SemanticError(
                    f"INTHON_SEM_002: Undefined name '{node.name}'",
                    node.span,
                )
            )

    def visit_MemberExpr(self, node: N.MemberExpr) -> None:
        root = self._get_root_name(node)
        if root and self._scope.lookup(root) is None:
            self._errors.append(
                SemanticError(
                    f"INTHON_SEM_003: Tool or module '{root}' used but not imported",
                    node.span,
                )
            )
        self.generic_visit(node)

    def _validate_call_arguments(
        self,
        func_name: str,
        params: tuple[N.Param, ...],
        args: tuple[N.Expr, ...],
        kwargs: tuple[tuple[str, N.Expr], ...],
        span: Span | None,
    ) -> None:
        from .type_checker import infer_type, is_subtype, _type_expr_to_str

        param_names = [p.name for p in params]
        mapped_args: dict[str, N.Expr] = {}

        if len(args) > len(params):
            raise SemanticError(
                f"INTHON_SEM_005: Too many positional arguments for function '{func_name}' "
                f"(expected at most {len(params)}, got {len(args)})",
                span,
            )
        for i, arg_expr in enumerate(args):
            mapped_args[param_names[i]] = arg_expr

        for k, v in kwargs:
            if k not in param_names:
                raise SemanticError(
                    f"INTHON_SEM_005: Unexpected keyword argument '{k}' for function '{func_name}'",
                    span,
                )
            if k in mapped_args:
                raise SemanticError(
                    f"INTHON_SEM_005: Multiple values for argument '{k}' in function '{func_name}'",
                    span,
                )
            mapped_args[k] = v

        for p in params:
            if p.name not in mapped_args:
                if p.default is None:
                    raise SemanticError(
                        f"INTHON_SEM_005: Missing required argument '{p.name}' for function '{func_name}'",
                        span,
                    )
            else:
                arg_expr = mapped_args[p.name]
                if p.type_ann:
                    inferred = infer_type(arg_expr, self._scope)
                    expected = _type_expr_to_str(p.type_ann)
                    if (
                        inferred != "any"
                        and expected != "any"
                        and not is_subtype(inferred, expected)
                    ):
                        raise SemanticError(
                            f"INTHON_SEM_004: Type mismatch: argument '{p.name}' of function '{func_name}' "
                            f"expected {expected}, got {inferred}",
                            span,
                        )

    def _validate_agent_arguments(
        self,
        agent_name: str,
        inputs: tuple[N.TypedField, ...],
        args: tuple[N.Expr, ...],
        kwargs: tuple[tuple[str, N.Expr], ...],
        span: Span | None,
    ) -> None:
        from .type_checker import infer_type, is_subtype, _type_expr_to_str

        input_names = [inp.name for inp in inputs]
        mapped_args: dict[str, N.Expr] = {}

        if args:
            raise SemanticError(
                f"INTHON_SEM_005: Positional arguments are not supported when invoking agent '{agent_name}'. "
                f"Use keyword arguments.",
                span,
            )

        for k, v in kwargs:
            if k not in input_names:
                raise SemanticError(
                    f"INTHON_SEM_005: Unexpected argument '{k}' for agent '{agent_name}'",
                    span,
                )
            if k in mapped_args:
                raise SemanticError(
                    f"INTHON_SEM_005: Multiple values for argument '{k}' in agent '{agent_name}'",
                    span,
                )
            mapped_args[k] = v

        for inp in inputs:
            if inp.name not in mapped_args:
                raise SemanticError(
                    f"INTHON_SEM_005: Missing required argument '{inp.name}' for agent '{agent_name}'",
                    span,
                )
            arg_expr = mapped_args[inp.name]
            inferred = infer_type(arg_expr, self._scope)
            expected = _type_expr_to_str(inp.type_ann)
            if (
                inferred != "any"
                and expected != "any"
                and not is_subtype(inferred, expected)
            ):
                raise SemanticError(
                    f"INTHON_SEM_004: Type mismatch: argument '{inp.name}' of agent '{agent_name}' "
                    f"expected {expected}, got {inferred}",
                    span,
                )

    def visit_CallExpr(self, node: N.CallExpr) -> None:
        if isinstance(node.callee, N.MemberExpr):
            root = self._get_root_name(node.callee)
            if root and self._scope.lookup(root) is None:
                self._errors.append(
                    SemanticError(
                        f"INTHON_SEM_003: Tool or module '{root}' used but not imported",
                        node.span,
                    )
                )
        elif isinstance(node.callee, N.Identifier):
            sym = self._scope.lookup(node.callee.name)
            if sym is not None:
                if sym.kind == SymbolKind.FUNCTION:
                    if hasattr(sym, "params"):
                        params = getattr(sym, "params", ())
                        try:
                            self._validate_call_arguments(
                                sym.name, params, node.args, node.kwargs, node.span
                            )
                        except SemanticError as e:
                            self._errors.append(e)
                elif sym.kind == SymbolKind.AGENT:
                    inputs = getattr(sym, "inputs", ())
                    try:
                        self._validate_agent_arguments(
                            sym.name, inputs, node.args, node.kwargs, node.span
                        )
                    except SemanticError as e:
                        self._errors.append(e)
        self.generic_visit(node)

    def visit_FnDecl(self, node: N.FnDecl) -> None:
        self._check_shadow(node.name, node.span)
        try:
            sym = Symbol(
                name=node.name,
                kind=SymbolKind.FUNCTION,
                type_ann=node.return_type,
                mutable=False,
                source_span=node.span,
            )
            sym.params = node.params
            self._scope.define(sym)
        except SemanticError as e:
            self._errors.append(e)

        outer_scope = self._scope
        self._scope = outer_scope.child()

        old_return_type = getattr(self, "_current_return_type", None)
        self._current_return_type = node.return_type

        for p in node.params:
            self._check_shadow(p.name, p.span)
            try:
                self._scope.define(
                    Symbol(
                        name=p.name,
                        kind=SymbolKind.PARAM,
                        type_ann=p.type_ann,
                        mutable=True,
                        source_span=p.span,
                    )
                )
            except SemanticError as e:
                self._errors.append(e)
            if p.default:
                self.visit(p.default)

        for stmt in node.body:
            self.visit(stmt)

        self._scope = outer_scope
        self._current_return_type = old_return_type

    def visit_AgentDecl(self, node: N.AgentDecl) -> None:
        self._check_shadow(node.name, node.span)
        try:
            sym = Symbol(
                name=node.name,
                kind=SymbolKind.AGENT,
                type_ann=None,
                mutable=False,
                source_span=node.span,
            )
            sym.inputs = node.inputs
            sym.outputs = node.outputs
            self._scope.define(sym)
        except SemanticError as e:
            self._errors.append(e)

        outer_scope = self._scope
        self._scope = outer_scope.child()
        self._scope.define(Symbol("self", SymbolKind.AGENT, None))

        old_agent_outputs = getattr(self, "_current_agent_outputs", None)
        self._current_agent_outputs = node.outputs

        for imp in node.imports:
            self.visit(imp)

        if node.policy:
            self.visit(node.policy)

        self.visit(node.plan)

        self._scope = outer_scope
        self._current_agent_outputs = old_agent_outputs

    def visit_ForStmt(self, node: N.ForStmt) -> None:
        self.visit(node.iterable)
        outer_scope = self._scope
        self._scope = outer_scope.child()

        self._check_shadow(node.var, node.span)
        self._scope.define(
            Symbol(
                name=node.var,
                kind=SymbolKind.VARIABLE,
                type_ann=None,
                mutable=True,
                source_span=node.span,
            )
        )

        for stmt in node.body:
            self.visit(stmt)

        self._scope = outer_scope

    def visit_RecallStmt(self, node: N.RecallStmt) -> None:
        self._check_shadow(node.var, node.span)
        try:
            self._scope.define(
                Symbol(
                    name=node.var,
                    kind=SymbolKind.VARIABLE,
                    type_ann=None,
                    mutable=True,
                    source_span=node.span,
                )
            )
        except SemanticError as e:
            self._errors.append(e)

    def visit_RetryStmt(self, node: N.RetryStmt) -> None:
        for stmt in node.body:
            self.visit(stmt)
        if node.catch_block:
            outer_scope = self._scope
            self._scope = outer_scope.child()
            self._check_shadow(node.catch_block.var, node.catch_block.span)
            self._scope.define(
                Symbol(
                    name=node.catch_block.var,
                    kind=SymbolKind.VARIABLE,
                    type_ann=None,
                    mutable=True,
                    source_span=node.catch_block.span,
                )
            )
            for stmt in node.catch_block.body:
                self.visit(stmt)
            self._scope = outer_scope

    def visit_ReturnStmt(self, node: N.ReturnStmt) -> None:
        expected_ret = getattr(self, "_current_return_type", None)
        if expected_ret is not None:
            from .type_checker import infer_type, is_subtype, _type_expr_to_str

            inferred = (
                "none" if node.value is None else infer_type(node.value, self._scope)
            )
            expected = _type_expr_to_str(expected_ret)
            if (
                inferred != "any"
                and expected != "any"
                and not is_subtype(inferred, expected)
            ):
                self._errors.append(
                    SemanticError(
                        f"INTHON_SEM_004: Type mismatch: function return type must be {expected}, got {inferred}",
                        node.span,
                    )
                )

        expected_outputs = getattr(self, "_current_agent_outputs", None)
        if expected_outputs is not None:
            from .type_checker import infer_type, is_subtype, _type_expr_to_str

            if len(expected_outputs) == 1:
                expected_type = expected_outputs[0].type_ann
                inferred = (
                    "none"
                    if node.value is None
                    else infer_type(node.value, self._scope)
                )
                expected = _type_expr_to_str(expected_type)
                if (
                    inferred != "any"
                    and expected != "any"
                    and not is_subtype(inferred, expected)
                ):
                    self._errors.append(
                        SemanticError(
                            f"INTHON_SEM_004: Type mismatch: agent output type must be {expected}, got {inferred}",
                            node.span,
                        )
                    )
        if node.value:
            self.visit(node.value)
