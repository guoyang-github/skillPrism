#!/usr/bin/env python3
"""Benchmark evaluation metrics registry and built-in metric functions."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, cast

# --------------------------------------------------------------------------- #
# Metric registry
# --------------------------------------------------------------------------- #

_METRICS: Dict[str, Callable[[Path, Optional[Path], Dict[str, Any]], Any]] = {}


def metric(metric_id: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that registers a function as the metric with ``metric_id``."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        _METRICS[metric_id] = fn
        return fn

    return decorator


def get_metric(metric_id: str) -> Optional[Callable[[Path, Optional[Path], Dict[str, Any]], Any]]:
    """Return the metric function registered for ``metric_id``, if any."""
    return _METRICS.get(metric_id)


def list_metrics() -> List[str]:
    """Return the ids of all registered metrics."""
    return sorted(_METRICS.keys())


def clear_metrics() -> None:
    """Remove all registered metrics (mainly for tests)."""
    _METRICS.clear()


# --------------------------------------------------------------------------- #
# Criteria checking
# --------------------------------------------------------------------------- #


def metric_passes(value: Any, spec: Dict[str, Any]) -> bool:
    # A compute function may return None when it cannot produce a value (e.g.
    # missing expected file, absent X_pca). Treat that as a failed metric
    # rather than raising TypeError on the comparison.
    if value is None:
        return False
    mtype = spec["type"]
    if mtype == "min":
        return bool(value >= cast(float, spec["threshold"]))
    if mtype == "max":
        return bool(value <= cast(float, spec["threshold"]))
    if mtype == "range":
        return bool(cast(float, spec["min"]) <= value <= cast(float, spec["max"]))
    if mtype == "tolerance":
        ref = cast(float, spec.get("reference", value))
        return bool(abs(value - ref) <= cast(float, spec["threshold"]))
    if mtype == "exact":
        return bool(value == spec["expected"])
    raise ValueError(f"Unknown metric type: {mtype}")


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _extract_headers(text: str) -> Set[str]:
    """Return the set of markdown headers (level 1-6) in lower case."""
    headers = re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)
    return {h.strip().lower() for h in headers}


def _tokenize(text: str) -> Set[str]:
    """Simple word tokenization; returns lower-cased word tokens."""
    return set(re.findall(r"\b\w+\b", text.lower()))


def _label_column(task_spec: Dict[str, Any]) -> str:
    """Resolve the clustering label column, defaulting to ``leiden``."""
    return (
        task_spec.get("label_column")
        or (task_spec.get("expected") or {}).get("label_column")
        or "leiden"
    )


# --------------------------------------------------------------------------- #
# CSV / table metrics
# --------------------------------------------------------------------------- #


@metric("row_count")
def row_count(actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]) -> int:
    rows = _read_csv_rows(actual_path)
    return len(rows)


@metric("col_count")
def col_count(actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]) -> int:
    rows = _read_csv_rows(actual_path)
    return len(rows[0].keys()) if rows else 0


@metric("diff_row_count")
def diff_row_count(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[int]:
    if expected_path is None or not expected_path.exists():
        return None
    actual_rows = _read_csv_rows(actual_path)
    expected_rows = _read_csv_rows(expected_path)
    return abs(len(actual_rows) - len(expected_rows))


@metric("expected_diff_rows")
def expected_diff_rows(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[int]:
    if expected_path is None or not expected_path.exists():
        return None
    actual_rows = _read_csv_rows(actual_path)
    expected_rows = _read_csv_rows(expected_path)
    return abs(len(actual_rows) - len(expected_rows))


@metric("has_required_columns")
def has_required_columns(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> bool:
    required = task_spec.get("output", {}).get("required_columns", [])
    if not required:
        return True
    rows = _read_csv_rows(actual_path)
    headers = list(rows[0].keys()) if rows else []
    return set(required).issubset(set(headers))


# --------------------------------------------------------------------------- #
# AnnData / clustering metrics
# --------------------------------------------------------------------------- #


@metric("n_clusters")
def n_clusters(actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]) -> int:
    import numpy as np
    import scanpy as sc

    adata = sc.read_h5ad(actual_path)
    labels = adata.obs[_label_column(task_spec)].astype(str).to_numpy()
    return int(len(np.unique(labels)))


@metric("largest_cluster_ratio")
def largest_cluster_ratio(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> float:
    import numpy as np
    import scanpy as sc

    adata = sc.read_h5ad(actual_path)
    labels = adata.obs[_label_column(task_spec)].astype(str).to_numpy()
    return float(np.max(np.unique(labels, return_counts=True)[1]) / len(labels))


@metric("silhouette_score")
def silhouette_score(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    import numpy as np
    import scanpy as sc
    from sklearn.metrics import silhouette_score as sk_silhouette

    adata = sc.read_h5ad(actual_path)
    labels = adata.obs[_label_column(task_spec)].astype(str).to_numpy()
    n_clusters = int(len(np.unique(labels)))
    X_pca = adata.obsm.get("X_pca")
    if X_pca is None or len(labels) <= n_clusters or n_clusters <= 1:
        return None
    return float(sk_silhouette(X_pca, labels))


@metric("ari")
def ari(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    if expected_path is None or not expected_path.exists():
        return None
    import scanpy as sc
    from sklearn.metrics import adjusted_rand_score

    actual = sc.read_h5ad(actual_path)
    expected = sc.read_h5ad(expected_path)
    col = _label_column(task_spec)
    labels = actual.obs[col].astype(str).to_numpy()
    expected_labels = expected.obs[col].astype(str).to_numpy()
    return float(adjusted_rand_score(expected_labels, labels))


@metric("nmi")
def nmi(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    if expected_path is None or not expected_path.exists():
        return None
    import scanpy as sc
    from sklearn.metrics import normalized_mutual_info_score

    actual = sc.read_h5ad(actual_path)
    expected = sc.read_h5ad(expected_path)
    col = _label_column(task_spec)
    labels = actual.obs[col].astype(str).to_numpy()
    expected_labels = expected.obs[col].astype(str).to_numpy()
    return float(normalized_mutual_info_score(expected_labels, labels))


# --------------------------------------------------------------------------- #
# Deconvolution metrics
# --------------------------------------------------------------------------- #


def _normalize_rows(df: Any) -> Any:
    """Row-normalize a frame to proportions; leave zero-sum rows unchanged."""
    row_sums = df.sum(axis=1)
    safe_sums = row_sums.where(row_sums != 0, other=1.0)
    return df.div(safe_sums, axis=0)


def _load_deconvolution_frames(actual_path: Path, expected_path: Optional[Path]) -> tuple[Any, Any]:
    """Load, align, and row-normalize actual/expected proportion data frames."""
    import pandas as pd

    out_df = pd.read_csv(actual_path, index_col=0)
    out_df = _normalize_rows(out_df)
    if expected_path is None or not expected_path.exists():
        return out_df, None
    exp_df = pd.read_csv(expected_path, index_col=0)
    exp_df = _normalize_rows(exp_df)
    common_idx = out_df.index.intersection(exp_df.index)
    common_cols = out_df.columns.intersection(exp_df.columns)
    if len(common_idx) == 0 or len(common_cols) == 0:
        return out_df, None
    return (
        out_df.loc[common_idx, common_cols],
        exp_df.loc[common_idx, common_cols],
    )


@metric("n_spots")
def n_spots(actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]) -> int:
    import pandas as pd

    out_df = pd.read_csv(actual_path, index_col=0)
    return int(out_df.shape[0])


@metric("n_cell_types")
def n_cell_types(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> int:
    import pandas as pd

    out_df = pd.read_csv(actual_path, index_col=0)
    return int(out_df.shape[1])


@metric("mean_rmse")
def mean_rmse(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    import numpy as np

    out_aligned, exp_aligned = _load_deconvolution_frames(actual_path, expected_path)
    if exp_aligned is None:
        return None
    rmses = []
    for col in out_aligned.columns:
        o = out_aligned[col].to_numpy(dtype=float)
        e = exp_aligned[col].to_numpy(dtype=float)
        rmses.append(float(np.sqrt(np.mean((o - e) ** 2))))
    return float(np.mean(rmses)) if rmses else None


@metric("max_rmse")
def max_rmse(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    import numpy as np

    out_aligned, exp_aligned = _load_deconvolution_frames(actual_path, expected_path)
    if exp_aligned is None:
        return None
    rmses = []
    for col in out_aligned.columns:
        o = out_aligned[col].to_numpy(dtype=float)
        e = exp_aligned[col].to_numpy(dtype=float)
        rmses.append(float(np.sqrt(np.mean((o - e) ** 2))))
    return float(np.max(rmses)) if rmses else None


@metric("mean_pearson")
def mean_pearson(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    import numpy as np

    out_aligned, exp_aligned = _load_deconvolution_frames(actual_path, expected_path)
    if exp_aligned is None:
        return None
    pears = []
    for col in out_aligned.columns:
        o = out_aligned[col].to_numpy(dtype=float)
        e = exp_aligned[col].to_numpy(dtype=float)
        std_o = np.std(o)
        std_e = np.std(e)
        if std_o > 0 and std_e > 0:
            pears.append(float(np.corrcoef(o, e)[0, 1]))
    valid = [p for p in pears if not np.isnan(p)]
    return float(np.mean(valid)) if valid else None


@metric("min_pearson")
def min_pearson(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    import numpy as np

    out_aligned, exp_aligned = _load_deconvolution_frames(actual_path, expected_path)
    if exp_aligned is None:
        return None
    pears = []
    for col in out_aligned.columns:
        o = out_aligned[col].to_numpy(dtype=float)
        e = exp_aligned[col].to_numpy(dtype=float)
        std_o = np.std(o)
        std_e = np.std(e)
        if std_o > 0 and std_e > 0:
            pears.append(float(np.corrcoef(o, e)[0, 1]))
    valid = [p for p in pears if not np.isnan(p)]
    return float(np.min(valid)) if valid else None


@metric("mean_jsd")
def mean_jsd(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> Optional[float]:
    import numpy as np
    from scipy.spatial.distance import jensenshannon

    out_aligned, exp_aligned = _load_deconvolution_frames(actual_path, expected_path)
    if exp_aligned is None:
        return None
    jsd_vals = []
    for idx in out_aligned.index:
        p = out_aligned.loc[idx].to_numpy(dtype=float)
        q = exp_aligned.loc[idx].to_numpy(dtype=float)
        js = jensenshannon(p, q)
        if js is not None and not np.isnan(js):
            jsd_vals.append(float(js**2))
    return float(np.mean(jsd_vals)) if jsd_vals else None


# --------------------------------------------------------------------------- #
# Document / text metrics
# --------------------------------------------------------------------------- #


@metric("section_overlap")
def section_overlap(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> float:
    output_text = actual_path.read_text(encoding="utf-8", errors="replace")
    expected_text = ""
    if expected_path and expected_path.exists():
        expected_text = expected_path.read_text(encoding="utf-8", errors="replace")
    output_headers = _extract_headers(output_text)
    expected_headers = _extract_headers(expected_text)
    if expected_headers:
        return round(len(output_headers & expected_headers) / len(expected_headers), 4)
    return 1.0 if not output_headers else 0.0


@metric("token_jaccard")
def token_jaccard(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> float:
    output_text = actual_path.read_text(encoding="utf-8", errors="replace")
    expected_text = ""
    if expected_path and expected_path.exists():
        expected_text = expected_path.read_text(encoding="utf-8", errors="replace")
    output_tokens = _tokenize(output_text)
    expected_tokens = _tokenize(expected_text)
    if expected_tokens:
        return round(len(output_tokens & expected_tokens) / len(output_tokens | expected_tokens), 4)
    return 1.0 if not output_tokens else 0.0


@metric("length_ratio")
def length_ratio(
    actual_path: Path, expected_path: Optional[Path], task_spec: Dict[str, Any]
) -> float:
    output_text = actual_path.read_text(encoding="utf-8", errors="replace")
    expected_text = ""
    if expected_path and expected_path.exists():
        expected_text = expected_path.read_text(encoding="utf-8", errors="replace")
    if expected_text:
        return round(len(output_text) / len(expected_text), 4)
    return 1.0 if output_text else 0.0
