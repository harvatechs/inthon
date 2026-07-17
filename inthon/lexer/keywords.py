"""INTHON keyword table (engine spec §3.2).

All keywords are reserved: no keyword may be used as an identifier.
"""

KEYWORDS: dict[str, str] = {
    # Declarations
    "let": "LET",
    "const": "CONST",
    "fn": "FN",
    "agent": "AGENT",
    # Control flow
    "if": "IF",
    "else": "ELSE",
    "for": "FOR",
    "while": "WHILE",
    "in": "IN",
    "return": "RETURN",
    "break": "BREAK",
    "continue": "CONTINUE",
    # Agent constructs
    "goal": "GOAL",
    "inputs": "INPUTS",
    "outputs": "OUTPUTS",
    "use": "USE",
    "policy": "POLICY",
    "plan": "PLAN",
    "tool": "TOOL",
    "py": "PY",
    "memory": "MEMORY",
    "as": "AS",
    "approve": "APPROVE",
    "before": "BEFORE",
    "remember": "REMEMBER",
    "recall": "RECALL",
    "forget": "FORGET",
    "from": "FROM",
    "guard": "GUARD",
    "retry": "RETRY",
    "with": "WITH",
    "backoff": "BACKOFF",
    "catch": "CATCH",
    "eval": "EVAL",
    "against": "AGAINST",
    "on": "ON",
    "fail": "FAIL",
    "rewrite": "REWRITE",
    "criteria": "CRITERIA",
    "rewriter": "REWRITER",
    # Logical operators (word form)
    "and": "AND",
    "or": "OR",
    "not": "NOT",
    # Literals
    "true": "BOOL",
    "false": "BOOL",
    "none": "NONE",
}

#: Words that are keywords in other popular languages but NOT in INTHON.
#: Used for "did you mean" diagnostics.
NOT_KEYWORDS: dict[str, str] = {
    "def": "fn",
    "function": "fn",
    "var": "let",
    "elif": "else if",
    "switch": "if / else if chains",
    "import": "use",
    "print_": "print (builtin, no keyword needed)",
    "lambda": "fn",
    "class": "(INTHON has no classes; use agent blocks and dicts)",
    "try": "retry ... catch",
    "except": "retry ... catch",
    "raise": "fail(...)",
    "assert": "guard",
    "yield": "(INTHON has no generators yet)",
    "async": "(INTHON is synchronous by design in v1.0)",
    "await": "(INTHON is synchronous by design in v1.0)",
    "null": "none",
    "None": "none",
    "True": "true",
    "False": "false",
    "&&": "and",
    "||": "or",
    "!": "not",
}
