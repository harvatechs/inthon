# Learning INTHON: Official Developer Guide

Welcome to the official learning portal for the INTHON programming language layer! 

INTHON (Intelligent Python) is a domain-specific language layer built for AI agents. By combining the readability of Python with sandbox guarantees, tool schemas, and cost policies, INTHON enables you to write secure, deterministic, and token-efficient agent plans.

This guide is structured to take you from a complete beginner to writing advanced, capability-bounded autonomous agents.

---

## The Learning Path

Follow these modules in sequence to master INTHON:

### 1. [Getting Started](01_getting_started.md)
* Learn the prerequisites, install INTHON, write your first script, and master CLI commands like `run`, `check`, `fmt`, and AST/IR printing.

### 2. [Syntax Basics & Type System](02_syntax_basics.md)
* Explore core language constructs: variables (`let`), constants (`const`), basic data types (string, int, float, boolean, list, dict), if-else branch conditions, custom functions (`fn`), and expressions.

### 3. [Structured Agent Blocks & Tool Integration](03_agents_and_tools.md)
* Understand the core model of INTHON: the `agent` declaration. Learn how to specify execution `goal`s, configure capability boundaries (`policy`), and call tools safely within an agent execution `plan`.

### 4. [PyBridge: Safe Python Interoperability](04_pybridge_interop.md)
* Learn how to leverage the Python ecosystem inside the INTHON sandbox. Understand how `use py` works, which standard libraries are pre-approved, and how import hook intercepts block malicious activities.

### 5. [Advanced Agent Capabilities](05_advanced_features.md)
* Master advanced runtime primitives: Human-in-the-loop (HITL) approval gates, short-term/long-term episodic memory (`remember` and `recall`), and resilient execution via `retry` loops with exponential backoff.

### 6. [Production Templates & Design Patterns](06_templates.md)
* Ready-to-use copy-pasteable boilerplates and design patterns to solve common challenges in professional agent systems: web scraper, CSV analytics, Stripe billing gates, and Q&A memory agents.

### 7. [The End-to-End Playbook](playbook.md)
* An exhaustive, comprehensive reference manual and scenario guide containing deep syntax references, sandboxing internals, interactive dashboard development guidelines, and troubleshooting tips.

---

## Why Learn INTHON?

Traditional agent patterns involve writing complex natural language prompts or passing verbose, fragile JSON structures back and forth. This is prone to errors, has high latency, and is vulnerable to security exploits.

By learning INTHON, you acquire the tools to build:
1. **Cost-Efficient Systems**: Reduce LLM prompt token sizes by up to **75%**.
2. **Ironclad Sandboxes**: Execute generated actions safely, knowing that unauthorised operating system access is strictly blocked.
3. **Fully Replayable Runs**: Every INTHON program logs a JSON trace graph showing exactly which tool was called, what was computed, and how much it cost.
