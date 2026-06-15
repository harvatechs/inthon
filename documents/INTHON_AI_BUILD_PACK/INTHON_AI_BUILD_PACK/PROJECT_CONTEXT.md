# INTHON Project Context

## One-line definition

INTHON is an agent-level programming language for AI-native computation, tool orchestration, and machine-speed workflows.

## Core thesis

Current agent systems express actions through verbose natural language, fragile JSON/YAML, or Python boilerplate. INTHON fills the gap with compact, deterministic, inspectable programs that are designed for tool-using AI agents.

## Product goals

1. Reduce token usage.
2. Make tool calling deterministic.
3. Make AI workflows auditable.
4. Support Python, data science, and ML deeply.
5. Stay flexible for engineers.

## Language philosophy

Natural language is for goals. INTHON is for executable intent.

## Design principles

- Compactness: terse syntax for common agent workflows.
- Determinism: explicit tool calls and declared side effects.
- Auditability: every run emits source, AST/IR, trace, tool log, state diff, errors, cost, safety events, and output.
- Safety: permissions, sandboxing, approval gates, and policy blocks are first-class.
- Python compatibility: Python interop is mandatory.
- Agent-native constructs: goals, tools, plans, memory, retries, approval, eval, guard.
- Progressive complexity: simple scripts should be simple, advanced workflows should be possible.

## v0.1 MVP architecture

```text
INTHON Source
  -> Lexer
  -> Parser
  -> AST
  -> Semantic Analyzer
  -> Type Checker
  -> Permission Checker
  -> IR Generator
  -> Execution Backend
       -> Python Transpiler
       -> INTHON Interpreter
       -> Agent Runtime Plan
       -> JSON Tool Call Graph
       -> Future Bytecode VM
```

For v0.1, prioritize:

1. Lexer
2. Parser
3. AST
4. Interpreter
5. Tool registry
6. Python bridge
7. CLI
8. Tests

## Engine invariants

1. Tool calls are schema-validated before execution.
2. Side effects are declared, logged, and policy-checked.
3. Executions emit complete, replayable traces.
4. Dangerous Python operations are blocked before import resolution.
5. Human approval gates halt synchronously.

## v0.1 hard constraints

- Never execute unregistered tool calls.
- Never import denied Python modules.
- Trace emission is synchronous.
- Agent policy is evaluated before agent plan execution.
- Monetary cost estimates must be upper-bounded before execution.

## Key syntax

```inth
agent MarketResearcher {
  goal "Analyze competitor pricing"
  use tool web.search
  use tool web.read
  use memory.project("pricing")

  policy {
    max_tool_calls: 20
    require_sources: true
    allow_network: true
  }

  plan {
    links = web.search("competitor pricing AI agent platform").top(10)
    pages = web.read(links)
    table = extract_table(pages, columns: ["company", "price", "plan", "source"])
    save table to memory
    return report(table)
  }
}
```

## Core non-goals

- Replace Python.
- Replace PyTorch, Pandas, SQL, or natural language.
- Become a full operating system.
- Build a native tensor engine.
- Build an AGI operating layer.

## Competitive positioning

INTHON is complementary to agent frameworks and protocols. It can compile to Python, JSON tool-call graphs, and DAG execution plans. It can act as a higher-level workflow language on top of MCP-style tool discovery, LangChain/LangGraph execution graphs, and Python/Pydantic validation.

## Roadmap summary

- v0.1: Python-hosted MVP with parser, AST, interpreter, tools, policy, Python bridge, CLI.
- v0.2: developer experience: formatter, linter, REPL, Tree-sitter, LSP start.
- v0.3: ecosystem: OpenAPI tools, vector DB adapter, notebook integration, benchmarks.
- v0.4: performance: IR optimizer, bytecode prototype, Rust parser prototype, container sandbox.
- v1.0: stable syntax, stable tool API, stable package format, security audit, docs site, public registry.
