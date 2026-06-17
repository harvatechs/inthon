from pathlib import Path

def mock_search(query, limit=5):
    return [{"title": f"Result for {query}", "snippet": "Snippet 1"}]

def main():
    # 1. Search the web
    search_res = mock_search("highest building", limit=1)
    snippet = search_res[0]["snippet"]
    
    # 2. Read local baseline
    p_base = Path("benchmarks/suite/baseline.txt")
    baseline = p_base.read_text(encoding="utf-8")
    
    # 3. Combine
    combined = f"Fact: {snippet}\n{baseline}"
    
    # 4. Write result
    p_out = Path("benchmarks/suite/chain_result_py.txt")
    p_out.write_text(combined, encoding="utf-8")
    
    print(combined)

if __name__ == "__main__":
    main()
