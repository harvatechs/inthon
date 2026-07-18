from __future__ import annotations
import json
import urllib.request
import urllib.parse
from typing import Any, Callable
from .schema import ToolSpec, ToolParam, ToolArgSchema
from .registry import ToolRegistry


def register_openapi_tools(
    registry: ToolRegistry,
    openapi_spec: dict | str,
    namespace: str,
    base_url: str | None = None,
) -> None:
    """
    Parse an OpenAPI 3.x specification and register its endpoints as Inthon tools.
    """
    if isinstance(openapi_spec, str):
        spec = json.loads(openapi_spec)
    else:
        spec = openapi_spec

    # Resolve base URL
    if not base_url:
        servers = spec.get("servers", [])
        if servers:
            base_url = servers[0].get("url", "")
        else:
            base_url = "http://localhost"

    paths = spec.get("paths", {})
    for path, path_item in paths.items():
        for method, op_item in path_item.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue

            # Resolve operation identifier and name
            op_id = op_item.get("operationId")
            if not op_id:
                # Fallback: construct from method and path
                clean_path = path.replace("/", "_").replace("{", "").replace("}", "")
                op_id = f"{method.lower()}{clean_path}"

            tool_name = f"{namespace}.{op_id}"
            description = op_item.get("summary", "") or op_item.get("description", "")
            if not description:
                description = f"Call {method.upper()} {path}"

            input_schema: dict[str, ToolArgSchema] = {}
            path_params: list[str] = []
            query_params: list[str] = []
            header_params: list[str] = []
            body_properties: list[str] = []

            # 1. Parse parameters (path, query, header)
            params_list = op_item.get("parameters", []) + path_item.get(
                "parameters", []
            )
            for p in params_list:
                name = p.get("name")
                p_in = p.get("in", "query")
                required = p.get("required", False)
                p_schema = p.get("schema", {})
                p_type = p_schema.get("type", "str")
                if p_type == "integer":
                    p_type = "int"
                elif p_type == "boolean":
                    p_type = "bool"
                elif p_type == "number":
                    p_type = "float"
                elif p_type == "string":
                    p_type = "str"

                # Store param classification
                if p_in == "path":
                    path_params.append(name)
                    required = True
                elif p_in == "query":
                    query_params.append(name)
                elif p_in == "header":
                    header_params.append(name)

                input_schema[name] = ToolArgSchema(
                    type=p_type,
                    description=p.get("description", ""),
                    required=required,
                    default=p_schema.get("default"),
                )

            # 2. Parse requestBody
            req_body = op_item.get("requestBody", {})
            content = req_body.get("content", {})
            json_media = content.get("application/json", {})
            body_schema = json_media.get("schema", {})
            if body_schema:
                props = body_schema.get("properties", {})
                required_props = body_schema.get("required", [])
                for name, p_details in props.items():
                    p_type = p_details.get("type", "str")
                    if p_type == "integer":
                        p_type = "int"
                    elif p_type == "boolean":
                        p_type = "bool"
                    elif p_type == "number":
                        p_type = "float"
                    elif p_type == "string":
                        p_type = "str"

                    body_properties.append(name)
                    input_schema[name] = ToolArgSchema(
                        type=p_type,
                        description=p_details.get("description", ""),
                        required=name in required_props,
                        default=p_details.get("default"),
                    )

            # Build implementation functions
            def make_impl(
                m: str,
                p_tpl: str,
                p_params: list[str],
                q_params: list[str],
                h_params: list[str],
                b_props: list[str],
                b_url: str,
            ) -> Callable:
                def impl(**kwargs: Any) -> Any:
                    # Construct URL path replacement
                    resolved_path = p_tpl
                    for param in p_params:
                        val = kwargs.get(param)
                        if val is not None:
                            resolved_path = resolved_path.replace(
                                f"{{{param}}}", str(val)
                            )

                    full_url = b_url.rstrip("/") + "/" + resolved_path.lstrip("/")

                    # Query parameters
                    qs = {}
                    for q in q_params:
                        if q in kwargs and kwargs[q] is not None:
                            qs[q] = kwargs[q]
                    if qs:
                        full_url += "?" + urllib.parse.urlencode(qs)

                    # Headers
                    headers = {"Content-Type": "application/json"}
                    for h in h_params:
                        if h in kwargs and kwargs[h] is not None:
                            headers[h] = str(kwargs[h])

                    # Request Body
                    body_data = {}
                    for b in b_props:
                        if b in kwargs and kwargs[b] is not None:
                            body_data[b] = kwargs[b]

                    data_bytes = None
                    if body_data:
                        data_bytes = json.dumps(body_data).encode("utf-8")

                    req = urllib.request.Request(
                        full_url,
                        data=data_bytes,
                        headers=headers,
                        method=m.upper(),
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            res_bytes = resp.read()
                            try:
                                return json.loads(res_bytes.decode("utf-8"))
                            except Exception:
                                return res_bytes.decode("utf-8")
                    except urllib.error.HTTPError as he:
                        err_content = he.read().decode("utf-8", errors="replace")
                        raise RuntimeError(
                            f"HTTP {he.code}: {he.reason}\n{err_content}"
                        )
                    except Exception as e:
                        raise RuntimeError(f"OpenAPI HTTP call failed: {e}")

                return impl

            def make_mock(n: str, m: str, p_tpl: str) -> Callable:
                def mock_impl(**kwargs: Any) -> Any:
                    return {
                        "mock": True,
                        "tool": n,
                        "method": m.upper(),
                        "path": p_tpl,
                        "args": kwargs,
                    }

                return mock_impl

            params_list = []
            for name, arg_schema in input_schema.items():
                params_list.append(ToolParam(
                    name=name,
                    type=arg_schema.type,
                    required=arg_schema.required,
                    default=arg_schema.default,
                    description=arg_schema.description
                ))

            spec = ToolSpec(
                path=tool_name,
                description=description,
                params=tuple(params_list),
                returns="any",
                side_effects=("network",),
                permissions=("allow_network",),
                cost_usd=0.002,
                handler=make_impl(
                    method,
                    path,
                    path_params,
                    query_params,
                    header_params,
                    body_properties,
                    base_url,
                ),
                mock=make_mock(tool_name, method, path),
            )

            registry.register(spec)
