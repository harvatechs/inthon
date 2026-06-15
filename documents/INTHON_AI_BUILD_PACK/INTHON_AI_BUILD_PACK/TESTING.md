# INTHON Testing Strategy

## Test philosophy

A language runtime without tests is a haunted vending machine. Every feature must ship with tests.

## Required commands

```bash
python -m pytest
python -m pytest --cov=inthon
ruff check .
mypy inthon
```

## Coverage targets

- Parser: 90 percent+
- Runtime: 85 percent+
- Tooling: 90 percent+
- Policy/security: 90 percent+

## Unit test groups

### Lexer tests

- literals
- identifiers
- keywords
- operators
- delimiters
- comments
- spans
- unexpected character errors

### Parser tests

- variables/constants
- type annotations
- functions
- imports
- tool calls
- Python imports
- agent blocks
- policy blocks
- plan blocks
- approval gates
- retry/catch
- eval
- guard
- memory operations
- syntax errors

### AST tests

- frozen dataclasses
- span preservation
- visitor traversal
- printer output

### Semantic tests

- undefined identifiers
- duplicate declarations
- const reassignment
- imports required before tool/module use
- policy before plan
- basic type inference

### IR tests

- AST lowering
- tool-call extraction
- JSON serialization
- source span preservation

### Runtime tests

- literals
- variables
- assignments
- binary expressions
- function calls
- returns
- errors
- trace emission
- sandbox timeout

### Tool tests

- registered tool execution
- unregistered tool denial
- schema validation
- mock tools
- cost estimation
- tool call logging

### Policy tests

- default deny
- allowed network
- denied network
- denied shell
- approval gate
- max tool calls
- max cost
- audit log

### Python bridge tests

- allowed import
- denied import
- alias import
- value conversion
- exception wrapping
- Pandas adapter if dependency installed

### Memory tests

- remember
- recall
- forget
- namespaces
- logging

## Integration tests

- `hello.inth`
- `tool_search.inth`
- `csv_summary.inth`
- `agent_research.inth`
- `approval_gate.inth`
- tool call pipeline
- Python interop pipeline
- policy violation pipeline

## Golden traces

For each integration program, store an expected trace pattern in `tests/fixtures/traces/`.

Golden traces should assert:

- run ID exists
- source hash exists
- parse/check/run events exist
- tool calls logged
- policy checks logged
- errors logged
- final result logged

Do not require timestamps to match exactly.

## Property-based parser tests

Use Hypothesis for:

- identifier generation
- integer/float literal generation
- string literal escaping
- simple arithmetic expression generation
- balanced block generation

## Regression test rule

Every bug fix must add a regression test that fails before the fix and passes after it.
