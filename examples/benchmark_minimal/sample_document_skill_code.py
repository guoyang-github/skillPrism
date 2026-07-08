#!/usr/bin/env python3
"""Deterministic SKILL.md generator for the document-demo benchmark.

This is a stand-in for agent-generated skill code. It reads the prompt file and
writes a simple SKILL.md to the output path without calling an LLM.
"""

from pathlib import Path

prompt_text = Path(prompt_path).read_text(encoding="utf-8")

# Detect a few keywords to make the generated document stable but not identical
# to the golden reference.
text_lower = prompt_text.lower()
has_csv = "csv" in text_lower
has_summary = "summary" in text_lower

title = "CSV Summary Skill" if has_csv and has_summary else "Data Analysis Skill"
description = (
    "Load a CSV file and summarize numeric columns."
    if has_csv and has_summary
    else "Analyze data and produce a report."
)
keywords = ["csv", "summary"] if has_csv and has_summary else ["data", "analysis"]
keywords_yaml = "\n".join(f"  - {kw}" for kw in keywords)

output = f"""---
name: {title.lower().replace(" ", "-")}
description: {description}
tool_type: python
keywords:
{keywords_yaml}
---

# {title}

## When to Use

Use this skill when you need to {prompt_text.strip().rstrip(".").lower()}.

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
"""

Path(output_path).write_text(output, encoding="utf-8")
