---
name: csv-summary
description: Summarize a CSV file by computing column statistics and writing a simple report.
tool_type: python
---

# CSV Summary Skill

## When to Use

Use this skill when you need a quick statistical summary of a CSV file.

## Inputs

| Name | Type | Description |
|---|---|---|
| input_csv | string | Path to the input CSV file |
| output_csv | string | Path where the summary CSV will be written |

## Outputs

| Name | Type | Description |
|---|---|---|
| summary_csv | CSV | One row per column with count, mean, std, min, max |

## Quick Start

```python
import pandas as pd
df = pd.read_csv("input.csv")
summary = df.describe().T
summary.to_csv("output.csv")
```

## Parameters Reference

| Parameter | Description |
|---|---|
| input_csv | Source CSV path |
| output_csv | Destination summary CSV path |

## Common Pitfalls / Troubleshooting

- Empty files will raise an error.
- Non-numeric columns are ignored by describe().

## Performance & Resources

- Runtime is linear in the number of rows.
- Memory holds the entire file in a DataFrame.

## References

- pandas documentation
