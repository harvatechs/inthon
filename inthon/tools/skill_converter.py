from __future__ import annotations
import ast
import json
import re
from pathlib import Path
from typing import Any


def parse_skill_yaml(skill_md_path: Path) -> dict[str, Any]:
    """Parses YAML frontmatter from a SKILL.md file."""
    content = skill_md_path.read_text(encoding="utf-8")
    # Find block between first and second ---
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {skill_md_path}")

    yaml_text = match.group(1)
    metadata: dict[str, Any] = {}
    for line in yaml_text.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip("'\"")
        metadata[key] = val

    return metadata


def parse_python_script_args(script_path: Path) -> list[dict[str, Any]]:
    """Parses a Python script's AST to extract argparse arguments."""
    try:
        content = script_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except Exception:
        # Fallback to no parsed arguments if script cannot be parsed
        return []

    args = []

    class ArgumentFinder(ast.NodeVisitor):
        def visit_Call(self, node):
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
            ):
                arg_info = {}
                flags = []
                for arg in node.args:
                    if isinstance(arg, ast.Constant):
                        flags.append(arg.value)

                if not flags:
                    self.generic_visit(node)
                    return

                # Determine name and whether optional
                optional_flags = [f for f in flags if f.startswith("-")]
                if optional_flags:
                    long_flag = max(flags, key=len)
                    arg_info["name"] = long_flag.lstrip("-").replace("-", "_")
                    arg_info["is_optional"] = True
                    arg_info["flag"] = long_flag
                else:
                    arg_info["name"] = flags[0]
                    arg_info["is_optional"] = False
                    arg_info["flag"] = None

                arg_info["description"] = ""
                arg_info["default"] = None
                arg_info["type"] = "str"
                arg_info["required"] = not arg_info["is_optional"]

                for kw in node.keywords:
                    if kw.arg == "help" and isinstance(kw.value, ast.Constant):
                        arg_info["description"] = kw.value.value
                    elif kw.arg == "default":
                        if isinstance(kw.value, ast.Constant):
                            arg_info["default"] = kw.value.value
                    elif kw.arg == "required" and isinstance(kw.value, ast.Constant):
                        arg_info["required"] = bool(kw.value.value)
                    elif kw.arg == "type":
                        if isinstance(kw.value, ast.Name):
                            arg_info["type"] = kw.value.id

                args.append(arg_info)
            self.generic_visit(node)

    ArgumentFinder().visit(tree)
    return args


def convert_skill_to_workflow(
    skill_dir: Path, output_dir: Path | None = None
) -> tuple[Path, Path]:
    """
    Converts a skill folder into an INTHON workflow file and tool schema.
    Returns the path to the generated .inth file and the .json schema file.
    """
    if skill_dir.is_file() and skill_dir.name == "SKILL.md":
        skill_md_path = skill_dir
        skill_dir = skill_dir.parent
    else:
        skill_md_path = skill_dir / "SKILL.md"

    if not skill_md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

    metadata = parse_skill_yaml(skill_md_path)
    skill_name = metadata.get("name", skill_dir.name)
    skill_description = metadata.get("description", "")

    sanitized_skill_name = skill_name.replace("-", "_")

    scripts_dir = skill_dir / "scripts"
    tools_list: list[dict[str, Any]] = []

    # Scan scripts directory if it exists
    if scripts_dir.is_dir():
        for script_file in sorted(scripts_dir.glob("*")):
            if script_file.suffix not in (".py", ".sh", ".ps1", ".bat"):
                continue

            script_name = script_file.stem
            sanitized_script_name = script_name.replace("-", "_")

            if script_file.suffix == ".py":
                script_args = parse_python_script_args(script_file)
            else:
                script_args = []

            # If no arguments were parsed, provide a generic args fallback
            if not script_args:
                script_args = [
                    {
                        "name": "args",
                        "type": "list[str]",
                        "is_optional": True,
                        "flag": None,
                        "description": "Raw list of command line arguments",
                        "required": False,
                        "default": [],
                    }
                ]

            tools_list.append(
                {
                    "name": f"skill.{sanitized_skill_name}.{sanitized_script_name}",
                    "description": f"Executable script '{script_file.name}' from skill '{skill_name}'",
                    "script_path": str(script_file.absolute()),
                    "args": script_args,
                }
            )

    # Default to single generic script if no scripts folder found
    if not tools_list:
        tools_list.append(
            {
                "name": f"skill.{sanitized_skill_name}.run",
                "description": f"Generic runner for skill '{skill_name}'",
                "script_path": str(skill_dir.absolute()),
                "args": [
                    {
                        "name": "args",
                        "type": "list[str]",
                        "is_optional": True,
                        "flag": None,
                        "description": "Raw list of command line arguments",
                        "required": False,
                        "default": [],
                    }
                ],
            }
        )

    # 1. Generate JSON schema for tool registry
    # Target directory for schema is .inthon/skills/ inside current or parent workspace
    workspace_root = Path.cwd()
    for p in [Path.cwd(), *Path.cwd().parents]:
        if (p / "inthon.toml").is_file() or (p / ".git").is_dir():
            workspace_root = p
            break

    inthon_skills_dir = workspace_root / ".inthon" / "skills"
    inthon_skills_dir.mkdir(parents=True, exist_ok=True)

    schema_data = {"skill_name": skill_name, "tools": tools_list}

    schema_path = inthon_skills_dir / f"{sanitized_skill_name}.json"
    schema_path.write_text(json.dumps(schema_data, indent=2), encoding="utf-8")

    # 2. Generate .inth workflow template file
    inth_lines = [
        f"// Auto-generated INTHON workflow for skill: {skill_name}",
        f"// Description: {skill_description.strip()}",
        "",
    ]

    # Add imports
    for t in tools_list:
        inth_lines.append(f"use tool {t['name']}")
    inth_lines.append("")

    # Add Agent block
    agent_name = (
        "".join(part.capitalize() for part in sanitized_skill_name.split("_")) + "Agent"
    )
    inth_lines.append(f"agent {agent_name} {{")
    inth_lines.append(f"    goal {json.dumps(skill_description.strip())}")

    # inputs block based on all tools
    all_inputs = {}
    for t in tools_list:
        for arg in t["args"]:
            all_inputs[arg["name"]] = arg["type"]

    if all_inputs:
        inth_lines.append("    inputs {")
        for name, typ in all_inputs.items():
            inth_lines.append(f"        {name}: {typ}")
        inth_lines.append("    }")

    inth_lines.append("    outputs {")
    inth_lines.append("        result: str")
    inth_lines.append("    }")
    inth_lines.append("")
    inth_lines.append("    policy {")
    inth_lines.append("        allow_network: true")
    inth_lines.append("        max_tool_calls: 10")
    inth_lines.append("    }")
    inth_lines.append("")
    inth_lines.append("    plan {")
    inth_lines.append("        // Example workflow execution plan:")
    for name, typ in all_inputs.items():
        default_val = "[]" if "list" in typ else '""'
        inth_lines.append(f"        let {name} = {default_val}")

    for t in tools_list:
        arg_calls = []
        for arg in t["args"]:
            arg_calls.append(f"{arg['name']}: {arg['name']}")
        args_str = ", ".join(arg_calls)
        inth_lines.append(
            f"        let res_{t['name'].split('.')[-1]} = {t['name']}({args_str})"
        )
    inth_lines.append('        return "Skill execution completed successfully"')
    inth_lines.append("    }")
    inth_lines.append("}")
    inth_lines.append("")

    # Add Workflow functions
    for t in tools_list:
        func_name = f"run_{sanitized_skill_name}_{t['name'].split('.')[-1]}"
        params_str = ", ".join(f"{arg['name']}: {arg['type']}" for arg in t["args"])
        call_args_str = ", ".join(f"{arg['name']}" for arg in t["args"])
        inth_lines.append(f"fn {func_name}({params_str}) -> str {{")
        inth_lines.append(f"    let result = {t['name']}({call_args_str})")
        inth_lines.append("    return result")
        inth_lines.append("}")
        inth_lines.append("")

    target_output_dir = output_dir or Path.cwd()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    inth_path = target_output_dir / f"{sanitized_skill_name}_workflow.inth"
    inth_path.write_text("\n".join(inth_lines), encoding="utf-8")

    return inth_path, schema_path
