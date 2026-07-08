---
name: bio-spatial-deconvolution-cell2location
description: >-
  Deconvolute spatial transcriptomics data into cell-type proportions using
  cell2location. Requires a scRNA-seq reference and a spatial Visium dataset.
tool_type: python
primary_tool: cell2location
languages:
  - python
keywords:
  - spatial-transcriptomics
  - deconvolution
  - cell2location
  - visium
  - cell-type-proportions
---

# Cell2location Spatial Deconvolution

## When to Use

Use this skill when you have:

- A 10x Genomics Visium spatial transcriptomics dataset (`adata_sp`).
- A matching scRNA-seq reference with annotated cell types (`adata_ref`).

You want to estimate the proportion of each cell type at every spatial spot.

## When NOT to Use

- If you only have bulk RNA-seq, use a bulk deconvolution method (e.g., CIBERSORTx).
- If cell-type labels are unreliable in the reference, fix annotation first.
- If the spatial dataset has very few spots (< 100), results will be noisy.

## Quick Start

```python
import scanpy as sc
import cell2location as c2l

# Load reference and spatial data
adata_ref = sc.read_h5ad("reference_annotated.h5ad")
adata_sp = sc.read_h5ad("visium.h5ad")

# Prepare reference: estimate cell-type signatures
c2l.models.RegressionModel.prepare_anndata(adata_ref, labels_key="cell_type")
mod_ref = c2l.models.RegressionModel(adata_ref)
mod_ref.train(max_epochs=250, batch_size=2500)
adata_ref = mod_ref.export_posterior(adata_ref, sample_kwargs={"num_samples": 1000})

# Deconvolute spatial data
adata_sp = c2l.models.Cell2location.prepare_anndata(adata_sp)
mod = c2l.models.Cell2location(
    adata_sp,
    cell_state_df=adata_ref.varm["means_per_cluster_mu_fg"],
    N_cells_per_location=10,
    detection_alpha=200,
)
mod.train(max_epochs=30000)
adata_sp = mod.export_posterior(adata_sp, sample_kwargs={"num_samples": 1000})

# Estimated proportions are in adata_sp.obsm["q05_cell_abundance_w_sf"]
print(adata_sp.obsm["q05_cell_abundance_w_sf"].head())
```

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `adata_sp` | AnnData | Yes | Spatial Visium object with raw counts in `X` |
| `adata_ref` | AnnData | Yes | scRNA-seq reference with cell-type labels in `obs` |
| `cell_type_key` | string | Yes | Column in `adata_ref.obs` containing cell-type labels |
| `max_epochs_ref` | int | No | Reference signature training epochs (default: 250) |
| `max_epochs_sp` | int | No | Spatial model training epochs (default: 30000) |

## Outputs

| Name | Type | Description |
|---|---|---|
| `proportions` | DataFrame | Cell-type proportions per spot |
| `adata_sp.obsm["q05_cell_abundance_w_sf"]` | DataFrame | 5% quantile of cell abundance |

## Parameters Reference

| Parameter | Typical Values | Notes |
|---|---|---|
| `N_cells_per_location` | 5–30 | Expected number of cells per Visium spot |
| `detection_alpha` | 20–200 | Prior for detection sensitivity; lower = more variable |

## Common Pitfalls / Troubleshooting

- **GPU memory**: cell2location can require > 16 GB GPU memory for large slides.
- **Raw counts**: both inputs must contain raw gene counts, not normalized data.
- **Reference mismatch**: ensure shared genes exist between `adata_ref` and `adata_sp`.

## Performance & Resources

- Runtime: hours on GPU for a full Visium slide.
- Memory: large sparse matrices dominate; subset to shared HVGs when possible.

## References

1. Kleshchevnikov, V., et al. (2022). Cell2location maps fine-grained cell types
   in spatial transcriptomics. *Nature Biotechnology*.

## Related Skills

- `bio-single-cell-clustering`
- `bio-spatial-visium-qc`
