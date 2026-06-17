import re


def parse_and_run(source):
    # Strip markdown fences
    md_match = re.search(
        r"```(?:python)?\s*(.*?)\s*```", source, re.DOTALL | re.IGNORECASE
    )
    if md_match:
        code = md_match.group(1)
    else:
        code = source

    local_vars = {}
    exec(code, {}, local_vars)
    return local_vars.get("sum", None)


def main():
    source = """Here is the code you requested:

```python
x = 100
y = 200
sum = x + y
```

I hope this helps you build your agentic workflows!
"""
    result = parse_and_run(source)
    print(result)


if __name__ == "__main__":
    main()
