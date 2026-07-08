#!/usr/bin/env python3
"""Tests for benchmark expected_result support."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from skillprism.benchmark.runner import run_benchmarks

from .benchmark_helpers import (
    make_benchmark_entry,
    make_pass_through_code,
    make_table_csv,
)


def _write_registry(tmp_path: Path, registry: Dict[str, Any]) -> Path:
    path = tmp_path / "benchmark_registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return path


def test_expected_fail_matches_error_passes(tmp_path: Path) -> None:
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "missing_input": {
                "name": "Missing Input",
                "skill": "my-skill",
                "task": "table",
                "level": 1,
                "task_spec": str(tmp_path / "tasks" / "table.yaml"),
                "input": {"path": str(tmp_path / "nonexistent.csv")},
                "expected_result": "fail",
                "expected_error": "No such file",
            },
        },
    }
    # Need a task spec even though the benchmark is expected to fail during path resolution.
    from .benchmark_helpers import make_task_spec

    make_task_spec(tmp_path, "my-skill", "table")
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path)
    bench = results["benchmarks"]["missing_input"]
    assert bench["_all_pass"] is True
    assert bench["_expected_result"] == "fail"
    assert bench["_expected_error_matched"] is True


def test_expected_fail_mismatched_error_fails(tmp_path: Path) -> None:
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "missing_input": {
                "name": "Missing Input",
                "skill": "my-skill",
                "task": "table",
                "level": 1,
                "task_spec": str(tmp_path / "tasks" / "table.yaml"),
                "input": {"path": str(tmp_path / "nonexistent.csv")},
                "expected_result": "fail",
                "expected_error": "Timeout",
            },
        },
    }
    from .benchmark_helpers import make_task_spec

    make_task_spec(tmp_path, "my-skill", "table")
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path)
    bench = results["benchmarks"]["missing_input"]
    assert bench["_all_pass"] is False
    assert bench["_expected_error_matched"] is False


def test_expected_pass_failure_still_fails(tmp_path: Path) -> None:
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "missing_input": {
                "name": "Missing Input",
                "skill": "my-skill",
                "task": "table",
                "level": 1,
                "task_spec": str(tmp_path / "tasks" / "table.yaml"),
                "input": {"path": str(tmp_path / "nonexistent.csv")},
                "expected_result": "pass",
            },
        },
    }
    from .benchmark_helpers import make_task_spec

    make_task_spec(tmp_path, "my-skill", "table")
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path)
    bench = results["benchmarks"]["missing_input"]
    assert bench["_all_pass"] is False
    assert "_expected_result" not in bench


def test_expected_pass_success_passes(tmp_path: Path) -> None:
    csv = make_table_csv(tmp_path, "data", [["x", "y"], ["1", "2"]])
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "simple_table": make_benchmark_entry(
                tmp_path,
                "simple_table",
                "Simple Table",
                "my-skill",
                "table",
                csv,
                code_path,
            ),
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path)
    bench = results["benchmarks"]["simple_table"]
    assert bench["_all_pass"] is True
