# Part 1: Getting Started with INTHON

This tutorial gets you set up with INTHON and guides you through writing and executing your very first INTHON script.

---

## 1. Prerequisites

Before installing, ensure your machine has:
* **Python**: Version `3.11` or higher.
* **Pip**: Python package manager.

Verify your installation:
```bash
python --version
```

---

## 2. Installation

Clone the repository and install INTHON in editable/developer mode. We recommend using a virtual environment.

```bash
# Clone the repository
git clone https://github.com/harvatechs/inthon.git
cd inthon

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix/macOS:
source .venv/bin/activate

# Install the package and optional dependencies
pip install -e .[dev,data,ml]
```

To verify the installation, query the CLI version:
```bash
inthon --help
```

---

## 3. Your First Program: `hello.inth`

Create a file named `hello.inth` in your text editor:

```inth
// hello.inth
// INTHON supports single-line comments using double-slashes

fn greet(name: str) -> str {
    return "Hello, " + name + "!"
}

let message = greet("INTHON Learner")
message
```

---

## 4. Running the Program

To run your program, use the `inthon run` command:

```bash
inthon run hello.inth
```

**Output:**
```
Hello, INTHON Learner!
```

---

## 5. Command Line Interface (CLI) Reference

The `inthon` command line tool provides several utilities for analyzing, validating, formatting, and executing code.

### A. Static Verification (`check`)
Before running, you can verify that your syntax is correct and types are valid without executing the file:
```bash
inthon check hello.inth
```
If there are spelling errors or type conflicts, the checker will print detailed diagnostics.

### B. Formatting Source Code (`fmt`)
INTHON features a built-in code formatter that standardizes spacing, newlines, and brackets.
```bash
# Preview formatting changes
inthon fmt hello.inth

# Write formatting changes directly to the file
inthon fmt hello.inth --write
```

### C. Viewing the AST (`ast`)
Prints the Abstract Syntax Tree parsed by Lark:
```bash
inthon ast hello.inth
```

### D. Viewing the Intermediate Representation (`ir`)
Prints the lowered IR tree serialized as JSON:
```bash
inthon ir hello.inth
```

### E. Specifying Execution Limits via CLI
You can override policy rules (like cost budgets) directly from the command line:
```bash
inthon run hello.inth --max-cost 0.25 --trace-out run_trace.json
```

---

## Next Steps

Now that you have your environment set up and know how to run scripts, head to **[Part 2: Syntax Basics & Type System](02_syntax_basics.md)** to learn how to write basic programming logic in INTHON.
