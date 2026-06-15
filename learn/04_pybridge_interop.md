# Part 4: PyBridge: Safe Python Interoperability

One of INTHON's strongest capabilities is **PyBridge**. It allows you to run existing Python libraries (like Pandas, NumPy, or Math) directly from your INTHON script while maintaining absolute sandbox safety.

---

## 1. Importing Python Modules (`use py`)

To import a Python package, prefix the import with the `py.` namespace. You can also create an alias using the `as` keyword:

```inth
use py.math
use py.numpy as np
use py.pandas as pd

let value = math.sqrt(16.0)
let arr = np.array([1, 2, 3])
```

---

## 2. Permitted Standard Modules

To prevent malicious activity (like downloading viruses, wiping directories, or leaking credentials), PyBridge filters module imports. 

Out of the box, the following libraries are **pre-approved**:

* **Mathematical Computing**: `numpy`, `math`
* **Data Processing**: `pandas`, `polars`, `pyarrow`
* **Utilities**: `json`, `collections`, `datetime`

### Data Cleaning Example:
```inth
use py.pandas as pd

// Create a DataFrame
let df = pd.DataFrame([
    {"name": "Alice", "score": 95},
    {"name": "Bob", "score": 78},
    {"name": "Charlie", "score": 88}
])

// Calculate the average score
let mean_score = df["score"].mean()
mean_score
```

---

## 3. Blocked Modules (Sandbox Safety)

To guarantee that AI-generated code cannot damage the host machine, PyBridge blocks system-level and execution-altering packages.

The following modules are **blocked**:
* **Shell & Execution**: `os`, `sys`, `subprocess`
* **Dynamic Evaluation**: `builtins.eval`, `builtins.exec`
* **Networking**: `socket`
* **Memory/Lower-level Access**: `ctypes`

If an agent attempts to import a blocked module:
```inth
use py.subprocess // Throws PyBridgeError!
```
The interpreter will immediately halt compilation/execution with:
`PyBridgeError: Module 'subprocess' is not permitted.`

---

## 4. How the Security Sandbox Works

PyBridge achieves this security via a two-layer defense mechanism:

1. **Import Hook Filter**: INTHON overrides Python's default import mechanics (`sys.meta_path`). When a script calls `use py.X`, the custom importer checks if `X` is on the allowed list. If it isn't, the import is rejected.
2. **Secure Proxy Wrappers (`InthonPyObject`)**: When a permitted module is imported, it is not returned directly. Instead, it is wrapped in a proxy object. This proxy intercepts every attribute and method lookup. If the code tries to access an unapproved side-effect (e.g. accessing `builtins` through global namespaces), the proxy rejects it.

---

## Next Steps

Now that you understand safety and how to run computational code, let's explore INTHON's advanced features: approval gates, episodic memory, and retry loops. Go to **[Part 5: Advanced Agent Capabilities](05_advanced_features.md)**.
