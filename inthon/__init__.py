"""INTHON — the agent-level programming language.

Public API:
    inthon.run(source, ...)          — execute INTHON source
    inthon.run_file(path, ...)       — execute a .inth file
    inthon.parse(source)             — parse to AST
    inthon.check(source)             — parse + semantic analysis
    inthon.compile_ir(source)        — compile to IR
"""

from .version import __version__, __version_info__

__all__ = [
    "__version__",
    "__version_info__",
    "run",
    "run_file",
    "parse",
    "check",
    "compile_ir",
    "RunResult",
    "RunOptions",
    "run_vm",
    "run_file_vm",
    "run_file_transpiled",
]


def __getattr__(name):  # lazy imports keep `import inthon` fast
    if name in (
        "run",
        "run_file",
        "parse",
        "check",
        "compile_ir",
        "RunResult",
        "RunOptions",
        "run_vm",
        "run_file_vm",
        "run_file_transpiled",
    ):
        from . import api

        return getattr(api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
