#!/usr/bin/env python3
"""Regression test helpers for benchmark results.

Supports per-metric comparison, suite-level regression, and mixed mock/real-data
suites where real-data benchmarks are checked for completion rather than scored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# Metric names that are "lower is better". Inferred when a metric spec does not
# declare an explicit ``direction``. A regression (worsening) for these is a
# positive diff; for everything else a regression is a negative diff.
_LOWER_BETTER_KEYWORDS = (
    "rmse",
    "mse",
    "mae",
    "jsd",
    "error",
    "diff",
    "divergence",
    "distance",
    "loss",
    "largest_cluster_ratio",
)


def _is_lower_better(name: str) -> bool:
    """Infer metric direction from its name (lower-is-better vs higher-is-better)."""
    lower = name.lower()
    return any(k in lower for k in _LOWER_BETTER_KEYWORDS)


def compare_metrics(
    current: Dict[str, Any],
    baseline: Dict[str, Any],
    tolerance: float = 0.03,
) -> Dict[str, Any]:
    """Compare current metrics against baseline with relative tolerance.

    Direction-aware: for lower-is-better metrics (rmse/jsd/error/...) a
    *decrease* is IMPROVED and an *increase* is REGRESSION; for higher-is-better
    metrics the reverse. A near-zero baseline is compared by absolute difference
    rather than dividing by zero (which previously flagged a stable 0 as a
    regression).
    """
    report: Dict[str, Any] = {}
    all_pass = True

    for name, base_value in baseline.items():
        if name == "version" or name.startswith("_"):
            continue
        current_value = current.get(name)
        if current_value is None:
            report[name] = {"status": "MISSING", "current": None, "baseline": base_value}
            all_pass = False
            continue

        if not isinstance(base_value, (int, float)) or not isinstance(current_value, (int, float)):
            report[name] = {"status": "SKIP", "current": current_value, "baseline": base_value}
            continue

        diff = current_value - base_value
        lower_better = _is_lower_better(name)

        if base_value == 0:
            # Avoid divide-by-zero: a stable 0 baseline must PASS when current is 0.
            within_tol = current_value == 0
            rel_diff = 0.0 if current_value == 0 else float("inf")
        else:
            rel_diff = diff / abs(base_value)
            within_tol = abs(rel_diff) <= tolerance

        if within_tol:
            status = "PASS"
        elif lower_better:
            if diff < 0:
                status = "IMPROVED"
            else:
                status = "REGRESSION"
                all_pass = False
        else:  # higher is better
            if diff > 0:
                status = "IMPROVED"
            else:
                status = "REGRESSION"
                all_pass = False

        report[name] = {
            "status": status,
            "current": current_value,
            "baseline": base_value,
            "relative_diff": "n/a" if rel_diff == float("inf") else f"{rel_diff:+.2%}",
        }

    return {"all_pass": all_pass, "metrics": report}


def compare_benchmark_results(
    current: Dict[str, Any],
    baseline: Dict[str, Any],
    tolerance: float = 0.03,
) -> Dict[str, Any]:
    """Compare full benchmark result documents."""
    current_benchmarks = current.get("benchmarks", {})
    baseline_benchmarks = baseline.get("benchmarks", {})

    overall: Dict[str, Any] = {"all_pass": True, "benchmarks": {}}
    for bench_id in baseline_benchmarks:
        if bench_id not in current_benchmarks:
            overall["benchmarks"][bench_id] = {
                "all_pass": False,
                "error": "MISSING in current results",
            }
            overall["all_pass"] = False
            continue

        comparison = compare_metrics(
            current_benchmarks[bench_id], baseline_benchmarks[bench_id], tolerance
        )
        overall["benchmarks"][bench_id] = comparison
        if not comparison["all_pass"]:
            overall["all_pass"] = False

    return overall


class RegressionSuite:
    """A collection of benchmark results used for regression testing."""

    def __init__(self, results: Dict[str, Any]) -> None:
        self.results = results
        self.skill = results.get("skill", "unknown")
        self.benchmarks = results.get("benchmarks", {})

    @classmethod
    def from_file(cls, path: Path) -> "RegressionSuite":
        return cls(load_yaml(path))

    def pass_rate(self, real_data_only: bool = False) -> float:
        """Return the fraction of benchmarks that passed."""
        benches = self.benchmarks.values()
        if real_data_only:
            benches = [b for b in benches if b.get("_real_data")]
        else:
            benches = [b for b in benches if not b.get("_real_data")]
        if not benches:
            return 0.0
        passed = sum(1 for b in benches if b.get("_all_pass"))
        return passed / len(benches)

    def compare_to(
        self,
        baseline: "RegressionSuite",
        tolerance: float = 0.03,
    ) -> Dict[str, Any]:
        """Compare this suite against a baseline suite."""
        return compare_benchmark_results(self.results, baseline.results, tolerance)


def compare_suite(
    current: Dict[str, Any],
    baseline: Dict[str, Any],
    tolerance: float = 0.03,
) -> Dict[str, Any]:
    """High-level suite comparison.

    Mock benchmarks are scored normally. Real-data benchmarks are checked for
    completion (``_all_pass`` must be True) but their metrics do not contribute
    to the quantitative comparison.
    """
    current_benchmarks = current.get("benchmarks", {})
    baseline_benchmarks = baseline.get("benchmarks", {})

    overall: Dict[str, Any] = {
        "all_pass": True,
        "mock": {"all_pass": True, "benchmarks": {}},
        "real_data": {"all_pass": True, "benchmarks": {}},
    }

    for bench_id in baseline_benchmarks:
        is_real = bool(baseline_benchmarks[bench_id].get("_real_data"))
        bucket = "real_data" if is_real else "mock"

        if bench_id not in current_benchmarks:
            overall[bucket]["benchmarks"][bench_id] = {
                "all_pass": False,
                "error": "MISSING in current results",
            }
            overall[bucket]["all_pass"] = False
            overall["all_pass"] = False
            continue

        if is_real:
            current_pass = bool(current_benchmarks[bench_id].get("_all_pass"))
            overall[bucket]["benchmarks"][bench_id] = {
                "all_pass": current_pass,
                "note": "real-data benchmark: checked for completion only",
            }
            if not current_pass:
                overall[bucket]["all_pass"] = False
                overall["all_pass"] = False
        else:
            comparison = compare_metrics(
                current_benchmarks[bench_id], baseline_benchmarks[bench_id], tolerance
            )
            overall[bucket]["benchmarks"][bench_id] = comparison
            if not comparison["all_pass"]:
                overall[bucket]["all_pass"] = False
                overall["all_pass"] = False

    return overall
