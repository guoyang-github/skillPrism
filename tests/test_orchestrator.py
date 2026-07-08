#!/usr/bin/env python3
"""Tests for skillprism.orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config
from skillprism.orchestrator import (
    _find_command,
    _run,
    find_worst_skill,
    generate_combined_report,
    main,
    run_benchmark_for_skill,
    run_benchmarks_all,
    run_gradual_all,
    run_gradual_for_skill,
    run_optimize_setup,
    run_rubric_all,
)

BASE_SKILL_MD = """---
name: orch-test-skill
description: A skill for testing orchestrator.
keywords:
  - test
---

# Orchestrator Test Skill

## Quick Start

```bash
echo hello
```
"""


def _make_skill(tmp_path: Path, name: str = "orch-test-skill") -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD, encoding="utf-8")
    return skill_dir


def test_find_command_prefers_installed_cli(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/bin/evaluate-skill")
    assert _find_command("evaluate-skill", "evaluate_skill.py", Path(".")) == ["evaluate-skill"]


def test_find_command_fallback_to_wrapper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    wrapper = tmp_path / "evaluate_skill.py"
    wrapper.write_text("", encoding="utf-8")
    cmd = _find_command("evaluate-skill", "evaluate_skill.py", tmp_path)
    assert cmd[0].endswith("python") or cmd[0].endswith("python3")
    assert cmd[-1] == str(wrapper)


def test_find_command_missing_exits(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(SystemExit):
        _find_command("evaluate-skill", "evaluate_skill.py", tmp_path)


def test_run_success(capsys) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert _run(["echo", "hi"]) == 0
        assert "$ echo hi" in capsys.readouterr().out


def test_run_failure_raises() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        with pytest.raises(RuntimeError):
            _run(["false"])


def test_find_worst_skill(tmp_path: Path) -> None:
    skill_a = _make_skill(tmp_path, "skill-a")
    skill_b = _make_skill(tmp_path, "skill-b")
    cfg = load_config(DEFAULT_CONFIG)
    report_a = evaluate_skill(skill_a, cfg, auto_generate_prompts=False)
    report_b = evaluate_skill(skill_b, cfg, auto_generate_prompts=False)
    worst = find_worst_skill([report_a, report_b], cfg)
    assert worst is not None
    assert worst.name in ("skill-a", "skill-b")


def test_generate_combined_report(tmp_path: Path) -> None:
    rubric = tmp_path / "rubric.md"
    rubric.write_text("# Rubric\n", encoding="utf-8")
    output = tmp_path / "combined.md"
    generate_combined_report(rubric, {}, None, output)
    assert output.exists()
    assert "# Rubric" in output.read_text(encoding="utf-8")


def test_run_rubric_all(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "rubric-skill")
    output = tmp_path / "scorecard.md"
    reports = run_rubric_all(skills_dir, tmp_path, DEFAULT_CONFIG, output, run_smoke=False)
    assert len(reports) == 1
    assert reports[0].name == "rubric-skill"
    assert output.exists()


def test_run_benchmark_for_skill(monkeypatch, tmp_path: Path) -> None:
    """Benchmark for skill delegates to run_benchmarks and optionally compares baseline."""
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "analysis-skill")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    called = {}

    def fake_run_benchmarks(skill, registry_path, code_path, output_path, suite=None):
        called["skill"] = skill
        called["output"] = output_path
        return {"_all_pass": True, "benchmarks": {"b1": {"_all_pass": True}}}

    monkeypatch.setattr("skillprism.benchmark.runner.run_benchmarks", fake_run_benchmarks)
    result = run_benchmark_for_skill("analysis-skill", "analysis", registry, skills_dir, output_dir)
    assert result["_all_pass"] is True
    assert (output_dir / "analysis-skill.yaml").exists()


def test_run_benchmark_for_skill_missing_registry(tmp_path: Path) -> None:
    result = run_benchmark_for_skill(
        "x", "analysis", tmp_path / "missing.yaml", tmp_path / "skills", tmp_path / "out"
    )
    assert "error" in result


def test_run_benchmarks_all_filters_by_type(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "schema_version: '2.0'\nbenchmarks:\n  b1:\n    skill: analysis-skill\n",
        encoding="utf-8",
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "analysis-skill")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    called = {}

    def fake_run_benchmark_for_skill(
        skill_name, skill_type, registry_path, skills_dir, output_dir, baseline_dir=None, suite=None
    ):
        called["skill"] = skill_name
        return {"_all_pass": True}

    monkeypatch.setattr(
        "skillprism.orchestrator.run_benchmark_for_skill", fake_run_benchmark_for_skill
    )
    monkeypatch.setattr("skillprism.orchestrator._get_skill_type", lambda sp, cfg: "analysis-skill")
    cfg = load_config(DEFAULT_CONFIG)
    results = run_benchmarks_all(skills_dir, registry, output_dir, config=cfg)
    assert called.get("skill") == "analysis-skill"
    assert results["analysis-skill"]["_all_pass"] is True


def test_run_optimize_setup(monkeypatch, tmp_path: Path) -> None:
    """run_optimize_setup records baseline and returns a judge command string."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_path = _make_skill(skills_dir, "opt-skill")
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_path, cfg, auto_generate_prompts=False)

    commands = []

    def fake_run(cmd):
        commands.append(cmd)
        return 0

    monkeypatch.setattr("skillprism.orchestrator._run", fake_run)
    monkeypatch.setattr(
        "skillprism.orchestrator._find_command",
        lambda cli, wrapper, engine_dir: [cli],
    )
    next_cmd = run_optimize_setup(report, skills_dir, tmp_path, DEFAULT_CONFIG)
    assert "improve-skill" in next_cmd
    assert "--judge" in next_cmd


def test_main_evaluate_intent(monkeypatch, tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "main-skill")
    output = tmp_path / "report.md"

    monkeypatch.setattr(
        "skillprism.orchestrator.run_rubric_all",
        lambda skills_dir, engine_dir, config_path, output, run_smoke: [],
    )
    monkeypatch.setattr(
        "skillprism.orchestrator.generate_combined_report",
        lambda rubric_output, benchmark_results, worst, output_path: None,
    )

    with patch(
        "sys.argv",
        [
            "skill-pipeline",
            "--intent",
            "evaluate all skills",
            "--skills-dir",
            str(skills_dir),
            "--output",
            str(output),
        ],
    ):
        assert main() == 0


def test_main_benchmark_intent_requires_registry(monkeypatch, tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "bench-skill")

    with patch(
        "sys.argv",
        [
            "skill-pipeline",
            "--intent",
            "run benchmarks",
            "--skills-dir",
            str(skills_dir),
        ],
    ):
        assert main() == 2


def test_main_gradual_intent(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "grad-skill")

    monkeypatch.setattr(
        "skillprism.orchestrator.run_gradual_all",
        lambda skills_dir, registry_path, output_dir, config=None, suite=None, max_level=3, ratchet=True: {},
    )

    with patch(
        "sys.argv",
        [
            "skill-pipeline",
            "--intent",
            "run gradual pipeline",
            "--skills-dir",
            str(skills_dir),
            "--benchmark-registry",
            str(registry),
            "--max-level",
            "1",
        ],
    ):
        assert main() == 0


def test_run_gradual_for_skill_and_all(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text("schema_version: '2.0'\nbenchmarks: {}\nsuites: {}\n", encoding="utf-8")

    called = {}

    class FakePipeline:
        def __init__(self, **kwargs):
            pass

        def run(self, **kwargs):
            called["run"] = kwargs
            return {"_all_pass": True}

    monkeypatch.setattr("skillprism.gradual.CIPipeline", FakePipeline)

    result = run_gradual_for_skill("analysis", "analysis", registry, tmp_path / "out", max_level=1)
    assert result["_all_pass"] is True


def test_run_gradual_all_stops_on_failure(monkeypatch, tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "schema_version: '2.0'\nbenchmarks:\n  b1:\n    skill: analysis-skill\n",
        encoding="utf-8",
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill(skills_dir, "analysis-skill")

    class FakePipeline:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run(self, **kwargs):
            if kwargs.get("level") == 0:
                return {"_all_pass": False}
            return {"_all_pass": True}

    monkeypatch.setattr("skillprism.gradual.CIPipeline", FakePipeline)
    monkeypatch.setattr("skillprism.orchestrator._get_skill_type", lambda sp, cfg: "analysis-skill")
    cfg = load_config(DEFAULT_CONFIG)
    all_results = run_gradual_all(skills_dir, registry, tmp_path / "out", config=cfg, max_level=2)
    result = all_results["analysis-skill"]
    assert result["_all_pass"] is False
    assert "level0" in result["stages"]
    assert "level1" not in result["stages"]
