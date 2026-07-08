#!/usr/bin/env python3
"""Shared helpers for benchmark tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def write_registry(tmp_path: Path, registry: Dict[str, Any]) -> Path:
    path = tmp_path / "benchmark_registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return path


def make_skill_registry(
    tmp_path: Path,
    skill: str,
    benchmarks: Dict[str, Any],
    suites: Dict[str, Any] | None = None,
) -> Path:
    """Create a per-skill registry under ``tmp_path/benchmarks/<skill>/registry.yaml``."""
    registry_dir = tmp_path / "benchmarks" / skill
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry: Dict[str, Any] = {"schema_version": "2.0", "benchmarks": benchmarks}
    if suites:
        registry["suites"] = suites
    path = registry_dir / "registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return path


def make_table_csv(tmp_path: Path, name: str, rows: list[list[str]]) -> Path:
    path = tmp_path / f"{name}.csv"
    lines = [",".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def make_task_spec(
    tmp_path: Path,
    skill: str,
    task: str,
    input_format: str = "csv",
    output_format: str = "csv",
) -> Path:
    """Create a minimal task spec for testing."""
    spec_dir = tmp_path / "tasks"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / f"{task}.yaml"
    spec_path.write_text(
        f"""id: {task}
skill: {skill}
name: {task.title()} Task
description: Minimal task for testing

prompt: |
  ## Role
  Test assistant

  ## Task
  Copy the input file to the output path.

  ## Input
  - path: {{input_csv}}
  - format: {input_format}

  ## Output
  - path: {{output_csv}}
  - format: {output_format}

input:
  format: {input_format}
  path: "{{input_csv}}"

output:
  format: {output_format}
  path: "{{output_csv}}"
""",
        encoding="utf-8",
    )
    return spec_path


def make_pass_through_code(tmp_path: Path) -> Path:
    """Create a skill code file that copies input_csv to output_csv."""
    code_path = tmp_path / "skill_code.py"
    code_path.write_text(
        "import shutil\nshutil.copy2(input_csv, output_csv)\n",
        encoding="utf-8",
    )
    return code_path


def make_benchmark_entry(
    tmp_path: Path,
    bench_id: str,
    name: str,
    skill: str,
    task: str,
    input_csv: Path,
    code_path: Path,
    level: int = 1,
    metrics: list[Dict[str, Any]] | None = None,
    expected_path: Path | None = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Create a new-format benchmark entry referencing a task spec."""
    make_task_spec(tmp_path, skill, task)
    if metrics is None:
        metrics = [
            {
                "id": "row_count",
                "name": "Row Count",
                "type": "min",
                "threshold": 1,
                "description": "Output must have at least one row",
            }
        ]
    entry: Dict[str, Any] = {
        "name": name,
        "skill": skill,
        "task": task,
        "level": level,
        "task_spec": str(tmp_path / "tasks" / f"{task}.yaml"),
        "input": {"path": str(input_csv)},
        "metrics": metrics,
        **extra,
    }
    if expected_path is not None:
        entry["expected"] = {"format": "csv", "path": str(expected_path)}
    return entry
