"""INTHON source formatter (`inthon fmt`).

Canonical style: 4-space indents, one statement per line, no semicolons,
single blank line between top-level declarations.
"""

from __future__ import annotations

from .ast import nodes

_PREC = {"or": 1, "and": 2, "==": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
         "+": 5, "-": 5, "*": 6, "/": 6, "%": 6, "**": 8}


def format_source(source: str, filename: str = "<stdin>") -> str:
    """Parse *source* and re-emit it in canonical form."""
    from .parser import parse

    program = parse(source, filename)
    return format_program(program)


def format_program(program: nodes.Program) -> str:
    f = _Formatter()
    lines: list[str] = []
    prev_decl = False
    for stmt in program.statements:
        is_decl = isinstance(stmt, (nodes.FnDecl, nodes.AgentDecl))
        if lines and (is_decl or prev_decl):
            lines.append("")
        lines.extend(f.stmt(stmt, 0))
        prev_decl = is_decl
    return "\n".join(lines) + "\n"


def _escape(s: str) -> str:
    return (s.replace("\\", "\\\\").replace('"', '\\"')
             .replace("\n", "\\n").replace("\t", "\\t"))


class _Formatter:
    IND = "    "

    # -- statements ---------------------------------------------------------
    def stmt(self, n, lvl: int) -> list[str]:
        m = getattr(self, f"s_{type(n).__name__}")
        return m(n, lvl)

    def _block(self, b: nodes.Block, lvl: int) -> list[str]:
        if not b.statements:
            return [self.IND * lvl + "pass"]
        out: list[str] = []
        for s in b.statements:
            out.extend(self.stmt(s, lvl))
        return out

    def s_UseTool(self, n: nodes.UseTool, lvl):
        return [self.IND * lvl + f"use tool {n.path}"]

    def s_UsePy(self, n: nodes.UsePy, lvl):
        alias = f" as {n.alias}" if n.alias else ""
        return [self.IND * lvl + f"use py.{n.module}{alias}"]

    def s_UseMemory(self, n: nodes.UseMemory, lvl):
        args = [self.expr(a) for a in n.args] + [f"{k}={self.expr(v)}" for k, v in n.kwargs]
        tail = f"({', '.join(args)})" if args else ""
        return [self.IND * lvl + f"use memory.{n.namespace}{tail}"]

    def s_LetDecl(self, n: nodes.LetDecl, lvl):
        t = f": {n.type_annotation.render()}" if n.type_annotation else ""
        v = f" = {self.expr(n.value)}" if n.value is not None else ""
        return [self.IND * lvl + f"let {n.name}{t}{v}"]

    def s_ConstDecl(self, n: nodes.ConstDecl, lvl):
        t = f": {n.type_annotation.render()}" if n.type_annotation else ""
        v = f" = {self.expr(n.value)}" if n.value is not None else ""
        return [self.IND * lvl + f"const {n.name}{t}{v}"]

    def s_FnDecl(self, n: nodes.FnDecl, lvl):
        params = ", ".join(self._param(p) for p in n.params)
        ret = f" -> {n.return_type.render()}" if n.return_type else ""
        lines = [self.IND * lvl + f"fn {n.name}({params}){ret} {{"]
        lines += self._block(n.body, lvl + 1)
        lines.append(self.IND * lvl + "}")
        return lines

    def _param(self, p: nodes.Param) -> str:
        t = f": {p.type_annotation.render()}" if p.type_annotation else ""
        d = f" = {self.expr(p.default)}" if p.default is not None else ""
        return f"{p.name}{t}{d}"

    def s_AgentDecl(self, n: nodes.AgentDecl, lvl):
        lines = [self.IND * lvl + f"agent {n.name} {{"]
        inner = lvl + 1
        if n.goal is not None:
            lines.append(self.IND * inner + f'goal "{_escape(n.goal)}"')
        if n.inputs:
            lines.append(self.IND * inner + "inputs {")
            for f in n.inputs:
                lines.append(self.IND * (inner + 1) + f"{f.name}: {f.type_annotation.render()}")
            lines.append(self.IND * inner + "}")
        if n.outputs:
            lines.append(self.IND * inner + "outputs {")
            for f in n.outputs:
                lines.append(self.IND * (inner + 1) + f"{f.name}: {f.type_annotation.render()}")
            lines.append(self.IND * inner + "}")
        for imp in n.imports:
            lines += self.stmt(imp, inner)
        if n.policies:
            lines.append(self.IND * inner + "policy {")
            for p in n.policies:
                lines.append(self.IND * (inner + 1) + f"{p.key}: {self._literal(p.value)}")
            lines.append(self.IND * inner + "}")
        for c in n.criteria:
            lines += self.s_CriteriaDecl(c, inner)
        for r in n.rewriters:
            lines += self.s_RewriterDecl(r, inner)
        if n.plan is not None:
            lines.append(self.IND * inner + "plan {")
            lines += self._block(n.plan, inner + 1)
            lines.append(self.IND * inner + "}")
        lines.append(self.IND * lvl + "}")
        return lines

    def s_CriteriaDecl(self, n: nodes.CriteriaDecl, lvl):
        lines = [self.IND * lvl + f"criteria {n.name} {{"]
        for c in n.criteria:
            if c.op == ":":
                lines.append(self.IND * (lvl + 1) + f"{c.name}: {self.expr(c.value)}")
            else:
                lines.append(self.IND * (lvl + 1) + f"{c.name} {c.op} {self.expr(c.value)}")
        lines.append(self.IND * lvl + "}")
        return lines

    def s_RewriterDecl(self, n: nodes.RewriterDecl, lvl):
        lines = [self.IND * lvl + f"rewriter {n.name} {{"]
        lines += self._block(n.body, lvl + 1)
        lines.append(self.IND * lvl + "}")
        return lines

    def s_IfStmt(self, n: nodes.IfStmt, lvl):
        lines = [self.IND * lvl + f"if {self.expr(n.condition)} {{"]
        lines += self._block(n.then_block, lvl + 1)
        if n.else_block is not None:
            if isinstance(n.else_block, nodes.IfStmt):
                sub = self.s_IfStmt(n.else_block, 0)
                lines.append(self.IND * lvl + "} else " + sub[0])
                lines += sub[1:]
            else:
                lines.append(self.IND * lvl + "} else {")
                lines += self._block(n.else_block, lvl + 1)
                lines.append(self.IND * lvl + "}")
        else:
            lines.append(self.IND * lvl + "}")
        return lines

    def s_ForStmt(self, n: nodes.ForStmt, lvl):
        lines = [self.IND * lvl + f"for {n.var} in {self.expr(n.iterable)} {{"]
        lines += self._block(n.body, lvl + 1)
        lines.append(self.IND * lvl + "}")
        return lines

    def s_WhileStmt(self, n: nodes.WhileStmt, lvl):
        lines = [self.IND * lvl + f"while {self.expr(n.condition)} {{"]
        lines += self._block(n.body, lvl + 1)
        lines.append(self.IND * lvl + "}")
        return lines

    def s_ReturnStmt(self, n: nodes.ReturnStmt, lvl):
        v = f" {self.expr(n.value)}" if n.value is not None else ""
        return [self.IND * lvl + f"return{v}"]

    def s_BreakStmt(self, n, lvl):
        return [self.IND * lvl + "break"]

    def s_ContinueStmt(self, n, lvl):
        return [self.IND * lvl + "continue"]

    def s_ApproveStmt(self, n: nodes.ApproveStmt, lvl):
        return [self.IND * lvl + f"approve {n.tool_path} before {n.action}"]

    def s_RememberStmt(self, n: nodes.RememberStmt, lvl):
        return [self.IND * lvl + f"remember {self.expr(n.value)} in {n.namespace}"]

    def s_ForgetStmt(self, n: nodes.ForgetStmt, lvl):
        return [self.IND * lvl + f"forget {self.expr(n.value)} from {n.namespace}"]

    def s_GuardStmt(self, n: nodes.GuardStmt, lvl):
        return [self.IND * lvl + f"guard {self.expr(n.condition)}"]

    def s_RetryStmt(self, n: nodes.RetryStmt, lvl):
        lines = [self.IND * lvl + f"retry {n.count} with {n.backoff} backoff {{"]
        lines += self._block(n.body, lvl + 1)
        if n.catch_body is not None:
            name = f" {n.catch_name}" if n.catch_name else ""
            lines.append(self.IND * lvl + f"}} catch{name} {{")
            lines += self._block(n.catch_body, lvl + 1)
        lines.append(self.IND * lvl + "}")
        return lines

    def s_EvalStmt(self, n: nodes.EvalStmt, lvl):
        head = f"eval {n.subject} against {n.rubric}"
        if n.criteria:
            lines = [self.IND * lvl + head + " {"]
            for c in n.criteria:
                if c.op == ":":
                    lines.append(self.IND * (lvl + 1) + f"{c.name}: {self.expr(c.value)}")
                else:
                    lines.append(self.IND * (lvl + 1) + f"{c.name} {c.op} {self.expr(c.value)}")
            lines.append(self.IND * lvl + "}")
        else:
            tail = f" on fail rewrite with {n.rewriter}" if n.rewriter else ""
            lines = [self.IND * lvl + head + tail]
        return lines

    def s_PolicyStmt(self, n: nodes.PolicyStmt, lvl):
        lines = [self.IND * lvl + "policy {"]
        for p in n.entries:
            lines.append(self.IND * (lvl + 1) + f"{p.key}: {self._literal(p.value)}")
        lines.append(self.IND * lvl + "}")
        return lines

    def s_ExprStmt(self, n: nodes.ExprStmt, lvl):
        return [self.IND * lvl + self.expr(n.expr)]

    def s_AssignStmt(self, n: nodes.AssignStmt, lvl):
        return [self.IND * lvl + f"{self.expr(n.target)} = {self.expr(n.value)}"]

    # -- expressions --------------------------------------------------------
    def expr(self, n, prec: int = 0) -> str:
        if n is None:
            return "none"
        m = getattr(self, f"e_{type(n).__name__}")
        return m(n, prec)

    def e_IntLiteral(self, n, prec):
        return str(n.value)

    def e_FloatLiteral(self, n, prec):
        return repr(n.value)

    def e_StringLiteral(self, n, prec):
        return f'"{_escape(n.value)}"'

    def e_InterpString(self, n, prec):
        out = []
        for part in n.parts:
            if isinstance(part, str):
                out.append(_escape(part))
            else:
                out.append("{" + self.expr(part) + "}")
        return '"' + "".join(out) + '"'

    def e_BoolLiteral(self, n, prec):
        return "true" if n.value else "false"

    def e_NoneLiteral(self, n, prec):
        return "none"

    def e_Identifier(self, n, prec):
        return n.name

    def e_ListExpr(self, n, prec):
        return "[" + ", ".join(self.expr(e) for e in n.elements) + "]"

    def e_DictExpr(self, n, prec):
        return "{" + ", ".join(f"{self.expr(k)}: {self.expr(v)}" for k, v in n.pairs) + "}"

    def e_BinaryOp(self, n: nodes.BinaryOp, prec):
        p = _PREC[n.op]
        left = self.expr(n.left, p + (1 if n.op == "**" else 0))
        right = self.expr(n.right, p + 1)
        s = f"{left} {n.op} {right}"
        return f"({s})" if p < prec else s

    def e_UnaryOp(self, n: nodes.UnaryOp, prec):
        p = 3 if n.op == "not" else 7
        operand = self.expr(n.operand, p + 1)
        s = f"not {operand}" if n.op == "not" else f"{n.op}{operand}"
        return f"({s})" if p < prec else s

    def e_CallExpr(self, n: nodes.CallExpr, prec):
        args = [self.expr(a) for a in n.args] + [f"{k}={self.expr(v)}" for k, v in n.kwargs]
        return f"{self.expr(n.callee, 9)}({', '.join(args)})"

    def e_MemberExpr(self, n: nodes.MemberExpr, prec):
        return f"{self.expr(n.object, 9)}.{n.name}"

    def e_IndexExpr(self, n: nodes.IndexExpr, prec):
        return f"{self.expr(n.object, 9)}[{self.expr(n.index)}]"

    def e_RecallExpr(self, n: nodes.RecallExpr, prec):
        return f'recall "{_escape(n.query)}" from {n.namespace}'

    def _literal(self, v) -> str:
        if v is True:
            return "true"
        if v is False:
            return "false"
        if v is None:
            return "none"
        if isinstance(v, str):
            return f'"{_escape(v)}"'
        return repr(v)
