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


def test_cli_trace_view(temp_inth_file, tmp_path):
    trace_json_file = tmp_path / "trace.json"
    html_file = tmp_path / "replay.html"

    # Step 1: Run program and output trace
    res_run = runner.invoke(
        app, ["run", str(temp_inth_file), "--trace-out", str(trace_json_file)]
    )
    assert res_run.exit_code == 0
    assert trace_json_file.exists()

    # Step 2: Generate visual HTML replay dashboard
    res_view = runner.invoke(
        app, ["trace-view", str(trace_json_file), "-o", str(html_file), "--no-open"]
    )
    assert res_view.exit_code == 0
    assert html_file.exists()

    html_content = html_file.read_text(encoding="utf-8")
    assert "INTHON Flight Recorder" in html_content
    assert "traceEvents" in html_content


def test_cli_run_transpile(temp_inth_file):
    result = runner.invoke(app, ["run", str(temp_inth_file), "--transpile"])
    assert result.exit_code == 0
    assert "10" in result.stdout


def test_cli_run_docker(temp_inth_file, monkeypatch):
    # Mock shutil.which to return None so that Docker is considered missing, triggering expected clean exit.
    import shutil

    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    result = runner.invoke(app, ["run", str(temp_inth_file), "--docker"])
    assert result.exit_code == 1
    assert "INTHON_CONTAINER_001" in result.stdout
