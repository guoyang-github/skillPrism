#!/usr/bin/env python3
"""Tests for improve-skill JSON output."""

from __future__ import annotations

import json
from pathlib import Path

from skillprism.evaluate_skill_rubric import (
    DimensionResult,
    SkillReport,
    load_config,
)
from skillprism.optimize_skill import (
    JudgeResult,
    judge_result_to_dict,
)


def test_judge_result_to_dict(tmp_path: Path) -> None:
    config = load_config(Path("skill_rubric_types.yaml"))
    report = SkillReport(
        name="test-skill",
        path=tmp_path,
        skill_type="analysis",
        dimensions=[
            DimensionResult(code="D4", name="依赖", score=2),
            DimensionResult(code="D2", name="文档", score=3),
        ],
    )
    result = JudgeResult(
        kept=True,
        applied=False,
        current_score=58.1,
        baseline_score=45.4,
        score_delta=12.7,
        benchmark_ok=True,
        benchmark_reason="benchmark acceptable",
        guard_violations=[],
        current_report=report,
        current_benchmark=None,
        decision_reason="Rubric score improved",
    )
    data = judge_result_to_dict(result, config)
    assert data["kept"] is True
    assert data["applied"] is False
    assert data["current_score"] == 58.1
    assert data["baseline_score"] == 45.4
    assert data["score_delta"] == 12.7
    assert data["decision"] == "KEEP"
    assert data["weakest_dimension"]["code"] == "D4"
    assert data["benchmark_ok"] is True
    assert data["guard_violations"] == []


def test_optimize_skill_cli_writes_json(tmp_path: Path) -> None:
    """End-to-end test that --output-json produces valid JSON."""
    import subprocess

    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: Test\nkeywords: [test]\ntool_type: python\n---\n\n# Test\n",
        encoding="utf-8",
    )

    # Record baseline
    subprocess.run(
        [
            "improve-skill",
            str(skill_dir),
            "--record-baseline",
            "--config",
            "skill_rubric_types.yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    # Judge and write JSON
    json_path = tmp_path / "judge.json"
    result = subprocess.run(
        [
            "improve-skill",
            str(skill_dir),
            "--judge",
            "--config",
            "skill_rubric_types.yaml",
            "--output-json",
            str(json_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1), result.stderr
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "current_score" in data
    assert "baseline_score" in data
    assert "decision" in data
