#!/usr/bin/env python3
"""Boundary-case testing utilities for skillPrism.

Provides a lightweight framework for declaring and running parameter boundary
cases. Useful for Skills that expose numeric or categorical parameters (e.g.
`N_cells_per_location`, `max_epochs`, `resolution`).

This module also provides default boundary tests for the built-in benchmark
tasks (table, clustering, document, deconvolution). When a benchmark is tagged
``level: 0`` the runner can optionally invoke these tests to verify that the
skill-generated code does not crash on edge inputs.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class BoundaryCase:
    """A single boundary-case test."""

    name: str
    args: Dict[str, Any]
    expected: str
    should_raise: Optional[type] = None


@dataclass
class BoundaryTestResult:
    """Result of a single boundary test execution."""

    name: str
    passed: bool
    error: str = ""


@dataclass
class BoundaryReport:
    """Aggregate boundary test report for a benchmark task."""

    task: str
    results: List[BoundaryTestResult] = field(default_factory=list)

    @property
    def all_pass(self) -> bool:
        return all(r.passed for r in self.results)


def run_boundary_cases(
    fn: Callable[..., Any],
    cases: List[BoundaryCase],
    base_kwargs: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[str]]:
    """Run a list of boundary cases against a callable.

    Args:
        fn: The function to test.
        cases: BoundaryCase instances.
        base_kwargs: Default kwargs merged with each case's args.

    Returns:
        (all_passed, failure_messages)
    """
    base = dict(base_kwargs or {})
    failures: List[str] = []

    for case in cases:
        kwargs = {**base, **case.args}
        try:
            result = fn(**kwargs)
            if case.should_raise:
                failures.append(f"{case.name}: expected {case.should_raise.__name__} but succeeded")
                continue
            if case.expected == "success" and result is not None:
                continue
            if case.expected == "fail":
                failures.append(f"{case.name}: expected failure but succeeded")
        except Exception as exc:
            if not case.should_raise:
                failures.append(f"{case.name}: unexpected {type(exc).__name__}: {exc}")
            elif not isinstance(exc, case.should_raise):
                failures.append(
                    f"{case.name}: expected {case.should_raise.__name__}, "
                    f"got {type(exc).__name__}: {exc}"
                )

    return len(failures) == 0, failures


# --------------------------------------------------------------------------- #
# Sandboxed execution helpers
# --------------------------------------------------------------------------- #


def _exec_skill_code_sandboxed(
    skill_code: str,
    variables: Dict[str, str],
    output_dir: Path,
    timeout: int = 60,
    memory_mb: int = 1024,
    cpu_seconds: int = 60,
    fsize_mb: int = 64,
) -> None:
    """Execute skill code in a sandboxed child process.

    Inputs/outputs are exchanged through files and environment variables so that
    the untrusted skill code never runs in the parent process. This aligns with
    the benchmark sandbox security model.

    Resource limits are configurable because boundary inputs can be large or
    complex (e.g. dense matrices, many layers).
    """
    if not skill_code.strip():
        raise ValueError("No skill code provided")
    from ..benchmark.sandbox import run_user_code

    result = run_user_code(
        skill_code,
        variables,
        output_dir,
        timeout=timeout,
        memory_mb=memory_mb,
        cpu_seconds=cpu_seconds,
        fsize_mb=fsize_mb,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()[-500:] if result.stderr else ""
        raise RuntimeError(f"sandboxed skill code failed (exit {result.returncode}): {stderr}")


def _check_adata_serializable(adata: "Any", case_name: str) -> None:
    """Warn about known H5AD serialization limitations for a boundary input.

    H5AD roundtrips X/obs/var/layers/uns/obsm reliably for basic numpy/pandas
    types, but may drop custom Python objects, non-standard dtypes, or some
    sparse-matrix formats. This function surfaces those risks without blocking
    the test, because the goal of boundary testing is crash detection, not
    perfect fidelity.
    """
    import warnings

    issues: List[str] = []

    # Check uns for non-serializable/custom objects.
    for key, value in getattr(adata, "uns", {}).items():
        if not isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
                type(None),
                list,
                tuple,
                dict,
                np.ndarray,
                pd.DataFrame,
                pd.Series,
            ),
        ):
            issues.append(f"uns['{key}'] has non-standard type {type(value).__name__}")

    # Check obsm/varm for non-ndarray values.
    for attr in ("obsm", "varm"):
        mapping = getattr(adata, attr, {})
        for key, value in mapping.items():
            if not isinstance(value, np.ndarray):
                issues.append(f"{attr}['{key}'] has non-ndarray type {type(value).__name__}")

    # Check X dtype.
    x_dtype = getattr(adata.X, "dtype", None)
    if x_dtype is not None and str(x_dtype) not in ("float32", "float64", "int32", "int64"):
        issues.append(f"X has non-standard dtype {x_dtype}")

    if issues:
        warnings.warn(
            f"Boundary case {case_name!r} may lose data during H5AD roundtrip: "
            + "; ".join(issues),
            stacklevel=3,
        )


def _write_adata_with_fallback(adata: "Any", path: Path) -> None:
    """Write AnnData to disk, falling back to pickle if H5AD fails.

    The fallback preserves custom objects that H5AD cannot serialize, but it is
    **not** a safe format for untrusted data. It is acceptable here because the
    parent process controls the input and the child process only consumes its
    own output; in production, treat pickle outputs with caution.
    """
    import pickle

    try:
        adata.write_h5ad(path)
    except Exception as exc:
        pickle_path = path.with_suffix(".pkl")
        pickle_path.write_bytes(pickle.dumps(adata))
        raise RuntimeError(
            f"H5AD serialization failed ({exc}); fallback written to {pickle_path}. "
            "Skill code may rely on data structures that H5AD cannot preserve."
        ) from exc


def _clustering_wrapper(skill_code: str) -> str:
    """Return a wrapper script that reads/writes AnnData via H5AD files.

    Exposes both the loaded ``adata`` object and the raw file paths so that
    skill code can fall back to direct file I/O if it needs structures that
    H5AD cannot preserve.
    """
    return (
        "import anndata\n"
        "import os\n"
        "input_adata_path = os.environ['SKILLPRISM_VAR_input_h5ad']\n"
        "output_adata_path = os.environ['SKILLPRISM_VAR_output_h5ad']\n"
        "adata = anndata.read_h5ad(input_adata_path)\n"
        "sc = None\n"
        f"{skill_code}\n"
        "if 'adata' in globals() and hasattr(adata, 'write_h5ad'):\n"
        "    try:\n"
        "        adata.write_h5ad(output_adata_path)\n"
        "    except Exception as _exc:\n"
        "        import pickle\n"
        "        with open(output_adata_path.replace('.h5ad', '.pkl'), 'wb') as _f:\n"
        "            pickle.dump(adata, _f)\n"
        "        raise RuntimeError(f'H5AD write failed: {_exc}') from _exc\n"
    )


def _table_wrapper(skill_code: str) -> str:
    return (
        "import os\n"
        "input_csv = os.environ['SKILLPRISM_VAR_input_csv']\n"
        "output_csv = os.environ['SKILLPRISM_VAR_output_csv']\n"
        "output_dir = os.environ['OUTPUT_DIR']\n"
        f"{skill_code}\n"
    )


def _document_wrapper(skill_code: str) -> str:
    return (
        "import os\n"
        "prompt_path = os.environ['SKILLPRISM_VAR_prompt_path']\n"
        "output_path = os.environ['SKILLPRISM_VAR_output_path']\n"
        "output_dir = os.environ['OUTPUT_DIR']\n"
        f"{skill_code}\n"
    )


def _deconvolution_wrapper(skill_code: str) -> str:
    return (
        "import os\n"
        "input_dir = os.environ['SKILLPRISM_VAR_input_dir']\n"
        "output_csv = os.environ['SKILLPRISM_VAR_output_csv']\n"
        "output_dir = os.environ['OUTPUT_DIR']\n"
        f"{skill_code}\n"
    )


# --------------------------------------------------------------------------- #
# Default boundary inputs for built-in benchmark tasks
# --------------------------------------------------------------------------- #


def _clustering_boundary_inputs() -> List[Tuple[str, "Any"]]:
    """Return boundary AnnData inputs for clustering task."""
    try:
        import anndata
    except ImportError as exc:
        raise ImportError("clustering boundary tests require anndata") from exc

    inputs: List[Tuple[str, Any]] = []

    # 0 cells
    inputs.append(
        (
            "zero_cells",
            anndata.AnnData(
                X=np.zeros((0, 100), dtype=np.float32),
                obs=pd.DataFrame(index=[]),
                var=pd.DataFrame(index=[f"gene_{i}" for i in range(100)]),
            ),
        )
    )

    # 1 cell, many genes
    inputs.append(
        (
            "one_cell",
            anndata.AnnData(
                X=np.ones((1, 100), dtype=np.float32),
                obs=pd.DataFrame(index=["cell_0"]),
                var=pd.DataFrame(index=[f"gene_{i}" for i in range(100)]),
            ),
        )
    )

    # many cells, 1 gene
    inputs.append(
        (
            "one_gene",
            anndata.AnnData(
                X=np.ones((10, 1), dtype=np.float32),
                obs=pd.DataFrame(index=[f"cell_{i}" for i in range(10)]),
                var=pd.DataFrame(index=["gene_0"]),
            ),
        )
    )

    return inputs


def _table_boundary_inputs(tmp_dir: Path) -> List[Tuple[str, Path]]:
    """Return boundary CSV paths for table task."""
    inputs: List[Tuple[str, Path]] = []

    # Empty file
    empty = tmp_dir / "empty.csv"
    empty.write_text("", encoding="utf-8")
    inputs.append(("empty_file", empty))

    # Header only
    header_only = tmp_dir / "header_only.csv"
    header_only.write_text("col_a,col_b,col_c\n", encoding="utf-8")
    inputs.append(("header_only", header_only))

    # Single column
    single_col = tmp_dir / "single_col.csv"
    single_col.write_text("value\n1\n2\n3\n", encoding="utf-8")
    inputs.append(("single_column", single_col))

    return inputs


def _document_boundary_inputs(tmp_dir: Path) -> List[Tuple[str, Path]]:
    """Return boundary prompt paths for document task."""
    inputs: List[Tuple[str, Path]] = []

    # Empty prompt
    empty = tmp_dir / "empty_prompt.txt"
    empty.write_text("", encoding="utf-8")
    inputs.append(("empty_prompt", empty))

    # Very long prompt (10k chars)
    long_prompt = tmp_dir / "long_prompt.txt"
    long_prompt.write_text("summarize " * 2000, encoding="utf-8")
    inputs.append(("long_prompt", long_prompt))

    return inputs


def _deconvolution_boundary_inputs(tmp_dir: Path) -> List[Tuple[str, Path]]:
    """Return boundary input directory paths for deconvolution task."""
    inputs: List[Tuple[str, Path]] = []

    # Empty directory (no files)
    empty_dir = tmp_dir / "empty_deconv"
    empty_dir.mkdir(parents=True, exist_ok=True)
    inputs.append(("empty_input_dir", empty_dir))

    # Single spot
    single_spot_dir = tmp_dir / "single_spot"
    single_spot_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"spot_id": ["spot_0"], "count": [10]}).to_csv(
        single_spot_dir / "spots.csv", index=False
    )
    inputs.append(("single_spot", single_spot_dir))

    return inputs


def run_task_boundary_tests(
    task: str,
    skill_code: str,
    output_dir: Path,
    *,
    memory_mb: int = 1024,
    cpu_seconds: int = 60,
    fsize_mb: int = 64,
) -> BoundaryReport:
    """Run default boundary tests for a built-in benchmark task.

    The goal is to catch unhandled crashes on edge inputs, not to validate
    correctness of output. A boundary test passes if the skill code either
    produces output or raises a recognizable exception without a raw system
    traceback crash.

    Resource limits are configurable because some boundary inputs (e.g. dense
    matrices, many layers) require more memory or disk than the defaults.
    """

    report = BoundaryReport(task=task)
    tmp_dir = Path(tempfile.mkdtemp(prefix="skillprism_boundary_"))

    try:
        if task == "clustering":
            inputs = _clustering_boundary_inputs()
            for name, adata in inputs:
                out_path = output_dir / f"boundary_{name}.h5ad"
                input_path = tmp_dir / f"boundary_{name}_input.h5ad"
                try:
                    _check_adata_serializable(adata, name)
                    _write_adata_with_fallback(adata, input_path)
                    wrapped = _clustering_wrapper(skill_code)
                    _exec_skill_code_sandboxed(
                        wrapped,
                        {
                            "input_h5ad": str(input_path),
                            "output_h5ad": str(out_path),
                        },
                        output_dir,
                        memory_mb=memory_mb,
                        cpu_seconds=cpu_seconds,
                        fsize_mb=fsize_mb,
                    )
                    report.results.append(BoundaryTestResult(name=name, passed=True))
                except Exception as exc:
                    report.results.append(
                        BoundaryTestResult(
                            name=name,
                            passed=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )

        elif task == "table":
            inputs = _table_boundary_inputs(tmp_dir)
            for name, input_path in inputs:
                out_path = output_dir / f"boundary_{name}.csv"
                try:
                    wrapped = _table_wrapper(skill_code)
                    _exec_skill_code_sandboxed(
                        wrapped,
                        {
                            "input_csv": str(input_path),
                            "output_csv": str(out_path),
                        },
                        output_dir,
                        memory_mb=memory_mb,
                        cpu_seconds=cpu_seconds,
                        fsize_mb=fsize_mb,
                    )
                    report.results.append(BoundaryTestResult(name=name, passed=True))
                except Exception as exc:
                    report.results.append(
                        BoundaryTestResult(
                            name=name,
                            passed=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )

        elif task == "document":
            inputs = _document_boundary_inputs(tmp_dir)
            for name, input_path in inputs:
                out_path = output_dir / f"boundary_{name}.md"
                try:
                    wrapped = _document_wrapper(skill_code)
                    _exec_skill_code_sandboxed(
                        wrapped,
                        {
                            "prompt_path": str(input_path),
                            "output_path": str(out_path),
                        },
                        output_dir,
                        memory_mb=memory_mb,
                        cpu_seconds=cpu_seconds,
                        fsize_mb=fsize_mb,
                    )
                    report.results.append(BoundaryTestResult(name=name, passed=True))
                except Exception as exc:
                    report.results.append(
                        BoundaryTestResult(
                            name=name,
                            passed=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )

        elif task == "deconvolution":
            inputs = _deconvolution_boundary_inputs(tmp_dir)
            for name, input_path in inputs:
                out_path = output_dir / f"boundary_{name}.csv"
                try:
                    wrapped = _deconvolution_wrapper(skill_code)
                    _exec_skill_code_sandboxed(
                        wrapped,
                        {
                            "input_dir": str(input_path),
                            "output_csv": str(out_path),
                        },
                        output_dir,
                        memory_mb=memory_mb,
                        cpu_seconds=cpu_seconds,
                        fsize_mb=fsize_mb,
                    )
                    report.results.append(BoundaryTestResult(name=name, passed=True))
                except Exception as exc:
                    report.results.append(
                        BoundaryTestResult(
                            name=name,
                            passed=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )

        else:
            report.results.append(
                BoundaryTestResult(
                    name="unsupported_task",
                    passed=False,
                    error=f"No boundary tests defined for task {task!r}",
                )
            )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return report


def format_boundary_report(report: BoundaryReport) -> str:
    """Return a markdown-formatted boundary test summary."""
    lines = ["### Boundary Tests"]
    if not report.results:
        lines.append("No boundary tests run.")
        return "\n".join(lines)
    lines.append("| Case | Status | Notes |")
    lines.append("|---|---|---|")
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        notes = r.error or "-"
        lines.append(f"| {r.name} | {status} | {notes} |")
    lines.append("")
    lines.append(f"**All boundary tests pass**: {report.all_pass}")
    return "\n".join(lines)
