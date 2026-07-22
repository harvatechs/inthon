"""Unit tests for PermissionAnalyzer."""

from inthon.parser import parse
from inthon.semantic.permissions import PermissionAnalyzer


def test_permission_analyzer():
    source = """
    use tool web.search
    use py.math as m
    use py.json
    """
    program = parse(source)
    analyzer = PermissionAnalyzer()
    analyzer.analyze(program)

    assert "web.search" in analyzer.used_tools
    assert "math" in analyzer.used_py_modules
    assert "json" in analyzer.used_py_modules
