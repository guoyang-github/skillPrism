#!/usr/bin/env python3
"""Generate synthetic spatial deconvolution data for the cell2location example.

This creates Visium-like spatial data and a matching scRNA-seq reference with
cell-type labels, plus golden proportion matrices for regression benchmarks.
Run it before the first benchmark:

    python examples/benchmark_cell2location/scripts/generate_data.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from skillprism.testing.mock_data import generate_visium_data


def _normalize_rows(df: pd.DataFrame) -> pd.DataFrame:
    row_sums = df.sum(axis=1).replace(0, np.nan)
    return df.div(row_sums, axis=0).fillna(0.0)


def main() -> None:
    base_dir = (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "bio-spatial-deconvolution-cell2location"
    )
    data_dir = base_dir / "data"
    expected_dir = base_dir / "expected"
    data_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        ("tiny", 10, 30, 3, 42),
        ("small", 50, 100, 5, 43),
        ("medium", 200, 500, 8, 44),
    ]

    for name, n_spots, n_cells_ref, n_cell_types, seed in configs:
        print(f"Generating {name} dataset ({n_spots} spots, {n_cells_ref} reference cells)...")
        adata_sp, adata_ref = generate_visium_data(
            n_spots=n_spots,
            n_cells_ref=n_cells_ref,
            n_genes=200,
            n_cell_types=n_cell_types,
            seed=seed,
        )
        dataset_dir = data_dir / name
        dataset_dir.mkdir(parents=True, exist_ok=True)
        sp_path = dataset_dir / "spatial.h5ad"
        ref_path = dataset_dir / "reference.h5ad"
        adata_sp.write_h5ad(sp_path)
        adata_ref.write_h5ad(ref_path)

        # Save golden proportions (ground truth from simulation)
        prop_path = expected_dir / f"{name}_proportions.csv"
        proportions = pd.DataFrame(
            adata_sp.obsm["true_proportions"],
            index=adata_sp.obs_names,
            columns=adata_sp.uns["cell_type_names"],
        )
        _normalize_rows(proportions).to_csv(prop_path)
        print(f"  -> {sp_path}, {ref_path}, {prop_path}")

    print("Done.")


if __name__ == "__main__":
    main()
