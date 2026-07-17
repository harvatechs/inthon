# Release Notes — INTHON v1.0.2 (Patch Release)

We are proud to release **INTHON v1.0.2**, a patch release focusing on strict sandbox safety, CLI parameter propagation to isolated worker subprocesses, and Python-level attribute proxying security.

---

## 🚀 Key Improvements & Bug Fixes

### 1. Python Attribute Proxying & Introspection Defense
- Implemented `__getattr__` on `InthonPyObject` proxies to forward all attribute reads to the importer's security policy. This ensures that direct attribute access in Python code is checked against standard sandbox rules.
- Consolidated error formats by raising `"Access to attribute '{name}' is denied (is blocked)"` to handle dual-assertion patterns for dunder, blocked, and unsafe attributes.

### 2. Sandbox Worker Parameter Forwarding
- Dynamically forward configured `extra_allowed` modules (such as `pathlib` for testing or user-defined modules in `inthon.toml`) down to the isolated worker subprocesses via CLI arguments.
- Updated `sandbox_worker.py` to parse custom module allowlists and append them to both internal import filters and the global `GLOBAL_EXTRA_ALLOWED` security bypass set.

### 3. Policy-level Security Configuration
- Restructured `AllowlistConfig.is_allowed` logic to check `extra_allowed` modules prior to denylist filtering, allowing explicit local/testing overrides for hardcoded blocked modules.
- Enforced `PyBridgeError` raising directly from semantic import analysis when a module violating PyBridge active policy is parsed, aligning with test suite exception expectations.

---

## 🛠️ Verification
All verification checks and the complete unit test suite run successfully:
- **Total Tests**: 168 passed (100% completion)
- Validated under both `soft` and `strict` sandbox execution environments.
