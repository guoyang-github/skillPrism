#!/usr/bin/env python3
"""Tests for benchmark suite support in skillPrism.benchmark.runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from skillprism.benchmark.runner import run_benchmarks


def _write_registry(tmp_path: Path, registry: Dict[str, Any]) -> Path:
    path = tmp_path / "benchmark_registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return path


def _make_table_csv(tmp_path: Path, name: str, rows: list[list[str]]) -> Path:
    path = tmp_path / f"{name}.csv"
    lines = [",".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _make_task_spec(tmp_path: Path, skill: str, task: str) -> Path:
    """Create a minimal task spec for CSV pass-through tests."""
    spec_dir = tmp_path / "tasks"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / f"{task}.yaml"
    spec_path.write_text(
        f"""id: {task}
skill: {skill}
name: {task.title()} Task
description: Minimal CSV task for testing

prompt: |
  ## Role
  Test assistant

  ## Task
  Copy input CSV to output CSV.

  ## Input
  - path: {{input_csv}}
  - format: CSV

  ## Output
  - path: {{output_csv}}
  - format: CSV

input:
  format: csv
  path: "{{input_csv}}"

output:
  format: csv
  path: "{{output_csv}}"
""",
        encoding="utf-8",
    )
    return spec_path


def _make_pass_through_code(tmp_path: Path) -> Path:
    """Create a skill code file that copies input_csv to output_csv."""
    code_path = tmp_path / "skill_code.py"
    code_path.write_text(
        "import shutil\nshutil.copy2(input_csv, output_csv)\n",
        encoding="utf-8",
    )
    return code_path


def _default_metrics() -> list[Dict[str, Any]]:
    return [
        {
            "id": "row_count",
            "name": "Row Count",
            "type": "min",
            "threshold": 1,
            "description": "Output must have at least one row",
        }
    ]


def _make_benchmark(
    tmp_path: Path,
    bench_id: str,
    name: str,
    skill: str,
    task: str,
    input_csv: Path,
    code_path: Path,
    level: int = 1,
    **extra: Any,
) -> Dict[str, Any]:
    _make_task_spec(tmp_path, skill, task)
    return {
        "name": name,
        "skill": skill,
        "task": task,
        "level": level,
        "task_spec": str(tmp_path / "tasks" / f"{task}.yaml"),
        "input": {"path": str(input_csv)},
        "metrics": _default_metrics(),
        **extra,
    }


def test_run_all_benchmarks_when_no_suite_specified(tmp_path: Path) -> None:
    input_a = _make_table_csv(tmp_path, "a", [["x", "y"], ["1", "2"]])
    input_b = _make_table_csv(tmp_path, "b", [["x", "y"], ["3", "4"]])
    code_path = _make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "2.0",
        "benchmarks": {
            "table_a": _make_benchmark(
                tmp_path, "table_a", "Table A", "my-skill", "table", input_a, code_path
            ),
            "table_b": _make_benchmark(
                tmp_path, "table_b", "Table B", "my-skill", "table", input_b, code_path
            ),
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path)
    assert set(results["benchmarks"].keys()) == {"table_a", "table_b"}
    assert results["_all_pass"] is True


def test_run_only_suite_benchmarks(tmp_path: Path) -> None:
    input_a = _make_table_csv(tmp_path, "a", [["x", "y"], ["1", "2"]])
    input_b = _make_table_csv(tmp_path, "b", [["x", "y"], ["3", "4"]])
    code_path = _make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "2.0",
        "benchmarks": {
            "table_a": _make_benchmark(
                tmp_path, "table_a", "Table A", "my-skill", "table", input_a, code_path
            ),
            "table_b": _make_benchmark(
                tmp_path, "table_b", "Table B", "my-skill", "table", input_b, code_path
            ),
        },
        "suites": {
            "darwin": {
                "description": "Fast mock suite",
                "benchmarks": ["table_a"],
            }
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path, suite="darwin")
    assert set(results["benchmarks"].keys()) == {"table_a"}
    assert results["_all_pass"] is True


def test_missing_suite_raises(tmp_path: Path) -> None:
    input_a = _make_table_csv(tmp_path, "a", [["x", "y"], ["1", "2"]])
    code_path = _make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "2.0",
        "benchmarks": {
            "table_a": _make_benchmark(
                tmp_path, "table_a", "Table A", "my-skill", "table", input_a, code_path
            ),
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    with pytest.raises(ValueError, match="Suite 'missing' not found"):
        run_benchmarks("my-skill", registry_path, code_path=code_path, suite="missing")


def test_suite_references_unknown_benchmark_raises(tmp_path: Path) -> None:
    input_a = _make_table_csv(tmp_path, "a", [["x", "y"], ["1", "2"]])
    code_path = _make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "2.0",
        "benchmarks": {
            "table_a": _make_benchmark(
                tmp_path, "table_a", "Table A", "my-skill", "table", input_a, code_path
            ),
        },
        "suites": {
            "bad": {"benchmarks": ["nonexistent"]},
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    with pytest.raises(ValueError, match="Suite references unknown benchmark"):
        run_benchmarks("my-skill", registry_path, code_path=code_path, suite="bad")


def test_suite_filters_by_skill_type(tmp_path: Path) -> None:
    input_a = _make_table_csv(tmp_path, "a", [["x", "y"], ["1", "2"]])
    input_b = _make_table_csv(tmp_path, "b", [["x", "y"], ["3", "4"]])
    code_path = _make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "2.0",
        "benchmarks": {
            "table_a": _make_benchmark(
                tmp_path, "table_a", "Table A", "skill-a", "table", input_a, code_path
            ),
            "table_b": _make_benchmark(
                tmp_path, "table_b", "Table B", "skill-b", "table", input_b, code_path
            ),
        },
        "suites": {
            "mixed": {"benchmarks": ["table_a", "table_b"]},
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("skill-a", registry_path, code_path=code_path, suite="mixed")
    assert set(results["benchmarks"].keys()) == {"table_a"}


def test_level_filter(tmp_path: Path) -> None:
    input_a = _make_table_csv(tmp_path, "a", [["x", "y"], ["1", "2"]])
    input_b = _make_table_csv(tmp_path, "b", [["x", "y"], ["3", "4"]])
    code_path = _make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "2.0",
        "benchmarks": {
            "table_unit": _make_benchmark(
                tmp_path,
                "table_unit",
                "Table Unit",
                "my-skill",
                "table",
                input_a,
                code_path,
                level=0,
            ),
            "table_integration": _make_benchmark(
                tmp_path,
                "table_integration",
                "Table Integration",
                "my-skill",
                "table",
                input_b,
                code_path,
                level=2,
            ),
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path, level=0)
    assert set(results["benchmarks"].keys()) == {"table_unit"}
    assert results["_level"] == 0


def test_gpu_benchmark_skipped_when_no_gpu(tmp_path: Path) -> None:
    input_a = _make_table_csv(tmp_path, "a", [["x", "y"], ["1", "2"]])
    input_b = _make_table_csv(tmp_path, "b", [["x", "y"], ["3", "4"]])
    code_path = _make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "2.0",
        "benchmarks": {
            "cpu_bench": _make_benchmark(
                tmp_path, "cpu_bench", "CPU Bench", "my-skill", "table", input_a, code_path
            ),
            "gpu_bench": {
                **_make_benchmark(
                    tmp_path, "gpu_bench", "GPU Bench", "my-skill", "table", input_b, code_path
                ),
                "requires_gpu": True,
            },
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path, gpu=False)
    assert set(results["benchmarks"].keys()) == {"cpu_bench"}


def test_real_data_flag_propagated_to_results(tmp_path: Path) -> None:
    input_a = _make_table_csv(tmp_path, "a", [["x", "y"], ["1", "2"]])
    code_path = _make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "2.0",
        "benchmarks": {
            "real_bench": {
                **_make_benchmark(
                    tmp_path,
                    "real_bench",
                    "Real Data Bench",
                    "my-skill",
                    "table",
                    input_a,
                    code_path,
                ),
                "real_data": True,
            },
        },
    }
    registry_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("my-skill", registry_path, code_path=code_path)
    assert results["benchmarks"]["real_bench"]["_real_data"] is True
