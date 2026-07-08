---
name: csv-summary
description: Summarize a CSV file by computing column statistics and writing a simple report.
tool_type: python
primary_tool: pandas
languages:
  - python
keywords:
  - csv
  - summary
  - statistics
---

# CSV Summary Skill

## When to Use

Use this skill when you need a quick statistical summary of a small-to-medium CSV file.

## When NOT to Use

- If the CSV is larger than available memory, use streaming or out-of-core tools.
- If you need visualizations, use a plotting skill instead.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `input_csv` | string | Yes | Path to the input CSV file |
| `output_csv` | string | Yes | Path where the summary CSV will be written |

## Outputs

| Name | Type | Description |
|---|---|---|
| `summary_csv` | CSV | One row per column with count, mean, std, min, max |

## Quick Start

```python
import pandas as pd

df = pd.read_csv("{input_csv}")
summary = df.describe().T
summary.to_csv("{output_csv}")
```

## Parameters Reference

| Parameter | Default | Description |
|---|---|---|
| `input_csv` | — | Source CSV path |
| `output_csv` | — | Destination summary CSV path |

## Common Pitfalls / Troubleshooting

- Empty files will raise a `pandas.errors.EmptyDataError`.
- Non-numeric columns are ignored by `describe()`.

## Performance & Resources

- Runtime: linear in the number of rows.
- Memory: the entire file is loaded into a DataFrame.

## References

- pandas documentation: https://pandas.pydata.org/
