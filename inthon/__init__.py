from dataclasses import dataclass
from typing import Any
from pathlib import Path


@dataclass
class RunResult:
    output: Any
    trace_json: str
    cost_usd: float
    duration_ms: float
    errors: list[dict]


def parse(source: str, filename: str = "<stdin>"):
    from .parser.parser import parse as parser_parse

    return parser_parse(source, filename)


def check(source: str, filename: str = "<stdin>"):
    from .parser.parser import parse as parser_parse
    from .semantic.analyzer import SemanticAnalyzer

    program = parser_parse(source, filename)
    analyzer = SemanticAnalyzer()
    analyzer.analyze(program)
    return True


def run(source: str, filename: str = "<stdin>", mock_tools: bool = True) -> RunResult:
    from .parser.parser import parse as parser_parse
    from .semantic.analyzer import SemanticAnalyzer
    from .runtime.context import ExecutionContext
    from .runtime.interpreter import Interpreter
    from .runtime.values import to_python
    from .tools.builtin_tools import register_builtins
    import time

    t0 = time.perf_counter()
    program = parser_parse(source, filename=filename)
    SemanticAnalyzer().analyze(program)

    ctx = ExecutionContext(filename=filename)
    register_builtins(ctx.tools, mock=mock_tools)

    interp = Interpreter(ctx)
    result_val = interp.run(program)
    duration_ms = (time.perf_counter() - t0) * 1000

    return RunResult(
        output=to_python(result_val),
        trace_json=ctx.tracer.to_json(),
        cost_usd=ctx.cost_usd,
        duration_ms=round(duration_ms, 2),
        errors=ctx.errors,
    )


def run_file(
    path: Path | str,
    mock_tools: bool = True,
    max_cost_usd: float = 1.0,
    max_runtime_sec: float = 300.0,
    dry_run: bool = False,
) -> RunResult:
    from .parser.parser import parse as parser_parse
    from .semantic.analyzer import SemanticAnalyzer
    from .runtime.context import ExecutionContext
    from .runtime.interpreter import Interpreter
    from .runtime.values import to_python
    from .tools.builtin_tools import register_builtins
    import time

    source = Path(path).read_text(encoding="utf-8")
    filename = str(path)
    t0 = time.perf_counter()

    program = parser_parse(source, filename=filename)
    SemanticAnalyzer().analyze(program)

    ctx = ExecutionContext(filename=filename)
    ctx.dry_run = dry_run
    ctx.sandbox.max_cost_usd = max_cost_usd
    ctx.sandbox.max_runtime_sec = max_runtime_sec
    register_builtins(ctx.tools, mock=mock_tools)

    interp = Interpreter(ctx)
    result_val = interp.run(program)
    duration_ms = (time.perf_counter() - t0) * 1000

    return RunResult(
        output=to_python(result_val),
        trace_json=ctx.tracer.to_json(),
        cost_usd=ctx.cost_usd,
        duration_ms=round(duration_ms, 2),
        errors=ctx.errors,
    )


# ─── VM-backed variants (Phase 1: Bytecode Compiler + Stack Machine) ──────────


def run_vm(
    source: str, filename: str = "<stdin>", mock_tools: bool = True
) -> RunResult:
    """
    Execute INTHON source via the bytecode compiler + InthonVM stack machine.
    Typically 10–50x faster than the tree-walk interpreter on loops.
    """
    from .parser.parser import parse as parser_parse
    from .semantic.analyzer import SemanticAnalyzer
    from .runtime.context import ExecutionContext
    from .vm.compiler import compile_program
    from .vm.machine import InthonVM
    from .tools.builtin_tools import register_builtins
    import time

    t0 = time.perf_counter()
    program = parser_parse(source, filename=filename)
    SemanticAnalyzer().analyze(program)

    ctx = ExecutionContext(filename=filename)
    register_builtins(ctx.tools, mock=mock_tools)

    code = compile_program(program, filename=filename)
    vm = InthonVM(ctx)
    result_val = vm.execute(code)
    duration_ms = (time.perf_counter() - t0) * 1000

    return RunResult(
        output=result_val,
        trace_json=ctx.tracer.to_json(),
        cost_usd=ctx.cost_usd,
        duration_ms=round(duration_ms, 2),
        errors=ctx.errors,
    )


def run_file_vm(
    path,
    mock_tools: bool = True,
    max_cost_usd: float = 1.0,
    max_runtime_sec: float = 300.0,
    persist_memory: bool = False,
    dry_run: bool = False,
) -> RunResult:
    """
    Execute an INTHON file via the bytecode compiler + InthonVM stack machine.
    When persist_memory=True, uses a SQLite-backed memory store.
    """
    from .parser.parser import parse as parser_parse
    from .semantic.analyzer import SemanticAnalyzer
    from .runtime.context import ExecutionContext
    from .vm.compiler import compile_program
    from .vm.machine import InthonVM
    from .tools.builtin_tools import register_builtins
    from .memory.store import MemoryStore
    from pathlib import Path
    import time

    source = Path(path).read_text(encoding="utf-8")
    filename = str(path)
    t0 = time.perf_counter()

    program = parser_parse(source, filename=filename)
    SemanticAnalyzer().analyze(program)

    # Optionally use persistent memory store
    memory = (
        MemoryStore.persistent(db_path=str(Path(path).parent / ".inthon" / "memory.db"))
        if persist_memory
        else MemoryStore.in_memory()
    )

    ctx = ExecutionContext(filename=filename, memory=memory)
    ctx.dry_run = dry_run
    ctx.sandbox.max_cost_usd = max_cost_usd
    ctx.sandbox.max_runtime_sec = max_runtime_sec
    register_builtins(ctx.tools, mock=mock_tools)

    code = compile_program(program, filename=filename)
    vm = InthonVM(ctx)
    result_val = vm.execute(code)
    duration_ms = (time.perf_counter() - t0) * 1000

    return RunResult(
        output=result_val,
        trace_json=ctx.tracer.to_json(),
        cost_usd=ctx.cost_usd,
        duration_ms=round(duration_ms, 2),
        errors=ctx.errors,
    )
