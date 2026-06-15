# INTHON Architecture

## High-level pipeline

```text
Source Program (.inth)
  -> Lex + Parse
  -> AST
  -> Semantic Pass
  -> Type Check
  -> IR
  -> Permission Check
  -> Interpreter / Transpiler / Planner
  -> Execution Context
  -> Values + Tools + PyBridge
  -> Trace + Result
```

## v0.1 backend

The v0.1 backend is a Python tree-walking interpreter. It may produce IR for analysis and future backends, but it does not require a bytecode VM.

## Core modules

### `lexer/`

Transforms source text into tokens with spans.

Files:

- `tokens.py`
- `keywords.py`
- `tokenizer.py`

### `parser/`

Parses source into AST using Lark and a custom transformer.

Files:

- `grammar.lark`
- `parser.py`
- `transformer.py`

### `ast/`

Defines immutable syntax nodes and visitor utilities.

Files:

- `nodes.py`
- `visitor.py`
- `printer.py`

### `semantic/`

Validates names, scopes, imports, type hints, and permissions.

Files:

- `scope.py`
- `analyzer.py`
- `type_checker.py`
- `permissions.py`

### `ir/`

Defines a simpler JSON-serializable representation for analysis and future execution targets.

Files:

- `nodes.py`
- `builder.py`
- `serializer.py`

### `runtime/`

Executes programs and emits traces.

Files:

- `context.py`
- `values.py`
- `evaluator.py`
- `executor.py`
- `interpreter.py`
- `trace.py`
- `sandbox.py`
- `errors.py`

### `tools/`

Registers tools, validates schemas, estimates cost, and executes tool calls.

Files:

- `schema.py`
- `validator.py`
- `registry.py`
- `builtin_tools.py`
- `cost.py`

### `policy/`

Enforces capabilities, approval gates, and audit logging.

Files:

- `model.py`
- `engine.py`
- `approval.py`
- `audit.py`

### `pybridge/`

Allows safe Python interoperability.

Files:

- `allowlist.py`
- `importer.py`
- `converter.py`
- `exception_wrap.py`
- `adapters/`

### `memory/`

Implements memory namespaces and operations.

Files:

- `store.py`
- `namespaces.py`
- `ops.py`

### `stdlib/`

Ships agent-native standard helpers written in INTHON.

Files:

- `agent.inth`
- `data.inth`
- `ml.inth`
- `memory.inth`
- `eval.inth`

## Execution context

Minimum fields:

```python
@dataclass
class ExecutionContext:
    filename: str
    scopes: ScopeStack
    tools: ToolRegistry
    policy: PolicyEngine
    pybridge: PyBridge
    memory: MemoryStore
    tracer: TraceLogger
    sandbox: Sandbox
    cost_usd: float
    errors: list[dict]
```

## Trace event model

Minimum fields:

```json
{
  "event_id": "evt_001",
  "run_id": "run_123",
  "type": "tool_call",
  "timestamp": "...",
  "span": {"file": "app.inth", "line": 1, "col": 1},
  "data": {},
  "state_diff": {},
  "cost_delta": 0.0
}
```

## Public API

```python
def parse(source: str, filename: str = "<stdin>"): ...
def check(source: str, filename: str = "<stdin>"): ...
def run(source: str, filename: str = "<stdin>", mock_tools: bool = True): ...
def run_file(path, mock_tools: bool = True, max_cost_usd: float = 1.0, max_runtime_sec: float = 300.0): ...
```

## CLI commands

```bash
inthon run app.inth
inthon check app.inth
inthon ast app.inth
inthon ir app.inth
inthon fmt app.inth
inthon trace run_id
inthon repl
```

## Data flow for tool calls

1. Parser recognizes `web.search(...)` as a call expression.
2. Semantic analyzer confirms `web` came from `use tool web.search`.
3. IR builder lowers the call into `IRToolCall`.
4. Policy engine checks required capability.
5. Tool registry confirms the tool exists.
6. Validator checks input schema.
7. Cost model estimates cost.
8. Approval gate blocks if needed.
9. Tool executes.
10. Result is converted to INTHON value.
11. Trace logger records call and result summary.

## Data flow for Python imports

1. Parser recognizes `use py.pandas as pd`.
2. Semantic analyzer creates alias symbol `pd`.
3. PyBridge checks denylist before import.
4. PyBridge checks allowlist/policy.
5. Importer loads module.
6. Adapter wraps module if available.
7. Calls are converted and traced.
8. Exceptions are wrapped into INTHON errors.
