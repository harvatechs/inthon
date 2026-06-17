from __future__ import annotations
from unittest.mock import patch
from inthon.repl import run_repl


def test_repl_interpreter_flow() -> None:
    inputs = [
        "let x: int = 10",
        "let y = x + 5",
        "y",
        ".exit",
    ]

    with (
        patch("builtins.input", side_effect=inputs),
        patch("builtins.print") as mock_print,
    ):
        run_repl(use_vm=False, mock_tools=True)

        # Let's verify prints
        calls = [call[0][0] for call in mock_print.call_args_list if call[0]]
        # We should see the result of evaluating y, which is 15 (printed as repr '15')
        assert "15" in calls


def test_repl_vm_flow() -> None:
    inputs = [
        "let a = 100",
        "a",
        ".exit",
    ]

    with (
        patch("builtins.input", side_effect=inputs),
        patch("builtins.print") as mock_print,
    ):
        run_repl(use_vm=True, mock_tools=True)

        calls = [call[0][0] for call in mock_print.call_args_list if call[0]]
        assert "100" in calls or 100 in calls


def test_repl_error_handling() -> None:
    inputs = [
        "let x = 10",
        'x = "invalid"',  # This triggers semantic type warning/error or runtime issue
        "y",  # Undefined variable
        ".exit",
    ]

    with (
        patch("builtins.input", side_effect=inputs),
        patch("builtins.print") as mock_print,
    ):
        run_repl(use_vm=False, mock_tools=True)

        calls = [str(call[0][0]) for call in mock_print.call_args_list if call[0]]
        # We should see semantic warnings or errors about 'y' or type mismatch
        assert any("INTHON_SEM_002" in c or "Undefined name" in c for c in calls)
