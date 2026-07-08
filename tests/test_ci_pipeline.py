#!/usr/bin/env python3
"""Tests for skillPrism.ci.pipeline."""

from __future__ import annotations

from pathlib import Path

import yaml

from skillprism.ci.pipeline import CIPipeline, run_ci_pipeline

from .benchmark_helpers import (
    make_benchmark_entry,
    make_pass_through_code,
    make_table_csv,
    write_registry,
)


def test_ci_pipeline_runs_benchmarks(tmp_path: Path) -> None:
    input_csv = make_table_csv(tmp_path, "data", [["x", "y"], ["1", "2"]])
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "table_basic": make_benchmark_entry(
                tmp_path, "table_basic", "Basic Table", "my-skill", "table", input_csv, code_path
            ),
        },
    }
    registry_path = write_registry(tmp_path, registry)
    pipeline = CIPipeline(
        skill="my-skill",
        registry_path=registry_path,
        output_dir=tmp_path / "out",
    )
    results = pipeline.run(output_format="yaml", code_path=code_path)
    assert results["_all_pass"] is True
    assert "table_basic" in results["benchmarks"]


def test_ci_pipeline_detects_regression(tmp_path: Path) -> None:
    input_csv = make_table_csv(tmp_path, "data", [["x", "y"], ["1", "2"]])
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "table_basic": make_benchmark_entry(
                tmp_path, "table_basic", "Basic Table", "my-skill", "table", input_csv, code_path
            ),
        },
    }
    registry_path = write_registry(tmp_path, registry)
    baseline_path = tmp_path / "baseline.yaml"
    baseline_path.write_text(
        yaml.safe_dump(
            {
                "skill": "my-skill",
                "benchmarks": {
                    "table_basic": {"row_count": 10, "_all_pass": True, "_real_data": False}
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    results = run_ci_pipeline(
        skill="my-skill",
        registry_path=registry_path,
        baseline_path=baseline_path,
        output_dir=tmp_path / "out",
        stop_on_regression=True,
        code_path=code_path,
    )
    assert results["_all_pass"] is False
    assert results["_regression"]["all_pass"] is False


def test_ci_pipeline_ratchets_baseline(tmp_path: Path) -> None:
    input_csv = make_table_csv(tmp_path, "data", [["x", "y"], ["1", "2"]])
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "table_basic": make_benchmark_entry(
                tmp_path, "table_basic", "Basic Table", "my-skill", "table", input_csv, code_path
            ),
        },
    }
    registry_path = write_registry(tmp_path, registry)
    baseline_path = tmp_path / "baseline.yaml"
    baseline_path.write_text(
        yaml.safe_dump(
            {
                "skill": "my-skill",
                "benchmarks": {
                    "table_basic": {"row_count": 1, "_all_pass": True, "_real_data": False}
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    results = run_ci_pipeline(
        skill="my-skill",
        registry_path=registry_path,
        baseline_path=baseline_path,
        output_dir=tmp_path / "out",
        ratchet=True,
        code_path=code_path,
    )
    assert results["_all_pass"] is True
    updated_baseline = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
    assert "table_basic" in updated_baseline["benchmarks"]
