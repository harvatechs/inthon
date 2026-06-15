# INTHON Prompt Chain

Use these prompts sequentially if your AI coding tool performs better with focused steps.

## Prompt 0: Repository setup

```text
Create the INTHON repository scaffold exactly from FILE_TREE.md. Add pyproject.toml for Python 3.11+, dependencies lark, typer, rich, pydantic, jsonschema, structlog, and dev dependencies pytest, pytest-cov, ruff, mypy, hypothesis. Add package imports, README, docs skeleton, examples skeleton, and empty tests. Do not implement language features yet. Run tests and show results.
```

## Prompt 1: Lexer

```text
Implement the INTHON lexer. Add Span, Token, TokenType, keyword map, and Tokenizer. Support literals, identifiers, keywords, operators, delimiters, comments, whitespace, newlines, EOF, and helpful lexer errors. Add unit tests for spans and all token groups. Do not implement parser behavior beyond lexer tests.
```

## Prompt 2: Parser and AST

```text
Implement the Lark parser and AST transformer for INTHON v0.1. Add grammar for variables, constants, imports, Python imports, functions, agent blocks, policy blocks, plan blocks, approval, retry/catch, eval, guard, memory operations, and expressions. Add frozen dataclass AST nodes and parser tests. Do not implement runtime execution.
```

## Prompt 3: Semantic analysis

```text
Implement semantic analysis for INTHON. Add scope chain, symbol table, duplicate declaration detection, undefined name detection, import validation, tool/module use-before-import validation, const reassignment detection, basic type inference, and agent policy-before-plan validation. Add tests.
```

## Prompt 4: IR

```text
Implement JSON-serializable IR for INTHON. Lower AST to IR, preserve source spans, extract static tool-call graph, and add serializer/deserializer. Add `inthon ir` CLI command if CLI exists, otherwise expose function and tests.
```

## Prompt 5: Runtime

```text
Implement the INTHON runtime interpreter. Add execution context, values, evaluator, executor, function calls, returns, errors, trace logger, and sandbox time/cost placeholders. Make hello.inth run successfully. Every run must emit trace JSON. Add tests.
```

## Prompt 6: Tool registry

```text
Implement the INTHON tool system. Add ToolSpec, ToolCall, ToolResult, ToolCostModel, registry, schema validator, mock built-in web.search and web.read tools, cost estimation, and tool call logging. Enforce that unregistered tools never execute. Add tests.
```

## Prompt 7: Policy/security

```text
Implement policy and security. Add default-deny capability model, policy engine, approval gate, audit log, network/filesystem/shell/email/payment capabilities, max tool call and max cost checks, and trace redaction. Shell must be hard-blocked in v0.1. Add safety tests.
```

## Prompt 8: Python bridge

```text
Implement safe Python bridge. Support `use py.module as alias`, deny dangerous modules/functions by default, allow configured modules, convert values between INTHON and Python, wrap exceptions, trace Python calls, and add Pandas adapter MVP. Add tests and csv_summary.inth example.
```

## Prompt 9: CLI

```text
Implement Typer CLI for `inthon run`, `inthon check`, `inthon ast`, `inthon ir`, and a basic `inthon fmt` stub. Use Rich for errors. Add JSON trace output option. Add CLI tests.
```

## Prompt 10: Docs and examples

```text
Write the INTHON docs: quickstart, language guide, runtime guide, tool guide, Python interop guide, data/ML guide, security guide, and contribution guide. Add hello.inth, tool_search.inth, csv_summary.inth, agent_research.inth, ml_inference.inth, and approval_gate.inth. Run full tests.
```

## Prompt 11: Benchmarks

```text
Build benchmark harnesses for token efficiency, agent workflow correctness, and safety. Compare natural language, JSON plan, Python, and INTHON. Produce JSON results and a short report. Add tests for benchmark utilities.
```

## Prompt 12: Release

```text
Prepare INTHON v0.1-alpha. Run full tests, coverage, lint, and type checks. Verify all examples. Write CHANGELOG.md and release notes. List known limitations and next steps.
```
