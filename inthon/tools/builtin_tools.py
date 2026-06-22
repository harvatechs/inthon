from __future__ import annotations
from .schema import ToolSpec, ToolArgSchema, ToolCostModel
from .registry import ToolRegistry


def register_builtins(registry: ToolRegistry, mock: bool = True) -> None:
    """Register the standard built-in tool set. Uses mock implementations by default."""
    # ── web.search ──────────────────────────────────────────────────────────
    registry.register(
        spec=ToolSpec(
            name="web.search",
            description="Search the web and return ranked results",
            input_schema={
                "query": ToolArgSchema(type="str", description="Search query"),
                "limit": ToolArgSchema(type="int", required=False, default=5),
            },
            output_schema={"results": "list[dict]"},
            side_effects=["network"],
            required_permissions=["allow_network"],
            cost_model=ToolCostModel(base_usd=0.0, per_call_usd=0.005),
        ),
        impl=_web_search_real,
        mock_impl=_web_search_mock,
    )
    # ── web.read ────────────────────────────────────────────────────────────
    registry.register(
        spec=ToolSpec(
            name="web.read",
            description="Fetch and parse the text content of a URL",
            input_schema={
                "url": ToolArgSchema(type="str", description="URL to fetch"),
            },
            output_schema={"content": "str"},
            side_effects=["network"],
            required_permissions=["allow_network"],
            cost_model=ToolCostModel(base_usd=0.0, per_call_usd=0.003),
        ),
        impl=_web_read_real,
        mock_impl=_web_read_mock,
    )
    
    # Register converted skills dynamically
    register_skills(registry)

    if mock:
        registry.use_mocks(True)


def _web_search_mock(query: str, limit: int = 5) -> list[dict]:
    return [
        {
            "title": f"Result {i + 1} for: {query}",
            "url": f"https://example.com/res{i + 1}",
            "snippet": f"Snippet {i + 1}",
        }
        for i in range(limit)
    ]


def _web_read_mock(url: str) -> str:
    return f"[Mock content from {url}]"


def _web_search_real(query: str, limit: int = 5) -> list[dict]:
    raise NotImplementedError("Real web.search requires API key configuration")


def _web_read_real(url: str) -> str:
    import urllib.request

    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="replace")[:50_000]


def register_skills(registry: ToolRegistry) -> None:
    from pathlib import Path
    import json
    import subprocess
    import sys
    import shutil
    from .schema import ToolSpec, ToolArgSchema, ToolCostModel

    # Check .inthon/skills/ directory in current dir and parents
    skills_dir = None
    for p in [Path.cwd(), *Path.cwd().parents]:
        d = p / ".inthon" / "skills"
        if d.is_dir():
            skills_dir = d
            break
            
    if not skills_dir:
        return
        
    for json_path in sorted(skills_dir.glob("*.json")):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for t in data.get("tools", []):
                name = t.get("name")
                description = t.get("description", "")
                script_path = t.get("script_path")
                args_list = t.get("args", [])
                
                # Build ToolSpec
                input_schema = {}
                for arg in args_list:
                    input_schema[arg["name"]] = ToolArgSchema(
                        type=arg.get("type", "str"),
                        description=arg.get("description", ""),
                        required=arg.get("required", True),
                        default=arg.get("default", None)
                    )
                
                spec = ToolSpec(
                    name=name,
                    description=description,
                    input_schema=input_schema,
                    output_schema={"output": "str"},
                    side_effects=["shell"],
                    required_permissions=["allow_shell"],
                    cost_model=ToolCostModel(base_usd=0.0, per_call_usd=0.01)
                )
                
                # Real implementation
                def make_impl(spath, alist):
                    def impl(**kwargs):
                        uv_path = shutil.which("uv")
                        
                        cmd = []
                        if uv_path:
                            cmd = [uv_path, "run", spath]
                        else:
                            cmd = [sys.executable, spath]
                            
                        for arg in alist:
                            val = kwargs.get(arg["name"])
                            if val is not None:
                                if arg["is_optional"]:
                                    cmd.append(arg["flag"])
                                    cmd.append(str(val))
                                else:
                                    cmd.append(str(val))
                        
                        res = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace"
                        )
                        if res.returncode != 0:
                            raise RuntimeError(
                                f"Skill script failed with code {res.returncode}:\n"
                                f"STDOUT:\n{res.stdout}\n"
                                f"STDERR:\n{res.stderr}"
                            )
                        return res.stdout
                    return impl
                
                # Mock implementation
                def make_mock(n, spath, alist):
                    def mock_impl(**kwargs):
                        args_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
                        return f"[Mock execution of {n} using {spath} with args: {args_str}]"
                    return mock_impl
                
                registry.register(
                    spec=spec,
                    impl=make_impl(script_path, args_list),
                    mock_impl=make_mock(name, script_path, args_list)
                )
        except Exception:
            pass

