import json
import subprocess
import sys
from pathlib import Path


def main():
    benchmarks_dir = Path(__file__).parent

    # Run the three benchmark scripts
    print("Running Token Efficiency Benchmark...")
    subprocess.run(
        [sys.executable, str(benchmarks_dir / "token_efficiency.py")], check=True
    )

    print("\nRunning Workflow Correctness Benchmark...")
    subprocess.run(
        [sys.executable, str(benchmarks_dir / "workflow_correctness.py")], check=True
    )

    print("\nRunning Safety Benchmark...")
    subprocess.run([sys.executable, str(benchmarks_dir / "safety.py")], check=True)

    # Aggregate results into a single results.json
    results = {}

    token_eff_path = benchmarks_dir / "results_token_efficiency.json"
    if token_eff_path.exists():
        results["token_efficiency"] = json.loads(
            token_eff_path.read_text(encoding="utf-8")
        )

    wf_correct_path = benchmarks_dir / "results_workflow_correctness.json"
    if wf_correct_path.exists():
        results["workflow_correctness"] = json.loads(
            wf_correct_path.read_text(encoding="utf-8")
        )

    safety_path = benchmarks_dir / "results_safety.json"
    if safety_path.exists():
        results["safety"] = json.loads(safety_path.read_text(encoding="utf-8"))

    output_path = benchmarks_dir / "results.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"\nUnified benchmark results written to {output_path}")


if __name__ == "__main__":
    main()
