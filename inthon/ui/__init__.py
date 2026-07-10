from __future__ import annotations
from typing import Any, Callable

# Global context reference
_active_context = None


def set_context(ctx: Any) -> None:
    global _active_context
    _active_context = ctx
    # Pass it to the server module
    from . import server

    server.set_active_context(ctx)


def get_context() -> Any:
    return _active_context


def init(title: str = "Inthon Agent Dashboard", port: int = 8000) -> None:
    from . import server

    server.init_state(title=title, port=port)


def launch(port: int = 8000, share: bool = False) -> None:
    from . import server

    server.start_server(port=port)


def title(text: str) -> None:
    from . import server

    server.add_component({"type": "title", "content": text})


def header(text: str) -> None:
    from . import server

    server.add_component({"type": "header", "content": text})


def text(text: str) -> None:
    from . import server

    server.add_component({"type": "text", "content": text})


def json(data: Any) -> None:
    from . import server

    server.add_component({"type": "json", "content": data})


def chat_input(placeholder: str = "Type your message...") -> None:
    from . import server

    server.add_component({"type": "chat_input", "placeholder": placeholder})


def chat_history_add(role: str, content: str) -> None:
    from . import server

    server.add_chat_message(role, content)


def clear_chat() -> None:
    from . import server

    server.clear_chat()


def status_start(label: str) -> str:
    from . import server

    return server.status_start(label)


def status_update(status_id: str, label: str) -> None:
    from . import server

    server.status_update(status_id, label)


def status_complete(
    status_id: str, label: str | None = None, success: bool = True
) -> None:
    from . import server

    server.status_complete(status_id, label, success)


def button(label: str, callback: Callable[[], Any]) -> None:
    from . import server

    server.add_button(label, callback)


def sidebar_start() -> None:
    from . import server

    server.sidebar_start()


def sidebar_end() -> None:
    from . import server

    server.sidebar_end()


def on_message(callback: Callable[[str], Any]) -> None:
    from . import server

    server.register_chat_callback(callback)
