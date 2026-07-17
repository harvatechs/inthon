"""INTHON error taxonomy.

Every error raised by the INTHON toolchain carries a stable machine-readable
code, an optional source span, and a human-actionable hint.  The taxonomy is
defined in docs/language-spec.md and mirrored here:

    INTHON_PARSE_xxx   syntax errors (lexer / parser)
    INTHON_SEM_xxx     semantic errors (scope, types, capabilities)
    INTHON_TYPE_xxx    runtime type errors
    INTHON_POLICY_xxx  policy / sandbox violations
    INTHON_TOOL_xxx    tool registry and invocation errors
    INTHON_PY_xxx      PyBridge import and conversion errors
    INTHON_MEM_xxx     memory subsystem errors
    INTHON_GUARD_xxx   guard assertion failures
    INTHON_VM_xxx      bytecode VM faults
    INTHON_CLI_xxx     command-line usage errors
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Span:
    """A half-open source range [start, end) with 1-based line/col."""

    filename: str
    line: int
    col: int
    end_line: int = 0
    end_col: int = 0
    offset: int = 0
    length: int = 1

    def __post_init__(self):
        if not self.end_line:
            object.__setattr__(self, "end_line", self.line)
        if not self.end_col:
            object.__setattr__(self, "end_col", self.col + max(self.length, 1))

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.filename}:{self.line}:{self.col}"


class InthonError(Exception):
    """Base class for all INTHON errors."""

    code: str = "INTHON_000"
    default_hint: Optional[str] = None

    def __init__(
        self,
        message: str,
        *,
        span: Optional[Span] = None,
        hint: Optional[str] = None,
        source_line: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.span = span
        self.hint = hint if hint is not None else self.default_hint
        self.source_line = source_line

    # -- rendering ---------------------------------------------------------
    def formatted(self, use_color: bool = False) -> str:
        """Render the error with file/line/column, a source caret and a hint."""
        lines = [f"{self.code}: {self.message}"]
        if self.span is not None:
            lines.append(f"  File: {self.span.filename}")
            lines.append(f"  Line {self.span.line}, Column {self.span.col}")
            if self.source_line is not None:
                gutter = f"{self.span.line:4d} | "
                lines.append(gutter + self.source_line.rstrip("\n"))
                caret_width = max(1, (self.span.end_col - self.span.col))
                lines.append(" " * len(gutter) + " " * (self.span.col - 1) + "^" * caret_width)
        if self.hint:
            lines.append(f"  Hint: {self.hint}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.formatted()


# ---------------------------------------------------------------------------
# Parse errors
# ---------------------------------------------------------------------------
class InthonParseError(InthonError):
    code = "INTHON_PARSE_001"


class InthonLexError(InthonParseError):
    code = "INTHON_PARSE_002"
    default_hint = "Check for unterminated strings, stray characters, or invalid number formats."


class InthonTypeSyntaxError(InthonParseError):
    code = "INTHON_PARSE_003"
    default_hint = "Expected a type such as int, str, bool, float, list[T], dict[K, V], tuple[...] or any."


# ---------------------------------------------------------------------------
# Semantic errors
# ---------------------------------------------------------------------------
class InthonSemanticError(InthonError):
    code = "INTHON_SEM_000"


class InthonNameError(InthonSemanticError):
    code = "INTHON_SEM_002"
    default_hint = "Declare the name with 'let' or 'const' before use, or import it with 'use'."


class InthonDuplicateError(InthonSemanticError):
    code = "INTHON_SEM_001"
    default_hint = "Rename one of the declarations; names must be unique within a scope."


class InthonConstError(InthonSemanticError):
    code = "INTHON_SEM_001"
    default_hint = "Use 'let' instead of 'const' if the binding must change."


class InthonCapabilityError(InthonSemanticError):
    code = "INTHON_SEM_003"
    default_hint = "Add the matching 'use tool <path>', 'use py.<module>' or 'use memory.<ns>' declaration."


class InthonStaticTypeError(InthonSemanticError):
    code = "INTHON_SEM_004"


# ---------------------------------------------------------------------------
# Runtime type errors
# ---------------------------------------------------------------------------
class InthonTypeError_(InthonError):
    code = "INTHON_TYPE_001"


class InthonIndexError(InthonTypeError_):
    code = "INTHON_TYPE_002"


class InthonArityError(InthonTypeError_):
    code = "INTHON_TYPE_003"


class InthonFailure(InthonError):
    """Raised by the stdlib fail() function and unrecoverable plan states."""

    code = "INTHON_001"


class GuardAssertionError(InthonError):
    code = "INTHON_GUARD_001"
    default_hint = "The guard expression evaluated to a falsy value."


# ---------------------------------------------------------------------------
# Policy errors
# ---------------------------------------------------------------------------
class PolicyViolationError(InthonError):
    code = "INTHON_POLICY_001"
    default_hint = "Declare the capability in the agent's policy block, e.g. policy { allow_network: true }."


class BudgetExhaustedError(PolicyViolationError):
    code = "INTHON_POLICY_002"


class ApprovalDeniedError(PolicyViolationError):
    code = "INTHON_POLICY_003"
    default_hint = "The approval gate rejected the action; handle this with retry/catch or adjust policy."


# ---------------------------------------------------------------------------
# Tool errors
# ---------------------------------------------------------------------------
class ToolNotFoundError(InthonError):
    code = "INTHON_TOOL_001"
    default_hint = "Check the tool path, e.g. use tool web.search."


class ToolValidationError(InthonError):
    code = "INTHON_TOOL_002"


class ToolExecutionError(InthonError):
    code = "INTHON_TOOL_003"


class ToolTimeoutError(ToolExecutionError):
    code = "INTHON_TOOL_004"


# ---------------------------------------------------------------------------
# PyBridge errors
# ---------------------------------------------------------------------------
class PyBridgeError(InthonError):
    pass


class InthonImportError_(PyBridgeError):
    code = "INTHON_PY_001"
    default_hint = "Add the module to [pybridge] allowed_modules in inthon.toml if it is safe."


class InthonPyAttributeError(PyBridgeError):
    code = "INTHON_PY_002"
    default_hint = "Private/dunder attributes and dangerous callables are blocked by the sandbox."


class InthonConversionError(PyBridgeError):
    code = "INTHON_PY_003"


class InthonPyRuntimeError(PyBridgeError):
    code = "INTHON_PY_004"
    default_hint = "The Python call raised; check the wrapped message for details."


ParseError = InthonParseError
SemanticError = InthonSemanticError


# ---------------------------------------------------------------------------
# Memory errors
# ---------------------------------------------------------------------------
class InthonMemoryError_(InthonError):
    code = "INTHON_MEM_001"


# ---------------------------------------------------------------------------
# VM errors
# ---------------------------------------------------------------------------
class InthonVMError(InthonError):
    code = "INTHON_VM_001"


class InthonStackOverflow(InthonVMError):
    code = "INTHON_VM_002"


class InthonIterationLimit(InthonVMError):
    code = "INTHON_VM_003"


class InthonRecursionLimit(InthonVMError):
    code = "INTHON_VM_004"


# ---------------------------------------------------------------------------
# CLI errors
# ---------------------------------------------------------------------------
class InthonCLIError(InthonError):
    code = "INTHON_CLI_001"


ALL_ERROR_CODES = {
    cls.code
    for cls in [
        InthonParseError, InthonLexError, InthonTypeSyntaxError,
        InthonSemanticError, InthonNameError, InthonDuplicateError,
        InthonConstError, InthonCapabilityError, InthonStaticTypeError,
        InthonTypeError_, InthonIndexError, InthonArityError, InthonFailure,
        GuardAssertionError, PolicyViolationError, BudgetExhaustedError,
        ApprovalDeniedError, ToolNotFoundError, ToolValidationError,
        ToolExecutionError, ToolTimeoutError, InthonImportError_,
        InthonPyAttributeError, InthonConversionError, InthonMemoryError_,
        InthonVMError, InthonStackOverflow, InthonIterationLimit,
        InthonRecursionLimit, InthonCLIError,
    ]
}
