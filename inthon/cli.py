from __future__ import annotations
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="inthon",
    help="INTHON — agent-level programming language",
    no_args_is_help=True,
)
console = Console()


@app.command("run")
def run_cmd(
    file: Path = typer.Argument(..., help="Path to .inth file"),
    mock_tools: bool = typer.Option(True, "--mock/--real-tools"),
    trace_out: Path | None = typer.Option(None, "--trace-out"),
    max_cost: float = typer.Option(1.0, "--max-cost"),
    verbose: bool = typer.Option(False, "-v"),
    vm: bool = typer.Option(
        False, "--vm", help="Use bytecode VM backend (faster for loops)"
    ),
    persist_memory: bool = typer.Option(
        False, "--persist-memory", help="Use SQLite-backed persistent memory"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Run in dry-run simulation mode"
    ),
) -> None:
    """Execute an INTHON program."""
    if vm:
        from . import run_file_vm

        def runner():
            return run_file_vm(
                file,
                mock_tools=mock_tools,
                max_cost_usd=max_cost,
                persist_memory=persist_memory,
                dry_run=dry_run,
            )
    else:
        from . import run_file

        def runner():
            return run_file(
                file,
                mock_tools=mock_tools,
                max_cost_usd=max_cost,
                dry_run=dry_run,
            )

    try:
        result = runner()
        if trace_out:
            trace_out.write_text(result.trace_json, encoding="utf-8")
            console.print(f"[green]Trace written to {trace_out}[/green]")
        if verbose:
            console.print(Panel(result.trace_json, title="Execution Trace"))
            backend = "VM (bytecode)" if vm else "Interpreter (tree-walk)"
            console.print(f"[cyan]Backend:[/cyan] {backend}")
            console.print(
                f"[cyan]Duration:[/cyan] {result.duration_ms}ms | [cyan]Cost:[/cyan] ${result.cost_usd:.6f}"
            )
        print(result.output)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


@app.command("async-run")
def async_run_cmd(
    file: Path = typer.Argument(..., help="Path to .inth file"),
    mock_tools: bool = typer.Option(True, "--mock/--real-tools"),
    max_cost: float = typer.Option(1.0, "--max-cost"),
    persist_memory: bool = typer.Option(False, "--persist-memory"),
    timeout: float = typer.Option(300.0, "--timeout"),
    verbose: bool = typer.Option(False, "-v"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Run in dry-run simulation mode"
    ),
) -> None:
    """Execute an INTHON program using the async cooperative scheduler."""
    import asyncio
    from .parser.parser import parse
    from .semantic.analyzer import SemanticAnalyzer
    from .runtime.context import ExecutionContext
    from .memory.store import MemoryStore
    from .tools.builtin_tools import register_builtins
    from .vm.compiler import compile_program
    from .runtime.scheduler import AgentScheduler

    source = file.read_text(encoding="utf-8")
    try:
        program = parse(source, filename=str(file))
        SemanticAnalyzer().analyze(program)

        memory = (
            MemoryStore.persistent(db_path=str(file.parent / ".inthon" / "memory.db"))
            if persist_memory
            else MemoryStore.in_memory()
        )
        ctx = ExecutionContext(filename=str(file), memory=memory)
        ctx.dry_run = dry_run
        ctx.sandbox.max_cost_usd = max_cost
        ctx.sandbox.max_runtime_sec = timeout
        register_builtins(ctx.tools, mock=mock_tools)

        code = compile_program(program, filename=str(file))

        async def _run():
            async with AgentScheduler(ctx) as scheduler:
                agent_id = await scheduler.spawn(file.stem, code)
                results = await scheduler.wait_all(timeout=timeout)
                if verbose:
                    for aid, res in scheduler.summary().items():
                        console.print(f"[cyan]{aid}[/cyan]: {res}")
                return results.get(agent_id)

        result = asyncio.run(_run())
        console.print(result)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


@app.command("check")
def check_cmd(
    file: Path = typer.Argument(..., help="Path to .inth file"),
) -> None:
    """Lint and type-check without executing."""
    from .parser.parser import parse
    from .semantic.analyzer import SemanticAnalyzer

    source = file.read_text(encoding="utf-8")
    try:
        program = parse(source, filename=str(file))
        analyzer = SemanticAnalyzer()
        analyzer.analyze(program)
        for warn in analyzer.warnings:
            console.print(f"[yellow]Warning: {warn}[/yellow]")
        console.print(f"[green]OK: {file} - no issues found[/green]")
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


@app.command("ast")
def ast_cmd(
    file: Path = typer.Argument(..., help="Path to .inth file"),
    fmt: str = typer.Option("tree", "--format", "-f", help="tree | json"),
) -> None:
    """Print the parsed AST."""
    from .parser.parser import parse
    from .ast.printer import print_ast, ast_to_json

    source = file.read_text(encoding="utf-8")
    program = parse(source, filename=str(file))
    if fmt == "json":
        print(ast_to_json(program))
    else:
        print_ast(program)


@app.command("ir")
def ir_cmd(
    file: Path = typer.Argument(..., help="Path to .inth file"),
) -> None:
    """Print the lowered IR as JSON."""
    from .parser.parser import parse
    from .ir.builder import build_ir
    from .ir.serializer import ir_to_json

    source = file.read_text(encoding="utf-8")
    program = parse(source, filename=str(file))
    ir = build_ir(program)
    print(ir_to_json(ir))


@app.command("fmt")
def fmt_cmd(
    file: Path = typer.Argument(..., help="Path to .inth file"),
    write: bool = typer.Option(
        False, "--write", "-w", help="Write changes back to file"
    ),
) -> None:
    """Format an INTHON file (standardizes spacing and newlines)."""
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(code=1)
    source = file.read_text(encoding="utf-8")
    # A simple but effective formatter: rstrips lines, ensures single ending newline
    lines = [line.rstrip() for line in source.splitlines()]
    formatted = "\n".join(lines) + "\n"
    if write:
        file.write_text(formatted, encoding="utf-8")
        console.print(f"[green]Formatted {file}[/green]")
    else:
        print(formatted)


@app.command("repl")
def repl_cmd(
    mock_tools: bool = typer.Option(True, "--mock/--real-tools"),
    vm: bool = typer.Option(
        False, "--vm", help="Use bytecode VM backend (faster for loops)"
    ),
) -> None:
    """Launch the interactive INTHON REPL."""
    from .repl import run_repl

    run_repl(use_vm=vm, mock_tools=mock_tools)


@app.command("trace-view")
def trace_view_cmd(
    trace_file: Path = typer.Argument(..., help="Path to execution trace JSON file"),
    out: Path = typer.Option(Path("trace_replay.html"), "--out", "-o", help="Output HTML file path"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open the dashboard automatically in a browser"),
) -> None:
    """Generate a beautiful interactive HTML trace replay visualizer."""
    if not trace_file.exists():
        console.print(f"[red]Trace file not found: {trace_file}[/red]")
        raise typer.Exit(code=1)

    trace_json = trace_file.read_text(encoding="utf-8")
    
    # Read the template
    template_path = Path(__file__).parent / "runtime" / "trace_visualizer.html.template"
    if not template_path.exists():
        console.print(f"[red]Template visualizer not found at {template_path}[/red]")
        raise typer.Exit(code=1)

    template_content = template_path.read_text(encoding="utf-8")
    
    # Replace placeholder with JSON string
    html_content = template_content.replace("{{TRACE_DATA_JSON}}", trace_json)
    
    out.write_text(html_content, encoding="utf-8")
    console.print(f"[green]Dashboard generated successfully: {out.absolute()}[/green]")
    
    if open_browser:
        import webbrowser
        webbrowser.open(out.absolute().as_uri())


@app.command("convert-skill")
def convert_skill_cmd(
    skill_dir: Path = typer.Argument(..., help="Path to the skill directory or SKILL.md file"),
    output_dir: Path | None = typer.Option(None, "--output", "-o", help="Target directory for generated workflow file"),
) -> None:
    """Convert an agentic Skill (with SKILL.md and scripts) into an INTHON workflow and dynamic tool registration."""
    from .tools.skill_converter import convert_skill_to_workflow

    try:
        inth_path, schema_path = convert_skill_to_workflow(skill_dir, output_dir)
        console.print("[green]Skill converted successfully![/green]")
        console.print(f"  -> Generated INTHON workflow: [cyan]{inth_path}[/cyan]")
        console.print(f"  -> Generated tool schema: [cyan]{schema_path}[/cyan]")
    except Exception as exc:
        console.print(f"[red]Error converting skill: {exc}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

