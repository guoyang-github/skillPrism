#!/usr/bin/env python3
"""Tests for skillprism.testing.mock_data generators."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from skillprism.testing.mock_data import generate_table_csv


def test_generate_table_csv_defaults(tmp_path: Path) -> None:
    path = generate_table_csv(output_path=tmp_path / "table.csv")
    assert path.exists()
    df = pd.read_csv(path)
    assert len(df) == 100
    assert list(df.columns) == ["col_0", "col_1", "col_2", "col_3"]


def test_generate_table_csv_custom(tmp_path: Path) -> None:
    path = generate_table_csv(rows=5, cols=2, output_path=tmp_path / "small.csv", seed=123)
    df = pd.read_csv(path)
    assert len(df) == 5
    assert len(df.columns) == 2


def test_generate_anndata_requires_scanpy() -> None:
    anndata_module = pytest.importorskip("anndata")
    pytest.importorskip("scanpy")
    from skillprism.testing.mock_data import generate_anndata

    # Use dimensions large enough for scanpy QC defaults.
    adata = generate_anndata(n_obs=10, n_vars=2000, n_cell_types=2, seed=7)
    assert isinstance(adata, anndata_module.AnnData)
    assert adata.n_obs == 10
    assert adata.n_vars == 2000


def test_generate_visium_data() -> None:
    anndata = pytest.importorskip("anndata")
    from skillprism.testing.mock_data import generate_visium_data

    sp, ref = generate_visium_data(n_spots=10, n_cells_ref=20, n_cell_types=2, n_genes=50, seed=7)
    assert isinstance(sp, anndata.AnnData)
    assert isinstance(ref, anndata.AnnData)
    assert sp.n_obs == 10
    assert ref.n_obs == 20
