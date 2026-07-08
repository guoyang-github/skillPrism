#!/usr/bin/env python3
"""Tests for diff_<metric> consistency metrics in benchmark evaluators."""

from __future__ import annotations

from pathlib import Path

from skillprism.benchmark.evaluators import GenericEvaluator


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_diff_row_count(tmp_path: Path) -> None:
    actual = tmp_path / "actual.csv"
    expected = tmp_path / "expected.csv"
    _write_csv(actual, [{"a": "1"}, {"a": "2"}, {"a": "3"}])
    _write_csv(expected, [{"a": "1"}, {"a": "2"}])

    evaluator = GenericEvaluator()
    result = evaluator.evaluate(
        actual,
        expected,
        [{"id": "diff_row_count", "type": "exact", "expected": 1}],
        {},
    )
    assert result["diff_row_count"] == 1
    assert result["_all_pass"] is True


def test_diff_row_count_zero(tmp_path: Path) -> None:
    actual = tmp_path / "actual.csv"
    expected = tmp_path / "expected.csv"
    _write_csv(actual, [{"a": "1"}, {"a": "2"}])
    _write_csv(expected, [{"a": "1"}, {"a": "2"}])

    evaluator = GenericEvaluator()
    result = evaluator.evaluate(
        actual,
        expected,
        [{"id": "diff_row_count", "type": "exact", "expected": 0}],
        {},
    )
    assert result["diff_row_count"] == 0
    assert result["_all_pass"] is True


def test_diff_metric_missing_expected(tmp_path: Path) -> None:
    actual = tmp_path / "actual.csv"
    _write_csv(actual, [{"a": "1"}])

    evaluator = GenericEvaluator()
    result = evaluator.evaluate(
        actual,
        None,
        [{"id": "diff_row_count", "type": "exact", "expected": 0}],
        {},
    )
    assert result["diff_row_count"] is None
    assert result["_all_pass"] is False
