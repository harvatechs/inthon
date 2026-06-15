# Part 2: Syntax Basics & Type System

This guide introduces the core building blocks of the INTHON language syntax, including variable scoping, static types, branch controls, and functions.

---

## 1. Variables and Constants

INTHON enforces block-scoped variable declarations using `let` (mutable) and `const` (immutable).

### Mutable Variables (`let`)
Variables declared with `let` can be reassigned:
```inth
let score = 10
score = score + 5
```

### Immutable Constants (`const`)
Constants declared with `const` cannot be reassigned once bound. Attempts to reassign them will fail during static checking.
```inth
const pi = 3.14159
// pi = 3.0 // ERROR: Cannot assign to constant 'pi'
```

---

## 2. Type System

INTHON is a statically-typed language with type inference. While you can omit type annotations, providing them increases script readability and safety.

### Core Data Types

| Type | Description | Example |
| :--- | :--- | :--- |
| `int` | Integer numbers | `let age: int = 25` |
| `float` | Floating-point numbers | `let price: float = 19.99` |
| `str` | Text string | `let name: str = "INTHON"` |
| `bool` | Boolean value | `let active: bool = true` |
| `list[T]` | Dynamic array of type `T` | `let tags: list[str] = ["ai", "compiler"]` |
| `dict[K, V]` | Hash map of key `K` to value `V` | `let meta: dict[str, float] = {"temp": 0.7}` |
| `any` | Bypasses type-check for the variable | `let payload: any = fetch_data()` |

### Collections Syntax
```inth
let numbers: list[int] = [1, 2, 3, 4]
let info: dict[str, any] = {
    "title": "Agent Research",
    "retries": 3,
    "completed": false
}
```

---

## 3. Conditionals (`if` / `else`)

Control flow branches are constructed using standard `if` and `else` blocks. Unlike Python, braces `{}` are required around the conditional body:

```inth
let temperature = 38.5

if temperature > 39.0 {
    let warning = "Critical heat alert"
} else {
    let warning = "Temperature is stable"
}
```

---

## 4. Functions (`fn`)

Functions are declared using the `fn` keyword, with parameter type annotations and optional return type declarations.

```inth
// Function with return type annotation
fn compute_cost(input_tokens: int, output_tokens: int) -> float {
    let cost = (input_tokens * 0.00001) + (output_tokens * 0.00003)
    return cost
}

let session_cost = compute_cost(1500, 350)
```

### Implicit Returns
If a function block (or a file) ends with an expression statement without an explicit `return` keyword, INTHON will implicitly return the evaluation of that statement.
```inth
fn double(x: int) -> int {
    x * 2 // Implicitly returns x * 2
}
```

---

## Next Steps

Now that you know how to write basic programming instructions, let's explore INTHON's most unique feature: autonomous agents and tool pipelines. Go to **[Part 3: Structured Agent Blocks & Tool Integration](03_agents_and_tools.md)**.
