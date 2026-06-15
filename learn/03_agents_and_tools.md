# Part 3: Structured Agent Blocks & Tool Integration

INTHON's defining feature is the **Structured Agent Block**. Instead of passing raw, unstructured text to an AI, INTHON allows you to encapsulate the agent's target goal, its inputs/outputs, its safety permissions, and its operational plan directly in code.

---

## 1. Importing Tools (`use tool`)

Tools represent external operations (such as calling web searches, sending database queries, or writing files). To use a tool inside an agent, you must declare it at the top of the file:

```inth
use tool web.search
use tool database.query
```

Declaring tools allows the static analyzer to fetch the tool schemas and validate their argument structures before executing the code.

---

## 2. Defining the `agent` Block

The `agent` keyword defines an agent node. Inside the block, you specify:
1. **`goal`**: A string description of what the agent needs to achieve. This is sent to the LLM backend during planning.
2. **`inputs` / `outputs`** (Optional): Strictly-typed boundary schemas.
3. **`policy`**: Safety boundaries that limit this agent's actions (e.g., maximum cost, tool call quota, network access).
4. **`plan`**: The sequence of INTHON instructions that execute the agent loop.

### Basic Agent Structure
```inth
use tool web.search

agent ResearchAssistant {
    goal "Find room-temperature superconductor papers"
    
    inputs {
        limit: int
    }
    outputs {
        papers: list[dict]
    }

    policy {
        max_tool_calls: 5
        max_cost_usd: 0.05
        allow_network: true
    }

    plan {
        // Calls the web.search tool declared above
        let query_str = "room-temperature superconductor arxiv 2026"
        let raw_results = web.search(query_str, limit: limit)
        return raw_results
    }
}
```

---

## 3. Sandboxing & Safety Policies

The `policy` block inside an agent serves as a runtime contract. If an agent tries to execute a statement that violates its policy, the interpreter immediately halts execution and raises a `PolicyViolationError`.

Available policy keys:

| Policy Key | Type | Description | Example |
| :--- | :---: | :--- | :--- |
| **`allow_network`** | `bool` | Enables/disables calling external network APIs. | `allow_network: true` |
| **`max_tool_calls`** | `int` | Caps the number of tool invocations allowed. | `max_tool_calls: 10` |
| **`max_cost_usd`** | `float` | Sets a maximum financial budget for LLM calls. | `max_cost_usd: 0.50` |
| **`allow_memory_persist`** | `bool` | Permits writing to episodic/semantic memory. | `allow_memory_persist: false` |

### Policy Violation Example
If `allow_network` is set to `false`, calling `web.search` will fail:
```inth
agent TrappedAgent {
    policy {
        allow_network: false
    }
    plan {
        // This will throw a PolicyViolationError at runtime!
        web.search("test") 
    }
}
```

---

## Next Steps

INTHON programs often need data manipulation utilities. Instead of implementing custom mathematical frameworks, you can securely access the Python ecosystem. Head to **[Part 4: PyBridge: Safe Python Interoperability](04_pybridge_interop.md)** to see how it works.
