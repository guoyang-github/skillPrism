#!/usr/bin/env python3
"""Tests for per-skill-type dimension enable/disable and D1 meta-skill flags."""

from __future__ import annotations

from pathlib import Path

from skillprism.dimensions.d1_structure import evaluate_d1_structure
from skillprism.evaluate_skill_rubric import (
    BUILTIN_DIMENSION_EVALUATORS,
    evaluate_skill,
    get_dimension_evaluators,
    load_config,
)


def _make_skill(tmp_path: Path, content: str = "# Test\n") -> Path:
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: A test skill.\nkeywords: [test]\n---\n\n" + content,
        encoding="utf-8",
    )
    return skill_dir


def test_get_dimension_evaluators_default(tmp_path: Path) -> None:
    config = load_config(Path("skill_rubric_types.yaml"))
    evaluators = get_dimension_evaluators(config, "analysis")
    assert len(evaluators) == 9


def test_get_dimension_evaluators_filtered(tmp_path: Path) -> None:
    config = {"skill_types": {"meta": {"enabled_dimensions": ["D1", "D2"]}}}
    evaluators = get_dimension_evaluators(config, "meta")
    assert len(evaluators) == 2
    assert all(
        ev in {BUILTIN_DIMENSION_EVALUATORS["D1"], BUILTIN_DIMENSION_EVALUATORS["D2"]}
        for ev in evaluators
    )


def test_get_dimension_evaluators_unknown_warns(tmp_path: Path, capsys) -> None:
    config = {"skill_types": {"x": {"enabled_dimensions": ["D1", "DX"]}}}
    evaluators = get_dimension_evaluators(config, "x")
    assert len(evaluators) == 1
    captured = capsys.readouterr()
    assert "unknown dimension 'DX'" in captured.err


def test_evaluate_skill_respects_enabled_dimensions(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    config = {"skill_types": {"generic": {"enabled_dimensions": ["D1", "D2"]}}}
    report = evaluate_skill(skill_dir, config)
    codes = [d.code for d in report.dimensions]
    assert codes == ["D1", "D2"]


def test_d1_require_examples_false(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    config = {
        "skill_types": {
            "generic": {
                "dimension_checks": {
                    "D1": {
                        "require_examples": False,
                        "require_usage_guide": False,
                        "dependency_file_candidates": [],
                    }
                }
            }
        }
    }
    result = evaluate_d1_structure(skill_dir, "generic", config)
    assert "缺少 examples/ 目录或示例" not in str(result.suggestions)
    assert "缺少用户使用指南" not in str(result.suggestions)


def test_d1_require_usage_guide_false(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    config = {
        "skill_types": {
            "generic": {
                "dimension_checks": {
                    "D1": {
                        "require_examples": True,
                        "require_usage_guide": False,
                        "dependency_file_candidates": [],
                    }
                }
            }
        }
    }
    result = evaluate_d1_structure(skill_dir, "generic", config)
    assert "缺少用户使用指南" not in str(result.suggestions)
    assert "缺少 examples/ 目录或示例" in str(result.suggestions)
