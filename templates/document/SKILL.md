---
name: skill-name-kebab-case
description: >-
  One or two sentences describing what this document-processing skill does, when
  to use it, and what the user gets back. Mention the output format.
tool_type: document
primary_tool: markdown
languages:
  - markdown
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

```markdown
# Report Title

## Summary

- **Objective**: state the goal of the document.
- **Data**: briefly describe the input data.
- **Conclusion**: summarize the key takeaway.
```

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `data` | dict/table | Yes | Structured data to summarize |
| `format` | string | No | Output format: `markdown`, `html`, `docx` |

## Outputs

| Name | Type | Description |
|---|---|---|
| `document` | string | Rendered document in the requested format |

## Parameters Reference

| Parameter | Typical Values | Notes |
|---|---|---|
| `citation_style` | APA, IEEE, GB/T | Bibliography format |
| `toc` | true/false | Include a table of contents |

## Common Pitfalls / Troubleshooting

- **Formatting consistency**: use the same heading level throughout.
- **Missing citations**: include references for any external data or methods.
- **Accessibility**: prefer plain tables over images for screen readers.

## Performance & Resources

- Runtime: negligible for small documents; scales linearly with content size.
- Memory: depends on embedded media and output format.

## Security & Data Privacy

- Redact personal identifiers before publishing documents.
- Verify that generated citations do not fabricate sources.

## References

1. Markdown Guide.

## Related Skills

- `document-report-generation`
- `document-citation-formatter`
