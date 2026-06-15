# INTHON End-to-End Build Plan

## Objective

Build INTHON v0.1 as a practical Python-hosted programming language for AI-native workflows. The MVP must parse `.inth` programs, execute basic language constructs, validate tool calls, enforce policy, interoperate safely with Python, emit replayable traces, expose a CLI, and ship with tests and docs.

## Product promise

INTHON converts agent intent into safe, compact, auditable execution.

## v0.1 scope

### Must have

- `.inth` source files
- package scaffold
- parser and AST
- semantic analyzer
- basic gradual type checking
- interpreter
- tool registry
- mock tools
- safe Python bridge
- policy engine
- trace logger
- CLI runner/checker
- examples
- docs
- tests

### Must not have

- bytecode VM
- self-hosted compiler
- distributed runtime
- arbitrary shell execution
- arbitrary API calling without schemas
- native tensor compiler
- full optimizer

## Milestone 0: Repository setup

### Deliverables

- package skeleton
- `pyproject.toml`
- `inthon.toml`
- README
- docs skeleton
- examples skeleton
- test skeleton
- CI workflow draft

### Tasks

- Create repo tree.
- Configure Hatchling or equivalent build backend.
- Add `lark`, `typer`, `rich`, `pydantic`, `jsonschema`, and `structlog` dependencies.
- Add dev dependencies: `pytest`, `pytest-cov`, `ruff`, `mypy`, `hypothesis`.
- Add `inthon/version.py`.
- Add placeholder public API in `inthon/__init__.py`.

### Acceptance

- `python -m pytest` runs.
- `python -c "import inthon"` works.
- `ruff check .` runs.

## Milestone 1: Lexer and parser

### Deliverables

- tokenizer
- token enum
- span model
- keyword map
- Lark grammar
- parser wrapper
- transformer skeleton
- parser unit tests

### Tasks

- Implement token definitions.
- Implement line/column/offset spans.
- Add keywords for language constructs.
- Implement comments, strings, numbers, identifiers, operators, delimiters.
- Add grammar for declarations, imports, functions, agent blocks, policy blocks, plan blocks, expressions, control flow, approval, retry, eval, guard, memory operations.
- Convert parse tree to AST.
- Add helpful parse errors.

### Acceptance

- Parses `hello.inth`.
- Parses `tool_search.inth`.
- Parses `agent_research.inth`.
- Parser coverage above 90 percent.

## Milestone 2: AST and semantic analyzer

### Deliverables

- frozen dataclass AST nodes
- visitor pattern
- AST printer
- scope chain
- symbol table
- semantic analyzer
- basic type checker
- permission analyzer skeleton

### Tasks

- Add nodes for program, imports, statements, expressions, functions, agents, policies, memory, retry, eval, approval.
- Add generic visitor.
- Add duplicate declaration detection.
- Add undefined name detection.
- Add tool/module use-before-import detection.
- Add policy-before-plan check for agents.
- Infer primitive literal types.

### Acceptance

- Semantic checks reject undefined identifiers.
- Semantic checks reject duplicate declarations.
- Tool/module calls require imports.
- Agent policy is analyzed before plan.

## Milestone 3: IR

### Deliverables

- IR node dataclasses
- AST-to-IR lowering
- IR JSON serializer
- static tool-call graph extraction

### Tasks

- Define `IRProgram`, `IRImport`, `IRAssign`, `IRReturn`, `IRCall`, `IRToolCall`, `IRPolicy`, `IRAgent`.
- Lower AST calls to tool calls when callee root is imported tool.
- Attach source spans.
- Serialize to JSON.
- Add CLI command `inthon ir`.

### Acceptance

- `inthon ir examples/tool_search.inth` returns valid JSON.
- Static tool calls can be listed before execution.

## Milestone 4: Runtime interpreter

### Deliverables

- execution context
- value model
- evaluator
- executor
- interpreter
- runtime errors
- trace logger
- sandbox limits

### Tasks

- Implement variable scopes.
- Evaluate literals, identifiers, unary, binary, calls, members, lists, dicts.
- Execute assignments, declarations, returns, functions.
- Add runtime state diffs to trace.
- Add timing and cost placeholders.
- Add error wrapping.

### Acceptance

- `inthon run examples/hello.inth` works.
- Function calls work.
- Runtime errors have structured codes.
- Every run emits trace JSON.

## Milestone 5: Tool registry

### Deliverables

- tool schema model
- tool registry
- validator
- built-in mock tools
- tool result model
- cost model

### Tasks

- Define `ToolSpec`, `ToolCall`, `ToolResult`, `ToolCostModel`.
- Register `web.search`, `web.read`, and test tools.
- Validate args before execution.
- Log every tool call.
- Block unregistered tools.
- Add deterministic mock outputs.

### Acceptance

- Unregistered tool returns `INTHON_TOOL_001`.
- Bad args return a structured schema error.
- Mock tools produce deterministic traces.

## Milestone 6: Policy and security

### Deliverables

- policy model
- capability enum
- policy engine
- approval gate
- audit log
- sandbox interface
- redaction utility

### Tasks

- Implement default deny for network, shell, filesystem write, email send, payment execute.
- Enforce tool side effects against policy.
- Enforce max tool calls and max cost.
- Implement synchronous approval gate.
- Redact secrets in traces.
- Add security tests.

### Acceptance

- Unauthorized network/tool access is blocked.
- Shell execution is hard-blocked.
- Approval gate halts execution.
- Audit log records policy checks.

## Milestone 7: Python bridge

### Deliverables

- safe importer
- allowlist/denylist
- converters
- exception wrapper
- adapter system
- Pandas adapter MVP

### Tasks

- Implement `use py.module as alias`.
- Deny `os`, `subprocess`, `builtins.eval`, `builtins.exec`, unsafe pickle usage by default.
- Allow configured modules.
- Convert primitives and collections both ways.
- Wrap Python exceptions in `INTHON_PYBRIDGE_*`.
- Trace Python calls when enabled.

### Acceptance

- Allowed import works.
- Denied import fails before resolution.
- Pandas read/describe demo can be checked or run if dependency exists.

## Milestone 8: CLI, docs, examples

### Deliverables

- `inthon run`
- `inthon check`
- `inthon ast`
- `inthon ir`
- `inthon fmt` stub
- docs
- examples
- quickstart

### Tasks

- Build Typer CLI.
- Format errors with Rich.
- Add JSON trace output flag.
- Write quickstart.
- Write language guide.
- Write security guide.
- Write tool guide.
- Add examples.

### Acceptance

- New user can run `hello.inth` in under 5 minutes.
- Docs cover all MVP syntax.
- All examples run or check.

## First 30-day plan

### Week 1

- Create repo.
- Write README.
- Define language spec draft.
- Implement lexer.
- Implement parser for variables/functions/imports.
- Add AST nodes.
- Add parser tests.

### Week 2

- Implement interpreter.
- Add runtime context.
- Add basic expressions.
- Add function execution.
- Add CLI `inthon run`.
- Add error formatting.

### Week 3

- Add tool registry.
- Add tool schema validation.
- Add mock tools.
- Add policy system.
- Add trace logger.
- Add `use tool`.

### Week 4

- Add Python bridge.
- Add Pandas demo.
- Add Transformers demo or optional stub.
- Add documentation.
- Add examples.
- Add end-to-end tests.

## Success metrics

### Developer metrics

- Time to first working program under 5 minutes.
- Parser test coverage above 90 percent.
- Runtime test coverage above 85 percent.
- Clear error messages for common mistakes.
- Documentation covers all MVP syntax.

### Agent metrics

- At least 30 percent fewer tokens than natural-language tool plans on benchmark tasks.
- At least 95 percent valid tool schema generation on benchmark tasks.
- At least 90 percent replay success rate.
- Full trace for every execution.

### Product metrics

- 10 example programs.
- 5 real or mock integrations.
- 3 benchmark reports.
- 1 public technical paper.

## Risk controls

| Risk | Control |
|---|---|
| Scope creep | Enforce v0.1 must-not-have list. |
| Unsafe Python interop | Default deny, allowlist, denylist, trace calls. |
| Parser complexity | Use Lark first, Tree-sitter later. |
| Runtime bugs | Add golden trace fixtures and replay tests. |
| Tool chaos | Tool schemas and mock tool registry before real integrations. |
| Weak docs | Docs required for each feature before done. |

## Final build strategy

Build small, testable layers. Do not build a giant perfect language first. The v0.1 win condition is a small language that safely and deterministically runs agent workflows with traceability.
