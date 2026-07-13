from inthon.tools.registry import ToolRegistry
from inthon.tools.openapi import register_openapi_tools

SAMPLE_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Sample API", "version": "1.0.0"},
    "servers": [{"url": "https://api.sample.com/v1"}],
    "paths": {
        "/users/{id}": {
            "get": {
                "operationId": "getUser",
                "summary": "Get user by ID",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "fields",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                    },
                ],
            }
        },
        "/users": {
            "post": {
                "operationId": "createUser",
                "summary": "Create a new user",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name", "email"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "age": {"type": "integer"},
                                },
                            }
                        }
                    },
                },
            }
        },
    },
}


def test_openapi_tool_parsing_and_registration():
    registry = ToolRegistry()
    register_openapi_tools(registry, SAMPLE_OPENAPI_SPEC, namespace="sample")

    # Verify registered tools
    tools = registry.list_tools()
    assert "sample.getUser" in tools
    assert "sample.createUser" in tools

    # Check sample.getUser spec
    spec_get = registry.get_spec("sample.getUser")
    assert spec_get.name == "sample.getUser"
    assert "id" in spec_get.input_schema
    assert spec_get.input_schema["id"].required is True
    assert spec_get.input_schema["id"].type == "str"
    assert "fields" in spec_get.input_schema
    assert spec_get.input_schema["fields"].required is False

    # Check sample.createUser spec
    spec_post = registry.get_spec("sample.createUser")
    assert spec_post.name == "sample.createUser"
    assert spec_post.input_schema["name"].required is True
    assert spec_post.input_schema["email"].required is True
    assert spec_post.input_schema["age"].required is False
    assert spec_post.input_schema["age"].type == "int"


def test_openapi_mock_calls():
    registry = ToolRegistry()
    register_openapi_tools(registry, SAMPLE_OPENAPI_SPEC, namespace="sample")
    registry.use_mocks(True)

    # Call getUser mock
    res_get = registry.call(
        "sample.getUser", args=["user_123"], kwargs={"fields": "name,email"}
    )
    assert res_get.success is True
    assert res_get.output["mock"] is True
    assert res_get.output["tool"] == "sample.getUser"
    assert res_get.output["method"] == "GET"
    assert res_get.output["path"] == "/users/{id}"
    assert res_get.output["args"]["id"] == "user_123"
    assert res_get.output["args"]["fields"] == "name,email"

    # Call createUser mock
    res_post = registry.call(
        "sample.createUser",
        args=[],
        kwargs={"name": "Alice", "email": "alice@example.com", "age": 30},
    )
    assert res_post.success is True
    assert res_post.output["mock"] is True
    assert res_post.output["args"]["name"] == "Alice"
    assert res_post.output["args"]["email"] == "alice@example.com"
    assert res_post.output["args"]["age"] == 30
