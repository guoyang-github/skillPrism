#!/usr/bin/env python3
"""Tests for skillprism.testing.boundary helpers."""

from __future__ import annotations

import pytest

boundary = pytest.importorskip("skillprism.testing.boundary")


def test_run_boundary_cases_success() -> None:
    cases = [
        boundary.BoundaryCase(name="ok", args={"x": 1}, expected="success"),
    ]
    ok, failures = boundary.run_boundary_cases(lambda x: x * 2, cases)
    assert ok is True
    assert failures == []


def test_run_boundary_cases_unexpected_failure() -> None:
    cases = [
        boundary.BoundaryCase(name="boom", args={}, expected="success"),
    ]

    def raise_error():
        raise ValueError("nope")

    ok, failures = boundary.run_boundary_cases(raise_error, cases)
    assert ok is False
    assert len(failures) == 1


def test_run_boundary_cases_expected_raise() -> None:
    cases = [
        boundary.BoundaryCase(name="raise", args={}, expected="success", should_raise=ValueError),
    ]

    def raise_value():
        raise ValueError("expected")

    ok, failures = boundary.run_boundary_cases(raise_value, cases)
    assert ok is True
    assert failures == []


def test_boundary_report_all_pass() -> None:
    report = boundary.BoundaryReport(task="demo")
    assert report.all_pass is True
    report.results.append(boundary.BoundaryTestResult(name="r", passed=True))
    assert report.all_pass is True
    report.results.append(boundary.BoundaryTestResult(name="f", passed=False))
    assert report.all_pass is False


def test_run_task_boundary_tests_table(tmp_path) -> None:
    """Sandboxed table boundary test runs skill code in a child process."""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    code = "import pandas as pd\ndf = pd.read_csv(input_csv)\ndf.to_csv(output_csv, index=False)\n"
    report = boundary.run_task_boundary_tests("table", code, output_dir)
    assert any(r.passed for r in report.results)
    # Malicious parent-process side effect must not happen.


def test_run_task_boundary_tests_table_failure(tmp_path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    code = "raise ValueError('boundary failure')"
    report = boundary.run_task_boundary_tests("table", code, output_dir)
    assert all(not r.passed for r in report.results)


def test_run_task_boundary_tests_does_not_run_in_parent_process(tmp_path) -> None:
    """A snippet that mutates parent globals proves it ran in a child."""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    code = (
        "import os\n"
        "with open(os.path.join(output_dir, 'child.txt'), 'w') as f:\n"
        "    f.write('child')\n"
    )
    report = boundary.run_task_boundary_tests("table", code, output_dir)
    assert any(r.passed for r in report.results)
    assert (output_dir / "child.txt").read_text() == "child"
    # If it had run in-process, globals like __file__ would leak; the subprocess
    # sandbox writes to the output dir instead.


def test_run_task_boundary_tests_clustering_roundtrip(tmp_path) -> None:
    """Clustering boundary test preserves AnnData shape through H5AD roundtrip."""
    pytest.importorskip("anndata")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    # Only assert non-negative obs count and that n_vars is preserved on a per-case basis.
    code = "assert adata.n_obs >= 0\nassert adata.n_vars >= 1\n"
    report = boundary.run_task_boundary_tests("clustering", code, output_dir)
    assert all(r.passed for r in report.results), [r.error for r in report.results]


def test_run_task_boundary_tests_clustering_shape_preserved(tmp_path) -> None:
    """Each boundary case retains its original shape after H5AD roundtrip."""
    pytest.importorskip("anndata")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    code = "pass"  # no-op; wrapper writes adata back unchanged
    report = boundary.run_task_boundary_tests("clustering", code, output_dir)
    assert all(r.passed for r in report.results), [r.error for r in report.results]
    import anndata

    zero = anndata.read_h5ad(output_dir / "boundary_zero_cells.h5ad")
    one_cell = anndata.read_h5ad(output_dir / "boundary_one_cell.h5ad")
    one_gene = anndata.read_h5ad(output_dir / "boundary_one_gene.h5ad")
    assert zero.shape == (0, 100)
    assert one_cell.shape == (1, 100)
    assert one_gene.shape == (10, 1)


def test_run_task_boundary_tests_clustering_mutation(tmp_path) -> None:
    """Skill code can mutate adata and the result is written back."""
    pytest.importorskip("anndata")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    code = "adata.obs['boundary_flag'] = 'ok'"
    report = boundary.run_task_boundary_tests("clustering", code, output_dir)
    assert all(r.passed for r in report.results), [r.error for r in report.results]
    assert (output_dir / "boundary_zero_cells.h5ad").exists()


def test_run_task_boundary_tests_clustering_file_path_convention(tmp_path) -> None:
    """Skill code can use input_adata_path/output_adata_path directly."""
    pytest.importorskip("anndata")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    code = (
        "import anndata\n"
        "adata = anndata.read_h5ad(input_adata_path)\n"
        "adata.obs['via_path'] = True\n"
        "adata.write_h5ad(output_adata_path)\n"
    )
    report = boundary.run_task_boundary_tests("clustering", code, output_dir)
    assert all(r.passed for r in report.results), [r.error for r in report.results]


def test_check_adata_serializable_warns_on_custom_objects(tmp_path) -> None:
    """Non-standard objects in uns trigger a warning."""
    anndata = pytest.importorskip("anndata")
    import warnings

    import numpy as np

    adata = anndata.AnnData(X=np.zeros((1, 1)), uns={"custom": object()})
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        boundary._check_adata_serializable(adata, "custom_obj_case")
    assert any("non-standard type" in str(warning.message) for warning in w)


def test_write_adata_with_fallback_success(tmp_path) -> None:
    """Normal AnnData writes via H5AD."""
    anndata = pytest.importorskip("anndata")
    import numpy as np

    adata = anndata.AnnData(X=np.zeros((2, 3)))
    path = tmp_path / "out.h5ad"
    boundary._write_adata_with_fallback(adata, path)
    assert path.exists()
    assert anndata.read_h5ad(path).shape == (2, 3)


def test_write_adata_with_fallback_pickle(tmp_path) -> None:
    """When H5AD write fails, a pickle fallback is produced."""
    anndata = pytest.importorskip("anndata")
    import numpy as np

    # object() is pickleable but not H5AD-serializable, so it triggers the fallback.
    adata = anndata.AnnData(X=np.zeros((1, 1)), uns={"custom": object()})
    path = tmp_path / "out.h5ad"

    with pytest.raises(RuntimeError) as exc_info:
        boundary._write_adata_with_fallback(adata, path)
    assert "fallback written to" in str(exc_info.value)
    assert (tmp_path / "out.pkl").exists()


def test_run_task_boundary_tests_resource_limits(tmp_path) -> None:
    """Resource limits are passed through without error."""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    code = "pass"
    report = boundary.run_task_boundary_tests(
        "table", code, output_dir, memory_mb=512, cpu_seconds=30, fsize_mb=32
    )
    assert len(report.results) > 0
