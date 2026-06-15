import pytest
from typer.testing import CliRunner
from inthon.cli import app

runner = CliRunner()


@pytest.fixture
def temp_inth_file(tmp_path):
    f = tmp_path / "test.inth"
    f.write_text("let x = 10\nx", encoding="utf-8")
    return f


@pytest.fixture
def temp_bad_file(tmp_path):
    f = tmp_path / "bad.inth"
    f.write_text("let x =", encoding="utf-8")
    return f


def test_cli_run(temp_inth_file):
    result = runner.invoke(app, ["run", str(temp_inth_file)])
    assert result.exit_code == 0
    assert "10" in result.stdout


def test_cli_run_bad(temp_bad_file):
    result = runner.invoke(app, ["run", str(temp_bad_file)])
    assert result.exit_code == 1
    assert "INTHON_PARSE_001" in result.stdout


def test_cli_check(temp_inth_file):
    result = runner.invoke(app, ["check", str(temp_inth_file)])
    assert result.exit_code == 0
    assert "no issues found" in result.stdout


def test_cli_check_bad(temp_bad_file):
    result = runner.invoke(app, ["check", str(temp_bad_file)])
    assert result.exit_code == 1
    assert "INTHON_PARSE_001" in result.stdout


def test_cli_ast_tree(temp_inth_file):
    result = runner.invoke(app, ["ast", str(temp_inth_file)])
    assert result.exit_code == 0
    assert "Program" in result.stdout


def test_cli_ast_json(temp_inth_file):
    result = runner.invoke(app, ["ast", str(temp_inth_file), "-f", "json"])
    assert result.exit_code == 0
    assert "node_type" in result.stdout


def test_cli_ir(temp_inth_file):
    result = runner.invoke(app, ["ir", str(temp_inth_file)])
    assert result.exit_code == 0
    assert "IRAssign" in result.stdout


def test_cli_fmt(temp_inth_file, tmp_path):
    # Test formatting printout
    result = runner.invoke(app, ["fmt", str(temp_inth_file)])
    assert result.exit_code == 0
    assert "let x = 10" in result.stdout

    # Test writing formatted changes back
    dirty_file = tmp_path / "dirty.inth"
    dirty_file.write_text("let x = 10    \n  \nx    ", encoding="utf-8")
    result_write = runner.invoke(app, ["fmt", str(dirty_file), "--write"])
    assert result_write.exit_code == 0
    assert "Formatted" in result_write.stdout
    assert dirty_file.read_text(encoding="utf-8") == "let x = 10\n\nx\n"


def test_cli_main_module():
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, "-m", "inthon", "--help"], capture_output=True, text=True
    )
    assert res.returncode == 0
    assert "INTHON" in res.stdout
