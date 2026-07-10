import pytest
from inthon.runtime.context import ExecutionContext
from inthon.pybridge.importer import SafeModuleImporter
from inthon.pybridge.allowlist import AllowlistConfig
from inthon.pybridge.subprocess_bridge import SubprocessBridgeError
from inthon.runtime.errors import IntHonRuntimeError
from inthon import run, run_vm

def test_strict_sandbox_hardening_pathlib_os():
    """Verify that pathlib.os attribute traversal is blocked in strict mode."""
    ctx = ExecutionContext()
    ctx.config = {"pybridge": {"sandbox": "strict"}}
    importer = SafeModuleImporter(config=AllowlistConfig(extra_allowed={"pathlib"}), ctx=ctx)
    pathlib = importer.import_module("pathlib")
    
    with pytest.raises(SubprocessBridgeError) as exc:
        _ = pathlib.os.system("echo strict_escaped")
    assert "Access to attribute 'os' is denied" in str(exc.value)

def test_strict_sandbox_hardening_io_open():
    """Verify that io.open attribute traversal is blocked in strict mode."""
    ctx = ExecutionContext()
    ctx.config = {"pybridge": {"sandbox": "strict"}}
    importer = SafeModuleImporter(config=AllowlistConfig(extra_allowed={"io"}), ctx=ctx)
    io_mod = importer.import_module("io")
    
    with pytest.raises(SubprocessBridgeError) as exc:
        _ = io_mod.open("foo.txt", "w")
    assert "Access to attribute 'open' is denied" in str(exc.value)

def test_soft_sandbox_hardening_interpreter():
    """Verify that dunder attribute walking is blocked in soft mode (interpreter)."""
    source = """
    use py.random
    let r = random.Random()
    let cls = r.__class__
    """
    with pytest.raises(IntHonRuntimeError) as exc:
        run(source)
    assert "Access to attribute '__class__' is denied" in str(exc.value)

def test_soft_sandbox_hardening_vm():
    """Verify that dunder attribute walking is blocked in soft mode (VM)."""
    source = """
    use py.random
    let r = random.Random()
    let cls = r.__class__
    """
    with pytest.raises(IntHonRuntimeError) as exc:
        run_vm(source)
    assert "Access to attribute '__class__' is denied" in str(exc.value)

def test_soft_sandbox_hardening_io_open_interpreter():
    """Verify that io.open is blocked in soft mode (interpreter)."""
    # Force io to be allowed in config by overriding execution context config or allowlist
    # But wait, run() reads inthon.toml by default. We can use run with custom allowlist if we mock it,
    # or we can write a test that directly calls SafeModuleImporter.
    # Let's test SafeModuleImporter's attribute check directly!
    ctx = ExecutionContext()
    importer = SafeModuleImporter(config=AllowlistConfig(extra_allowed={"io"}), ctx=ctx)
    io_mod = importer.import_module("io")
    with pytest.raises(Exception) as exc:
        _ = io_mod.open
    assert "is blocked" in str(exc.value)

