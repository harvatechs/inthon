"""
inthon.pybridge.subprocess_bridge — Secure Python module bridge via subprocess isolation.

SubprocessPyBridge replaces SafeModuleImporter in strict sandbox mode. Instead
of importing Python modules in-process (where attribute-walking attacks are
possible), it spawns an isolated sandbox_worker subprocess and communicates via
JSON-RPC over stdin/stdout pipes.

Benefits over SafeModuleImporter (soft sandbox):
- Python object introspection is impossible: all values cross the boundary as JSON.
- OS-level resource limits are applied to the worker process.
- The worker's import hook blocks all non-allowlisted modules.
- Worker crash (OOM, SIGKILL) is handled gracefully — the bridge respawns or errors.

Usage::
    bridge = SubprocessPyBridge()
    wrapper = bridge.import_module("json", alias=None)
    result = wrapper.loads(args=['"hello"'])
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from ..runtime.errors import IntHonRuntimeError


class SubprocessBridgeError(IntHonRuntimeError):
    pass


_WORKER_PATH = str(Path(__file__).parent / "sandbox_worker.py")


class SubprocessPyBridge:
    """
    Manages a pool of sandbox worker subprocesses and dispatches
    Python module calls to them via JSON-RPC.

    Thread-safety: each call acquires the lock, making this safe for
    single-threaded VM use. The async VM should use separate bridge instances.
    """

    def __init__(
        self,
        max_workers: int = 1,
        timeout_sec: float = 30.0,
    ) -> None:
        self._timeout = timeout_sec
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._req_counter = 0
        self._pending: dict[int, Any] = {}

    # ── Public API ─────────────────────────────────────────────────────── #

    def import_module(
        self, module_path: str, alias: str | None = None
    ) -> "BridgeModuleProxy":
        """Return a proxy object that calls the module's attributes via the sandbox."""
        return BridgeModuleProxy(module_path=module_path, bridge=self)

    def call(
        self,
        module_path: str,
        attr_chain: list[str],
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any:
        """Execute a function call in the sandbox worker."""
        worker = self._ensure_worker()

        req_id = self._next_id()
        request = {
            "id": req_id,
            "module": module_path,
            "attr_chain": attr_chain,
            "args": self._serialise_args(args),
            "kwargs": {k: self._serialise_value(v) for k, v in kwargs.items()},
        }

        with self._lock:
            if worker.stdin is None or worker.stdout is None:
                raise SubprocessBridgeError(
                    "INTHON_SANDBOX_PIPE: Failed to open pipes to worker process"
                )
            try:
                line = json.dumps(request) + "\n"
                worker.stdin.write(line)
                worker.stdin.flush()

                # Read response with timeout
                start = time.monotonic()
                while True:
                    if time.monotonic() - start > self._timeout:
                        self._kill_worker()
                        raise SubprocessBridgeError(
                            f"INTHON_SANDBOX_TIMEOUT: Call to '{module_path}.{'.'.join(attr_chain)}' "
                            f"exceeded {self._timeout}s timeout"
                        )
                    response_line = worker.stdout.readline()
                    if not response_line:
                        # Worker died
                        self._proc = None
                        raise SubprocessBridgeError(
                            f"INTHON_SANDBOX_CRASH: Worker process died during call to '{module_path}'"
                        )
                    try:
                        response = json.loads(response_line.strip())
                        break
                    except json.JSONDecodeError:
                        continue  # Skip malformed output

            except BrokenPipeError:
                self._proc = None
                raise SubprocessBridgeError(
                    f"INTHON_SANDBOX_PIPE: Worker pipe broken for '{module_path}'"
                )

        if response.get("error"):
            raise SubprocessBridgeError(
                f"INTHON_SANDBOX_CALL_ERROR: {response['error']}"
            )

        return response.get("result")

    def shutdown(self) -> None:
        """Terminate the worker subprocess."""
        self._kill_worker()

    # ── Internal helpers ───────────────────────────────────────────────── #

    def _ensure_worker(self) -> subprocess.Popen:
        """Spawn a worker subprocess if one is not already running."""
        if self._proc is not None and self._proc.poll() is None:
            return self._proc

        self._proc = subprocess.Popen(
            [sys.executable, _WORKER_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )
        return self._proc

    def _kill_worker(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def _next_id(self) -> int:
        self._req_counter += 1
        return self._req_counter

    @staticmethod
    def _serialise_value(val: Any) -> Any:
        """Convert a value to a JSON-safe representation."""
        if isinstance(val, (bool, int, float, str, type(None))):
            return val
        if isinstance(val, (list, tuple)):
            return [SubprocessPyBridge._serialise_value(v) for v in val]
        if isinstance(val, dict):
            return {
                str(k): SubprocessPyBridge._serialise_value(v) for k, v in val.items()
            }
        return str(val)  # Fallback: repr

    @classmethod
    def _serialise_args(cls, args: list[Any]) -> list[Any]:
        return [cls._serialise_value(a) for a in args]

    def __del__(self) -> None:
        self._kill_worker()


class BridgeModuleProxy:
    """
    Proxy returned by SubprocessPyBridge.import_module().
    Attribute access builds up a call chain; calling the proxy dispatches
    to the sandbox worker.
    """

    def __init__(
        self,
        module_path: str,
        bridge: SubprocessPyBridge,
        attr_chain: list[str] | None = None,
    ) -> None:
        self._module_path = module_path
        self._bridge = bridge
        self._attr_chain: list[str] = attr_chain or []

    def __getattr__(self, name: str) -> "BridgeModuleProxy":
        if name.startswith("_"):
            raise SubprocessBridgeError(
                f"INTHON_SANDBOX: Access to private attribute '{name}' is denied."
            )
        return BridgeModuleProxy(
            module_path=self._module_path,
            bridge=self._bridge,
            attr_chain=[*self._attr_chain, name],
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._bridge.call(
            module_path=self._module_path,
            attr_chain=self._attr_chain,
            args=list(args),
            kwargs=kwargs,
        )

    def __repr__(self) -> str:
        chain = ".".join([self._module_path, *self._attr_chain])
        return f"<BridgeProxy '{chain}'>"
