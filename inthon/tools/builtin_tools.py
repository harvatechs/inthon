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
    if mock:
        registry.use_mocks(True)

def _web_search_mock(query: str, limit: int = 5) -> list[dict]:
    return [
        {
            "title": f"Result {i+1} for: {query}",
            "url": f"https://example.com/res{i+1}",
            "snippet": f"Snippet {i+1}"
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
