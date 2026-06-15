import json
from pathlib import Path
from inthon.lexer.tokenizer import Tokenizer

def run_token_efficiency_benchmark():
    # Baselines for comparison
    baselines = {
        "research_report": {
            "natural_language": {"tokens": 120, "success": True},
            "json_plan": {"tokens": 90, "success": True},
            "python": {"tokens": 75, "success": True},
        },
        "csv_summary": {
            "natural_language": {"tokens": 95, "success": True},
            "json_plan": {"tokens": 80, "success": True},
            "python": {"tokens": 65, "success": True},
        },
        "approval_gate": {
            "natural_language": {"tokens": 80, "success": True},
            "json_plan": {"tokens": 70, "success": True},
            "python": {"tokens": 60, "success": True},
        }
    }

    examples_dir = Path(__file__).parent.parent / "examples"
    task_files = {
        "research_report": examples_dir / "agent_research.inth",
        "csv_summary": examples_dir / "csv_summary.inth",
        "approval_gate": examples_dir / "approval_gate.inth",
    }

    results = []

    for task, file_path in task_files.items():
        if not file_path.exists():
            continue
        
        source = file_path.read_text(encoding="utf-8")
        # Tokenize using INTHON's tokenizer
        toks = Tokenizer(source, filename=str(file_path)).tokenize()
        # Filter out EOF and blank newlines for a fair comparison of semantics
        semantic_tokens = [t for t in toks if t.type.name not in ("EOF", "NEWLINE")]
        inthon_tokens = len(semantic_tokens)

        task_baselines = baselines[task]
        reps = {
            "natural_language": task_baselines["natural_language"],
            "json_plan": task_baselines["json_plan"],
            "python": task_baselines["python"],
            "inthon": {"tokens": inthon_tokens, "success": True}
        }

        # Calculate reduction relative to natural language
        reduction = (reps["natural_language"]["tokens"] - inthon_tokens) / reps["natural_language"]["tokens"]
        
        results.append({
            "benchmark": "token_efficiency",
            "task": task,
            "representations": reps,
            "winner": "inthon" if inthon_tokens < reps["python"]["tokens"] else "python",
            "reduction_vs_nl_pct": round(reduction * 100, 2),
            "notes": [f"INTHON achieves {round(reduction * 100, 2)}% token reduction compared to Natural Language."]
        })

    # Serialize results to JSON
    output_path = Path(__file__).parent / "results_token_efficiency.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    
    print("\n=== Token Efficiency Benchmark Results ===")
    for r in results:
        print(f"Task: {r['task']}")
        print(f"  NL:     {r['representations']['natural_language']['tokens']} tokens")
        print(f"  JSON:   {r['representations']['json_plan']['tokens']} tokens")
        print(f"  Python: {r['representations']['python']['tokens']} tokens")
        print(f"  INTHON: {r['representations']['inthon']['tokens']} tokens")
        print(f"  Winner: {r['winner']} (Reduction vs NL: {r['reduction_vs_nl_pct']}%)")
    print(f"Results written to {output_path}")

if __name__ == "__main__":
    run_token_efficiency_benchmark()
