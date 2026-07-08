"""Self-contained minimal example for skill-name-kebab-case.

This script should run end-to-end without requiring external data files.
It is used by the Rubric evaluator's smoke test runner.
"""

import scanpy as sc


def main():
    # Use built-in data so the example is self-contained
    adata = sc.datasets.pbmc3k_processed()

    # Core skill logic
    sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
    sc.tl.leiden(adata, resolution=0.5)
    sc.tl.umap(adata)

    print(f"Clusters: {adata.obs['leiden'].nunique()}")
    print(adata.obs["leiden"].value_counts())


if __name__ == "__main__":
    main()
