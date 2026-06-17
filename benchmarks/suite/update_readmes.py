import json
import re
from pathlib import Path

def generate_markdown_table(metrics):
    table = [
        "| Benchmark Problem | INTHON Time | Python Time | INTHON Memory | Python Memory | Status |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |"
    ]
    for key, data in metrics.items():
        name = data["name"]
        it = f"{data['inthon']['time_ms']:.1f} ms" if data["inthon"]["success"] else "FAIL"
        pt = f"{data['python']['time_ms']:.1f} ms" if data["python"]["success"] else "FAIL"
        im = f"{data['inthon']['memory_mb']:.1f} MB" if data["inthon"]["success"] else "FAIL"
        pm = f"{data['python']['memory_mb']:.1f} MB" if data["python"]["success"] else "FAIL"
        status = "PASS" if (data["inthon"]["success"] and data["python"]["success"]) else "FAIL"
        table.append(f"| **{name}** | {it} | {pt} | {im} | {pm} | {status} |")
    return "\n".join(table)

def update_file(file_path, table_md):
    content = file_path.read_text(encoding="utf-8")
    
    # Define start and end markers for replacement
    start_marker = "<!-- BENCHMARK_TABLE_START -->"
    end_marker = "<!-- BENCHMARK_TABLE_END -->"
    
    pattern = re.compile(
        r"<!-- BENCHMARK_TABLE_START -->.*?<!-- BENCHMARK_TABLE_END -->",
        re.DOTALL
    )
    
    replacement = f"{start_marker}\n\n{table_md}\n\n{end_marker}"
    
    if pattern.search(content):
        new_content = pattern.sub(replacement, content)
        file_path.write_text(new_content, encoding="utf-8")
        print(f"Updated benchmarks table in {file_path}")
    else:
        # If markers are not present, append to the end or find a suitable section
        print(f"[WARNING] Markers not found in {file_path}. Appending table.")
        new_content = content + f"\n\n## Technical Benchmarks (INTHON vs Python)\n\n{replacement}\n"
        file_path.write_text(new_content, encoding="utf-8")

def main():
    suite_dir = Path(__file__).parent
    workspace_dir = suite_dir.parent.parent
    
    metrics_path = suite_dir / "agent_metrics.json"
    if not metrics_path.exists():
        print(f"[ERROR] agent_metrics.json not found at {metrics_path}")
        return
        
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    table_md = generate_markdown_table(metrics)
    
    # Update README.md
    readme_path = workspace_dir / "README.md"
    if readme_path.exists():
        update_file(readme_path, table_md)
        
    # Update benchmarks/README.md
    bench_readme_path = suite_dir.parent / "README.md"
    if bench_readme_path.exists():
        update_file(bench_readme_path, table_md)

if __name__ == "__main__":
    main()
