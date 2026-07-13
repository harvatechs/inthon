import pytest
from inthon.runtime.context import ExecutionContext
from inthon.pybridge.importer import SafeModuleImporter, PyBridgeError
from inthon.pybridge.allowlist import AllowlistConfig
from inthon.pybridge.subprocess_bridge import SubprocessBridgeError
from inthon.runtime.errors import IntHonRuntimeError
from inthon import run, run_vm


def test_strict_sandbox_hardening_pathlib_os():
    """Verify that pathlib.os attribute traversal is blocked in strict mode."""
    ctx = ExecutionContext()
    ctx.config = {"pybridge": {"sandbox": "strict"}}
    importer = SafeModuleImporter(
        config=AllowlistConfig(extra_allowed={"pathlib"}), ctx=ctx
    )
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
    ctx = ExecutionContext()
    importer = SafeModuleImporter(config=AllowlistConfig(extra_allowed={"io"}), ctx=ctx)
    io_mod = importer.import_module("io")
    with pytest.raises(Exception) as exc:
        _ = io_mod.open
    assert "is blocked" in str(exc.value)


# --- 16 Additional Sandbox Attack Vector Tests ---


def test_sandbox_dunder_bases():
    source = "use py.random\nlet r = random.Random()\nlet x = r.__class__.__bases__"
    with pytest.raises(IntHonRuntimeError) as exc:
        run(source)
    assert "Access to attribute '__class__' is denied" in str(exc.value)


def test_sandbox_dunder_subclasses():
    source = (
        "use py.random\nlet r = random.Random()\nlet x = r.__class__.__subclasses__"
    )
    with pytest.raises(IntHonRuntimeError) as exc:
        run(source)
    assert "Access to attribute '__class__' is denied" in str(exc.value)


def test_sandbox_dunder_globals():
    source = "use py.random\nlet r = random.randint\nlet x = r.__globals__"
    with pytest.raises(IntHonRuntimeError) as exc:
        run(source)
    assert "Access to attribute '__globals__' is denied" in str(exc.value)


def test_sandbox_dunder_code():
    source = "use py.random\nlet r = random.randint\nlet x = r.__code__"
    with pytest.raises(IntHonRuntimeError) as exc:
        run(source)
    assert "Access to attribute '__code__' is denied" in str(exc.value)


def test_sandbox_dunder_dict():
    source = "use py.random\nlet r = random.Random()\nlet x = r.__dict__"
    with pytest.raises(IntHonRuntimeError) as exc:
        run(source)
    assert "Access to attribute '__dict__' is denied" in str(exc.value)


def test_sandbox_sys_blocked():
    source = "use py.sys"

    with pytest.raises(PyBridgeError) as exc:
        run(source)
    assert "is not permitted" in str(exc.value)


def test_sandbox_os_blocked():
    source = "use py.os"

    with pytest.raises(PyBridgeError) as exc:
        run(source)
    assert "is not permitted" in str(exc.value)


def test_sandbox_subprocess_blocked():
    source = "use py.subprocess"

    with pytest.raises(PyBridgeError) as exc:
        run(source)
    assert "is not permitted" in str(exc.value)


def test_sandbox_socket_blocked():
    source = "use py.socket"

    with pytest.raises(PyBridgeError) as exc:
        run(source)
    assert "is not permitted" in str(exc.value)


def test_sandbox_ctypes_blocked():
    source = "use py.ctypes"

    with pytest.raises(PyBridgeError) as exc:
        run(source)
    assert "is not permitted" in str(exc.value)


def test_sandbox_importlib_blocked():
    source = "use py.importlib"

    with pytest.raises(PyBridgeError) as exc:
        run(source)
    assert "is not permitted" in str(exc.value)


def test_sandbox_pickle_blocked():
    source = "use py.pickle"

    with pytest.raises(PyBridgeError) as exc:
        run(source)
    assert "is not permitted" in str(exc.value)


def test_sandbox_alias_import_bypass_attempt():
    source = "use py.sys as my_sys"

    with pytest.raises(PyBridgeError) as exc:
        run(source)
    assert "is not permitted" in str(exc.value)


def test_sandbox_eval_blocked():
    from inthon.pybridge.allowlist import is_safe_attribute_access
    import builtins

    assert is_safe_attribute_access(None, "eval", builtins.eval) is False


def test_sandbox_exec_blocked():
    from inthon.pybridge.allowlist import is_safe_attribute_access
    import builtins

    assert is_safe_attribute_access(None, "exec", builtins.exec) is False


def test_sandbox_open_blocked():
    from inthon.pybridge.allowlist import is_safe_attribute_access
    import builtins

    assert is_safe_attribute_access(None, "open", builtins.open) is False
