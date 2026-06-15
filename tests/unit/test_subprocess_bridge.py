"""
tests/unit/test_subprocess_bridge.py — Unit tests for secure subprocess sandboxing (Phase 3).
"""

import pytest
from inthon.runtime.context import ExecutionContext
from inthon.pybridge.importer import SafeModuleImporter
from inthon.pybridge.subprocess_bridge import SubprocessBridgeError


def test_subprocess_bridge_success():
    """Verify loading allowed module and basic operations."""
    ctx = ExecutionContext()
    ctx.config = {"pybridge": {"sandbox": "strict"}}

    importer = SafeModuleImporter(ctx=ctx)
    js = importer.import_module("json")

    # Test method calls
    res = js.loads('{"a": 10}')
    assert res == {"a": 10}

    res_str = js.dumps({"b": 20})
    assert "20" in res_str


def test_subprocess_bridge_blocked_module():
    """Verify that importing non-allowlisted modules fails in strict sandbox mode."""
    ctx = ExecutionContext()
    ctx.config = {"pybridge": {"sandbox": "strict"}}

    importer = SafeModuleImporter(ctx=ctx)
    with pytest.raises(Exception) as exc:
        importer.import_module("os")
    assert "not permitted" in str(exc.value) or "ImportError" in str(exc.value)


def test_subprocess_bridge_private_attribute_blocked():
    """Verify that private/dunder attribute access is denied."""
    ctx = ExecutionContext()
    ctx.config = {"pybridge": {"sandbox": "strict"}}

    importer = SafeModuleImporter(ctx=ctx)
    js = importer.import_module("json")

    # Access private attributes directly should fail
    with pytest.raises(SubprocessBridgeError) as exc:
        _ = js._private
    assert "Access to private attribute" in str(exc.value)

    # Access dunder attributes
    with pytest.raises(SubprocessBridgeError) as exc:
        _ = js.__subclasses__
    assert "Access to private attribute" in str(exc.value)


def test_subprocess_bridge_error_propagation():
    """Verify that exceptions raised in the sandbox worker are correctly wrapped and propagated."""
    ctx = ExecutionContext()
    ctx.config = {"pybridge": {"sandbox": "strict"}}

    importer = SafeModuleImporter(ctx=ctx)
    js = importer.import_module("json")

    with pytest.raises(SubprocessBridgeError) as exc:
        # Invalid json format will raise JSONDecodeError in worker
        js.loads("invalid json")
    assert "JSONDecodeError" in str(exc.value)
