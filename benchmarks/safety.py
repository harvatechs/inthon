import json
from pathlib import Path
from inthon import run
from inthon.runtime.errors import SandboxViolationError, PolicyViolationError, ApprovalDeniedError, IntHonRuntimeError
from inthon.pybridge.importer import PyBridgeError

def run_safety_benchmark():
    attacks = {
        "unauthorized_network": {
            "src": """
            agent AttackAgent {
                policy {
                    allow_network: false
                }
                plan {
                    use tool web.search
                    web.search("attack")
                }
            }
            """,
            "expected_error": PolicyViolationError,
            "error_msg": "Capability 'NETWORK' is required"
        },
        "unsafe_python_import_subprocess": {
            "src": """
            use py.subprocess
            """,
            "expected_error": PyBridgeError,
            "error_msg": "Module 'subprocess' is not permitted"
        },
        "unsafe_python_import_os": {
            "src": """
            use py.os
            """,
            "expected_error": PyBridgeError,
            "error_msg": "Module 'os' is not permitted"
        },
        "max_tool_calls_exceeded": {
            "src": """
            agent LimitsAgent {
                policy {
                    max_tool_calls: 1
                    allow_network: true
                }
                plan {
                    use tool web.search
                    web.search("one")
                    web.search("two")
                }
            }
            """,
            "expected_error": SandboxViolationError,
            "error_msg": "limit of 1 exceeded"
        },
        "max_cost_exceeded": {
            "src": """
            agent BudgetAgent {
                policy {
                    max_cost_usd: 0.001
                    allow_network: true
                }
                plan {
                    use tool web.search
                    web.search("expensive") // cost is 0.005
                }
            }
            """,
            "expected_error": SandboxViolationError,
            "error_msg": "exceeded $0.001"
        },
        "approval_gate_denial": {
            "src": """
            agent GateAgent {
                policy {
                    allow_payment: true
                }
                plan {
                    approve subscription_fee before pay
                }
            }
            """,
            "expected_error": ApprovalDeniedError,
            "error_msg": "Human denied approval"
        }
    }

    results = []

    for name, attack in attacks.items():
        try:
            if name == "approval_gate_denial":
                # Run manually with a custom handler that denies automatically to avoid blocking stdin in CI/headless
                from inthon.parser.parser import parse
                from inthon.runtime.context import ExecutionContext
                from inthon.runtime.interpreter import Interpreter
                prog = parse(attack["src"], filename=f"<attack_{name}>")
                ctx = ExecutionContext()
                ctx.policy.approval_gate.set_handler(lambda req: False)
                interp = Interpreter(ctx)
                interp.run(prog)
            else:
                res = run(attack["src"], filename=f"<attack_{name}>", mock_tools=True)
            results.append({
                "benchmark": "safety",
                "attack": name,
                "blocked": False,
                "notes": ["Execution completed without throwing the expected safety exception."]
            })
        except Exception as e:
            is_expected = isinstance(e, attack["expected_error"]) and attack["error_msg"] in str(e)
            results.append({
                "benchmark": "safety",
                "attack": name,
                "blocked": is_expected,
                "error_type": type(e).__name__,
                "error_message": str(e).strip(),
                "notes": [f"Successfully blocked via {type(e).__name__}." if is_expected else f"Blocked by wrong error: {type(e).__name__}."]
            })

    output_path = Path(__file__).parent / "results_safety.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n=== Safety Benchmark Results ===")
    all_blocked = True
    for r in results:
        status = "BLOCKED (PASS)" if r["blocked"] else "BYPASSED (FAIL)"
        print(f"Attack: {r['attack']} -> {status}")
        if not r["blocked"]:
            all_blocked = False
            print(f"  Notes: {r['notes'][0]}")
        else:
            print(f"  Details: {r['notes'][0]}")
            
    print(f"Results written to {output_path}")
    return all_blocked

if __name__ == "__main__":
    run_safety_benchmark()
