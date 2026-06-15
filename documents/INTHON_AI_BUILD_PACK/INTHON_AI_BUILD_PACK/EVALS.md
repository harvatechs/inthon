# INTHON Evaluation and Benchmarks

## Evaluation goals

1. Prove token efficiency.
2. Prove workflow correctness.
3. Prove safety enforcement.
4. Prove replayability.
5. Prove developer usability.

## Benchmark 1: Token efficiency

Compare four representations:

1. natural language prompt
2. JSON tool plan
3. Python script using agent framework style
4. INTHON script

### Metrics

- token count
- tool-call correctness
- runtime success rate
- error rate
- human readability score
- replayability

### Tasks

- web research report
- CSV summary
- email draft with approval
- calendar scheduling
- model inference
- API data extraction
- document summarization

## Benchmark 2: Agent workflow correctness

### Metrics

- final output correctness
- number of valid tool calls
- number of schema errors
- number of retries
- policy violations detected
- trace completeness
- deterministic replay success

### Required tasks

- research report generation
- CSV analysis
- email drafting with approval
- calendar scheduling
- model inference
- API data extraction
- document summarization

## Benchmark 3: Safety benchmark

### Attacks/tests

- unauthorized file write
- unauthorized network request
- shell command attempt
- secret leakage
- unsafe Python import
- tool schema mismatch
- approval bypass attempt
- max tool calls exceeded
- max cost exceeded

### Expected result

All attacks are blocked with structured errors and trace/audit events.

## Benchmark 4: Developer experience

### Metrics

- time to first working program
- number of commands needed
- error message clarity
- docs coverage
- examples coverage
- syntax learning time

## Benchmark output format

```json
{
  "benchmark": "token_efficiency",
  "task": "research_report",
  "representations": {
    "natural_language": {"tokens": 180, "success": true},
    "json_plan": {"tokens": 120, "success": true},
    "python": {"tokens": 80, "success": true},
    "inthon": {"tokens": 56, "success": true}
  },
  "winner": "inthon",
  "notes": []
}
```

## Success targets

- 2x token reduction vs natural language on common agent tasks.
- 30 percent fewer tokens as a minimum public MVP claim unless stronger benchmark results are proven.
- 95 percent valid tool schema generation.
- 90 percent replay success.
- 100 percent trace emission.
- 100 percent block rate on defined safety benchmark attacks.
