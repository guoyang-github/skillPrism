"""Tests for skillprism.gradual."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from skillprism.gradual import (
    _default_baseline_path,
    main,
    run_gradual_pipeline,
    run_gradual_stage,
)


def test_default_baseline_path() -> None:
    path = _default_baseline_path(Path("skills/foo"), 1, None, Path("out"))
    assert path == Path("out/.baselines/foo/gradual_baseline_level1.yaml")


def test_default_baseline_path_with_suite() -> None:
    path = _default_baseline_path(Path("skills/foo"), 2, "release", Path("out"))
    assert path == Path("out/.baselines/foo/gradual_baseline_level2_release.yaml")


def test_run_gradual_stage(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")

    called = {}

    class FakePipeline:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run(self, **kwargs):
            called["init"] = self.kwargs
            called["run"] = kwargs
            return {"_all_pass": True}

    monkeypatch.setattr("skillprism.gradual.CIPipeline", FakePipeline)
    result = run_gradual_stage("foo", registry, level=0, output_dir=tmp_path / "out")
    assert result["_all_pass"] is True
    assert called["init"]["skill"] == "foo"
    assert called["run"]["level"] == 0


def test_run_gradual_pipeline_all_pass(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")

    class FakePipeline:
        def __init__(self, **kwargs):
            pass

        def run(self, **kwargs):
            return {"_all_pass": True}

    monkeypatch.setattr("skillprism.gradual.CIPipeline", FakePipeline)
    result = run_gradual_pipeline("foo", registry, max_level=2, base_output_dir=tmp_path / "out")
    assert result["_all_pass"] is True
    assert set(result["stages"].keys()) == {"level0", "level1", "level2"}


def test_run_gradual_pipeline_stops_on_failure(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")

    class FakePipeline:
        def __init__(self, **kwargs):
            pass

        def run(self, **kwargs):
            if kwargs.get("level") == 1:
                return {"_all_pass": False}
            return {"_all_pass": True}

    monkeypatch.setattr("skillprism.gradual.CIPipeline", FakePipeline)
    result = run_gradual_pipeline("foo", registry, max_level=3, base_output_dir=tmp_path / "out")
    assert result["_all_pass"] is False
    assert set(result["stages"].keys()) == {"level0", "level1"}


def test_run_gradual_pipeline_invalid_level() -> None:
    with pytest.raises(ValueError, match="max_level must be between 0 and 3"):
        run_gradual_pipeline("foo", Path("registry.yaml"), max_level=4)


def test_main_pass(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")

    class FakePipeline:
        def __init__(self, **kwargs):
            pass

        def run(self, **kwargs):
            return {"_all_pass": True}

    monkeypatch.setattr("skillprism.gradual.CIPipeline", FakePipeline)

    with patch(
        "sys.argv",
        [
            "skill-gradual",
            "--skill",
            "foo",
            "--registry",
            str(registry),
            "--output-dir",
            str(tmp_path / "out"),
            "--max-level",
            "1",
        ],
    ):
        assert main() == 0


def test_main_fail(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")

    class FakePipeline:
        def __init__(self, **kwargs):
            pass

        def run(self, **kwargs):
            return {"_all_pass": False}

    monkeypatch.setattr("skillprism.gradual.CIPipeline", FakePipeline)

    with patch(
        "sys.argv",
        [
            "skill-gradual",
            "--skill",
            "foo",
            "--registry",
            str(registry),
            "--output-dir",
            str(tmp_path / "out"),
            "--max-level",
            "0",
        ],
    ):
        assert main() == 1


def test_main_code_with_results_mode_error(tmp_path: Path) -> None:
    code = tmp_path / "code.py"
    code.write_text("print('x')", encoding="utf-8")
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")

    with patch(
        "sys.argv",
        [
            "skill-gradual",
            "--skill",
            "foo",
            "--registry",
            str(registry),
            "--output-dir",
            str(tmp_path / "out"),
            "--code",
            str(code),
            "--results",
        ],
    ):
        assert main() == 2
