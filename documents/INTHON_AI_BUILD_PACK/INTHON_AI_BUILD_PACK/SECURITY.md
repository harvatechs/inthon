# INTHON Security Model

## Core rule

Default deny for dangerous capabilities.

## Capabilities

| Capability | Default | Policy key | v0.1 behavior |
|---|---:|---|---|
| network | deny | `allow_network: true` | enforce |
| filesystem read | allow working dir only | `allow_filesystem: read_only` | enforce |
| filesystem write | deny | `allow_filesystem: write` | enforce |
| shell | deny | `allow_shell: true` | hard-block in v0.1 |
| email send | deny | `allow_email: true` | enforce + approval recommended |
| payment execute | deny | `allow_payment: true` | enforce + approval required |
| memory write | session only | `allow_memory_persist: true` | enforce |
| database write | deny | `allow_database: true` | stub/enforce if implemented |
| model download | deny | `allow_model_download: true` | stub/enforce if implemented |

## Tool call security

Before a tool executes:

1. Confirm it was imported.
2. Confirm it is registered.
3. Validate args against schema.
4. Check side effects against policy.
5. Estimate cost.
6. Require approval if needed.
7. Log the call.
8. Execute through registry only.
9. Log result summary.

## Python bridge security

Deny by default:

- `os.system`
- `subprocess`
- arbitrary shell execution
- dynamic `eval`
- dynamic `exec`
- unsafe deserialization
- unrestricted file writes
- unrestricted network calls
- import of known dangerous modules unless explicitly permitted and wrapped

Import flow:

1. Canonicalize module name.
2. Check denylist.
3. Check allowlist or policy.
4. Import module.
5. Wrap module with adapter if available.
6. Trace calls if configured.
7. Wrap exceptions.

## Approval gates

Approval gates are synchronous in v0.1.

```inth
approve payment before execute
approve email before send
approve file.delete before run
```

If approval is denied, raise a catchable `INTHON_POLICY_*` error.

## Sandboxing

### v0.1

- Python-level restrictions
- path restrictions
- tool registry restrictions
- timeout enforcement
- memory limits where feasible
- redaction in traces

### Future

- container isolation
- seccomp/AppArmor profiles
- network egress controls
- filesystem mount controls
- secrets manager
- external audit log

## Redaction

Trace logs must never expose raw secrets. Redact values whose keys include:

- `secret`
- `token`
- `api_key`
- `password`
- `authorization`
- `cookie`

## Required safety tests

- unauthorized file write
- unauthorized network request
- shell command attempt
- secret leakage
- unsafe Python import
- tool schema mismatch
- approval bypass attempt
- max tool calls exceeded
- max cost exceeded

## Security acceptance criteria

- Unregistered tools never execute.
- Unsafe Python imports fail before resolution.
- Shell is hard-blocked.
- Every side effect has a policy check.
- Every policy check is auditable.
- Approval gate cannot be skipped.
