#!/usr/bin/env python3
"""Mock data generators for skillPrism benchmarks and tests.

This module provides deterministic, lightweight synthetic data for the built-in
benchmark tasks (table, clustering, document, deconvolution). It is used by both
unit tests and benchmark runners so that Skills can be validated without relying
on large real-world datasets during rapid iteration.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np
import pandas as pd


def generate_table_csv(
    rows: int = 100,
    cols: int = 4,
    output_path: Optional[Path] = None,
    seed: int = 42,
) -> Path:
    """Generate a simple CSV file and return its path."""
    rng = np.random.default_rng(seed)
    data = {f"col_{i}": rng.integers(0, 100, size=rows) for i in range(cols)}
    df = pd.DataFrame(data)
    if output_path is None:
        output_path = Path(tempfile.mkdtemp()) / "input.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def generate_anndata(
    n_obs: int = 500,
    n_vars: int = 2000,
    n_cell_types: int = 5,
    seed: int = 42,
) -> "Any":
    """Generate a synthetic AnnData object for clustering/deconvolution tests.

    Returns an AnnData-like object. scanpy is imported lazily so that this
    module can be used even when scanpy is not installed.
    """
    try:
        import anndata
        import scanpy as sc
    except ImportError as exc:
        raise ImportError(
            "generate_anndata requires 'anndata' and 'scanpy'. "
            "Install them with: pip install anndata scanpy"
        ) from exc

    rng = np.random.default_rng(seed)
    counts = rng.integers(0, 10, size=(n_obs, n_vars))
    cell_types = [f"cell_type_{i % n_cell_types}" for i in range(n_obs)]

    adata = anndata.AnnData(
        X=counts.astype(np.float32),
        obs=pd.DataFrame({"cell_type": cell_types}, index=[f"cell_{i}" for i in range(n_obs)]),
        var=pd.DataFrame(index=[f"gene_{i}" for i in range(n_vars)]),
    )
    # Minimal preprocessing so downstream clustering tools do not crash.
    sc.pp.calculate_qc_metrics(adata, inplace=True, log1p=False)
    return adata


def generate_visium_data(
    n_spots: int = 200,
    n_cells_ref: int = 500,
    n_cell_types: int = 5,
    n_genes: int = 1000,
    seed: int = 42,
) -> Tuple["Any", "Any"]:
    """Generate synthetic spatial (Visium-like) and reference scRNA-seq data.

    Returns (adata_sp, adata_ref). Both are AnnData objects with shared genes.
    The spatial object contains ground-truth cell-type proportions in
    ``obsm['true_proportions']`` and cell-type names in ``uns['cell_type_names']``,
    making it suitable for deconvolution benchmarks.
    """
    try:
        import anndata
    except ImportError as exc:
        raise ImportError(
            "generate_visium_data requires 'anndata'. Install it with: pip install anndata"
        ) from exc

    rng = np.random.default_rng(seed)
    genes = [f"gene_{i}" for i in range(n_genes)]
    cell_type_names = [f"cell_type_{i}" for i in range(n_cell_types)]

    # Reference scRNA-seq data with cell-type-specific expression signatures
    ref_counts = np.zeros((n_cells_ref, n_genes), dtype=np.float32)
    cell_types = np.array([i % n_cell_types for i in range(n_cells_ref)])
    for cell_idx, ctype in enumerate(cell_types):
        # Each cell type has a distinct signature: elevated expression in a gene block.
        signature = rng.poisson(2, size=n_genes).astype(np.float32)
        block_start = (ctype * n_genes) // n_cell_types
        block_end = ((ctype + 1) * n_genes) // n_cell_types
        signature[block_start:block_end] += rng.poisson(8, size=block_end - block_start).astype(
            np.float32
        )
        ref_counts[cell_idx] = signature

    adata_ref = anndata.AnnData(
        X=ref_counts,
        obs=pd.DataFrame(
            {"cell_type": [cell_type_names[i] for i in cell_types]},
            index=[f"ref_{i}" for i in range(n_cells_ref)],
        ),
        var=pd.DataFrame(index=genes),
    )

    # Spatial Visium-like data generated as a mixture of cell-type signatures.
    proportions = rng.dirichlet(np.ones(n_cell_types) * 0.8, size=n_spots).astype(np.float32)
    # Build signature matrix (n_cell_types x n_genes)
    signature_matrix = np.zeros((n_cell_types, n_genes), dtype=np.float32)
    for ctype in range(n_cell_types):
        block_start = (ctype * n_genes) // n_cell_types
        block_end = ((ctype + 1) * n_genes) // n_cell_types
        signature_matrix[ctype, block_start:block_end] = rng.poisson(
            8, size=block_end - block_start
        ).astype(np.float32)
        signature_matrix[ctype] += rng.poisson(1, size=n_genes).astype(np.float32)

    spot_counts = (proportions @ signature_matrix).astype(np.float32)
    # Add a small amount of Poisson noise to make the task non-trivial.
    spot_counts = rng.poisson(spot_counts + 0.5).astype(np.float32)

    spatial_coords = rng.uniform(0, 10, size=(n_spots, 2))
    adata_sp = anndata.AnnData(
        X=spot_counts,
        obs=pd.DataFrame(
            {
                "array_row": spatial_coords[:, 0].astype(int),
                "array_col": spatial_coords[:, 1].astype(int),
            },
            index=[f"spot_{i}" for i in range(n_spots)],
        ),
        var=pd.DataFrame(index=genes),
    )
    adata_sp.obsm["spatial"] = spatial_coords
    adata_sp.obsm["true_proportions"] = proportions
    adata_sp.uns["cell_type_names"] = cell_type_names

    return adata_sp, adata_ref


def generate_document_prompt(
    skill_topic: str = "CSV summary tool",
    output_path: Optional[Path] = None,
) -> Path:
    """Generate a simple prompt file for document-generation benchmarks."""
    prompt = (
        f"Write a concise SKILL.md for a {skill_topic}. "
        "Include frontmatter, When to Use, Inputs, Outputs, and Quick Start."
    )
    if output_path is None:
        output_path = Path(tempfile.mkdtemp()) / "prompt.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")
    return output_path
