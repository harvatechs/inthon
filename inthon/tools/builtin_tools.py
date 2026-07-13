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
    import os
    import json
    import urllib.request
    import urllib.parse

    # 1. Tavily API
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        try:
            url = "https://api.tavily.com/search"
            req_data = json.dumps({"query": query, "max_results": limit}).encode(
                "utf-8"
            )
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {tavily_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = []
                for r in data.get("results", []):
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "snippet": r.get("content", ""),
                        }
                    )
                if results:
                    return results[:limit]
        except Exception:
            pass

    # 2. SerpAPI
    serpapi_key = os.environ.get("SERPAPI_API_KEY")
    if serpapi_key:
        try:
            params = urllib.parse.urlencode(
                {"q": query, "api_key": serpapi_key, "engine": "google"}
            )
            url = f"https://serpapi.com/search.json?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = []
                for r in data.get("organic_results", []):
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "url": r.get("link", ""),
                            "snippet": r.get("snippet", ""),
                        }
                    )
                if results:
                    return results[:limit]
        except Exception:
            pass

    # 3. Google Custom Search Engine
    google_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CSE_ID")
    if google_key and google_cx:
        try:
            params = urllib.parse.urlencode(
                {"q": query, "key": google_key, "cx": google_cx, "num": limit}
            )
            url = f"https://www.googleapis.com/customsearch/v1?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = []
                for r in data.get("items", []):
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "url": r.get("link", ""),
                            "snippet": r.get("snippet", ""),
                        }
                    )
                if results:
                    return results[:limit]
        except Exception:
            pass

    # 4. Fallback: DuckDuckGo + Wikipedia (Keyless APIs)
    results = []

    # 4a. DuckDuckGo Instant Answer API
    try:
        ddg_url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json"}
        )
        req = urllib.request.Request(ddg_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("AbstractText"):
                results.append(
                    {
                        "title": data.get("Heading", query),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("AbstractText", ""),
                    }
                )
            for topic in data.get("RelatedTopics", []):
                if "FirstURL" in topic and "Text" in topic:
                    results.append(
                        {
                            "title": topic.get("Text", "").split(" - ")[0],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                        }
                    )
    except Exception:
        pass

    # 4b. Wikipedia OpenSearch API
    try:
        wiki_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "opensearch", "search": query, "limit": limit, "format": "json"}
        )
        req = urllib.request.Request(wiki_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            wiki_data = json.loads(resp.read().decode("utf-8"))
            if len(wiki_data) >= 4:
                titles = wiki_data[1]
                snippets = wiki_data[2]
                urls = wiki_data[3]
                for i in range(len(titles)):
                    url = urls[i]
                    if not any(r["url"] == url for r in results):
                        results.append(
                            {
                                "title": titles[i],
                                "url": url,
                                "snippet": snippets[i]
                                or f"Wikipedia article about {titles[i]}.",
                            }
                        )
    except Exception:
        pass

    # Fallback if empty
    if not results:
        results = [
            {
                "title": f"No online results for '{query}'",
                "url": "https://en.wikipedia.org/wiki/Special:Search",
                "snippet": f"Could not fetch real-time search results for query: {query}. Please check your internet connection.",
            }
        ]
    return results[:limit]


def _web_read_real(url: str) -> str:
    import urllib.request
    import re

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw_bytes = resp.read()

        # 1. Try to get charset from Content-Type header
        content_type = resp.headers.get("Content-Type", "")
        charset = None
        if "charset=" in content_type.lower():
            charset = content_type.lower().split("charset=")[-1].strip()
            charset = charset.split(";")[0].strip()

        # 2. Try to get charset from HTML meta tags in first 4096 bytes
        if not charset:
            try:
                prefix = raw_bytes[:4096].decode("latin-1", errors="ignore")
                # Look for <meta charset="xxxx">
                match1 = re.search(
                    r'<meta\s+charset=["\']?([a-zA-Z0-9_-]+)["\']?',
                    prefix,
                    re.IGNORECASE,
                )
                if match1:
                    charset = match1.group(1)
                else:
                    # Look for <meta http-equiv="Content-Type" content="...charset=xxxx">
                    match2 = re.search(
                        r'content=["\']?[^"\'>]*charset=([a-zA-Z0-9_-]+)',
                        prefix,
                        re.IGNORECASE,
                    )
                    if match2:
                        charset = match2.group(1)
            except Exception:
                pass

        # 3. Fallback logic
        if not charset:
            charset = "utf-8"

        try:
            html = raw_bytes.decode(charset, errors="replace")
        except Exception:
            html = raw_bytes.decode("utf-8", errors="replace")

        return html[:100_000]


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
                        default=arg.get("default", None),
                    )

                spec = ToolSpec(
                    name=name,
                    description=description,
                    input_schema=input_schema,
                    output_schema={"output": "str"},
                    side_effects=["shell"],
                    required_permissions=["allow_shell"],
                    cost_model=ToolCostModel(base_usd=0.0, per_call_usd=0.01),
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
                            errors="replace",
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
                    mock_impl=make_mock(name, script_path, args_list),
                )
        except Exception:
            pass
