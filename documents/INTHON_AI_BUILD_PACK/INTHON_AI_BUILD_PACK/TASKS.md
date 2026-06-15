# INTHON Engineering Tasks

Use these as issue-ready tasks for an AI coding agent.

## Phase 0: Setup

- [ ] Create package skeleton.
- [ ] Add `pyproject.toml`.
- [ ] Add `inthon.toml`.
- [ ] Add `README.md` quickstart.
- [ ] Add docs skeleton.
- [ ] Add examples skeleton.
- [ ] Add tests folders.
- [ ] Add CI workflow.
- [ ] Add public API stubs.

## Phase 1: Lexer

- [ ] Define `Span` dataclass.
- [ ] Define `Token` dataclass.
- [ ] Define `TokenType` enum.
- [ ] Define keyword map.
- [ ] Implement tokenizer.
- [ ] Support numbers, strings, bool, none.
- [ ] Support comments.
- [ ] Support operators and delimiters.
- [ ] Emit EOF.
- [ ] Emit line/column/offset spans.
- [ ] Add lexer tests.

## Phase 2: Parser

- [ ] Add Lark grammar.
- [ ] Add parser wrapper.
- [ ] Add transformer.
- [ ] Parse variables/constants.
- [ ] Parse assignments.
- [ ] Parse function declarations.
- [ ] Parse imports.
- [ ] Parse agent blocks.
- [ ] Parse policy blocks.
- [ ] Parse plan blocks.
- [ ] Parse expressions.
- [ ] Parse approval gates.
- [ ] Parse retry blocks.
- [ ] Parse eval blocks.
- [ ] Parse guard clauses.
- [ ] Parse memory operations.
- [ ] Add parser error formatting.
- [ ] Add parser tests.

## Phase 3: AST

- [ ] Define root `Program`.
- [ ] Define statement nodes.
- [ ] Define expression nodes.
- [ ] Define type expression nodes.
- [ ] Define agent/policy/plan nodes.
- [ ] Define memory/eval/retry/approval nodes.
- [ ] Add visitor.
- [ ] Add AST printer.
- [ ] Add AST tests.

## Phase 4: Semantic analysis

- [ ] Implement symbol model.
- [ ] Implement scope chain.
- [ ] Implement duplicate declaration detection.
- [ ] Implement undefined name detection.
- [ ] Implement tool import tracking.
- [ ] Implement Python module alias tracking.
- [ ] Implement const reassignment check.
- [ ] Implement agent policy-before-plan check.
- [ ] Implement basic type inference.
- [ ] Implement permission analyzer skeleton.
- [ ] Add semantic tests.

## Phase 5: IR

- [ ] Define IR nodes.
- [ ] Add AST-to-IR builder.
- [ ] Add tool call extraction.
- [ ] Add policy extraction.
- [ ] Add source spans.
- [ ] Add JSON serializer.
- [ ] Add IR CLI output.
- [ ] Add IR tests.

## Phase 6: Runtime

- [ ] Implement runtime values.
- [ ] Implement execution context.
- [ ] Implement scope stack.
- [ ] Implement evaluator.
- [ ] Implement executor.
- [ ] Implement return control flow.
- [ ] Implement interpreter entrypoint.
- [ ] Implement runtime errors.
- [ ] Implement sandbox time limit.
- [ ] Add runtime tests.

## Phase 7: Trace logging

- [ ] Define trace event model.
- [ ] Add run ID.
- [ ] Record source hash.
- [ ] Record parse/check/execution events.
- [ ] Record state diffs.
- [ ] Record tool calls.
- [ ] Record policy checks.
- [ ] Record errors.
- [ ] Serialize to JSON.
- [ ] Add golden trace tests.

## Phase 8: Tool registry

- [ ] Define `ToolSpec`.
- [ ] Define `ToolCall`.
- [ ] Define `ToolResult`.
- [ ] Define `ToolCostModel`.
- [ ] Implement registry.
- [ ] Implement validator.
- [ ] Implement built-in mock `web.search`.
- [ ] Implement built-in mock `web.read`.
- [ ] Implement cost estimation.
- [ ] Enforce tool registration.
- [ ] Add tool tests.

## Phase 9: Policy and security

- [ ] Define capabilities.
- [ ] Define policy model.
- [ ] Implement default deny.
- [ ] Enforce network policy.
- [ ] Enforce filesystem policy.
- [ ] Hard-block shell.
- [ ] Enforce max tool calls.
- [ ] Enforce max cost.
- [ ] Implement approval gate.
- [ ] Implement audit log.
- [ ] Implement redaction helpers.
- [ ] Add security tests.

## Phase 10: Python bridge

- [ ] Implement denylist.
- [ ] Implement allowlist.
- [ ] Implement safe importer.
- [ ] Implement alias binding.
- [ ] Convert INTHON primitive values to Python.
- [ ] Convert Python primitive values to INTHON.
- [ ] Convert lists/dicts.
- [ ] Wrap Python exceptions.
- [ ] Trace Python calls.
- [ ] Add Pandas adapter.
- [ ] Add NumPy adapter stub.
- [ ] Add Torch adapter stub.
- [ ] Add Transformers adapter stub.
- [ ] Add pybridge tests.

## Phase 11: Memory

- [ ] Define memory namespaces.
- [ ] Implement `MemoryStore`.
- [ ] Implement `InMemoryStore`.
- [ ] Implement remember.
- [ ] Implement recall.
- [ ] Implement forget.
- [ ] Log memory operations.
- [ ] Add memory tests.

## Phase 12: CLI

- [ ] Build Typer app.
- [ ] Add `inthon run`.
- [ ] Add `inthon check`.
- [ ] Add `inthon ast`.
- [ ] Add `inthon ir`.
- [ ] Add `inthon fmt` stub.
- [ ] Add JSON trace flag.
- [ ] Add Rich error output.
- [ ] Add CLI tests.

## Phase 13: Docs and examples

- [ ] Write quickstart.
- [ ] Write language guide.
- [ ] Write runtime guide.
- [ ] Write tool guide.
- [ ] Write Python interop guide.
- [ ] Write security guide.
- [ ] Write contribution guide.
- [ ] Add `hello.inth`.
- [ ] Add `tool_search.inth`.
- [ ] Add `csv_summary.inth`.
- [ ] Add `agent_research.inth`.
- [ ] Add `approval_gate.inth`.

## Phase 14: Benchmarks

- [ ] Build token efficiency benchmark.
- [ ] Build workflow correctness benchmark.
- [ ] Build safety benchmark.
- [ ] Compare natural language vs JSON vs Python vs INTHON.
- [ ] Measure tool-call correctness.
- [ ] Measure replay success.
- [ ] Write benchmark report.

## Phase 15: Release

- [ ] Run full tests.
- [ ] Run lint.
- [ ] Run type checks.
- [ ] Verify docs.
- [ ] Verify examples.
- [ ] Create changelog.
- [ ] Tag v0.1-alpha.
