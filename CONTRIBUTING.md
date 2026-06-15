# Contributing to INTHON

Thank you for your interest in contributing to INTHON! As a new programming language layer optimized for AI agents, we want to maintain the highest standards of safety, token efficiency, and clean code.

This document guides you through setting up your environment, coding standards, testing, and submitting your contributions.

---

## 1. Getting Started

### Prerequisites
* **Python**: `3.11`, `3.12`, `3.13`, or `3.14`
* **Package Manager**: `pip` (or `uv` for ultra-fast installs)
* **Git**

### Local Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/harvatechs/inthon.git
   cd inthon
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Unix/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies in development mode**:
   We recommend installing with all developer, data science, and machine learning extras:
   ```bash
   pip install -e .[dev,data,ml]
   ```

---

## 2. Repository Architecture

Before writing code, familiarize yourself with our module breakdown:
* [ast/](file:///e:/AITHON/inthon/ast/) — Immutable AST Node definitions and structural visitors.
* [lexer/](file:///e:/AITHON/inthon/lexer/) — Lexical analysis, tokens, and LALR tokenizer integration.
* [parser/](file:///e:/AITHON/inthon/parser/) — Lark EBNF parser grammar files and parse-tree transformers.
* [ir/](file:///e:/AITHON/inthon/ir/) — Lowered Intermediate Representation AST definitions and JSON serialization.
* [semantic/](file:///e:/AITHON/inthon/semantic/) — Static Analyzer, scope checker, type validator, and import resolver.
* [policy/](file:///e:/AITHON/inthon/policy/) — Execution Policy configurations and Human-in-the-loop (HITL) approval gateways.
* [pybridge/](file:///e:/AITHON/inthon/pybridge/) — Import hooks and proxy objects for sandboxed execution of external Python libraries.
* [runtime/](file:///e:/AITHON/inthon/runtime/) — Execution context and AST-walking interpreter.
* [tools/](file:///e:/AITHON/inthon/tools/) — System and custom tool schemas, calling contracts, and schema validators.

---

## 3. Style & Quality Guidelines

We enforce strict linting, formatting, and static typing to maintain codebase health.

### Code Formatting & Linting
We use **Ruff** for fast linting and formatting. Always format your files before pushing:
```bash
# Run syntax/formatting checks
python -m ruff check .

# Apply auto-fixes
python -m ruff check --fix .

# Format code
python -m ruff format .
```

### Static Type Checking
All core code must be type annotated. We run **Mypy** with strict settings:
```bash
python -m mypy inthon/
```
Ensure that no new typing errors are introduced by your changes.

---

## 4. Testing & Verification

Every feature, language primitive, or parser update must be backed by unit tests.

### Running Tests
We use **pytest** to orchestrate tests.
```bash
# Run the complete test suite
python -m pytest

# Run with coverage reports
python -m pytest --cov=inthon --cov-report=term-missing
```

### Writing Tests
* Place tests under the [tests/](file:///e:/AITHON/tests/) directory.
* Prefix test file names with `test_` (e.g. `test_semantic_analyzer.py`).
* Use `hypothesis` for property-based testing of core components where applicable.

---

## 5. Development Workflows & PRs

We follow a typical Git feature branch workflow:

1. **Branch Naming**: Use clean, descriptive names:
   * `feature/some-feature-name`
   * `bugfix/issue-description`
   * `docs/refactor-readmes`

2. **Commit Messages**: Write concise, professional commit messages. We recommend following Conventional Commits (e.g. `feat: add exponential backoff to retry blocks`).

3. **Submitting a Pull Request**:
   * Ensure all tests pass (`pytest`) and code style checks succeed (`ruff`, `mypy`).
   * Create a Pull Request against the `main` branch.
   * Fill out the Pull Request template completely.
   * A project maintainer will review your code. Address any requested changes promptly.
