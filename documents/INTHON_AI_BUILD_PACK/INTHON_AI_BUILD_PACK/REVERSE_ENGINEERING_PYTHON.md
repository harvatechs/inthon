# Reverse-Engineering Python as a Blueprint for INTHON

## Purpose

This document explains how to use Python's language/runtime architecture as a learning blueprint for building INTHON without copying CPython implementation code.

The goal is not to clone Python. The goal is to reverse-engineer the creation process of a language like Python and apply the same layered thinking to a new AI-agent language.

## Rule of clean-room implementation

You may study public concepts, behavior, docs, and architecture. You must not copy CPython source code into INTHON. Implement INTHON from its own spec.

## Python creation process to emulate

### 1. Define the philosophy

Python chose readability, simple syntax, batteries included, and broad interoperability.

INTHON chooses compactness, deterministic tool calling, auditability, safety, and Python compatibility.

### 2. Define source files and package format

Python has `.py` files and package metadata. INTHON has `.inth` files and `inthon.toml`.

### 3. Build lexical analysis

Python source becomes tokens. INTHON source becomes tokens with precise spans.

Implementation target:

- `inthon/lexer/tokens.py`
- `inthon/lexer/keywords.py`
- `inthon/lexer/tokenizer.py`

Minimum token categories:

- literals
- identifiers
- keywords
- operators
- delimiters
- comments
- EOF
- source spans

### 4. Build grammar and parser

Python has a formal grammar. INTHON v0.1 uses Lark grammar.

Implementation target:

- `inthon/parser/grammar.lark`
- `inthon/parser/parser.py`
- `inthon/parser/transformer.py`

Parse into AST immediately. Do not let the rest of the system depend on parser-library internals.

### 5. Build AST

Python exposes an AST model. INTHON needs its own AST with frozen dataclasses and spans.

Implementation target:

- `inthon/ast/nodes.py`
- `inthon/ast/visitor.py`
- `inthon/ast/printer.py`

AST design rules:

- immutable nodes
- explicit source spans
- visitor traversal
- no random dictionaries as syntax trees

### 6. Build symbol and semantic analysis

Python resolves scopes and names. INTHON must resolve variables, functions, tools, Python modules, agents, and policy capabilities.

Implementation target:

- `inthon/semantic/scope.py`
- `inthon/semantic/analyzer.py`
- `inthon/semantic/type_checker.py`
- `inthon/semantic/permissions.py`

Checks:

- duplicate declarations
- undefined names
- use-before-import
- const reassignment
- agent policy before plan
- required capabilities

### 7. Build intermediate representation

Python lowers to bytecode. INTHON v0.1 should lower to a simpler IR for static analysis, tool-call graphs, permission checks, cost estimation, replay, and future backends.

Implementation target:

- `inthon/ir/nodes.py`
- `inthon/ir/builder.py`
- `inthon/ir/serializer.py`

v0.1 IR does not need to be executable bytecode.

### 8. Build evaluation runtime

Python has an evaluation loop. INTHON v0.1 uses a tree-walking interpreter.

Implementation target:

- `inthon/runtime/context.py`
- `inthon/runtime/evaluator.py`
- `inthon/runtime/executor.py`
- `inthon/runtime/interpreter.py`
- `inthon/runtime/values.py`

Runtime responsibilities:

- execute statements
- evaluate expressions
- manage scopes
- call functions
- dispatch tools only through registry
- call Python only through safe bridge
- emit traces
- enforce sandbox limits

### 9. Build import and module system

Python uses `import`. INTHON uses:

```inth
use tool web.search
use py.pandas as pd
use memory.project("research")
```

Implementation target:

- tools import through `ToolRegistry`
- Python import through `PyBridge`
- memory namespace through `MemoryStore`

### 10. Build standard library

Python became powerful because of its standard library. INTHON needs a small agent-native stdlib first.

Implementation target:

- `stdlib/agent.inth`
- `stdlib/data.inth`
- `stdlib/ml.inth`
- `stdlib/memory.inth`
- `stdlib/eval.inth`

### 11. Build CLI and tooling

Python has `python file.py`, package tools, formatters, linters. INTHON needs:

```bash
inthon run app.inth
inthon check app.inth
inthon ast app.inth
inthon ir app.inth
inthon trace run_id
inthon fmt app.inth
inthon repl
```

Implementation target:

- `inthon/cli.py`

### 12. Build tests and benchmarks

Python has a huge test suite. INTHON should start with disciplined tests.

Test categories:

- lexer tests
- parser tests
- AST tests
- semantic tests
- IR tests
- runtime tests
- tool tests
- policy tests
- Python bridge tests
- memory tests
- integration examples
- golden traces
- security benchmarks

## CPython-to-INTHON mapping

| CPython layer | What to learn | INTHON layer |
|---|---|---|
| tokenizer | source-to-token discipline | lexer |
| grammar | formal syntax definition | parser grammar |
| ast module | structured syntax tree | AST dataclasses |
| symtable | scope resolution | semantic scope |
| compiler pipeline | multi-stage validation | semantic + IR |
| eval loop | runtime state machine | interpreter |
| importlib | controlled module loading | pybridge importer |
| exceptions | rich error hierarchy | structured error codes |
| trace/profile | observability hooks | TraceLogger |
| stdlib | useful primitives | stdlib + tools |
| unittest/regression tests | stability culture | pytest + golden traces |

## Recommended learning tasks for AI agent

1. Summarize how Python source becomes executable behavior.
2. Create a minimal tokenizer for INTHON.
3. Create a minimal grammar for INTHON.
4. Create AST nodes.
5. Create semantic checks.
6. Create an interpreter for expressions and statements.
7. Add a tool registry.
8. Add policy checks.
9. Add Python bridge.
10. Add CLI and tests.

## Avoid these mistakes

- Do not start with bytecode.
- Do not attempt self-hosting.
- Do not make arbitrary Python callable by default.
- Do not let tools bypass schema validation.
- Do not use JSON as the only language representation.
- Do not skip docs.
- Do not skip tests.
- Do not copy CPython source.
