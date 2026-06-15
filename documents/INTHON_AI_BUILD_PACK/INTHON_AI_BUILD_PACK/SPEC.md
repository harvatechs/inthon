# INTHON v0.1 Language Specification

## Status

Draft implementation specification for v0.1-alpha.

## File extension

`.inth`

## Package file

`inthon.toml`

## Comments

```inth
// Single-line comment

/*
Multi-line comment
*/
```

## Primitive types

- `int`
- `float`
- `bool`
- `str`
- `bytes`
- `none`
- `any`

## Collection types

- `list[T]`
- `dict[K, V]`
- `tuple[T...]`
- `set[T]`

## Agent-specific types

- `Goal`
- `Plan`
- `ToolCall`
- `ToolResult`
- `Trace`
- `MemoryRef`
- `Approval`
- `Policy`
- `Prompt`
- `Embedding`
- `VectorStore`
- `DataFrame`
- `Tensor`
- `Model`
- `Dataset`

## Variables and constants

```inth
let x = 10
let name: str = "INTHON"
const MAX_RETRIES = 3
```

Constants cannot be reassigned.

## Functions

```inth
fn add(a: int, b: int) -> int {
  return a + b
}
```

## Imports

### Tool import

```inth
use tool web.search
```

### Python import

```inth
use py.pandas as pd
use py.numpy as np
```

### Memory import

```inth
use memory.project("research")
```

## Agent block

```inth
agent Assistant {
  goal "Complete user task safely"

  policy {
    allow_network: false
    allow_shell: false
    max_tool_calls: 10
  }

  plan {
    return "done"
  }
}
```

Agent execution order:

1. parse agent block
2. validate imports
3. evaluate policy
4. execute plan
5. emit trace

## Policy block

Policy blocks declare capabilities and limits.

```inth
policy {
  allow_network: true
  allow_filesystem: read_only
  allow_shell: false
  max_runtime_sec: 60
  max_cost_usd: 0.25
}
```

Default deny applies to dangerous capabilities.

## Tool calls

```inth
results = web.search("best parser generators", limit: 5)
```

Tool call semantics:

1. tool must be imported
2. tool must be registered
3. arguments must validate against schema
4. side effects must be allowed by policy
5. cost must be under budget or require approval
6. call must be logged
7. result must be structured

## Approval gates

```inth
draft = email.compose(to: "client@example.com", subject: "Update", body: body)
approve draft before send
email.send(draft)
```

Approval gates halt execution synchronously.

## Retry

```inth
retry 3 with backoff exponential {
  data = api.get("/reports/latest")
} catch err {
  log.error(err)
  return fail("Could not fetch report")
}
```

## Eval

```inth
eval answer against rubric {
  accuracy >= 0.95
  max_length <= 2000
}
```

## Guard

```inth
guard no_pii_leak
guard max_tool_calls <= 10
```

Guard failure terminates execution with a structured error.

## Memory

```inth
remember summary in memory.project
facts = recall "pricing model" from memory.project
forget "outdated source" from memory.project
```

Memory rules:

- writes are explicit
- deletes are supported
- operations are logged
- namespaces are explicit
- sensitive memory requires approval when persistent

## Expressions

Supported v0.1 expression forms:

- literals
- identifiers
- binary ops: `+`, `-`, `*`, `/`, `%`, `**`
- comparison ops: `==`, `!=`, `<`, `<=`, `>`, `>=`
- boolean ops: `and`, `or`, `not`
- calls
- member access
- indexing
- lists
- dicts

## Error standard

```text
INTHON_PARSE_001:
Expected closing "}" for agent block.
File: examples/research.inth
Line: 14
Column: 1
Hint: Add "}" after the plan block.
```

## Execution result

Every run returns:

```json
{
  "output": null,
  "trace_json": "...",
  "cost_usd": 0.0,
  "duration_ms": 0.0,
  "errors": []
}
```
