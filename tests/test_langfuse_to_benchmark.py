#!/usr/bin/env python3
"""Tests for scripts/langfuse_to_benchmark.py."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from scripts import langfuse_to_benchmark


def _fake_client(trace_input, trace_output, metadata):
    class _TraceApi:
        @classmethod
        def get(cls, trace_id):
            return SimpleNamespace(
                input=trace_input,
                output=trace_output,
                metadata=metadata,
            )

    class _Client:
        trace = _TraceApi

    class _Langfuse:
        client = _Client()

    return _Langfuse()


def test_trace_to_benchmark_dry_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_HOST", "https://example.com")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")

    fake = _fake_client("a,b\n1,2", "ok", {"skill_name": "csv", "task": "summary"})
    with patch.object(langfuse_to_benchmark, "_get_langfuse_client", return_value=fake):
        registry = tmp_path / "benchmarks" / "registry.yaml"
        with patch(
            "sys.argv",
            [
                "langfuse_to_benchmark",
                "--trace-id",
                "t1",
                "--registry",
                str(registry),
                "--dry-run",
            ],
        ):
            assert langfuse_to_benchmark.main() == 0

    assert not registry.exists()


def test_trace_to_benchmark_writes_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_HOST", "https://example.com")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")

    fake = _fake_client(
        {"query": "count rows"},
        {"rows": 5},
        {"skill_name": "json-skill", "task": "count"},
    )
    with patch.object(langfuse_to_benchmark, "_get_langfuse_client", return_value=fake):
        registry = tmp_path / "benchmarks" / "registry.yaml"
        with patch(
            "sys.argv",
            [
                "langfuse_to_benchmark",
                "--trace-id",
                "t1",
                "--registry",
                str(registry),
                "--suite",
                "smoke",
            ],
        ):
            assert langfuse_to_benchmark.main() == 0

    assert registry.exists()
    loaded = yaml.safe_load(registry.read_text(encoding="utf-8"))
    assert "json-skill_count_auto" in loaded["benchmarks"]
    assert "smoke" in loaded["suites"]

    task_spec = tmp_path / "benchmarks" / "tasks" / "count.yaml"
    assert task_spec.exists()
    spec = yaml.safe_load(task_spec.read_text(encoding="utf-8"))
    assert spec["id"] == "count"
    assert spec["skill"] == "json-skill"
    assert "metrics" not in spec

    input_file = tmp_path / "benchmarks" / "data" / "count" / "input.json"
    expected_file = tmp_path / "benchmarks" / "expected" / "count.json"
    assert json.loads(input_file.read_text(encoding="utf-8")) == {"query": "count rows"}
    assert json.loads(expected_file.read_text(encoding="utf-8")) == {"rows": 5}


def test_missing_skill_name_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_HOST", "https://example.com")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")

    fake = _fake_client("in", "out", {})
    with patch.object(langfuse_to_benchmark, "_get_langfuse_client", return_value=fake):
        with patch(
            "sys.argv",
            ["langfuse_to_benchmark", "--trace-id", "t1"],
        ):
            assert langfuse_to_benchmark.main() == 2
