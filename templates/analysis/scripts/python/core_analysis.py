"""Reusable core analysis functions for skill-name-kebab-case."""

import scanpy as sc


def run_clustering(
    adata,
    n_neighbors: int = 15,
    n_pcs: int = 30,
    resolution: float = 0.5,
    random_state: int = 42,
) -> None:
    """Run standard clustering workflow on a preprocessed AnnData object.

    Parameters
    ----------
    adata : AnnData
        Normalized, log-transformed, HVG-selected object.
    n_neighbors : int
        Number of neighbors for the neighborhood graph.
    n_pcs : int
        Number of principal components to use.
    resolution : float
        Leiden resolution.
    random_state : int
        Random seed for reproducibility.
    """
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs, random_state=random_state)
    sc.tl.leiden(adata, resolution=resolution, random_state=random_state)
    sc.tl.umap(adata, random_state=random_state)
