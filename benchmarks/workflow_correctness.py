import json
import time
from pathlib import Path
from inthon import run_file


def run_workflow_correctness_benchmark():
    examples_dir = Path(__file__).parent.parent / "examples"
    test_files = {
        "hello": examples_dir / "hello.inth",
        "tool_search": examples_dir / "tool_search.inth",
        "csv_summary": examples_dir / "csv_summary.inth",
        "agent_research": examples_dir / "agent_research.inth",
    }

    results = []

    for name, path in test_files.items():
        if not path.exists():
            continue

        t0 = time.perf_counter()
        try:
            res = run_file(path, mock_tools=True)
            duration_ms = (time.perf_counter() - t0) * 1000

            trace_events = json.loads(res.trace_json)
            has_trace = len(trace_events) > 0

            results.append(
                {
                    "benchmark": "workflow_correctness",
                    "task": name,
                    "success": True,
                    "output": str(res.output)[:200],
                    "duration_ms": round(duration_ms, 2),
                    "trace_events_count": len(trace_events),
                    "has_valid_trace": has_trace,
                    "cost_usd": res.cost_usd,
                    "errors": res.errors,
                }
            )
        except Exception as e:
            results.append(
                {
                    "benchmark": "workflow_correctness",
                    "task": name,
                    "success": False,
                    "error": str(e),
                    "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                    "has_valid_trace": False,
                    "cost_usd": 0.0,
                    "errors": [{"message": str(e)}],
                }
            )

    output_path = Path(__file__).parent / "results_workflow_correctness.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n=== Workflow Correctness Benchmark Results ===")
    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        print(f"Workflow: {r['task']} -> {status}")
        if r["success"]:
            print(f"  Output:      {r['output']}")
            print(f"  Duration:    {r['duration_ms']} ms")
            print(f"  Trace Count: {r['trace_events_count']} events")
        else:
            print(f"  Error:       {r['error']}")
    print(f"Results written to {output_path}")


if __name__ == "__main__":
    run_workflow_correctness_benchmark()
