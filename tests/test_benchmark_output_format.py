#!/usr/bin/env python3
"""Tests for benchmark output formatting."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from skillprism.benchmark.runner import run_benchmarks

from .benchmark_helpers import make_benchmark_entry, make_pass_through_code, write_registry


def _make_csv(tmp_path: Path, name: str) -> Path:
    path = tmp_path / f"{name}.csv"
    path.write_text("x,y\n1,2\n", encoding="utf-8")
    return path


def test_output_json_format(tmp_path: Path) -> None:
    csv = _make_csv(tmp_path, "data")
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "simple": make_benchmark_entry(
                tmp_path, "simple", "Simple", "my-skill", "table", csv, code_path
            ),
        },
    }
    registry_path = write_registry(tmp_path, registry)
    output_path = tmp_path / "results.json"
    run_benchmarks(
        "my-skill",
        registry_path,
        code_path=code_path,
        output_path=output_path,
        output_format="json",
    )
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["skill"] == "my-skill"
    assert data["benchmarks"]["simple"]["_all_pass"] is True


def test_output_markdown_format(tmp_path: Path) -> None:
    csv = _make_csv(tmp_path, "data")
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "simple": make_benchmark_entry(
                tmp_path, "simple", "Simple", "my-skill", "table", csv, code_path
            ),
        },
    }
    registry_path = write_registry(tmp_path, registry)
    output_path = tmp_path / "results.md"
    run_benchmarks(
        "my-skill",
        registry_path,
        code_path=code_path,
        output_path=output_path,
        output_format="markdown",
    )
    text = output_path.read_text(encoding="utf-8")
    assert "# Benchmark Results" in text
    assert "| simple | PASS |" in text


def test_output_yaml_format_default(tmp_path: Path) -> None:
    csv = _make_csv(tmp_path, "data")
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "simple": make_benchmark_entry(
                tmp_path, "simple", "Simple", "my-skill", "table", csv, code_path
            ),
        },
    }
    registry_path = write_registry(tmp_path, registry)
    output_path = tmp_path / "results.yaml"
    run_benchmarks("my-skill", registry_path, code_path=code_path, output_path=output_path)
    data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert data["skill"] == "my-skill"
