import asyncio
from fastapi.testclient import TestClient
from inthon import parse
from inthon.runtime.context import ExecutionContext
from inthon.runtime.interpreter import Interpreter
import inthon.ui as ui
from inthon.ui.server import app, session_state

def test_ui_api_state_accumulation():
    # Reset state
    ui.init(title="Test Board", port=9000)
    assert session_state.title == "Test Board"
    assert session_state.port == 9000
    assert len(session_state.components) == 0

    # Add components
    ui.title("My Title")
    ui.header("My Header")
    ui.text("My Text")
    ui.json({"a": 1})
    
    assert len(session_state.components) == 4
    assert session_state.components[0]["type"] == "title"
    assert session_state.components[0]["content"] == "My Title"
    assert session_state.components[1]["type"] == "header"
    assert session_state.components[2]["type"] == "text"
    assert session_state.components[3]["type"] == "json"

    # Sidebar components
    ui.sidebar_start()
    ui.text("Sidebar text")
    ui.sidebar_end()
    
    assert len(session_state.components) == 5
    assert session_state.components[4]["type"] == "text"
    assert session_state.components[4]["sidebar"] is True

    # Status components
    status_id = ui.status_start("Loading...")
    assert session_state.components[5]["type"] == "status"
    assert session_state.components[5]["label"] == "Loading..."
    assert session_state.components[5]["state"] == "running"
    
    ui.status_update(status_id, "Halfway...")
    assert session_state.components[5]["label"] == "Halfway..."
    
    ui.status_complete(status_id, label="Done!", success=True)
    assert session_state.components[5]["label"] == "Done!"
    assert session_state.components[5]["state"] == "success"

    # Chat history
    ui.chat_history_add("user", "Hello")
    assert len(session_state.chat_history) == 1
    assert session_state.chat_history[0]["role"] == "user"
    assert session_state.chat_history[0]["content"] == "Hello"
    
    ui.clear_chat()
    assert len(session_state.chat_history) == 0


def test_ui_websocket_server():
    ui.init(title="WS Test", port=9001)
    ui.title("Welcome")
    ui.chat_history_add("assistant", "Hi there")
    
    # Mock event loop inside session state
    loop = asyncio.new_event_loop()
    session_state.loop = loop
    
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Check initial handshake state payload
        data = websocket.receive_json()
        assert data["event"] == "init"
        payload = data["data"]
        assert payload["title"] == "WS Test"
        assert len(payload["components"]) == 1
        assert payload["components"][0]["content"] == "Welcome"
        assert len(payload["chat_history"]) == 1
        assert payload["chat_history"][0]["content"] == "Hi there"
        
        # Test broadcasting dynamic component updates
        ui.text("Dynamically added")
        # Run loop events to process threadsafe call
        loop.run_until_complete(asyncio.sleep(0.01))
        
        ws_msg = websocket.receive_json()
        assert ws_msg["event"] == "add_component"
        assert ws_msg["data"]["content"] == "Dynamically added"
    
    loop.close()


def test_pybridge_inthon_ui_integration():
    src = """
    use py.inthon.ui as ui
    ui.init(title: "PyBridge UI Title", port: 9500)
    ui.title("Loaded via Inthon Code")
    """
    
    # Execute the Inthon script
    ctx = ExecutionContext()
    prog = parse(src)
    interpreter = Interpreter(ctx)
    interpreter.run(prog)
    
    # Verify the context was set and state accumulated
    assert ui.get_context() == ctx
    assert session_state.title == "PyBridge UI Title"
    assert len(session_state.components) == 1
    assert session_state.components[0]["content"] == "Loaded via Inthon Code"
