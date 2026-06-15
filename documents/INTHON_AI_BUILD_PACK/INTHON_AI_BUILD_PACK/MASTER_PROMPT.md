# MASTER PROMPT: Build INTHON End to End

You are an expert compiler engineer, Python runtime engineer, programming language designer, AI-agent systems architect, test engineer, and security reviewer.

Your mission is to build **INTHON**, an agent-level programming language for AI-native workflows. INTHON stands for Intelligent + Python. It is not meant to replace Python. It is a Python-hosted language layer that helps AI agents express executable intent as compact, deterministic, auditable programs.

You must build this project incrementally from a working MVP to a production-ready foundation.

---

## 0. Source of truth

Use the provided project documents as the authority:

- `INTHON_PRD.pdf` - product requirements, roadmap, examples, MVP scope, AI agent build pack.
- `INTHON_ENGINE.pdf` - authoritative v0.1 engineering reference, module layout, invariants, subsystems.
- `INTHON_PAPER.pdf` - research thesis, design rationale, type system, security, evaluation plan.
- `INTHON_KIMI_REF.pdf` - market/technical feasibility, competitor analysis, implementation strategy.

When the docs conflict, follow this order:

1. `INTHON_ENGINE.pdf` for v0.1 engineering decisions.
2. `INTHON_PRD.pdf` for product scope and build sequence.
3. `INTHON_PAPER.pdf` for language design and research claims.
4. `INTHON_KIMI_REF.pdf` for feasibility and roadmap context.

Do not invent unsupported features before the MVP works.

---

## 1. Core mission

Build a complete v0.1 implementation that supports:

- `.inth` files
- CLI runner
- variables and constants
- functions
- basic expressions
- agent blocks
- policy blocks
- tool imports
- tool registry
- mock tools
- safe Python import bridge
- basic Pandas adapter
- runtime trace logging
- tests
- documentation
- examples

The v0.1 implementation must be written in Python. Use Python 3.11+.

Recommended dependencies:

- `lark` for parser prototyping
- `typer` for CLI
- `rich` for terminal output
- `pydantic` and/or `jsonschema` for tool schema validation
- `pytest`, `pytest-cov`, `hypothesis`, `ruff`, and `mypy` for development

---

## 2. Non-negotiable runtime invariants

Every execution path must respect these invariants:

1. Every tool call is validated against its schema before execution.
2. Every side effect is declared, logged, and policy-checked.
3. Every execution emits a complete, replayable trace.
4. Dangerous Python operations are blocked before import resolution.
5. Human approval gates are synchronous: execution halts until resolved.

If any code path returns a result without satisfying these invariants, treat it as a runtime bug.

---

## 3. What not to build in v0.1

Do not build these yet:

- custom bytecode VM
- full optimizer
- native tensor compiler
- distributed runtime
- self-hosting compiler
- arbitrary API calling without schemas
- arbitrary shell execution
- fully autonomous sensitive actions without approval
- replacement ML framework
- replacement DataFrame engine

Use Python, Pandas, NumPy, PyTorch, Transformers, and existing systems. INTHON orchestrates; it does not replace them.

---

## 4. Reverse-engineering Python correctly

Use Python and CPython as a design blueprint, not as code to copy.

Study and reproduce the **architecture pattern**:

1. Source text
2. Tokenization
3. Parsing
4. AST
5. Symbol analysis
6. Type/semantic checking
7. Intermediate representation
8. Execution runtime
9. Import/module system
10. Standard library
11. CLI/package tooling
12. Tests and documentation

Map Python concepts to INTHON concepts:

| Python / CPython concept | INTHON v0.1 equivalent |
|---|---|
| tokenizer | `inthon/lexer/tokenizer.py` |
| grammar/parser | `inthon/parser/grammar.lark`, `parser.py` |
| AST nodes | `inthon/ast/nodes.py` |
| symbol table | `inthon/semantic/scope.py` |
| semantic analysis | `inthon/semantic/analyzer.py` |
| bytecode/interpreter loop | tree-walking interpreter in `runtime/` |
| importlib | safe Python bridge in `pybridge/` |
| builtins/stdlib | `stdlib/` and built-in tools |
| traceback/errors | structured error system with codes |
| tracing/profiling | `TraceLogger` and replayable trace JSON |

Important: do not copy CPython source code. Build a clean-room Python-hosted DSL implementation inspired by the public architecture of language runtimes.

---

## 5. Required repository layout

Create this structure first:

```text
inthon/
  pyproject.toml
  inthon.toml
  README.md
  docs/
    language-spec.md
    runtime-spec.md
    tool-spec.md
    security.md
    architecture.md
  examples/
    hello.inth
    tool_search.inth
    csv_summary.inth
    agent_research.inth
    approval_gate.inth
  inthon/
    __init__.py
    version.py
    cli.py
    lexer/
      __init__.py
      tokens.py
      keywords.py
      tokenizer.py
    parser/
      __init__.py
      grammar.lark
      parser.py
      transformer.py
    ast/
      __init__.py
      nodes.py
      visitor.py
      printer.py
    semantic/
      __init__.py
      scope.py
      analyzer.py
      type_checker.py
      permissions.py
    ir/
      __init__.py
      nodes.py
      builder.py
      serializer.py
    runtime/
      __init__.py
      context.py
      values.py
      evaluator.py
      executor.py
      interpreter.py
      trace.py
      sandbox.py
      errors.py
    tools/
      __init__.py
      schema.py
      validator.py
      registry.py
      builtin_tools.py
      cost.py
    policy/
      __init__.py
      model.py
      engine.py
      approval.py
      audit.py
    pybridge/
      __init__.py
      allowlist.py
      importer.py
      converter.py
      exception_wrap.py
      adapters/
        __init__.py
        pandas_adapter.py
        numpy_adapter.py
        torch_adapter.py
        transformers_adapter.py
    memory/
      __init__.py
      store.py
      namespaces.py
      ops.py
    stdlib/
      agent.inth
      data.inth
      ml.inth
      memory.inth
      eval.inth
  tests/
    conftest.py
    unit/
    integration/
    fixtures/
      programs/
      traces/
```

---

## 6. Build order

Implement in this exact order unless tests force a small refactor:

### Phase 0: Repository setup

Deliver:

- `pyproject.toml`
- package skeleton
- CI-ready test layout
- README
- examples folder
- first docs skeleton

Acceptance:

- `python -m pytest` runs.
- `ruff check .` runs.
- package imports with `import inthon`.

### Phase 1: Lexer and parser

Deliver:

- token definitions
- keyword table
- tokenizer with spans
- Lark grammar
- parser wrapper
- transformer to AST
- parser tests

Must parse:

- `let` / `const`
- assignments
- arithmetic expressions
- function declarations
- `use tool`
- `use py`
- `agent`, `goal`, `policy`, `plan`
- `approve`, `retry`, `eval`, `guard`, `remember`, `recall`, `forget`

Acceptance:

- helpful parse errors with file, line, column, and code like `INTHON_PARSE_001`.
- at least 90 percent parser test coverage.

### Phase 2: AST and semantic analysis

Deliver:

- frozen dataclass AST nodes
- visitor base class
- AST printer
- symbol table/scope chain
- semantic analyzer
- basic type checker
- permission analyzer skeleton

Acceptance:

- undefined variables are detected.
- duplicate declarations are detected.
- tool/module usage before import is detected.
- policy is analyzed before agent plan execution.

### Phase 3: IR

Deliver:

- JSON-serializable IR nodes
- AST-to-IR builder
- IR serializer/deserializer
- static tool-call extraction

Acceptance:

- `inthon ir examples/tool_search.inth` prints valid JSON.
- IR contains imports, assignments, calls, tool calls, policies, and returns.

### Phase 4: Runtime interpreter

Deliver:

- execution context
- runtime value conversion
- expression evaluator
- statement executor
- function execution
- return control flow
- error hierarchy
- trace logger
- sandbox limits

Acceptance:

- `hello.inth` executes.
- expression, function, and assignment tests pass.
- every run emits a trace JSON.

### Phase 5: Tool system

Deliver:

- `ToolSpec`, `ToolCall`, `ToolResult`, `ToolCostModel`
- registry
- schema validation
- mock built-in tools
- cost estimation
- tool call logs

Acceptance:

- unregistered tool call returns `INTHON_TOOL_001`.
- schema mismatch returns structured `INTHON_TOOL_*` error.
- tool call is denied if policy lacks capability.
- mock tools can replay deterministic results.

### Phase 6: Policy/security

Deliver:

- capability enum
- policy model
- policy engine
- approval gate
- audit log
- sandbox resource/time limits
- deny dangerous Python operations

Acceptance:

- default deny for network, shell, filesystem writes, email send, payment execute.
- shell is hard-blocked in v0.1.
- approval gates halt execution synchronously.
- policy violations are logged.

### Phase 7: Python bridge

Deliver:

- `use py.module as alias`
- import allowlist/denylist
- value converters
- exception wrapper
- Pandas adapter MVP
- NumPy/Torch/Transformers adapter stubs or optional tests

Acceptance:

- `use py.pandas as pd` works when allowed.
- dangerous modules/functions are denied before import resolution.
- Python exceptions become `INTHON_PYBRIDGE_*` errors.
- Python calls can be traced when configured.

### Phase 8: CLI and docs

Deliver:

- `inthon run`
- `inthon check`
- `inthon ast`
- `inthon ir`
- `inthon fmt` stub or simple formatter
- docs
- examples

Acceptance:

- time to first working program under 5 minutes.
- all MVP examples run or check successfully.
- documentation covers all MVP syntax.

---

## 7. Coding rules

Follow these rules on every change:

1. Make the smallest coherent change.
2. Add or update tests with every feature.
3. Add or update docs with every user-facing feature.
4. Add an example for every language feature.
5. Use structured error codes.
6. Do not silently swallow errors.
7. Keep runtime side effects policy-gated.
8. Keep trace emission synchronous in v0.1.
9. Prefer explicit, boring code over clever magic.
10. Never use unsafe shell execution as a shortcut.

---

## 8. Required public API

Implement this API:

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Any

@dataclass
class RunResult:
    output: Any
    trace_json: str
    cost_usd: float
    duration_ms: float
    errors: list[dict]

def parse(source: str, filename: str = "<stdin>"):
    ...

def check(source: str, filename: str = "<stdin>"):
    ...

def run(source: str, filename: str = "<stdin>", mock_tools: bool = True) -> RunResult:
    ...

def run_file(path: Path | str, mock_tools: bool = True, max_cost_usd: float = 1.0, max_runtime_sec: float = 300.0) -> RunResult:
    ...
```

---

## 9. Error code standard

Use this pattern:

```text
INTHON_PARSE_001:
Expected closing "}" for agent block.
File: examples/research.inth
Line: 14
Column: 1
Hint: Add "}" after the plan block.
```

Families:

- `INTHON_PARSE_*`
- `INTHON_SEM_*`
- `INTHON_TYPE_*`
- `INTHON_TOOL_*`
- `INTHON_POLICY_*`
- `INTHON_RUNTIME_*`
- `INTHON_PYBRIDGE_*`
- `INTHON_MEMORY_*`

---

## 10. Example programs that must ship

### `hello.inth`

```inth
let name = "INTHON"
return "Hello from " + name
```

### `tool_search.inth`

```inth
use tool web.search
results = web.search("agent programming language", limit: 3)
return results
```

### `csv_summary.inth`

```inth
use py.pandas as pd
df = pd.read_csv("sales.csv")
summary = df.describe()
return summary
```

### `agent_research.inth`

```inth
agent Researcher {
  goal "Research a topic and return sourced notes"
  use tool web.search
  use tool web.read
  policy {
    allow_network: true
    max_tool_calls: 10
  }
  plan {
    links = web.search("INTHON agent language", limit: 5)
    pages = web.read(links)
    notes = summarize(pages)
    return notes
  }
}
```

---

## 11. Definition of done

A phase is not done until:

- implementation exists
- unit tests exist
- integration tests exist where relevant
- documentation exists
- example program exists where relevant
- CLI path works where relevant
- error paths are tested
- trace/policy/security behavior is tested where relevant

The full v0.1 MVP is done when:

- all tests pass
- examples run or check
- parser coverage is above 90 percent
- runtime coverage is above 85 percent
- every execution emits trace JSON
- unregistered tools cannot execute
- unsafe Python imports cannot resolve
- approval gates block synchronously
- README lets a new user run a program in under 5 minutes

---

## 12. First response protocol

Before writing code, respond with:

1. a concise interpretation of the project
2. the repo tree you will create
3. the first 10 implementation tasks
4. the test command you will run after each phase
5. explicit confirmation that v0.1 will not include bytecode VM, arbitrary shell execution, or self-hosting compiler

Then begin implementation phase by phase.
