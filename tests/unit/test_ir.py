import pytest
from inthon.parser.parser import parse
from inthon.ir.builder import build_ir
from inthon.ir.serializer import ir_to_json, ir_from_json
from inthon.ir import nodes as IR

def test_ast_to_ir_basic():
    src = "let x = 10"
    prog = parse(src)
    ir_prog = build_ir(prog)
    assert len(ir_prog.body) == 1
    assert isinstance(ir_prog.body[0], IR.IRAssign)
    assert ir_prog.body[0].target == "x"
    assert isinstance(ir_prog.body[0].value, IR.IRLiteral)
    assert ir_prog.body[0].value.value == 10

def test_ast_to_ir_tool_call():
    src = "use tool web.search\nresults = web.search(\"inthon\", limit: 3)"
    prog = parse(src)
    ir_prog = build_ir(prog)
    assert len(ir_prog.imports) == 1
    assert ir_prog.imports[0].kind == "tool"
    assert ir_prog.imports[0].path == "web.search"
    assert len(ir_prog.body) == 1
    assign = ir_prog.body[0]
    assert isinstance(assign, IR.IRAssign)
    assert assign.target == "results"
    assert isinstance(assign.value, IR.IRToolCall)
    assert assign.value.tool == "web.search"
    assert len(assign.value.args) == 1
    assert assign.value.args[0].value == "inthon"
    assert "limit" in assign.value.kwargs
    assert assign.value.kwargs["limit"].value == 3

def test_ast_to_ir_py_call():
    src = "use py.pandas as pd\ndf = pd.read_csv(\"sales.csv\")"
    prog = parse(src)
    ir_prog = build_ir(prog)
    assert len(ir_prog.imports) == 1
    assert ir_prog.imports[0].kind == "py"
    assert ir_prog.imports[0].path == "pandas"
    assert ir_prog.imports[0].alias == "pd"
    assert len(ir_prog.body) == 1
    assign = ir_prog.body[0]
    assert isinstance(assign, IR.IRAssign)
    assert assign.target == "df"
    assert isinstance(assign.value, IR.IRPyCall)
    assert assign.value.module == "pandas"
    assert assign.value.attr_chain == ["read_csv"]

def test_ir_json_round_trip():
    src = "use tool web.search\nlet x = 10\nweb.search(\"query\")"
    prog = parse(src)
    ir_prog = build_ir(prog)
    json_str = ir_to_json(ir_prog)
    reconstructed = ir_from_json(json_str)

    assert len(reconstructed.imports) == 1
    assert reconstructed.imports[0].path == "web.search"
    assert len(reconstructed.body) == 2
    assert isinstance(reconstructed.body[0], IR.IRAssign)
    assert isinstance(reconstructed.body[1], IR.IRToolCall)
