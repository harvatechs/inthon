"""INTHON public API: parse / check / run / compile_ir."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .ast import nodes
from .errors import InthonError
from .runtime.context import ExecutionContext, RunOptions
from .runtime.values import InthonValue, display
from .version import __version__


@dataclass
class RunResult:
    """The outcome of executing an INTHON program."""

    ok: bool
    result: Optional[InthonValue] = None
    result_python: Any = None
    result_display: str = "none"
    trace: dict = field(default_factory=dict)
    stdout: str = ""
    error: Optional[InthonError] = None
    backend: str = "tree"

    @property
    def output(self) -> Any:
        return self.result_python

    @property
    def trace_json(self) -> str:
        import json
        return json.dumps(self.trace)

    @property
    def duration_ms(self) -> float:
        return self.trace.get("duration_ms", 0.0)

    @property
    def cost_usd(self) -> float:
        cost_dict = self.trace.get("cost")
        if isinstance(cost_dict, dict):
            return cost_dict.get("usd", 0.0)
        return 0.0

    def raise_for_error(self):
        if self.error is not None:
            raise self.error


def parse(source: str, filename: str = "<stdin>") -> nodes.Program:
    from .parser import parse as _parse

    return _parse(source, filename)


def check(source: str, filename: str = "<stdin>", ctx: Optional[ExecutionContext] = None) -> nodes.Program:
    """Parse + run the semantic analyzer; raises on any static error."""
    from .semantic.analyzer import SemanticAnalyzer

    program = parse(source, filename)
    analyzer = SemanticAnalyzer(ctx or ExecutionContext(RunOptions(source=source, filename=filename)))
    analyzer.analyze(program)
    return program


def compile_ir(source: str, filename: str = "<stdin>") -> dict:
    from .ir.builder import build_ir

    program = check(source, filename)
    return build_ir(program, source=source, filename=filename)


def run(source: str, options: Optional[RunOptions] = None, **kwargs) -> RunResult:
    """Execute INTHON source text.  Keyword args override RunOptions fields."""
    opts = _merge_options(options, kwargs)
    opts.source = source
    res = _execute(source, opts)
    if not res.ok and res.error is not None:
        raise res.error
    return res


def run_vm(source: str, filename: str = "<stdin>", mock_tools: bool = True) -> RunResult:
    return run(source, filename=filename, mock=mock_tools, backend="vm")


def run_file_vm(
    path: str,
    mock_tools: bool = True,
    max_cost_usd: float = 1.0,
    max_runtime_sec: float = 300.0,
    persist_memory: bool = False,
    dry_run: bool = False,
) -> RunResult:
    from .policy.model import Policy
    policy = Policy(max_cost_usd=max_cost_usd, max_runtime_sec=max_runtime_sec)
    return run_file(
        path,
        mock=mock_tools,
        backend="vm",
        policy=policy,
        dry_run=dry_run,
    )


def run_file_transpiled(
    path: str,
    mock_tools: bool = True,
    max_cost_usd: float = 1.0,
    max_runtime_sec: float = 300.0,
) -> RunResult:
    from pathlib import Path
    from .compiler.transpiler import run_transpiled
    source = Path(path).read_text(encoding="utf-8")
    return run_transpiled(source, filename=path, mock_tools=mock_tools)



def run_file(path: str, options: Optional[RunOptions] = None, **kwargs) -> RunResult:
    source = Path(path).read_text(encoding="utf-8")
    opts = _merge_options(options, kwargs)
    opts.filename = path
    opts.source = source
    return _execute(source, opts)


def _merge_options(options: Optional[RunOptions], overrides: dict) -> RunOptions:
    opts = options or RunOptions()
    policy_overrides = {}
    for key, value in list(overrides.items()):
        if key == "mock_tools":
            key = "mock"
        if key == "max_cost_usd":
            policy_overrides["max_cost_usd"] = value
            continue
        if key == "max_runtime_sec":
            policy_overrides["max_runtime_sec"] = value
            continue
        if not hasattr(opts, key):
            raise TypeError(f"Unknown RunOptions field {key!r}")
        setattr(opts, key, value)

    if policy_overrides:
        from .policy.model import Policy
        base_policy = opts.policy or Policy()
        new_policy = Policy(
            allow_network=base_policy.allow_network,
            allow_shell=base_policy.allow_shell,
            allow_email=base_policy.allow_email,
            allow_payment=base_policy.allow_payment,
            allow_database=base_policy.allow_database,
            allow_model=base_policy.allow_model,
            allow_memory_persist=base_policy.allow_memory_persist,
            filesystem=base_policy.filesystem,
            max_cost_usd=policy_overrides.get("max_cost_usd", base_policy.max_cost_usd),
            max_runtime_sec=policy_overrides.get("max_runtime_sec", base_policy.max_runtime_sec),
        )
        opts.policy = new_policy

    return opts


def _execute(source: str, opts: RunOptions) -> RunResult:
    stdout_buf = io.StringIO()
    raw_out = opts.write_out or (lambda s: print(s))

    def tee(s: str):
        raw_out(s)
        stdout_buf.write(s + "\n")

    opts.write_out = tee

    ctx = ExecutionContext(opts)
    try:
        program = parse(source, opts.filename)
        from .semantic.analyzer import SemanticAnalyzer

        SemanticAnalyzer(ctx).analyze(program)

        if opts.backend == "vm":
            from .vm.vm import InthonVM

            result = InthonVM(ctx).run(program)
        else:
            from .runtime.interpreter import run_program

            result = run_program(program, ctx)
        trace = ctx.tracer.finish(result_type=result.type_name, result_preview=display(result)[:200])
        return RunResult(
            ok=True,
            result=result,
            result_python=result.to_python(),
            result_display=display(result),
            trace=trace,
            stdout=stdout_buf.getvalue(),
            backend=opts.backend,
        )
    except InthonError as exc:
        ctx.tracer.emit_error(exc.code, exc.message, exc.span)
        trace = ctx.tracer.finish(result_type="error", result_preview=f"{exc.code}: {exc.message}")
        return RunResult(
            ok=False,
            error=exc,
            trace=trace,
            stdout=stdout_buf.getvalue(),
            backend=opts.backend,
        )
    finally:
        ctx.close()
