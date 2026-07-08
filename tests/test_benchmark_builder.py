#!/usr/bin/env python3
"""Tests for skillPrism.benchmark.builder scaffold options."""

from __future__ import annotations

from skillprism.benchmark.builder import build_benchmark_entry


def test_build_entry_defaults_to_level_one() -> None:
    entry = build_benchmark_entry(
        bench_id="b1",
        name="Bench One",
        skill="my-skill",
        task="csv_summary",
        task_spec_path="benchmarks/my-skill/tasks/csv_summary.yaml",
        input_path="data/input.csv",
        expected_path="expected.csv",
        metrics=None,
    )
    assert entry["b1"]["level"] == 1
    assert "requires_gpu" not in entry["b1"]
    assert "real_data" not in entry["b1"]
    assert entry["b1"]["skill"] == "my-skill"
    assert entry["b1"]["task"] == "csv_summary"
    assert "metrics" not in entry["b1"]


def test_build_entry_with_level_gpu_and_real_data() -> None:
    entry = build_benchmark_entry(
        bench_id="b1",
        name="Bench One",
        skill="my-skill",
        task="csv_summary",
        task_spec_path="benchmarks/my-skill/tasks/csv_summary.yaml",
        input_path="data/input.csv",
        expected_path=None,
        metrics=None,
        level=3,
        requires_gpu=True,
        real_data=True,
    )
    assert entry["b1"]["level"] == 3
    assert entry["b1"]["requires_gpu"] is True
    assert entry["b1"]["real_data"] is True


def test_build_entry_metrics_list() -> None:
    entry = build_benchmark_entry(
        bench_id="b1",
        name="Bench One",
        skill="my-skill",
        task="csv_summary",
        task_spec_path="benchmarks/my-skill/tasks/csv_summary.yaml",
        input_path="data/input.csv",
        expected_path="expected.csv",
        metrics=["row_count:min:8", "col_count:min:2"],
    )
    assert entry["b1"]["metrics"] == [
        {"id": "row_count", "type": "min", "threshold": 8},
        {"id": "col_count", "type": "min", "threshold": 2},
    ]
    assert "metric_overrides" not in entry["b1"]


def test_parse_metric_specs() -> None:
    from skillprism.benchmark.builder import _parse_metric

    assert _parse_metric("row_count:min:2") == {"id": "row_count", "type": "min", "threshold": 2}
    assert _parse_metric("score:max:0.5") == {"id": "score", "type": "max", "threshold": 0.5}
    assert _parse_metric("n_clusters:range:3:8") == {
        "id": "n_clusters",
        "type": "range",
        "min": 3,
        "max": 8,
    }
