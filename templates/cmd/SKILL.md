---
name: skill-name-kebab-case
description: >-
  One or two sentences describing what this command-line skill does, when to use
  it, and what the user gets back. Mention the shell or interpreter required.
tool_type: cmd
primary_tool: bash
languages:
  - bash
keywords:
  - keyword-one
  - keyword-two
  - keyword-three
---

# Skill Title

## When to Use

Describe the exact problem this skill solves and the input data/state expected.

## When NOT to Use

List cases where another skill or approach would be better.

## Quick Start

```bash
# Self-contained minimal example using sample data
input="sample.fastq.gz"
output="sample.filtered.fastq.gz"

zcat "${input}" | head -n 4000 | gzip > "${output}"
echo "Wrote ${output}"
```

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `input` | file | Yes | Path to the input file |
| `output` | file | No | Path to the output file (default: stdout) |

## Outputs

| Name | Type | Description |
|---|---|---|
| `output` | file | Processed output file or stdout stream |

## Parameters Reference

| Parameter | Typical Values | Notes |
|---|---|---|
| `threads` | 1-16 | Parallelism for IO-bound tools |
| `memory` | 1G-16G | Memory limit to request on cluster |

## Common Pitfalls / Troubleshooting

- **Missing executable**: ensure the required tool is installed and on `$PATH`.
- **Shell quoting**: use `"${variable}"` to handle paths with spaces.
- **Large files**: prefer streaming over loading everything into memory.

## Performance & Resources

- Memory: typically low for streaming command-line tools.
- Runtime: depends on input size; benchmark on a representative subset first.

## Security & Data Privacy

- Validate all user-supplied paths before using them in shell commands.
- Avoid `rm -rf` or destructive operations without explicit confirmation.
- Do not hard-code secrets or credentials in command examples.

## References

1. GNU Bash Reference Manual.

## Related Skills

- `cmd-fastq-preprocessing`
- `cmd-alignment-workflow`
