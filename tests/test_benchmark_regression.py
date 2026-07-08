#!/usr/bin/env python3
"""Tests for skillPrism.benchmark.regression suite comparison."""

from __future__ import annotations

from skillprism.benchmark.regression import (
    compare_benchmark_results,
    compare_metrics,
    compare_suite,
)


def test_compare_metrics_pass_within_tolerance() -> None:
    current = {"accuracy": 1.0, "f1": 0.95}
    baseline = {"accuracy": 1.0, "f1": 0.94}
    report = compare_metrics(current, baseline, tolerance=0.03)
    assert report["all_pass"] is True
    assert report["metrics"]["f1"]["status"] == "PASS"


def test_compare_metrics_detects_regression() -> None:
    current = {"accuracy": 0.90}
    baseline = {"accuracy": 1.0}
    report = compare_metrics(current, baseline, tolerance=0.03)
    assert report["all_pass"] is False
    assert report["metrics"]["accuracy"]["status"] == "REGRESSION"


def test_compare_metrics_detects_improvement() -> None:
    current = {"accuracy": 1.05}
    baseline = {"accuracy": 1.0}
    report = compare_metrics(current, baseline, tolerance=0.03)
    assert report["all_pass"] is True
    assert report["metrics"]["accuracy"]["status"] == "IMPROVED"


def test_compare_metrics_lower_better_rmse_decrease_is_improvement() -> None:
    """For lower-is-better metrics, a decrease is IMPROVED (not REGRESSION)."""
    current = {"mean_rmse": 0.10}
    baseline = {"mean_rmse": 0.20}
    report = compare_metrics(current, baseline, tolerance=0.03)
    assert report["all_pass"] is True
    assert report["metrics"]["mean_rmse"]["status"] == "IMPROVED"


def test_compare_metrics_lower_better_rmse_increase_is_regression() -> None:
    """For lower-is-better metrics, an increase is REGRESSION (not IMPROVED)."""
    current = {"mean_rmse": 0.30}
    baseline = {"mean_rmse": 0.20}
    report = compare_metrics(current, baseline, tolerance=0.03)
    assert report["all_pass"] is False
    assert report["metrics"]["mean_rmse"]["status"] == "REGRESSION"


def test_compare_metrics_jsd_increase_is_regression() -> None:
    current = {"mean_jsd": 0.05}
    baseline = {"mean_jsd": 0.01}
    report = compare_metrics(current, baseline, tolerance=0.03)
    assert report["all_pass"] is False
    assert report["metrics"]["mean_jsd"]["status"] == "REGRESSION"


def test_compare_metrics_zero_baseline_stable_passes() -> None:
    """A stable 0 baseline must PASS, not be flagged as REGRESSION via inf."""
    current = {"expected_diff_rows": 0}
    baseline = {"expected_diff_rows": 0}
    report = compare_metrics(current, baseline, tolerance=0.03)
    assert report["all_pass"] is True
    assert report["metrics"]["expected_diff_rows"]["status"] == "PASS"


def test_compare_metrics_zero_baseline_nonzero_current_is_change() -> None:
    """A 0 baseline with a nonzero current is a change (regression for lower-better)."""
    current = {"mean_rmse": 0.5}
    baseline = {"mean_rmse": 0}
    report = compare_metrics(current, baseline, tolerance=0.03)
    assert report["all_pass"] is False
    assert report["metrics"]["mean_rmse"]["status"] == "REGRESSION"


def test_compare_benchmark_results_missing_benchmark() -> None:
    current = {"benchmarks": {}}
    baseline = {"benchmarks": {"b1": {"accuracy": 1.0}}}
    report = compare_benchmark_results(current, baseline)
    assert report["all_pass"] is False
    assert report["benchmarks"]["b1"]["error"] == "MISSING in current results"


def test_compare_suite_treats_real_data_as_completion() -> None:
    baseline = {
        "benchmarks": {
            "mock": {"accuracy": 0.9, "_real_data": False},
            "real": {"accuracy": 0.5, "_real_data": True},
        }
    }
    current = {
        "benchmarks": {
            "mock": {"accuracy": 0.88, "_real_data": False},
            "real": {"accuracy": 0.5, "_real_data": True, "_all_pass": True},
        }
    }
    report = compare_suite(current, baseline, tolerance=0.03)
    assert report["mock"]["benchmarks"]["mock"]["all_pass"] is True
    assert report["real_data"]["benchmarks"]["real"]["all_pass"] is True
    assert report["all_pass"] is True


def test_compare_suite_fails_when_real_data_not_complete() -> None:
    baseline = {
        "benchmarks": {
            "real": {"_real_data": True},
        }
    }
    current = {
        "benchmarks": {
            "real": {"_real_data": True, "_all_pass": False},
        }
    }
    report = compare_suite(current, baseline)
    assert report["all_pass"] is False
    assert report["real_data"]["all_pass"] is False
