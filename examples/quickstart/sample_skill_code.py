"""Sample skill code for the csv-summary document benchmark.

The benchmark runner executes this script in a sandboxed subprocess.  The task
spec exposes ``prompt_path`` and ``output_path`` as top-level globals, so the
script can read the prompt and write the generated SKILL.md directly.
"""

from pathlib import Path

# These are injected as globals by the benchmark sandbox.
input_path = Path(prompt_path)  # noqa: F821
output_path = Path(output_path)  # noqa: F821

prompt = input_path.read_text(encoding="utf-8")

# A deterministic, prompt-following generator (no LLM required for the quickstart).
content = f"""---
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

<!-- prompt: {prompt[:40].replace(chr(10), " ")}... -->
"""

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(content, encoding="utf-8")
