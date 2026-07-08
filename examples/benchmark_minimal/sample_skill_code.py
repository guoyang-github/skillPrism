"""Sample skill-generated code for bio-single-cell-clustering.

This is what an LLM Agent might produce after reading the SKILL.md.
It is used to demonstrate the benchmark runner.
"""

import scanpy as sc

adata = sc.read_h5ad(adata)
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.5)
sc.tl.umap(adata)
adata.write_h5ad(output_h5ad)
