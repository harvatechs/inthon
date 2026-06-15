# Source Map

This build pack distills the uploaded INTHON project documents into implementation prompts and engineering files.

## `INTHON_PRD.pdf`

Used for:

- product definition
- vision and target users
- v0.1 MVP scope
- non-goals
- syntax examples
- architecture overview
- repository structure
- tool system requirements
- Python interop requirements
- security model
- observability requirements
- standard library functions
- package manager commands
- engineering milestones
- AI agent prompts
- first 30-day build plan
- success metrics

## `INTHON_ENGINE.pdf`

Used for:

- hard runtime invariants
- authoritative v0.1 build decisions
- full repository/module layout
- lexer subsystem details
- parser subsystem details
- AST design
- semantic analysis pass order
- type system strategy
- IR requirements
- runtime engine
- tool registry
- Python bridge
- agent runtime
- memory subsystem
- policy/security engine
- observability engine
- CLI architecture
- testing infrastructure
- performance targets

## `INTHON_PAPER.pdf`

Used for:

- research thesis
- design goals
- language philosophy
- formal syntax and semantics
- type system rationale
- tool system architecture
- capability-based security model
- Python interoperability rationale
- evaluation plan
- limitations and future work

## `INTHON_KIMI_REF.pdf`

Used for:

- market/technical feasibility
- competitive positioning
- implementation strategy
- parser strategy validation
- Tree-sitter/LSP/Rust future roadmap
- type system and Python bridge feasibility
- capability-based security context
- complementarity with MCP/LangChain/Pydantic-style ecosystems

## Decision hierarchy

When sources conflict:

1. Engineering implementation decisions: `INTHON_ENGINE.pdf`
2. Product scope and roadmap: `INTHON_PRD.pdf`
3. Research framing and design goals: `INTHON_PAPER.pdf`
4. External feasibility and market strategy: `INTHON_KIMI_REF.pdf`
