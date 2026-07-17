from __future__ import annotations
from typing import Any
from ..ast.visitor import ASTVisitor
from ..ast import nodes as N
from .nodes import (
    IRProgram, IRImport, IRAssign, IRReturn, IRToolCall, IRPyCall,
    IRAgentBlock, IRApproval, IRConditional, IRLoop, IRLiteral,
    IRVar, IRBinaryOp, IRList, IRDict, IRCall, IRValue, IRNode
)

class IRBuilder(ASTVisitor):
    def __init__(self) -> None:
        self.imported_tools: set[str] = set()
        self.imported_py: dict[str, str] = {}  # alias -> canonical module name

    def build(self, program: N.Program) -> IRProgram:
        imports: list[IRImport] = []
        body: list[IRNode] = []

        # First pass: collect imports to resolve call expressions correctly
        for stmt in program.statements:
            if isinstance(stmt, (N.UseTool, N.UsePy, N.UseMemory)):
                imp = self.visit(stmt)
                if imp:
                    imports.append(imp)

        # Second pass: construct body
        for stmt in program.statements:
            if not isinstance(stmt, (N.UseTool, N.UsePy, N.UseMemory)):
                node = self.visit(stmt)
                if node:
                    body.append(node)

        return IRProgram(imports=imports, body=body)

    def _resolve_callee(self, callee: N.Expression) -> tuple[str | None, list[str]]:
        if isinstance(callee, N.Identifier):
            return callee.name, []
        if isinstance(callee, N.MemberExpr):
            root, chain = self._resolve_callee(callee.object)
            chain.append(callee.name)
            return root, chain
        return None, []

    # --- Imports ---
    def visit_UseTool(self, node: N.UseTool) -> IRImport:
        self.imported_tools.add(node.path)
        return IRImport(kind="tool", path=node.path)

    def visit_UsePy(self, node: N.UsePy) -> IRImport:
        alias = node.alias or node.module.split(".")[-1]
        self.imported_py[alias] = node.module
        return IRImport(kind="py", path=node.module, alias=node.alias)

    def visit_UseMemory(self, node: N.UseMemory) -> IRImport:
        return IRImport(kind="memory", path=node.namespace)

    # --- Statements ---
    def visit_LetDecl(self, node: N.LetDecl) -> IRAssign:
        return IRAssign(target=node.name, value=self.visit(node.value))

    def visit_ConstDecl(self, node: N.ConstDecl) -> IRAssign:
        return IRAssign(target=node.name, value=self.visit(node.value))

    def visit_AssignStmt(self, node: N.AssignStmt) -> IRAssign:
        if isinstance(node.target, N.Identifier):
            target_name = node.target.name
        else:
            root, chain = self._resolve_callee(node.target)
            target_name = f"{root}.{'.'.join(chain)}" if root else str(node.target)
        return IRAssign(target=target_name, value=self.visit(node.value))

    def visit_RecallExpr(self, node: N.RecallExpr) -> IRCall:
        return IRCall(
            callee=IRVar("recall"),
            args=[IRLiteral(node.query, "str"), IRLiteral(node.namespace, "str")],
            kwargs={}
        )

    def visit_ReturnStmt(self, node: N.ReturnStmt) -> IRReturn:
        return IRReturn(value=self.visit(node.value) if node.value else None)

    def visit_ExprStmt(self, node: N.ExprStmt) -> IRNode | None:
        val = self.visit(node.expr)
        if isinstance(val, (IRToolCall, IRPyCall, IRCall)):
            return val
        return None

    def visit_ApproveStmt(self, node: N.ApproveStmt) -> IRApproval:
        return IRApproval(target=node.target, action=node.action)

    def visit_IfStmt(self, node: N.IfStmt) -> IRConditional:
        then_branch = [self.visit(s) for s in node.then_branch]
        else_branch = [self.visit(s) for s in node.else_branch] if node.else_branch else None
        return IRConditional(condition=self.visit(node.condition), then_branch=then_branch, else_branch=else_branch)

    def visit_ForStmt(self, node: N.ForStmt) -> IRLoop:
        body = [self.visit(s) for s in node.body]
        return IRLoop(kind="for", var=node.var, iterable=self.visit(node.iterable), condition=None, body=body)

    def visit_WhileStmt(self, node: N.WhileStmt) -> IRLoop:
        body = [self.visit(s) for s in node.body]
        return IRLoop(kind="while", var=None, iterable=None, condition=self.visit(node.condition), body=body)

    def visit_AgentDecl(self, node: N.AgentDecl) -> IRAgentBlock:
        policy_dict = {e.key: e.value for e in node.policy.entries} if node.policy else {}
        plan_nodes = [self.visit(s) for s in node.plan.statements]
        return IRAgentBlock(name=node.name, goal=node.goal, policy=policy_dict, plan=plan_nodes)

    def visit_RememberStmt(self, node: N.RememberStmt) -> IRCall:
        return IRCall(
            callee=IRVar("remember"),
            args=[self.visit(node.value), IRLiteral(node.namespace, "str")],
            kwargs={}
        )

    def visit_ForgetStmt(self, node: N.ForgetStmt) -> IRCall:
        return IRCall(
            callee=IRVar("forget"),
            args=[self.visit(node.key), IRLiteral(node.namespace, "str")],
            kwargs={}
        )

    def visit_RecallStmt(self, node: N.RecallStmt) -> IRAssign:
        recall_call = IRCall(
            callee=IRVar("recall"),
            args=[IRLiteral(node.query, "str"), IRLiteral(node.namespace, "str")],
            kwargs={}
        )
        return IRAssign(target=node.var, value=recall_call)

    def visit_GuardStmt(self, node: N.GuardStmt) -> IRCall:
        return IRCall(
            callee=IRVar("guard"),
            args=[self.visit(node.condition)],
            kwargs={}
        )

    def visit_RetryStmt(self, node: N.RetryStmt) -> IRLoop:
        body = [self.visit(s) for s in node.body]
        return IRLoop(
            kind="retry",
            var=None,
            iterable=None,
            condition=IRLiteral(node.count, "int"),
            body=body
        )

    def visit_EvalStmt(self, node: N.EvalStmt) -> IRCall:
        criteria_list = []
        for c in node.criteria:
            criteria_list.append(IRDict(pairs=[
                (IRLiteral("metric", "str"), IRLiteral(c.metric, "str")),
                (IRLiteral("op", "str"), IRLiteral(c.op, "str")),
                (IRLiteral("threshold", "str"), self.visit(c.threshold))
            ]))
        return IRCall(
            callee=IRVar("eval"),
            args=[IRVar(node.subject), IRLiteral(node.rubric, "str"), IRList(elements=criteria_list)],
            kwargs={}
        )

    # --- Expressions ---
    def visit_IntLiteral(self, node: N.IntLiteral) -> IRLiteral:
        return IRLiteral(value=node.value, type_hint="int")

    def visit_FloatLiteral(self, node: N.FloatLiteral) -> IRLiteral:
        return IRLiteral(value=node.value, type_hint="float")

    def visit_StringLiteral(self, node: N.StringLiteral) -> IRLiteral:
        return IRLiteral(value=node.value, type_hint="str")

    def visit_BoolLiteral(self, node: N.BoolLiteral) -> IRLiteral:
        return IRLiteral(value=node.value, type_hint="bool")

    def visit_NoneLiteral(self, node: N.NoneLiteral) -> IRLiteral:
        return IRLiteral(value=None, type_hint="none")

    def visit_Identifier(self, node: N.Identifier) -> IRVar:
        return IRVar(name=node.name)

    def visit_BinaryOp(self, node: N.BinaryOp) -> IRBinaryOp:
        return IRBinaryOp(op=node.op, left=self.visit(node.left), right=self.visit(node.right))

    def visit_UnaryOp(self, node: N.UnaryOp) -> IRBinaryOp:
        return IRBinaryOp(op=node.op, left=self.visit(node.operand), right=IRLiteral(None, "none"))

    def visit_ListExpr(self, node: N.ListExpr) -> IRList:
        return IRList(elements=[self.visit(e) for e in node.elements])

    def visit_DictExpr(self, node: N.DictExpr) -> IRDict:
        return IRDict(pairs=[(self.visit(p[0]), self.visit(p[1])) for p in node.pairs])

    def visit_CallExpr(self, node: N.CallExpr) -> IRValue:
        root, chain = self._resolve_callee(node.callee)
        args = [self.visit(a) for a in node.args]
        kwargs = {k: self.visit(v) for k, v in node.kwargs}

        if root:
            if root in self.imported_tools or any(root == t.split(".")[0] for t in self.imported_tools):
                tool_path = f"{root}.{'.'.join(chain)}" if chain else root
                return IRToolCall(tool=tool_path, args=args, kwargs=kwargs)
            if root in self.imported_py:
                module = self.imported_py[root]
                return IRPyCall(module=module, attr_chain=chain, args=args, kwargs=kwargs)

        return IRCall(callee=self.visit(node.callee), args=args, kwargs=kwargs)

    def visit_MemberExpr(self, node: N.MemberExpr) -> IRValue:
        root, chain = self._resolve_callee(node)
        if root in self.imported_py:
            module = self.imported_py[root]
            return IRPyCall(module=module, attr_chain=chain, args=[], kwargs={})
        return IRVar(name=f"{root}.{'.'.join(chain)}" if root else "")

    def visit_IndexExpr(self, node: N.IndexExpr) -> IRCall:
        return IRCall(
            callee=IRVar("getitem"),
            args=[self.visit(node.object), self.visit(node.index)],
            kwargs={}
        )

def build_ir(program: N.Program, *, source: str = "", filename: str = "<stdin>") -> IRProgram:
    builder = IRBuilder()
    return builder.build(program)
