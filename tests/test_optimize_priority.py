#!/usr/bin/env python3
"""Tests for improve-skill dimension priority selection."""

from __future__ import annotations

from pathlib import Path

from skillprism.evaluate_skill_rubric import DimensionResult, SkillReport, load_config
from skillprism.optimize_skill import select_weakest_dimension


def _report(scores: dict[str, int]) -> SkillReport:
    return SkillReport(
        name="test",
        path=Path("."),
        skill_type="analysis",
        dimensions=[
            DimensionResult(code=code, name=code, score=score) for code, score in scores.items()
        ],
    )


def test_select_blocker_dimension_first() -> None:
    config = load_config(Path("skill_rubric_types.yaml"))
    config["optimization"] = {
        "priority": {
            "blockers": ["D9"],
            "high_roi": ["D4"],
            "blocker_threshold": 3,
            "improvement_threshold": 3,
        }
    }
    report = _report({"D9": 1, "D4": 1, "D2": 1})
    weakest = select_weakest_dimension(report, config)
    assert weakest is not None
    assert weakest.code == "D9"


def test_select_high_roi_when_no_blocker() -> None:
    config = load_config(Path("skill_rubric_types.yaml"))
    config["optimization"] = {
        "priority": {
            "blockers": ["D9"],
            "high_roi": ["D4"],
            "blocker_threshold": 3,
            "improvement_threshold": 3,
        }
    }
    report = _report({"D9": 4, "D4": 2, "D2": 1})
    weakest = select_weakest_dimension(report, config)
    assert weakest is not None
    assert weakest.code == "D4"


def test_fallback_to_lowest_score() -> None:
    config = load_config(Path("skill_rubric_types.yaml"))
    config["optimization"] = {
        "priority": {
            "blockers": ["D9"],
            "high_roi": ["D4"],
            "blocker_threshold": 3,
            "improvement_threshold": 3,
        }
    }
    report = _report({"D9": 4, "D4": 4, "D2": 1})
    weakest = select_weakest_dimension(report, config)
    assert weakest is not None
    assert weakest.code == "D2"
