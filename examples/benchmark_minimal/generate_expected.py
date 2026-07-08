#!/usr/bin/env python3
"""Generate the expected (golden standard) output for the PBMC 3k benchmark."""

from pathlib import Path

import scanpy as sc


def main():
    out_dir = (
        Path(__file__).resolve().parent / "benchmarks" / "bio-single-cell-clustering" / "expected"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    adata = sc.datasets.pbmc3k_processed()
    sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
    sc.tl.leiden(adata, resolution=0.5)
    sc.tl.umap(adata)

    output_path = out_dir / "adata.h5ad"
    adata.write_h5ad(output_path)
    print(f"Expected output written to: {output_path}")
    print(f"Clusters: {adata.obs['leiden'].nunique()}")


if __name__ == "__main__":
    main()
