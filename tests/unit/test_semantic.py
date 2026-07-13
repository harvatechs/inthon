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
    src = 'results = web.search("agent language")'
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
    analyzer.analyze(prog)  # Should not raise any semantic errors


def test_type_mismatch_error():
    src = 'let x: int = "hello"'
    prog = parse(src)
    analyzer = SemanticAnalyzer()
    with pytest.raises(SemanticError) as excinfo:
        analyzer.analyze(prog)
    assert "INTHON_SEM_004" in str(excinfo.value)
    assert "Type mismatch: variable 'x'" in str(excinfo.value)

    src_const = "const y: float = true"
    prog_const = parse(src_const)
    with pytest.raises(SemanticError) as excinfo:
        SemanticAnalyzer().analyze(prog_const)
    assert "INTHON_SEM_004" in str(excinfo.value)
    assert "Type mismatch: constant 'y'" in str(excinfo.value)


def test_shadow_warning():
    src = """
    let x = 10
    fn f() {
        let x = 20
    }
    """
    prog = parse(src)
    analyzer = SemanticAnalyzer()
    analyzer.analyze(prog)
    assert len(analyzer.warnings) == 1
    assert "shadow name 'x'" in analyzer.warnings[0]


def test_function_argument_type_mismatch():
    src = """
    fn f(a: int) {
        return a
    }
    f("hello")
    """
    prog = parse(src)
    with pytest.raises(SemanticError) as excinfo:
        SemanticAnalyzer().analyze(prog)
    assert "INTHON_SEM_004" in str(excinfo.value)
    assert "argument 'a' of function 'f' expected int, got str" in str(excinfo.value)


def test_return_type_mismatch():
    src = """
    fn f() -> int {
        return "hello"
    }
    """
    prog = parse(src)
    with pytest.raises(SemanticError) as excinfo:
        SemanticAnalyzer().analyze(prog)
    assert "INTHON_SEM_004" in str(excinfo.value)
    assert "function return type must be int, got str" in str(excinfo.value)
