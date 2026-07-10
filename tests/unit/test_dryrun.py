"""
tests/unit/test_dryrun.py — Unit tests for Declarative DryRun Mocking.
"""

from __future__ import annotations
from inthon.runtime.context import ExecutionContext
from inthon.parser.parser import parse
from inthon.vm.compiler import compile_program
from inthon.vm.machine import InthonVM
from inthon.runtime.interpreter import Interpreter
from inthon.tools.builtin_tools import register_builtins


def test_dryrun_mocking_vm():
    ctx = ExecutionContext()
    ctx.dry_run = True
    register_builtins(
        ctx.tools, mock=False
    )  # mock is False, meaning it would call real if not dry_run

    src = """
use tool web.search
let res = web.search("test query")
"""
    prog = parse(src, "<test>")
    code = compile_program(prog, "<test>")

    vm = InthonVM(ctx)
    vm.execute(code)

    # In dry-run mode, it should successfully return mock data conforming to schema
    assert "res" in vm._globals
    res_val = vm._globals["res"]

    # In VM, values are coerced to python primitives
    assert isinstance(res_val, dict)
    assert "results" in res_val
    assert isinstance(res_val["results"], list)
    assert res_val["results"][0]["title"] == "Mock Search Result"


def test_dryrun_mocking_interpreter():
    ctx = ExecutionContext()
    ctx.dry_run = True
    register_builtins(ctx.tools, mock=False)

    src = """
use tool web.search
let res = web.search("test query")
"""
    prog = parse(src, "<test>")

    interp = Interpreter(ctx)
    interp.run(prog)

    # In tree-walk interpreter, we look at the scope stack variable
    res_val = ctx.get_var("res")
    from inthon.runtime.values import InthonDict, to_python

    assert isinstance(res_val, InthonDict)
    py_val = to_python(res_val)
    assert py_val["results"][0]["title"] == "Mock Search Result"
