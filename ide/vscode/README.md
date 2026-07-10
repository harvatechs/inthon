# INTHON Language Support

This VS Code extension provides a comprehensive integration suite for the **INTHON** programming language (`.inth`), an agent-level programming language designed for AI-native workflows.

## Features

- **Syntax Highlighting**: Supports control keywords, agentic paradigms (`agent`, `goal`, `policy`, `plan`, `remember`, `recall`, etc.), python bridges, strings, comments, and primitive types.
- **Custom File Icon**: Renders `.inth` files in your VS Code workspace with the official INTHON branding.
- **Bracket Matching & Auto-closing**: Smart editing configurations for functions and statements.
- **Rich Code Snippets**: Quick templates for declaring agents, policies, inputs, outputs, memory actions, and tool bindings.
- **Real-time Diagnostics**: Linting errors and warning annotations highlighted on save or typing via the local compiler server.
- **Auto-Formatting**: Drop-in layout formatting support using VS Code's standard formatter.
- **Interactive Script Runner**: Execute `.inth` files instantly from the Command Palette (`INTHON: Run Current Script`) and view trace logs, execution outputs, duration, and LLM budget/cost calculations.

## Requirements

The extension communicates with the INTHON IDE server. Before editing or running code:
1. Start the compiler server:
   ```bash
   python ide/inthon_server.py
   ```
2. The server runs on `http://localhost:7474` and bridges VS Code editing events directly to the INTHON compiler pipeline.

## Installation

### Manual Installation
To install the extension locally:
1. Copy the `ide/vscode` folder into your VS Code extensions directory:
   - **Windows**: `%USERPROFILE%\.vscode\extensions\inthon-support`
   - **macOS / Linux**: `~/.vscode/extensions/inthon-support`
2. Restart VS Code.
   - For forks like **Cursor** or **VSCodium**, place the extension inside their respective extension folders (e.g. `~/.cursor/extensions/inthon-support` or `~/.vscodium/extensions/inthon-support`).

## Usage
Simply open any `.inth` file (e.g., `examples/hello.inth`) and enjoy full syntax highlighting, diagnostics, formatting, and live script running.

