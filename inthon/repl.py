from __future__ import annotations
from .parser.parser import parse, ParseError
from .semantic.analyzer import SemanticAnalyzer
from .semantic.scope import SemanticError
from .runtime.context import ExecutionContext
from .runtime.interpreter import Interpreter
from .runtime.values import to_python, InthonNone, InthonValue
from .runtime.errors import IntHonRuntimeError
from .tools.builtin_tools import register_builtins
from .vm.compiler import compile_program
from .vm.machine import InthonVM

try:
    import readline  # noqa: F401
except ImportError:
    pass


def run_repl(use_vm: bool = False, mock_tools: bool = True) -> None:
    """
    Launch the interactive INTHON REPL.
    Supports multiline input, persistent context, type warnings, and cost/trace commands.
    """
    print("=" * 65)
    print(" INTHON v0.1 Interactive REPL")
    print(f" Backend: {'Bytecode VM' if use_vm else 'AST Interpreter'}")
    print(" Type '.exit' or '.quit' to exit, '.help' for help.")
    print("=" * 65)

    # 1. Initialize persistent state
    ctx = ExecutionContext(filename="<stdin>")
    register_builtins(ctx.tools, mock=mock_tools)

    analyzer = SemanticAnalyzer()
    interp = Interpreter(ctx)
    vm = InthonVM(ctx) if use_vm else None

    input_lines: list[str] = []

    while True:
        try:
            prompt = "..... " if input_lines else "inthon> "
            try:
                line = input(prompt)
            except EOFError:
                print()
                break

            stripped = line.strip()

            # REPL meta-commands
            if not input_lines and stripped.startswith("."):
                cmd = stripped[1:].lower()
                if cmd in ("exit", "quit"):
                    break
                elif cmd == "help":
                    print("REPL commands:")
                    print("  .exit / .quit   - Exit the REPL")
                    print("  .help           - Show this help message")
                    print("  .memory         - Show local memory keys")
                    print("  .trace          - Print execution trace summary")
                    print("  .vars           - Print currently defined variables")
                    continue
                elif cmd == "memory":
                    print(
                        f"Memory namespaces: {ctx.memory.namespaces() if hasattr(ctx.memory, 'namespaces') else ctx.memory}"
                    )
                    continue
                elif cmd == "trace":
                    import json

                    print(json.dumps(ctx.to_trace_summary(), indent=2))
                    continue
                elif cmd == "vars":
                    if ctx._scope_stack:
                        py_vars = {
                            k: to_python(v) if isinstance(v, InthonValue) else v
                            for k, v in ctx._scope_stack[-1].items()
                        }
                        print(f"Variables: {py_vars}")
                    continue
                else:
                    print(f"Unknown REPL command: .{cmd}")
                    continue

            # Standard input parsing
            if stripped == "":
                if not input_lines:
                    continue

            input_lines.append(line)
            source_text = "\n".join(input_lines)

            # Check for block nesting to support multiline inputs
            open_braces = source_text.count("{") - source_text.count("}")
            open_brackets = source_text.count("[") - source_text.count("]")
            open_parens = source_text.count("(") - source_text.count(")")

            if open_braces > 0 or open_brackets > 0 or open_parens > 0:
                continue

            try:
                # Attempt to parse
                program = parse(source_text, filename="<stdin>")
            except ParseError as pe:
                # If it looks like unexpected EOF or trailing structure, read more lines
                if "Unexpected input" in str(pe) and (
                    open_braces > 0
                    or line.strip().endswith("{")
                    or line.strip().endswith("[")
                ):
                    continue
                print(pe)
                input_lines.clear()
                continue
            except Exception as e:
                print(f"Parse Error: {e}")
                input_lines.clear()
                continue

            input_lines.clear()

            # Transform the last statement to ReturnStmt if it is an ExprStmt
            from .ast import nodes as N

            if program.body and isinstance(program.body[-1], N.ExprStmt):
                expr_stmt = program.body[-1]
                new_last = N.ReturnStmt(value=expr_stmt.expr, span=expr_stmt.span)
                new_body = program.body[:-1] + (new_last,)
                program = N.Program(body=new_body, span=program.span)

            # 2. Semantic Analysis
            try:
                analyzer._errors.clear()
                analyzer.warnings.clear()
                analyzer.analyze(program)
                for warn in analyzer.warnings:
                    print(f"[WARNING] {warn}")
            except SemanticError as se:
                print(se)
                continue
            except Exception as e:
                print(f"Semantic Error: {e}")
                continue

            # 3. Execution
            try:
                if use_vm:
                    code = compile_program(program, filename="<stdin>")
                    result_val = vm.execute(code)
                    if result_val is not None:
                        # Output values cleanly
                        py_val = (
                            to_python(result_val)
                            if isinstance(result_val, InthonValue)
                            else result_val
                        )
                        if not isinstance(py_val, InthonNone):
                            print(repr(py_val))
                else:
                    result_val = interp.run(program)
                    if result_val is not None and not isinstance(
                        result_val, InthonNone
                    ):
                        print(repr(to_python(result_val)))
            except IntHonRuntimeError as re:
                print(re)
            except Exception as e:
                print(f"Runtime Error: {e}")

        except KeyboardInterrupt:
            print("\nKeyboardInterrupt")
            input_lines.clear()
            continue
