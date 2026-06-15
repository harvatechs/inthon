# Target Repository Tree

```text
inthon/
├── README.md
├── pyproject.toml
├── inthon.toml
├── CHANGELOG.md
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── docs/
│   ├── architecture.md
│   ├── language-spec.md
│   ├── runtime-spec.md
│   ├── tool-spec.md
│   ├── security.md
│   ├── python-interop.md
│   ├── data-ml.md
│   └── contributing.md
├── examples/
│   ├── hello.inth
│   ├── tool_search.inth
│   ├── csv_summary.inth
│   ├── agent_research.inth
│   ├── ml_inference.inth
│   └── approval_gate.inth
├── benchmarks/
│   ├── token_efficiency.py
│   ├── workflow_correctness.py
│   └── safety.py
├── inthon/
│   ├── __init__.py
│   ├── version.py
│   ├── cli.py
│   ├── lexer/
│   │   ├── __init__.py
│   │   ├── tokens.py
│   │   ├── keywords.py
│   │   └── tokenizer.py
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── grammar.lark
│   │   ├── parser.py
│   │   └── transformer.py
│   ├── ast/
│   │   ├── __init__.py
│   │   ├── nodes.py
│   │   ├── visitor.py
│   │   └── printer.py
│   ├── semantic/
│   │   ├── __init__.py
│   │   ├── scope.py
│   │   ├── analyzer.py
│   │   ├── type_checker.py
│   │   └── permissions.py
│   ├── ir/
│   │   ├── __init__.py
│   │   ├── nodes.py
│   │   ├── builder.py
│   │   └── serializer.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── context.py
│   │   ├── values.py
│   │   ├── evaluator.py
│   │   ├── executor.py
│   │   ├── interpreter.py
│   │   ├── trace.py
│   │   ├── sandbox.py
│   │   └── errors.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── schema.py
│   │   ├── validator.py
│   │   ├── registry.py
│   │   ├── builtin_tools.py
│   │   └── cost.py
│   ├── policy/
│   │   ├── __init__.py
│   │   ├── model.py
│   │   ├── engine.py
│   │   ├── approval.py
│   │   └── audit.py
│   ├── pybridge/
│   │   ├── __init__.py
│   │   ├── allowlist.py
│   │   ├── importer.py
│   │   ├── converter.py
│   │   ├── exception_wrap.py
│   │   └── adapters/
│   │       ├── __init__.py
│   │       ├── pandas_adapter.py
│   │       ├── numpy_adapter.py
│   │       ├── torch_adapter.py
│   │       └── transformers_adapter.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── store.py
│   │   ├── namespaces.py
│   │   └── ops.py
│   └── stdlib/
│       ├── agent.inth
│       ├── data.inth
│       ├── ml.inth
│       ├── memory.inth
│       └── eval.inth
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_lexer.py
    │   ├── test_parser.py
    │   ├── test_ast.py
    │   ├── test_semantic.py
    │   ├── test_type_checker.py
    │   ├── test_ir.py
    │   ├── test_interpreter.py
    │   ├── test_tools.py
    │   ├── test_policy.py
    │   ├── test_pybridge.py
    │   └── test_memory.py
    ├── integration/
    │   ├── test_hello.py
    │   ├── test_agent_workflow.py
    │   ├── test_tool_call_pipeline.py
    │   └── test_python_interop.py
    └── fixtures/
        ├── programs/
        └── traces/
```
