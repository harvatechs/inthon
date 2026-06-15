# INTHON Acceptance Criteria

## v0.1 MVP is accepted only if all gates pass.

## Gate 1: Repository

- [ ] Package installs in editable mode.
- [ ] `import inthon` works.
- [ ] CLI entrypoint exists.
- [ ] Docs and examples exist.

## Gate 2: Parser

- [ ] `hello.inth` parses.
- [ ] `tool_search.inth` parses.
- [ ] `agent_research.inth` parses.
- [ ] Helpful parse errors include code, file, line, column, hint.
- [ ] Parser coverage above 90 percent.

## Gate 3: Semantics

- [ ] Undefined variables rejected.
- [ ] Duplicate declarations rejected.
- [ ] Const reassignment rejected.
- [ ] Tool/module usage before import rejected.
- [ ] Agent policy analyzed before plan.

## Gate 4: Runtime

- [ ] `hello.inth` runs.
- [ ] variables and assignments work.
- [ ] functions work.
- [ ] returns work.
- [ ] runtime coverage above 85 percent.
- [ ] every execution emits trace JSON.

## Gate 5: Tool system

- [ ] registered mock tools execute.
- [ ] unregistered tools never execute.
- [ ] args validated before execution.
- [ ] side effects checked before execution.
- [ ] tool calls logged.

## Gate 6: Policy/security

- [ ] default deny enforced.
- [ ] unauthorized network blocked.
- [ ] unauthorized filesystem write blocked.
- [ ] shell hard-blocked.
- [ ] approval gate halts synchronously.
- [ ] secrets redacted in traces.

## Gate 7: Python bridge

- [ ] allowed Python import works.
- [ ] denied Python import fails before import resolution.
- [ ] values convert both ways.
- [ ] Python exceptions become structured INTHON errors.
- [ ] Pandas demo works or is skipped cleanly when dependency missing.

## Gate 8: CLI

- [ ] `inthon run` works.
- [ ] `inthon check` works.
- [ ] `inthon ast` works.
- [ ] `inthon ir` works.
- [ ] `inthon fmt` exists.

## Gate 9: Documentation

- [ ] README quickstart works.
- [ ] language syntax documented.
- [ ] tool calling documented.
- [ ] Python interop documented.
- [ ] security model documented.
- [ ] all examples documented.

## Gate 10: Benchmarks

- [ ] token efficiency benchmark exists.
- [ ] workflow correctness benchmark exists.
- [ ] safety benchmark exists.
- [ ] benchmark results serialize to JSON.

## Final acceptance command set

```bash
python -m pytest --cov=inthon
ruff check .
mypy inthon
inthon check examples/hello.inth
inthon run examples/hello.inth
inthon ast examples/agent_research.inth
inthon ir examples/agent_research.inth
```

## Reject release if

- any tool can bypass schema validation
- any side effect can bypass policy
- dangerous Python import resolves before denylist check
- approval gate can be skipped
- traces are missing for successful runs
- docs do not let a new user run a program
- tests are missing for a feature
