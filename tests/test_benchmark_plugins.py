#!/usr/bin/env python3
"""Tests for benchmark execution via task specs (legacy plugin API removed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from skillprism.benchmark.runner import run_benchmarks

from .benchmark_helpers import make_benchmark_entry, make_pass_through_code


def _write_registry(tmp_path: Path, registry: Dict[str, Any]) -> Path:
    path = tmp_path / "benchmark_registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return path


def test_task_spec_runs_successfully(tmp_path: Path) -> None:
    csv = tmp_path / "data.csv"
    csv.write_text("x,y\n1,2\n", encoding="utf-8")
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "custom_1": make_benchmark_entry(
                tmp_path, "custom_1", "custom plugin benchmark", "analysis", "table", csv, code_path
            ),
        },
    }
    reg_path = _write_registry(tmp_path, registry)
    results = run_benchmarks("analysis", reg_path, code_path=code_path, output_format="json")
    assert results["_all_pass"] is True
    assert results["benchmarks"]["custom_1"]["row_count"] == 1


def test_registered_plugin_task_is_dispatched_by_runner(tmp_path: Path) -> None:
    """A plugin registered via plugins.register is dispatched by run_benchmarks."""
    from skillprism.benchmark import plugins

    def my_task(benchmark, skill, code_path, registry, registry_dir):
        return {"_all_pass": True, "custom_metric": 42, "source": "plugin"}

    plugins.register("my_plugin_task", my_task)
    try:
        registry = {
            "schema_version": "1.0",
            "benchmarks": {
                "plug_1": {
                    "name": "Plugin benchmark",
                    "skill": "analysis",
                    "task": "my_plugin_task",
                    "input": {"path": str(tmp_path / "in.csv")},
                    "output": {"path": str(tmp_path / "out.csv")},
                    "expected": {"path": str(tmp_path / "exp.csv")},
                },
            },
        }
        reg_path = _write_registry(tmp_path, registry)
        results = run_benchmarks("analysis", reg_path, output_format="json")
        assert results["benchmarks"]["plug_1"]["_all_pass"] is True
        assert results["benchmarks"]["plug_1"]["source"] == "plugin"
        assert results["benchmarks"]["plug_1"]["custom_metric"] == 42
    finally:
        plugins.unregister("my_plugin_task")
