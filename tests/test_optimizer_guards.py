#!/usr/bin/env python3
"""Unit tests for optimizer anti-pattern guards."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillprism.evaluate_skill_rubric import DimensionResult, SkillReport
from skillprism.optimizer_guards import (
    guard_dry_run_ratio,
    guard_no_bloat,
    guard_no_reset_hard,
    guard_no_silent_errors,
    guard_one_dimension_per_round,
    guard_self_judge,
)


class TestOneDimensionPerRound:
    def test_single_improvement_ok(self) -> None:
        baseline = SkillReport(
            name="s",
            path=Path("."),
            skill_type="generic",
            dimensions=[DimensionResult(code="D1", name="D1", score=3)],
        )
        candidate = SkillReport(
            name="s",
            path=Path("."),
            skill_type="generic",
            dimensions=[DimensionResult(code="D1", name="D1", score=4)],
        )
        assert guard_one_dimension_per_round(baseline, candidate) is None

    def test_multi_dimension_warn(self) -> None:
        baseline = SkillReport(
            name="s",
            path=Path("."),
            skill_type="generic",
            dimensions=[
                DimensionResult(code="D1", name="D1", score=3),
                DimensionResult(code="D2", name="D2", score=3),
            ],
        )
        candidate = SkillReport(
            name="s",
            path=Path("."),
            skill_type="generic",
            dimensions=[
                DimensionResult(code="D1", name="D1", score=4),
                DimensionResult(code="D2", name="D2", score=5),
            ],
        )
        v = guard_one_dimension_per_round(baseline, candidate)
        assert v is not None
        assert v.severity == "warn"
        assert "多个维度" in v.message


class TestDryRunRatio:
    def test_low_ratio_ok(self) -> None:
        report = SkillReport(
            name="s",
            path=Path("."),
            skill_type="generic",
            dimensions=[
                DimensionResult(code="D1", name="D1", score=4, total_checks=5, skipped_checks=1)
            ],
        )
        assert guard_dry_run_ratio(report, threshold=0.3) is None

    def test_high_ratio_warns(self) -> None:
        report = SkillReport(
            name="s",
            path=Path("."),
            skill_type="generic",
            dimensions=[
                DimensionResult(code="D1", name="D1", score=2, total_checks=5, skipped_checks=4)
            ],
        )
        v = guard_dry_run_ratio(report, threshold=0.3)
        assert v is not None
        assert v.severity == "warn"
        assert "干跑比例" in v.message


class TestNoResetHard:
    def test_clean_skill(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("Use git revert for rollback.")
        assert guard_no_reset_hard(tmp_path) is None

    def test_skill_md_forbidden_example_does_not_block(self, tmp_path: Path) -> None:
        """SKILL.md may document `git reset --hard` as a forbidden command (D9
        strategy tells the editor to write it). The guard must NOT block that."""
        (tmp_path / "SKILL.md").write_text(
            "## High-Risk Action Blacklist\n\nForbidden: `git reset --hard`, `rm -rf /`.\n"
        )
        assert guard_no_reset_hard(tmp_path) is None

    def test_resets_hard_in_script_blocks(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("doc")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "rollback.sh").write_text("git reset --hard origin/main\n")
        v = guard_no_reset_hard(tmp_path)
        assert v is not None
        assert v.severity == "block"
        assert "rollback.sh" in v.message

    def test_baseline_snapshot_ignored(self, tmp_path: Path) -> None:
        """A previously-reverted snapshot containing the command must not block."""
        base = tmp_path / ".skillprism_baseline"
        base.mkdir()
        (base / "SKILL.md.bak").write_text("git reset --hard\n")
        (tmp_path / "SKILL.md").write_text("clean doc")
        assert guard_no_reset_hard(tmp_path) is None


class TestNoBloat:
    def test_no_baseline_no_violation(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("Short doc.")
        assert guard_no_bloat(tmp_path) is None

    def test_bloat_warn(self, tmp_path: Path) -> None:
        baseline_dir = tmp_path / ".skillprism_baseline"
        baseline_dir.mkdir()
        (baseline_dir / "SKILL.md").write_text("Line1\nLine2\n")
        long_text = "\n".join([f"filler line {i}" for i in range(20)])
        (tmp_path / "SKILL.md").write_text(long_text)
        v = guard_no_bloat(tmp_path, {"score": 50.0, "candidate_score": 50.5})
        assert v is not None
        assert v.severity == "warn"


class TestNoSilentErrors:
    def test_no_errors(self) -> None:
        report = SkillReport(name="s", path=Path("."), skill_type="generic")
        assert guard_no_silent_errors(report) is None

    def test_errors_reported(self) -> None:
        report = SkillReport(name="s", path=Path("."), skill_type="generic", errors=["scan failed"])
        v = guard_no_silent_errors(report)
        assert v is not None
        assert "error" in v.message.lower() or "错误" in v.message


class TestSelfJudge:
    def test_different_models_ok(self) -> None:
        assert guard_self_judge("gpt-4", "claude-3") is None

    def test_same_model_warns(self) -> None:
        v = guard_self_judge("gpt-4", "gpt-4")
        assert v is not None
        assert v.severity == "warn"
