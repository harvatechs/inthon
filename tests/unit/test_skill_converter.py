from __future__ import annotations
from pathlib import Path
import pytest
from typer.testing import CliRunner

from inthon.cli import app
from inthon.tools.registry import ToolRegistry
from inthon.tools.builtin_tools import register_skills
from inthon.tools.skill_converter import (
    parse_skill_yaml,
    parse_python_script_args,
    convert_skill_to_workflow,
)

MOCK_SKILL_MD = """---
name: mock-test-skill
description: 'A mock skill to test conversion'
metadata:
  tags: mock, test, converter
---

# Mock Test Skill
This is a mock skill instructions file.
"""

MOCK_PY_SCRIPT = """# Mock script
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock argparse script")
    parser.add_argument("uniprot_id", help="The UniProt ID")
    parser.add_argument("-o", "--output-dir", help="Output directory", required=True)
    parser.add_argument("--limit", type=int, default=10, help="Max limits")
    args = parser.parse_args()
    print(f"MOCK_RUN: {args.uniprot_id} {args.output_dir} {args.limit}")
"""

MOCK_SH_SCRIPT = """#!/bin/bash
echo "MOCK_SH_RUN"
"""


@pytest.fixture
def temp_skill_dir(tmp_path):
    skill_dir = tmp_path / "mock-test-skill"
    skill_dir.mkdir()

    # Write SKILL.md
    (skill_dir / "SKILL.md").write_text(MOCK_SKILL_MD, encoding="utf-8")

    # Write scripts
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "fetch.py").write_text(MOCK_PY_SCRIPT, encoding="utf-8")
    (scripts_dir / "cleanup.sh").write_text(MOCK_SH_SCRIPT, encoding="utf-8")

    return skill_dir


def test_parse_skill_yaml(temp_skill_dir):
    meta = parse_skill_yaml(temp_skill_dir / "SKILL.md")
    assert meta["name"] == "mock-test-skill"
    assert meta["description"] == "A mock skill to test conversion"


def test_parse_python_script_args(temp_skill_dir):
    args = parse_python_script_args(temp_skill_dir / "scripts" / "fetch.py")
    assert len(args) == 3

    uniprot = next(a for a in args if a["name"] == "uniprot_id")
    assert uniprot["is_optional"] is False
    assert uniprot["type"] == "str"

    out_dir = next(a for a in args if a["name"] == "output_dir")
    assert out_dir["is_optional"] is True
    assert out_dir["flag"] == "--output-dir"
    assert out_dir["required"] is True

    limit = next(a for a in args if a["name"] == "limit")
    assert limit["is_optional"] is True
    assert limit["flag"] == "--limit"
    assert limit["type"] == "int"
    assert limit["default"] == 10


def test_convert_skill_to_workflow(temp_skill_dir, tmp_path, monkeypatch):
    # Mock workspace_root logic to point to temp directory
    (tmp_path / "inthon.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

    inth_path, schema_path = convert_skill_to_workflow(temp_skill_dir, tmp_path)

    assert inth_path.exists()
    assert schema_path.exists()

    # Check .inth content
    inth_content = inth_path.read_text(encoding="utf-8")
    assert "use tool skill.mock_test_skill.fetch" in inth_content
    assert "use tool skill.mock_test_skill.cleanup" in inth_content
    assert "agent MockTestSkillAgent" in inth_content
    assert "A mock skill to test conversion" in inth_content
    assert "fn run_mock_test_skill_fetch" in inth_content
    assert "fn run_mock_test_skill_cleanup" in inth_content

    # Check schema json content
    import json

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["skill_name"] == "mock-test-skill"
    assert len(schema["tools"]) == 2

    tools = {t["name"]: t for t in schema["tools"]}
    assert "skill.mock_test_skill.fetch" in tools
    assert "skill.mock_test_skill.cleanup" in tools


def test_dynamic_registration_and_execution(temp_skill_dir, tmp_path, monkeypatch):
    (tmp_path / "inthon.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

    # Convert first to populate the schema in .inthon/skills/
    convert_skill_to_workflow(temp_skill_dir, tmp_path)

    registry = ToolRegistry()
    register_skills(registry)

    # Check tools registered
    tools = registry.list_tools()
    assert "skill.mock_test_skill.cleanup" in tools
    assert "skill.mock_test_skill.fetch" in tools

    # Test Mock Execution
    registry.use_mocks(True)
    res_mock = registry.call(
        "skill.mock_test_skill.fetch",
        args=[],
        kwargs={"uniprot_id": "P12345", "output_dir": "/tmp", "limit": 5},
    )
    assert res_mock.success is True
    assert "Mock execution" in res_mock.output
    assert "uniprot_id=P12345" in res_mock.output

    # Test Real Execution
    registry.use_mocks(False)
    res_real = registry.call(
        "skill.mock_test_skill.fetch",
        args=[],
        kwargs={"uniprot_id": "P12345", "output_dir": "/tmp", "limit": 5},
    )
    assert res_real.success is True
    # The output should come from stdout of the script
    assert "MOCK_RUN: P12345 /tmp 5" in res_real.output.strip()


def test_cli_convert_skill(temp_skill_dir, tmp_path, monkeypatch):
    (tmp_path / "inthon.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app, ["convert-skill", str(temp_skill_dir), "-o", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "Skill converted successfully" in result.stdout

    # Verify files created
    assert (tmp_path / "mock_test_skill_workflow.inth").exists()
    assert (tmp_path / ".inthon" / "skills" / "mock_test_skill.json").exists()
