# Release Notes — INTHON v1.0.1 (Patch Release)

We are proud to release **INTHON v1.0.1**, a patch release that fixes compatibility regressions, improves REPL statefulness, and hardens the secure subprocess execution sandbox.

---

## 🚀 Key Improvements & Bug Fixes

### 1. Core Language API & AST Enhancements
- **Program Node Constructor**: Added a custom `__init__` constructor supporting the legacy `body` keyword arguments alongside the new `statements` parameter to prevent crashes when loading compiled programs.
- **AST Visitor**: Restored the `ASTVisitor` helper class to ease walking AST nodes for custom tools and compile-time checkers.
- **Exceptions & Aliases**: Added missing compatibility class mappings (including `PyBridgeError` and `InthonTypeError_`) to standardise semantic exception raises.

### 2. Stateful REPL Sessions
- Pass active `ExecutionContext` references to `SemanticAnalyzer` during REPL evaluation steps.
- Programmatically map active runtime variables into the static analysis scope chain, preventing undefined variable warnings on subsequent lines.
- Updated bytecode execution loop to use the correct `InthonVM.run_code` API.

### 3. Strict Sandbox Hardening
- Attribute access checks using `is_safe_attribute_access` are now fully applied on proxied objects, preventing dunder-based introspection leaks (like `__class__.__bases__`).
- Updated allowlist config logic to allow overrides (e.g. `pathlib`) when modules are explicitly declared in `extra_allowed` settings or tests.
- Config overrides are automatically forwarded to isolated subprocess sandboxes via CLI parameters.

### 4. Episodic Memory API Bridge
- Restored factory patterns `MemoryStore.in_memory()` and `MemoryStore.persistent(...)`.
- Restored backwards-compatible memory access methods: `write()`, `read()`, `delete()`, and `search()`.
- Implemented unboxing properties on `MemoryEntry` to return standard Python objects to host scripts while preserving internal `InthonValue` packaging.

### 5. Web Parsing & Encoding Detection
- Web page parsing helper `_real_web_read` now dynamically reads the HTTP `Content-Type` charset attribute.
- Re-implemented meta tag header traversal, scanning the first 1024 bytes of the HTML response to accurately detect local charsets (like `gbk`, `iso-8859-1`) and avoid Unicode encoding errors.

---

## 🛠️ Verification
All **168 unit tests** in the verification suite pass successfully, representing 100% completion of the language specification test matrix.
