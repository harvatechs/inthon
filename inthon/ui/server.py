from __future__ import annotations
import asyncio
import uuid
import threading
from typing import Any, Callable
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from inthon.runtime.trace import TraceLogger
from inthon.policy.approval import ApprovalRequest

# Global active context
_active_context = None

def set_active_context(ctx: Any) -> None:
    global _active_context
    _active_context = ctx
    if ctx and not isinstance(ctx.tracer, UITraceLogger):
        ui_tracer = UITraceLogger()
        ui_tracer._events = ctx.tracer._events
        ctx.tracer = ui_tracer

class UITraceLogger(TraceLogger):
    def emit(
        self,
        kind: str,
        data: dict[str, Any],
        span_line: int | None = None,
        duration_ms: float | None = None,
    ) -> None:
        super().emit(kind, data, span_line, duration_ms)
        handle_trace_event(kind, data, span_line, duration_ms)

# UI State Representation
class SessionState:
    def __init__(self):
        self.title: str = "Inthon Agent Dashboard"
        self.port: int = 8000
        self.components: list[dict] = []
        self.chat_history: list[dict] = []
        self.buttons: dict[str, Callable[[], Any]] = {}
        self.chat_callback: Callable[[str], Any] | None = None
        self.websocket_connections: set[WebSocket] = set()
        self.approvals: dict[str, dict] = {}
        self.in_sidebar: bool = False
        self.loop: asyncio.AbstractEventLoop | None = None

session_state = SessionState()

def init_state(title: str, port: int) -> None:
    session_state.title = title
    session_state.port = port
    session_state.components = []
    session_state.chat_history = []
    session_state.buttons = {}
    session_state.chat_callback = None
    session_state.approvals = {}
    session_state.in_sidebar = False

def broadcast(msg: dict) -> None:
    if not session_state.loop or session_state.loop.is_closed():
        return
    async def do_broadcast():
        closed = []
        for conn in list(session_state.websocket_connections):
            try:
                await conn.send_json(msg)
            except Exception:
                closed.append(conn)
        for conn in closed:
            session_state.websocket_connections.discard(conn)
    session_state.loop.call_soon_threadsafe(
        lambda: asyncio.create_task(do_broadcast())
    )

def add_component(comp: dict) -> None:
    comp["id"] = comp.get("id") or f"comp_{uuid.uuid4().hex[:8]}"
    if session_state.in_sidebar:
        comp["sidebar"] = True
    session_state.components.append(comp)
    broadcast({"event": "add_component", "data": comp})

def sidebar_start() -> None:
    session_state.in_sidebar = True

def sidebar_end() -> None:
    session_state.in_sidebar = False

def add_chat_message(role: str, content: str) -> None:
    msg = {"id": f"msg_{uuid.uuid4().hex[:8]}", "role": role, "content": content}
    session_state.chat_history.append(msg)
    broadcast({"event": "chat_message", "data": msg})

def clear_chat() -> None:
    session_state.chat_history = []
    broadcast({"event": "clear_chat"})

def status_start(label: str) -> str:
    status_id = f"status_{uuid.uuid4().hex[:8]}"
    comp = {
        "id": status_id,
        "type": "status",
        "label": label,
        "state": "running"
    }
    add_component(comp)
    return status_id

def status_update(status_id: str, label: str) -> None:
    for comp in session_state.components:
        if comp.get("id") == status_id:
            comp["label"] = label
            broadcast({"event": "update_component", "data": comp})
            break

def status_complete(status_id: str, label: str | None = None, success: bool = True) -> None:
    for comp in session_state.components:
        if comp.get("id") == status_id:
            comp["state"] = "success" if success else "failed"
            if label is not None:
                comp["label"] = label
            broadcast({"event": "update_component", "data": comp})
            break

def add_button(label: str, callback: Callable[[], Any]) -> None:
    btn_id = f"btn_{uuid.uuid4().hex[:8]}"
    session_state.buttons[btn_id] = callback
    comp = {"id": btn_id, "type": "button", "label": label}
    add_component(comp)

def register_chat_callback(callback: Callable[[str], Any]) -> None:
    session_state.chat_callback = callback

def handle_trace_event(
    kind: str,
    data: dict[str, Any],
    span_line: int | None = None,
    duration_ms: float | None = None,
) -> None:
    if kind == "tool_call":
        tool_name = data.get("tool", "unknown tool")
        args_str = ", ".join(f"{k}={v}" for k, v in data.get("args", {}).items())
        result_str = str(data.get("result", ""))
        comp = {
            "id": f"trace_{uuid.uuid4().hex[:8]}",
            "type": "trace_step",
            "title": f"Called tool: {tool_name}",
            "subtitle": f"Arguments: ({args_str})",
            "content": result_str,
            "duration": f"{duration_ms:.1f}ms" if duration_ms else "N/A"
        }
        add_component(comp)
    elif kind == "remember":
        comp = {
            "id": f"trace_{uuid.uuid4().hex[:8]}",
            "type": "trace_step",
            "title": "Remembered fact",
            "subtitle": f"Namespace: {data.get('namespace', 'session')}",
            "content": str(data.get("key", ""))
        }
        add_component(comp)

def ui_approval_handler(req: ApprovalRequest) -> bool:
    req_id = f"req_{uuid.uuid4().hex[:8]}"
    evt = threading.Event()
    app_info = {
        "event": evt,
        "approved": False,
        "request": req
    }
    session_state.approvals[req_id] = app_info
    
    broadcast({
        "event": "approval_required",
        "data": {
            "id": req_id,
            "action": req.action,
            "target": req.target,
            "summary": req.context_summary
        }
    })
    
    evt.wait()
    
    del session_state.approvals[req_id]
    broadcast({"event": "approval_resolved", "data": {"id": req_id}})
    return app_info["approved"]

def get_metrics() -> dict:
    ctx = _active_context
    if not ctx:
        return {"cost_usd": 0.0, "tool_calls": 0, "run_id": "N/A"}
    return {
        "cost_usd": getattr(ctx, "cost_usd", 0.0),
        "tool_calls": getattr(ctx, "tool_call_count", 0),
        "run_id": getattr(ctx, "run_id", "N/A"),
    }

def get_memory_items() -> list[dict]:
    ctx = _active_context
    if not ctx or not ctx.memory:
        return []
    
    items = []
    try:
        from inthon.memory.store import InMemoryStore
        from inthon.memory.sqlite_store import SQLiteMemoryStore
        
        if isinstance(ctx.memory, InMemoryStore):
            for ns, entries in ctx.memory._store.items():
                for key, entry in entries.items():
                    items.append({
                        "key": entry.key,
                        "value": str(entry.value),
                        "namespace": entry.namespace
                    })
        elif isinstance(ctx.memory, SQLiteMemoryStore):
            cursor = ctx.memory._conn.cursor()
            cursor.execute("SELECT id, namespace, content_text FROM memory_entries ORDER BY created_at DESC")
            rows = cursor.fetchall()
            for row in rows:
                items.append({
                    "key": row["id"],
                    "value": row["content_text"],
                    "namespace": row["namespace"]
                })
    except Exception:
        pass
    return items

# FastAPI App
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def get_index():
    from pathlib import Path
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Template index.html not found</h1>")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_state.websocket_connections.add(websocket)
    
    await websocket.send_json({
        "event": "init",
        "data": {
            "title": session_state.title,
            "components": session_state.components,
            "chat_history": session_state.chat_history,
            "memory": get_memory_items(),
            "metrics": get_metrics()
        }
    })
    
    for req_id, app_info in list(session_state.approvals.items()):
        if not app_info["event"].is_set():
            await websocket.send_json({
                "event": "approval_required",
                "data": {
                    "id": req_id,
                    "action": app_info["request"].action,
                    "target": app_info["request"].target,
                    "summary": app_info["request"].context_summary
                }
            })
            
    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")
            payload = data.get("data", {})
            
            if event == "chat_message":
                text_msg = payload.get("text", "")
                if text_msg and session_state.chat_callback:
                    asyncio.create_task(run_callback_in_thread(session_state.chat_callback, text_msg))
            elif event == "button_click":
                btn_id = payload.get("id")
                callback = session_state.buttons.get(btn_id)
                if callback:
                    asyncio.create_task(run_callback_in_thread(callback))
            elif event == "approval_response":
                req_id = payload.get("id")
                approved = payload.get("approved", False)
                if req_id in session_state.approvals:
                    app_info = session_state.approvals[req_id]
                    app_info["approved"] = approved
                    app_info["event"].set()
    except WebSocketDisconnect:
        session_state.websocket_connections.discard(websocket)
    except Exception:
        session_state.websocket_connections.discard(websocket)

async def run_callback_in_thread(callback: Callable, *args):
    broadcast({"event": "status_change", "data": "thinking"})
    
    def worker():
        try:
            from inthon.runtime.values import from_python, InthonCallable
            from inthon.runtime.interpreter import Interpreter
            
            inthon_args = [from_python(a) for a in args]
            if isinstance(callback, InthonCallable):
                ctx = _active_context
                if not ctx:
                    from inthon.runtime.context import ExecutionContext
                    ctx = ExecutionContext()
                
                interpreter = Interpreter(ctx)
                interpreter._call_function(callback, inthon_args, {})
            else:
                callback(*args)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            add_chat_message("system", f"Callback Error: {str(e)}\n\n{tb}")
        finally:
            broadcast({"event": "status_change", "data": "idle"})
            broadcast({"event": "update_metrics", "data": get_metrics()})
            broadcast({"event": "update_memory", "data": get_memory_items()})
            
    await asyncio.to_thread(worker)

def start_server(port: int = 8000) -> None:
    session_state.port = port
    
    ctx = _active_context
    if ctx:
        ctx.policy.approval_gate.set_handler(ui_approval_handler)
        if not isinstance(ctx.tracer, UITraceLogger):
            ui_tracer = UITraceLogger()
            ui_tracer._events = ctx.tracer._events
            ctx.tracer = ui_tracer
            
    @app.on_event("startup")
    async def on_startup():
        session_state.loop = asyncio.get_running_loop()
        def open_browser():
            import time
            import webbrowser
            time.sleep(0.5)
            webbrowser.open(f"http://127.0.0.1:{port}")
        threading.Thread(target=open_browser, daemon=True).start()
        
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
