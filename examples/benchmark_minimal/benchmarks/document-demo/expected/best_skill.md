---
name: csv-summary-skill
description: Load a CSV file, summarize numeric columns, and produce a report.
tool_type: python
keywords:
  - csv
  - summary
  - pandas
---

# CSV Summary Skill

## When to Use

Use this skill when you need a quick statistical summary of a CSV file.

## Inputs

| Name | Type | Description |
|---|---|---|
| `input_csv` | file path | Path to the input CSV file |

## Outputs

A Markdown report containing:

- Row and column counts
- Mean / min / max for each numeric column

## Quick Start

```python
import pandas as pd

df = pd.read_csv(input_csv)
report = df.describe()
print(report.to_markdown())
```

## Common Pitfalls

- Non-numeric columns are ignored by `describe()`.
- Large files may require memory consideration.
