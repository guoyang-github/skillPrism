---
name: skill-name-kebab-case
description: >-
  One or two sentences describing what this skill does, when to use it,
  and what the user gets back. This text is used by the agent to decide
  whether to invoke the skill, so be concrete and keyword-rich.
tool_type: python
primary_tool: scanpy
languages:
  - python
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

```python
import scanpy as sc

# Self-contained minimal example using built-in or tiny test data
adata = sc.datasets.pbmc3k_processed()

# Core skill logic here
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.5)

print(adata.obs['leiden'].value_counts())
```

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `adata` | AnnData | Yes | Normalized, log-transformed, HVG-selected object |
| `resolution` | float | No | Leiden resolution, typical values 0.2-2.0 |

## Outputs

| Name | Type | Description |
|---|---|---|
| `adata.obs['leiden']` | category | Cluster labels |

## Parameters Reference

| Parameter | Typical Values | Notes |
|---|---|---|
| `n_neighbors` | 10-30 | Larger = more global structure |
| `n_pcs` | 10-50 | Use elbow plot or PC variance |

## Method Comparison

| Method | Best For | Pitfall |
|---|---|---|
| Leiden | Most datasets | Resolution-sensitive |
| Louvain | Legacy compatibility | Deprecated in Scanpy |

## Failure Modes (Explicit Encoding)

Don't just say "be careful". Explicitly encode the failure paths so the agent knows what to avoid and how to recover.

| Failure Mode | Symptom | Recovery |
|---|---|---|
| Raw counts as input | Clusters driven by sequencing depth | Normalize and select HVGs first |
| Resolution too high | Too many tiny clusters | Lower resolution |
| Out of memory | Crash on large datasets | Downsample or use `method='umap'` |

## High-Risk Action Blacklist

The following destructive commands must never be used by this skill:

- `rm -rf /` or unbounded `rm -rf`
- `git reset --hard`
- `git push --force`
- Any operation that overwrites user files without explicit backup

## Common Pitfalls / Troubleshooting

- **Input is raw counts**: normalize and select HVGs first.
- **Too many clusters**: lower resolution.
- **Memory error on large data**: downsample or use `sc.pp.neighbors(..., method='umap')`.

## Actionable Specificity Check

Avoid vague phrases like "consider", "maybe", "depending on the situation", or "as appropriate". Every instruction must be concrete enough for the agent to execute without further clarification.

## Performance & Resources

- Memory: ~2x the size of `adata.X` for neighbors graph.
- Runtime: seconds to minutes for <100k cells.
- For >100k cells consider downsampling or using a GPU-backed method.

## Security & Data Privacy

- This skill operates on AnnData objects in-memory; it does not transmit data externally.
- When handling human subject data, ensure de-identification and compliance with local IRB/DSMB policies.
- Use fixed random seeds (`random_state=42`) for reproducibility where applicable.

## References

1. Wolf, F. A., et al. (2018). SCANPY: large-scale single-cell gene expression data analysis. *Genome Biology*.
2. Traag, V. A., et al. (2019). From Louvain to Leiden: guaranteeing well-connected communities. *Scientific Reports*.

## Related Skills

- `bio-single-cell-preprocessing`
- `bio-single-cell-annotation-celltypist`
