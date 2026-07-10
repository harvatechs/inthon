# The INTHON End-to-End Playbook for Learners

Welcome to the definitive learning playbook for the INTHON programming language layer. This document provides a deep, comprehensive overview of the language mechanics, advanced execution paradigms, system-level safety invariants, and troubleshooting patterns. It is designed to take you from basic concepts to building production-ready, capability-bounded AI agents.

---

## 1. Motivation & Core Philosophy

Autonomous agent systems rely on Large Language Models (LLMs) to select and invoke operations. Traditional orchestration paradigms have major architectural drawbacks:
1. **JSON Tool-Calling Overhead**: Serializing tool schemas in system messages consumes significant token space, leading to higher inference costs and latency.
2. **Subprocess Execution Vulnerability**: Permitting an agent to execute raw Python or shell code on a host machine runs the risk of arbitrary code execution, local file system leakage, or outbound security threats.
3. **Lack of Determinism & Audits**: In traditional agent loops, execution is an unmonitored black box.

**INTHON** addresses these issues by defining a formal language layer:
* **Token-Efficient Syntax**: INTHON's EBNF-defined grammar is optimized for direct generation by LLMs. An agent plan written in INTHON is up to **75% smaller** in token size than equivalent nested JSON structures.
* **Declarative Agent Containers**: The `agent` block brings boundaries, goals, capability controls (`policy`), and operational logic (`plan`) into a single, cohesive syntactic block.
* **Double-Layer Sandboxing**: Capability permissions are checked statically at compile-time and dynamically at runtime. Python integrations are wrapped inside strict security proxies (`InthonPyObject`).
* **Relational Execution Traces**: Evaluated expressions emit detailed, replayable JSON logs tracking execution paths, data, and LLM billing accumulators.

---

## 2. Complete Language Syntax Reference

Here is a quick reference table of INTHON's types, operators, and statement structures.

### Data Types

| Type Identifier | Classification | Description | Syntax Example |
| :--- | :--- | :--- | :--- |
| `int` | Primitive | Signed 64-bit integer | `let count: int = 5` |
| `float` | Primitive | Double-precision float | `let temp: float = 98.6` |
| `str` | Primitive | UTF-8 encoded text string | `let text: str = "query"` |
| `bool` | Primitive | Boolean truth values (`true`/`false`) | `let active: bool = false` |
| `none` | Primitive | Null placeholder value (`none`) | `let data: none = none` |
| `any` | Primitive | Dynamic escape hatch type check | `let payload: any = value` |
| `list[T]` | Collection | Ordered dynamic array of type `T` | `let items: list[int] = [1, 2]` |
| `dict[K, V]` | Collection | Key-value associative mapping | `let map: dict[str, int] = {"a": 1}` |
| `tuple[T1, T2]` | Collection | Fixed-size heterogeneous sequence | `let pair: tuple[str, int] = ["id", 10]` |
| `set[T]` | Collection | Unique unordered collection of type `T` | `let unique: set[str] = ["a", "b"]` |

### Operator Precedence (Highest to Lowest)

1. **Unary Operators**: `!` (logical NOT), `-` (negative sign conversion)
2. **Exponentiation**: `**` (power)
3. **Multiplicative**: `*` (multiplication), `/` (division), `%` (modulo)
4. **Additive**: `+` (addition / string concatenation), `-` (subtraction)
5. **Relational**: `<`, `<=`, `>`, `>=`
6. **Equality**: `==` (equal to), `!=` (not equal to)
7. **Logical AND**: `and`
8. **Logical OR**: `or`

---

## 3. Writing Your First Agent Block

The `agent` keyword declares a structured agent block. Let's look at the structure of a complete agent script:

```inth
// agent_example.inth
use tool web.search

let max_results = 3

agent ResearchAssistant {
    // 1. Goal directive (analyzed by the reasoning backend)
    goal "Locate and summarize recent space missions from NASA"
    
    // 2. Typed input boundary (space-separated, no commas)
    inputs {
        max_results: int
    }
    
    // 3. Typed output boundary (space-separated, no commas)
    outputs {
        report: list[dict[str, any]]
    }
    
    // 4. Execution safety policies
    policy {
        allow_network: true
        max_tool_calls: 5
        max_cost_usd: 0.10
    }
    
    // 5. Procedural plan statement sequence
    plan {
        let results = web.search("NASA space mission 2026", limit: max_results)
        return results
    }
}

// Evaluate the agent
let NASA_report = ResearchAssistant
NASA_report
```

---

## 4. Fine-Grained Policy Guards

The `policy` block acts as a strict boundary contract between the agent and the host machine. If an execution step attempts to exceed these limits, the interpreter immediately halts the process and raises a `PolicyViolationError`.

### How Policies Prevent Exploits

* **`allow_network: false`**: Completely disables outgoing HTTP/socket operations inside the agent's current call stack.
* **`max_tool_calls: N`**: Limits tool invocations to a maximum of `N`. If an agent tries to call tools in a loop indefinitely, the run is terminated.
* **`max_cost_usd: X.XX`**: Accumulates LLM token fees dynamically. Once cumulative cost exceeds `$X.XX`, execution halts.
* **`allow_memory_persist: false`**: Prevents writing to episodic/semantic tables, making memory operations read-only.
* **`allow_fs: false`**: Prevents reading or writing to files outside the permitted sandbox path.
* **`allow_payment: false`**: Prevents billing APIs from executing charges without an explicit approval gate.

---

## 5. Safe Python Interoperability (PyBridge)

INTHON leverages PyBridge to allow scripts to access Python's rich library ecosystem while maintaining isolation.

### The sys.meta_path Interception

When you declare `use py.numpy as np`, the INTHON interpreter routes the request through a custom importer registered in Python's `sys.meta_path`. This hook performs:
1. **Module Name Verification**: Only pre-approved modules configured in `inthon.toml` (e.g. `numpy`, `pandas`, `math`, `json`, `re`) are allowed. System libraries (`os`, `sys`, `subprocess`, `ctypes`, `socket`) are rejected.
2. **Access Proxy Wrapping (`InthonPyObject`)**: All returned Python objects are wrapped inside a proxy. When code attempts to traverse namespaces (e.g., calling `np.__config__.__builtins__['eval']`), the proxy intercepts the lookup and throws a `SecurityViolation` exception.

### Custom PyBridge Setup

To allow a custom Python module to run within the sandbox, add it to your project's local `inthon.toml` file under the `[pybridge]` block:

```toml
// inthon.toml
[pybridge]
allowed_modules = ["random", "time", "my_custom_module"]
```

Ensure `my_custom_module.py` is present in your Python path or in the local project directory.

---

## 6. Native Agent Primitives

INTHON defines several native primitives to coordinate agent activities:

### A. Human Approval Gates (`approve`)

To require human intervention before executing a high-risk operation, use `approve`:

```inth
approve charge_alert before stripe
```

During execution, the VM triggers the host's approval event listener and blocks the execution thread. If approved, the VM resumes. If denied, it throws an `ApprovalDeniedError`.

### B. Episodic Memory (`remember` / `recall`)

Episodes and semantic statements can be written to and queried from the relational SQLite persistence layer:

```inth
remember "Client requested a summary of solar panels" in session
let facts = recall "solar panel feedback" from session
```

* **Cosine Similarity Match**: The `recall` statement uses text embeddings vectors calculated by the LLM backend to retrieve the statement with the highest cosine similarity:
  \[\text{Similarity} = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\| \|\mathbf{B}\|}\]

### C. Retry Loops with Exponential Backoff (`retry`)

To handle unstable network resources, INTHON offers native retry support:

```inth
retry 3 with backoff exponential {
    let response = web.search("quantum computing")
    guard response.length > 0
} catch err {
    return "API unavailable: " + err.message
}
```

The time interval between retry attempts is computed as:
\[t_{\text{backoff}} = \text{base} \times 2^{\text{attempt}} \pm \text{jitter}\]

---

## 7. Interactive Dashboard Development (`py.inthon.ui`)

You can build interactive web dashboards with INTHON using `use py.inthon.ui`. This allows you to handle user events, trigger agents, and update state reactively.

### Dashboard Layout API

* `ui.init(title, port)`: Launches the UI server.
* `ui.sidebar_start()` / `ui.sidebar_end()`: Encloses sidebar controls.
* `ui.title(text)` / `ui.header(text)` / `ui.text(text)`: Renders text elements.
* `ui.chat_history_add(role, text)`: Appends messages to the main chat pane.
* `ui.button(label, callback_fn)`: Binds click events to functions.
* `ui.status_start(label)`: Starts a visual loading indicator.
* `ui.status_update(id, label)`: Updates visual indicator status text.
* `ui.status_complete(id, label, success)`: Closes the loading indicator.
* `ui.on_message(callback_fn)`: Binds a callback function to the main chat input field.

---

## 8. Complete End-to-End Playbook Scenarios

Here are two complete, production-ready scenarios showcasing how to put these pieces together.

### Scenario A: Customer Support Auto-Responder with HITL Fallback

This scenario sets up an automated responder. If the user query is about refunds, it routes execution to the human approval gate before executing database operations.

```inth
// support_agent.inth
use tool db.delete
use tool email.send

let ticket_id = "tx_9011"
let category = "refund"
let customer_email = "user@example.com"

agent SupportAgent {
    goal "Respond to customer tickets and process refund updates"
    inputs {
        ticket_id: str
        category: str
        customer_email: str
    }
    outputs {
        status: str
        message: str
    }
    policy {
        allow_payment: true
        allow_network: true
    }
    plan {
        if category == "refund" {
            // Requiring human validation before executing database deletion
            approve refund_approval before db
            
            let res = db.delete(table: "transactions", id: ticket_id)
            email.send(
                to: customer_email, 
                subject: "Refund Approved", 
                body: "Your refund ticket has been processed successfully."
            )
            return {
                "status": "refunded",
                "message": "Refund processed and confirmation email sent."
            }
        }
        
        email.send(
            to: customer_email, 
            subject: "Ticket Received", 
            body: "We have received your ticket and are reviewing it."
        )
        return {
            "status": "ticket_opened",
            "message": "Standard ticket response sent."
        }
    }
}
```

### Scenario B: Financial Market Tracker with Retries and Data Aggregation

This script fetches ticker prices, performs analysis via NumPy, and retries the network tool on failures.

```inth
// market_tracker.inth
use tool web.search
use py.numpy as np

let ticker = "AAPL"

agent MarketTracker {
    goal "Fetch daily stock tickers and calculate price averages"
    inputs {
        ticker: str
    }
    outputs {
        average_price: float
        outlier_detected: bool
    }
    policy {
        allow_network: true
        max_tool_calls: 5
    }
    plan {
        let prices = []
        
        // Wrap network call in a retry loop with exponential backoff
        retry 3 with backoff exponential {
            let data = web.search("stock price " + ticker)
            guard data.length >= 3
            
            prices = [
                data[0]["price"],
                data[1]["price"],
                data[2]["price"]
            ]
        } catch err {
            // Fallback default values on failure
            prices = [100.0, 101.2, 99.8]
        }
        
        // Calculate average using NumPy
        let arr = np.array(prices)
        let mean_val = arr.mean()
        let max_val = arr.max()
        
        let is_outlier = false
        if max_val > (mean_val * 1.05) {
            is_outlier = true
        }
        
        return {
            "average_price": mean_val,
            "outlier_detected": is_outlier
        }
    }
}
```

---

## 9. Troubleshooting & FAQ

### Linter Errors (Compile-Time Diagnostics)

* **`SymbolNotFoundError: Name 'X' is not defined`**:
  * *Cause*: You referenced a variable or function `X` without declaring it first.
  * *Solution*: Check for typos, or ensure the variable is defined using `let X = value` or `const X = value`.
* **`TypeMismatchError: Cannot assign type 'float' to variable of type 'int'`**:
  * *Cause*: INTHON's type checker detected a mismatch during assignment.
  * *Solution*: Explicitly cast the value or change the variable's type annotation.

### Runtime Exceptions

* **`PolicyViolationError: Operation disallowed under current policy`**:
  * *Cause*: Your plan attempted to invoke an operation restricted by the `policy` block.
  * *Solution*: Add the necessary permission (e.g. `allow_network: true`) to the agent's policy block, or adjust the plan.
* **`PyBridgeError: Module 'X' is not permitted`**:
  * *Cause*: You attempted to import a package that is not in the allowed modules list.
  * *Solution*: Check if `X` is a system-level module (like `os` or `subprocess`), which are blocked. If it is a safe custom package, add it to `allowed_modules` in `inthon.toml`.
* **`ApprovalDeniedError: Human validator rejected action`**:
  * *Cause*: The human administrator rejected the action prompted by the `approve` primitive.
  * *Solution*: Wrap critical transactions in exception handlers to gracefully handle human denials:
    ```inth
    // Graceful approval gate handling
    let approved = true
    retry 1 with backoff exponential {
        approve payment before stripe
    } catch err {
        approved = false
    }
    ```
