# INTHON AI Build Pack

This pack is designed to let an AI coding agent build INTHON end to end as a practical v0.1 language implementation, not a fantasy architecture dump.

## Start here

1. Paste `MASTER_PROMPT.md` into your AI coding agent.
2. Give it the uploaded source docs: `INTHON_PRD.pdf`, `INTHON_ENGINE.pdf`, `INTHON_PAPER.pdf`, and `INTHON_KIMI_REF.pdf`.
3. Tell the agent to create the repository from `FILE_TREE.md`.
4. Execute the phases in `PLAN.md` and the work orders in `TASKS.md`.
5. Use `AGENT.md` if you want a multi-agent workflow.
6. Use `PROMPT_CHAIN.md` if your AI tool works best with short sequential prompts.

## What this pack contains

- `MASTER_PROMPT.md` - the main prompt for an AI coding agent.
- `PLAN.md` - milestone plan, 30-day plan, scope, risks, and success metrics.
- `AGENT.md` - multi-agent roles and handoff protocol.
- `PROJECT_CONTEXT.md` - distilled project context from the research and PRD.
- `REVERSE_ENGINEERING_PYTHON.md` - how to use Python/CPython as an architectural blueprint without copying it.
- `SPEC.md` - v0.1 language spec.
- `ARCHITECTURE.md` - module architecture and execution pipeline.
- `FILE_TREE.md` - target repository layout.
- `TASKS.md` - issue-ready engineering backlog.
- `SECURITY.md` - default-deny security model and Python bridge rules.
- `TESTING.md` - test strategy and acceptance thresholds.
- `EVALS.md` - benchmark plan for token efficiency, workflow correctness, and safety.
- `ACCEPTANCE_CRITERIA.md` - final quality gates.
- `PROMPT_CHAIN.md` - phase-by-phase prompts.
- `AI_WORKFLOW.yaml` - machine-readable agent workflow.
- `SOURCE_MAP.md` - where the build pack draws from the uploaded project docs.
- `examples/` - seed `.inth` programs.
- `templates/` - reusable feature, bug, and AI handoff templates.

## Build principle

Build INTHON in layers:

1. Language core
2. Runtime
3. Tool system
4. Python bridge
5. Agent syntax
6. Data/ML adapters
7. Security
8. Developer tools
9. Benchmarks
10. Production runtime

The winning move is to build a small language that does one thing extremely well: convert agent intent into safe, compact, auditable execution.
