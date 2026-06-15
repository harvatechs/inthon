# Part 5: Advanced Agent Capabilities

INTHON provides advanced, native runtime primitives designed specifically for building robust and safe AI agents. These include **human-in-the-loop approval gates**, **episodic memory systems**, and **automatic execution retries**.

---

## 1. Approval Gateways (`approve`)

Critical actions (like sending payments, deleting database records, or sending emails) should not be performed by an AI without human verification. INTHON introduces the `approve` primitive to block execution until a human yields permission:

```inth
approve resource_identifier before action_name
```

### Payment Verification Example:
```inth
agent BillingAgent {
    policy {
        allow_payment: true
    }
    plan {
        // Enforces a human check before triggering Stripe charge
        approve subscription_payment before stripe.charge(amount: 49.00)
    }
}
```

At runtime, the interpreter intercepts this instruction and fires an approval request hook. If the human approves, execution continues. If the human denies it, an `ApprovalDeniedError` is thrown, aborting the transaction.

---

## 2. Episodic Memory Operations (`remember` / `recall`)

AI agents need to store facts during their execution cycle to build context. INTHON has built-in primitives to save and retrieve facts using semantic memory namespaces:

### Storing Facts (`remember`)
```inth
remember "Research shows room-temperature superconductors operate best under high pressure" in session
```

### Retrieving Facts (`recall`)
```inth
let fact = recall "superconductor pressure" from session
```

---

## 3. Resilient Executions (`retry`)

Network calls and external tool APIs are frequently unstable. Instead of letting your agent crash, you can wrap operations in a `retry` block. INTHON supports exponential backoff retries out-of-the-box:

```inth
retry max_attempts with backoff backoff_type {
    // Attempt block
} catch error_variable {
    // Failure handling
}
```

### Robust Tool Call Example:
```inth
use tool web.search

agent RobustSearcher {
    policy {
        allow_network: true
    }
    plan {
        // Retries up to 3 times with exponential backoff if the search API fails
        retry 3 with backoff exponential {
            let results = web.search("AI compilers")
            return results
        } catch err {
            return "Search failed after 3 attempts: " + err.message
        }
    }
}
```

---

## Summary of the Learner Guide

Congratulations! You have completed the official INTHON Learner Guide. You now know how to:
1. Setup and run `.inth` programs via the CLI.
2. Structure basic code logic (variables, constants, types, if-else, functions).
3. Build structured `agent` blocks and set sandbox capability `policy` restrictions.
4. Execute Python math/data packages securely via `PyBridge`.
5. Implement approval gates, episodic memory, and retry-catch loops.

For full API documentation or to review benchmarks, check out:
* **[Repository README](../README.md)**
* **[Benchmark Specifications](../benchmarks/README.md)**
