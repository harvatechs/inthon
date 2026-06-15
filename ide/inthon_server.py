"""
Inthon IDE Server — bridges the HTML IDE frontend to the real Inthon compiler.
Runs on http://localhost:7474

Usage:
    python inthon_server.py
"""

from __future__ import annotations
import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Ensure the inthon package is importable
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PORT = 7474
VERSION = "0.1.0"

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _json_response(handler: "IDERequestHandler", status: int, data: dict) -> None:
    body = json.dumps(data, indent=2, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    for k, v in CORS_HEADERS.items():
        handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(body)


def handle_compile(source: str, mock_tools: bool, max_cost: float) -> dict:
    """Run full compilation + execution pipeline."""
    try:
        from inthon import run as inthon_run

        result = inthon_run(source, mock_tools=mock_tools)
        return {
            "ok": True,
            "output": str(result.output) if result.output is not None else "none",
            "trace": json.loads(result.trace_json) if result.trace_json else [],
            "cost_usd": result.cost_usd,
            "duration_ms": result.duration_ms,
            "errors": result.errors,
        }
    except Exception as e:
        tb = traceback.format_exc()
        return {
            "ok": False,
            "error": str(e),
            "traceback": tb,
            "output": None,
            "trace": [],
            "cost_usd": 0.0,
            "duration_ms": 0.0,
            "errors": [{"message": str(e), "traceback": tb}],
        }


def handle_check(source: str) -> dict:
    """Parse + semantic analysis only — no execution."""
    try:
        from inthon.parser.parser import parse
        from inthon.semantic.analyzer import SemanticAnalyzer

        program = parse(source, filename="<ide>")
        analyzer = SemanticAnalyzer()
        try:
            analyzer.analyze(program)
            warnings = analyzer.warnings
            errors = []
        except Exception as sem_err:
            errors = [{"message": str(sem_err), "type": "semantic"}]
            warnings = getattr(analyzer, "warnings", [])

        return {
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": [{"message": w} for w in warnings],
        }
    except Exception as e:
        tb = traceback.format_exc()
        # Try to extract line/col from error message
        error_info = _parse_error_location(str(e))
        return {
            "ok": False,
            "errors": [{"message": str(e), "traceback": tb, **error_info}],
            "warnings": [],
        }


def handle_ast(source: str) -> dict:
    """Return the AST as JSON."""
    try:
        from inthon.parser.parser import parse
        from inthon.ast.printer import ast_to_json

        program = parse(source, filename="<ide>")
        ast_json_str = ast_to_json(program)
        return {"ok": True, "ast": json.loads(ast_json_str)}
    except Exception as e:
        return {"ok": False, "error": str(e), "ast": None}


def handle_ir(source: str) -> dict:
    """Return the IR as JSON."""
    try:
        from inthon.parser.parser import parse
        from inthon.ir.builder import build_ir
        from inthon.ir.serializer import ir_to_json

        program = parse(source, filename="<ide>")
        ir = build_ir(program)
        ir_json_str = ir_to_json(ir)
        return {"ok": True, "ir": json.loads(ir_json_str)}
    except Exception as e:
        return {"ok": False, "error": str(e), "ir": None}


def handle_format(source: str) -> dict:
    """Format the source code."""
    try:
        lines = [line.rstrip() for line in source.splitlines()]
        formatted = "\n".join(lines) + "\n"
        return {"ok": True, "formatted": formatted}
    except Exception as e:
        return {"ok": False, "error": str(e), "formatted": source}


def _parse_error_location(msg: str) -> dict:
    """Try to extract line/col info from Lark error messages."""
    import re

    # Lark: "...at line X col Y..."
    m = re.search(r"line (\d+).*?col(?:umn)? (\d+)", msg, re.IGNORECASE)
    if m:
        return {"line": int(m.group(1)), "col": int(m.group(2))}
    # "...line X..."
    m = re.search(r"line (\d+)", msg, re.IGNORECASE)
    if m:
        return {"line": int(m.group(1)), "col": 1}
    return {}


class IDERequestHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Quiet server logging
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "version": VERSION,
                    "python": sys.version,
                    "inthon": _get_inthon_version(),
                },
            )
        else:
            _json_response(self, 404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")

        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            _json_response(self, 400, {"ok": False, "error": "Invalid JSON"})
            return

        source = payload.get("source", "")
        mock_tools = payload.get("mock_tools", True)
        max_cost = float(payload.get("max_cost", 1.0))

        route_map = {
            "/compile": lambda: handle_compile(source, mock_tools, max_cost),
            "/check": lambda: handle_check(source),
            "/ast": lambda: handle_ast(source),
            "/ir": lambda: handle_ir(source),
            "/format": lambda: handle_format(source),
        }

        handler = route_map.get(self.path)
        if handler:
            result = handler()
            _json_response(self, 200, result)
        else:
            _json_response(
                self, 404, {"ok": False, "error": f"Unknown route: {self.path}"}
            )


def _get_inthon_version() -> str:
    try:
        from inthon.version import __version__

        return __version__
    except Exception:
        return "unknown"


def main():
    server = HTTPServer(("localhost", PORT), IDERequestHandler)
    print(f"[Inthon IDE Server] Running on http://localhost:{PORT}")
    print(
        f"[Inthon IDE Server] Python {sys.version.split()[0]}, Inthon {_get_inthon_version()}"
    )
    print("[Inthon IDE Server] Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Inthon IDE Server] Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
