import pytest
from inthon.parser.parser import parse
from inthon.semantic.analyzer import SemanticAnalyzer
from inthon.semantic.scope import SemanticError

def test_duplicate_declaration():
    src = "let x = 10\nlet x = 20"
    prog = parse(src)
    analyzer = SemanticAnalyzer()
    with pytest.raises(SemanticError) as excinfo:
        analyzer.analyze(prog)
    assert "INTHON_SEM_001" in str(excinfo.value)
    assert "already declared" in str(excinfo.value)

def test_reassign_constant():
    src = "const x = 10\nx = 20"
    prog = parse(src)
    analyzer = SemanticAnalyzer()
    with pytest.raises(SemanticError) as excinfo:
        analyzer.analyze(prog)
    assert "INTHON_SEM_001" in str(excinfo.value)
    assert "Reassignment to constant" in str(excinfo.value)

def test_undefined_variable():
    src = "let x = y + 10"
    prog = parse(src)
    analyzer = SemanticAnalyzer()
    with pytest.raises(SemanticError) as excinfo:
        analyzer.analyze(prog)
    assert "INTHON_SEM_002" in str(excinfo.value)
    assert "Undefined name" in str(excinfo.value)

def test_tool_usage_before_import():
    src = "results = web.search(\"agent language\")"
    prog = parse(src)
    analyzer = SemanticAnalyzer()
    with pytest.raises(SemanticError) as excinfo:
        analyzer.analyze(prog)
    assert "INTHON_SEM_003" in str(excinfo.value)
    assert "used but not imported" in str(excinfo.value)

def test_correct_nested_scope():
    src = """
    fn add(a: int) -> int {
        let x = 10
        return a + x
    }
    let y = add(5)
    """
    prog = parse(src)
    analyzer = SemanticAnalyzer()
    analyzer.analyze(prog) # Should not raise any semantic errors

def test_type_mismatch_warning():
    src = """
    let x: int = "hello"
    const y: float = true
    let z: str = 10
    """
    prog = parse(src)
    analyzer = SemanticAnalyzer()
    analyzer.analyze(prog)
    assert len(analyzer.warnings) == 3
    assert "variable 'x' declared as int but assigned str" in analyzer.warnings[0]
    assert "constant 'y' declared as float but assigned bool" in analyzer.warnings[1]
    assert "variable 'z' declared as str but assigned int" in analyzer.warnings[2]

