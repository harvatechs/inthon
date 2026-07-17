"""
inthon.vm.compiler â€” AST â†’ Bytecode compiler for INTHON.

The Compiler walks the frozen AST nodes produced by the parser and emits
Instruction objects into a CodeObject. It uses the same ASTVisitor pattern as
the tree-walk Interpreter so both backends stay structurally symmetric.

Key responsibilities:
1. Scope tracking: module-level vs function-level vs agent-level.
2. Constant pooling: identical literals share one pool entry.
3. Forward-jump patching: `if` / `while` / `for` emit placeholder jumps that
   are backpatched once the target index is known.
4. Agent-primitive compilation: agent/goal/plan/policy blocks are lowered to
   the agent-native opcodes (AGENT_ENTER, APPLY_POLICY, AGENT_REMEMBER â€¦).
"""

from __future__ import annotations
from typing import Any
from .old_visitor import ASTVisitor
from . import old_nodes as N
from .old_opcodes import OpCode
from .code_object import CodeObject


class CompilerError(Exception):
    pass


class _Scope:
    """Tracks whether we are at module, function, or agent scope."""

    MODULE = "module"
    FUNCTION = "function"
    AGENT = "agent"


class Compiler(ASTVisitor):
    """
    Compiles an INTHON AST into a top-level CodeObject.

    Usage::

        compiler = Compiler(filename="example.inth")
        code = compiler.compile(program_ast)
    """

    def __init__(self, filename: str = "<stdin>") -> None:
        self._filename = filename
        # Stack of CodeObjects being built. The current one is always last.
        self._code_stack: list[CodeObject] = []
        self._scope_stack: list[str] = [_Scope.MODULE]

    # â”€â”€ Public entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    def compile(self, program: N.Program) -> CodeObject:
        """Compile a parsed Program node into a top-level CodeObject."""
        top = CodeObject(name="<module>", filename=self._filename)
        self._code_stack.append(top)

        returned = self._compile_statement_sequence(program.body, implicit_return=True)

        if not returned:
            self._emit(OpCode.LOAD_CONST, self._co.add_const(None))
            self._emit(OpCode.RETURN_VALUE)

        return self._code_stack.pop()

    # â”€â”€ Internal helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    @property
    def _co(self) -> CodeObject:
        """Current CodeObject being compiled."""
        return self._code_stack[-1]

    def _emit(self, op: OpCode, arg: Any = None, span: Any = None) -> int:
        lineno = span.line if span else 0
        colno = span.col if span else 0
        return self._co.emit(op, arg, lineno=lineno, colno=colno)

    def _emit_load(self, name: str, span: Any = None) -> None:
        """Emit LOAD_FAST or LOAD_GLOBAL depending on current scope."""
        if (
            self._co.has_var_in_locals(name)
            if hasattr(self._co, "has_var_in_locals")
            else (name in self._co.varnames)
        ):
            self._emit(OpCode.LOAD_FAST, name, span)
        else:
            self._emit(OpCode.LOAD_GLOBAL, name, span)

    def _emit_store(self, name: str, span: Any = None) -> None:
        """Emit STORE_FAST or STORE_GLOBAL depending on scope."""
        if self._scope_stack[-1] in (_Scope.FUNCTION, _Scope.AGENT):
            self._co.add_varname(name)
            self._emit(OpCode.STORE_FAST, name, span)
        else:
            self._emit(OpCode.STORE_GLOBAL, name, span)

    def _push_code(self, name: str) -> CodeObject:
        child = CodeObject(name=name, filename=self._filename)
        self._code_stack.append(child)
        return child

    def _pop_code(self) -> CodeObject:
        return self._code_stack.pop()

    def _compile_statement_sequence(
        self, statements: tuple[N.Statement, ...], implicit_return: bool = False
    ) -> bool:
        """Compile a statement sequence.

        Returns True when the sequence emits a guaranteed final RETURN_VALUE.
        """
        for index, stmt in enumerate(statements):
            is_last = index == len(statements) - 1
            if implicit_return and is_last and isinstance(stmt, N.ExprStmt):
                self.visit(stmt.expr)
                self._emit(OpCode.RETURN_VALUE, span=stmt.span)
                return True

            self.visit(stmt)
            if is_last and isinstance(stmt, N.ReturnStmt):
                return True

        return False

    # â”€â”€ Statement visitors â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    def visit_LetStmt(self, node: N.LetStmt) -> None:
        self.visit(node.value)
        self._emit_store(node.name, node.span)

    def visit_ConstStmt(self, node: N.ConstStmt) -> None:
        self.visit(node.value)
        self._emit_store(node.name, node.span)

    def visit_AssignStmt(self, node: N.AssignStmt) -> None:
        self.visit(node.value)
        # Parse compound assignment targets (a.b, a[i])
        target = node.target
        if "." in target or "[" in target:
            # Split at first separator to handle obj.attr or obj[key]
            self._compile_complex_store(target, node.span)
        else:
            self._emit_store(target, node.span)

    def _compile_complex_store(self, target: str, span: Any) -> None:
        """Compile assignment to a member or subscript target."""
        # Determine if this is attr or index assignment
        dot_pos = target.find(".")
        bracket_pos = target.find("[")

        if dot_pos > 0 and (bracket_pos < 0 or dot_pos < bracket_pos):
            obj_name = target[:dot_pos]
            attr = target[dot_pos + 1 :]
            # Stack: [value] â†’ we need [obj, value]
            # ROT_TWO to get: push obj under value
            # Actually: value is TOS; load obj, then rot, then SET_ATTR
            # We need: LOAD obj, ROT_TWO (so obj is TOS1, value is TOS), SET_ATTR
            self._emit(OpCode.LOAD_GLOBAL, obj_name, span)
            self._emit(OpCode.ROT_TWO)
            self._emit(OpCode.SET_ATTR, attr, span)
        elif bracket_pos > 0:
            obj_name = target[:bracket_pos]
            key_str = target[bracket_pos + 1 : target.rfind("]")]
            # value is TOS; load obj, push idx, rotate, SET_ITEM
            self._emit(OpCode.LOAD_GLOBAL, obj_name, span)
            # Compile the key expression (literal or variable)
            if key_str.isdigit():
                self._emit(OpCode.LOAD_CONST, self._co.add_const(int(key_str)), span)
            elif key_str.startswith(("'", '"')):
                self._emit(OpCode.LOAD_CONST, self._co.add_const(key_str[1:-1]), span)
            else:
                self._emit(OpCode.LOAD_GLOBAL, key_str, span)
            # Stack is now: [value, obj, key] â€” ROT_THREE to get [obj, key, value]
            self._emit(OpCode.SET_ITEM)
        else:
            self._emit_store(target, span)

    def visit_ReturnStmt(self, node: N.ReturnStmt) -> None:
        if node.value:
            self.visit(node.value)
        else:
            self._emit(OpCode.LOAD_CONST, self._co.add_const(None))
        self._emit(OpCode.RETURN_VALUE, span=node.span)

    def visit_ExprStmt(self, node: N.ExprStmt) -> None:
        self.visit(node.expr)
        self._emit(OpCode.POP_TOP)

    # â”€â”€ Control flow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    def visit_IfStmt(self, node: N.IfStmt) -> None:
        # Compile condition
        self.visit(node.condition)
        # Emit conditional jump (placeholder target)
        jump_if_false = self._emit(OpCode.POP_JUMP_IF_FALSE, 0, node.span)

        # Then branch
        for stmt in node.then_branch:
            self.visit(stmt)

        if node.else_branch:
            # Jump over else
            jump_over_else = self._emit(OpCode.JUMP_ABSOLUTE, 0)
            # Patch the conditional jump to here (start of else)
            self._co.patch_jump(jump_if_false, self._co.next_index())
            # Else branch
            for stmt in node.else_branch:
                self.visit(stmt)
            # Patch the jump-over-else to after the else block
            self._co.patch_jump(jump_over_else, self._co.next_index())
        else:
            # Patch conditional jump to after then block
            self._co.patch_jump(jump_if_false, self._co.next_index())

    def visit_WhileStmt(self, node: N.WhileStmt) -> None:
        loop_start = self._co.next_index()
        # Condition
        self.visit(node.condition)
        jump_out = self._emit(OpCode.POP_JUMP_IF_FALSE, 0, node.span)
        # Body
        for stmt in node.body:
            self.visit(stmt)
        # Loop back
        self._emit(OpCode.JUMP_ABSOLUTE, loop_start)
        # Patch exit jump
        self._co.patch_jump(jump_out, self._co.next_index())

    def visit_ForStmt(self, node: N.ForStmt) -> None:
        # Push the iterable and convert to iterator
        self.visit(node.iterable)
        self._emit(OpCode.GET_ITER)
        loop_start = self._co.next_index()
        # FOR_ITER: advance iterator; jump to end when exhausted
        for_iter_idx = self._emit(OpCode.FOR_ITER, 0, node.span)
        # Loop variable is TOS after a successful FOR_ITER
        self._emit_store(node.var, node.span)
        # Body
        for stmt in node.body:
            self.visit(stmt)
        # Jump back to the FOR_ITER
        self._emit(OpCode.JUMP_ABSOLUTE, loop_start)
        # Patch FOR_ITER target to instruction after the loop
        self._co.patch_jump(for_iter_idx, self._co.next_index())

    # â”€â”€ Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    def visit_FnDecl(self, node: N.FnDecl) -> None:
        # Build child CodeObject for the function body
        self._scope_stack.append(_Scope.FUNCTION)
        child_co = self._push_code(node.name)

        # Register params as locals and set up default handling
        for param in node.params:
            child_co.add_varname(param.name)

        returned = self._compile_statement_sequence(node.body, implicit_return=True)

        if not returned:
            self._emit(OpCode.LOAD_CONST, child_co.add_const(None))
            self._emit(OpCode.RETURN_VALUE)

        finished_child = self._pop_code()
        self._scope_stack.pop()

        # Compile default expressions in the parent scope and stash them
        # in the CodeObject's constant pool as a dict
        default_dict: dict[str, Any] = {}
        # Build defaults by compiling each default expression separately
        # and evaluating it at compile time if it's a literal
        for param in node.params:
            if param.default is not None:
                lit = self._extract_literal(param.default)
                if lit is not None:
                    default_dict[param.name] = lit

        # Stash defaults and param names in the CodeObject
        finished_child.param_names = [p.name for p in node.params]
        finished_child.defaults = default_dict

        # In parent: push CodeObject constant, then MAKE_FUNCTION
        idx = self._co.add_const(finished_child)
        self._emit(OpCode.LOAD_CONST, idx, node.span)
        self._emit(OpCode.MAKE_FUNCTION, node.name, node.span)
        self._emit_store(node.name, node.span)

    def _extract_literal(self, expr: N.Expr) -> Any:
        """Try to evaluate a literal expression at compile time. Returns None if non-literal."""
        if isinstance(expr, N.IntLiteral):
            return expr.value
        if isinstance(expr, N.FloatLiteral):
            return expr.value
        if isinstance(expr, N.StringLiteral):
            return expr.value
        if isinstance(expr, N.BoolLiteral):
            return expr.value
        if isinstance(expr, N.NoneLiteral):
            return None
        return object()  # sentinel: non-literal (can't be used as default)

    # â”€â”€ Agent declarations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    def visit_AgentDecl(self, node: N.AgentDecl) -> None:
        self._scope_stack.append(_Scope.AGENT)

        # Serialize policy entries for APPLY_POLICY opcode
        policy_dict: dict[str, Any] = {}
        if node.policy:
            for entry in node.policy.entries:
                policy_dict[entry.key] = entry.value

        # AGENT_ENTER: set up agent scope, apply policy
        self._emit(OpCode.AGENT_ENTER, (node.name, node.goal), node.span)
        if policy_dict:
            self._emit(OpCode.APPLY_POLICY, policy_dict, node.span)

        # Compile imports inside agent scope
        for imp in node.imports:
            self.visit(imp)

        # Compile plan body
        for stmt in node.plan.body:
            self.visit(stmt)

        # Load None as the agent's return value, then exit
        self._emit(OpCode.LOAD_CONST, self._co.add_const(None))
        self._emit(OpCode.AGENT_EXIT, node.name, node.span)
        self._scope_stack.pop()

    # â”€â”€ Import statements â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    def visit_UseToolStmt(self, node: N.UseToolStmt) -> None:
        self._emit(OpCode.IMPORT_TOOL, node.tool_path, node.span)
        root = node.tool_path.split(".")[0]
        self._emit_store(root, node.span)

    def visit_UsePyStmt(self, node: N.UsePyStmt) -> None:
        alias = node.alias or node.module_path.split(".")[-1]
        self._emit(OpCode.IMPORT_PY, (node.module_path, node.alias), node.span)
        self._emit_store(alias, node.span)

    def visit_UseMemoryStmt(self, node: N.UseMemoryStmt) -> None:
        # Memory namespace registration â€” no-op in bytecode (handled at runtime init)
        pass

    # â”€â”€ Agent primitives â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    def visit_RememberStmt(self, node: N.RememberStmt) -> None:
        self.visit(node.value)
        self._emit(OpCode.AGENT_REMEMBER, node.namespace, node.span)

    def visit_ForgetStmt(self, node: N.ForgetStmt) -> None:
        self.visit(node.key)
        self._emit(OpCode.AGENT_FORGET, node.namespace, node.span)

    def visit_RecallStmt(self, node: N.RecallStmt) -> None:
        self._emit(
            OpCode.AGENT_RECALL, (node.query, node.namespace, node.var), node.span
        )

    def visit_ApproveStmt(self, node: N.ApproveStmt) -> None:
        self._emit(OpCode.AGENT_APPROVE, (node.target, node.action), node.span)

    def visit_GuardStmt(self, node: N.GuardStmt) -> None:
        self.visit(node.condition)
        self._emit(OpCode.AGENT_GUARD, None, node.span)

    def visit_RetryStmt(self, node: N.RetryStmt) -> None:
        self._emit(OpCode.SETUP_RETRY, (node.count, node.backoff), node.span)
        for stmt in node.body:
            self.visit(stmt)
        self._emit(OpCode.END_RETRY, None, node.span)

    def visit_EvalStmt(self, node: N.EvalStmt) -> None:
        criteria = []
        for c in node.criteria:
            lit = self._extract_literal(c.threshold)
            criteria.append(
                {
                    "metric": c.metric,
                    "op": c.op,
                    "threshold": lit if type(lit) is not object else str(c.threshold),
                }
            )
        self._emit(OpCode.AGENT_EVAL, (node.subject, node.rubric, criteria), node.span)

    # â”€â”€ Expression visitors â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ #

    def visit_IntLiteral(self, node: N.IntLiteral) -> None:
        idx = self._co.add_const(node.value)
        self._emit(OpCode.LOAD_CONST, idx, node.span)

    def visit_FloatLiteral(self, node: N.FloatLiteral) -> None:
        idx = self._co.add_const(node.value)
        self._emit(OpCode.LOAD_CONST, idx, node.span)

    def visit_StringLiteral(self, node: N.StringLiteral) -> None:
        idx = self._co.add_const(node.value)
        self._emit(OpCode.LOAD_CONST, idx, node.span)

    def visit_BoolLiteral(self, node: N.BoolLiteral) -> None:
        idx = self._co.add_const(node.value)
        self._emit(OpCode.LOAD_CONST, idx, node.span)

    def visit_NoneLiteral(self, node: N.NoneLiteral) -> None:
        idx = self._co.add_const(None)
        self._emit(OpCode.LOAD_CONST, idx, node.span)

    def visit_Identifier(self, node: N.Identifier) -> None:
        self._emit(OpCode.LOAD_GLOBAL, node.name, node.span)

    def visit_BinaryOp(self, node: N.BinaryOp) -> None:
        self.visit(node.left)
        self.visit(node.right)
        op_map = {
            "+": OpCode.BINARY_ADD,
            "-": OpCode.BINARY_SUB,
            "*": OpCode.BINARY_MUL,
            "/": OpCode.BINARY_DIV,
            "%": OpCode.BINARY_MOD,
            "**": OpCode.BINARY_POW,
            "==": OpCode.COMPARE_EQ,
            "!=": OpCode.COMPARE_NE,
            "<": OpCode.COMPARE_LT,
            "<=": OpCode.COMPARE_LE,
            ">": OpCode.COMPARE_GT,
            ">=": OpCode.COMPARE_GE,
            "and": OpCode.LOGICAL_AND,
            "or": OpCode.LOGICAL_OR,
        }
        if node.op not in op_map:
            raise CompilerError(f"Unknown binary operator: {node.op!r}")
        self._emit(op_map[node.op], span=node.span)

    def visit_UnaryOp(self, node: N.UnaryOp) -> None:
        self.visit(node.operand)
        if node.op == "not":
            self._emit(OpCode.UNARY_NOT, span=node.span)
        elif node.op == "-":
            self._emit(OpCode.UNARY_NEG, span=node.span)
        elif node.op == "+":
            self._emit(OpCode.UNARY_POS, span=node.span)
        else:
            raise CompilerError(f"Unknown unary operator: {node.op!r}")

    def visit_ListExpr(self, node: N.ListExpr) -> None:
        for elem in node.elements:
            self.visit(elem)
        self._emit(OpCode.BUILD_LIST, len(node.elements), node.span)

    def visit_DictExpr(self, node: N.DictExpr) -> None:
        for key, val in node.pairs:
            self.visit(key)
            self.visit(val)
        self._emit(OpCode.BUILD_DICT, len(node.pairs), node.span)

    def visit_MemberExpr(self, node: N.MemberExpr) -> None:
        self.visit(node.obj)
        self._emit(OpCode.GET_ATTR, node.attr, node.span)

    def visit_IndexExpr(self, node: N.IndexExpr) -> None:
        self.visit(node.obj)
        self.visit(node.index)
        self._emit(OpCode.GET_ITEM, span=node.span)

    def visit_CallExpr(self, node: N.CallExpr) -> None:
        # Compile callee
        self.visit(node.callee)

        # Compile positional args
        for arg in node.args:
            self.visit(arg)

        # Compile keyword args â€” interleaved as (key_const, value) pairs
        for kw_name, kw_val in node.kwargs:
            idx = self._co.add_const(kw_name)
            self._emit(OpCode.LOAD_CONST, idx, node.span)
            self.visit(kw_val)

        self._emit(
            OpCode.CALL_FUNCTION,
            (len(node.args), len(node.kwargs)),
            node.span,
        )


def compile_program(program: N.Program, filename: str = "<stdin>") -> CodeObject:
    """Convenience function: compile a Program AST into a CodeObject."""
    compiler = Compiler(filename=filename)
    return compiler.compile(program)
