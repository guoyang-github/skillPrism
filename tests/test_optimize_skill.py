#!/usr/bin/env python3
"""Unit tests for skillPrism.optimize_skill apply/revert behavior."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillprism.evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    load_config,
)
from skillprism.optimize_skill import (
    _run_auto_edit_rounds,
    judge_candidate,
    load_baseline,
    save_baseline,
)
from skillprism.skill_editor import SkillEditor

GOOD_SKILL_MD = """---
name: test-skill
description: A test skill for optimizer behavior.
keywords:
  - test
  - skill
---

# Test Skill

## When to Use

Use this skill to test the optimizer.

## Inputs

| Name | Type | Required |
|---|---|---|
| input | string | Yes |

## Outputs

The output is a success message.

## Quick Start

```bash
echo "hello"
```
"""


class TestJudgeApply:
    def test_dry_run_does_not_revert(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(GOOD_SKILL_MD)

        config = load_config(DEFAULT_CONFIG)
        # Use real evaluation for baseline
        from skillprism.evaluate_skill_rubric import evaluate_skill

        report = evaluate_skill(skill_dir, config)
        save_baseline(skill_dir, report)
        baseline = load_baseline(skill_dir)

        # Edit the skill
        skill_md.write_text(GOOD_SKILL_MD + "\n## Notes\n\nExtra section.\n")

        result = judge_candidate(
            skill_dir,
            config,
            baseline,
            apply=False,
        )
        assert result.applied is False
        # Dry-run should not revert
        assert "Extra section" in skill_md.read_text()

    def test_apply_reverts_no_improvement(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(GOOD_SKILL_MD)

        config = load_config(DEFAULT_CONFIG)
        from skillprism.evaluate_skill_rubric import evaluate_skill

        report = evaluate_skill(skill_dir, config)
        save_baseline(skill_dir, report)
        baseline = load_baseline(skill_dir)
        original = skill_md.read_text()

        # Make the skill worse: remove frontmatter
        skill_md.write_text("# Test Skill\n\nBroken doc.\n")

        result = judge_candidate(
            skill_dir,
            config,
            baseline,
            apply=True,
        )
        assert result.applied is True
        assert result.kept is False
        # Should revert to baseline copy
        assert skill_md.read_text() == original


class TestAutoEdit:
    def test_auto_edit_invoked_and_judged(self, tmp_path: Path) -> None:
        """Verify that --auto-edit invokes the configured editor and then judges."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(GOOD_SKILL_MD)

        config = load_config(DEFAULT_CONFIG)
        from skillprism.evaluate_skill_rubric import evaluate_skill

        report = evaluate_skill(skill_dir, config)
        save_baseline(skill_dir, report)

        calls: list[str] = []

        def fake_editor(prompt: str) -> str:
            calls.append(prompt)
            # Return unchanged content; judge should revert.
            return GOOD_SKILL_MD

        editor = SkillEditor(caller=fake_editor)

        _run_auto_edit_rounds(
            skill_dir,
            config,
            editor,
            benchmark_registry=None,
            benchmark_output_dir=None,
            code=None,
            min_gain=1.0,
            allow_regression=0.5,
            ratchet=False,
            context=None,
            verbose=False,
            llm_judge=None,
            max_rounds=1,
        )

        assert len(calls) == 1
        assert skill_dir.name in calls[0]
        assert "SKILL.md" in calls[0]

    def test_auto_edit_multi_round_stops_on_revert(self, tmp_path: Path) -> None:
        """Verify that --auto-edit with max_rounds stops when an edit is reverted."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(GOOD_SKILL_MD)

        config = load_config(DEFAULT_CONFIG)
        from skillprism.evaluate_skill_rubric import evaluate_skill

        report = evaluate_skill(skill_dir, config)
        save_baseline(skill_dir, report)

        calls: list[str] = []

        def fake_editor(prompt: str) -> str:
            calls.append(prompt)
            # Always return unchanged content, so judge reverts after first round.
            return GOOD_SKILL_MD

        editor = SkillEditor(caller=fake_editor)

        _run_auto_edit_rounds(
            skill_dir,
            config,
            editor,
            benchmark_registry=None,
            benchmark_output_dir=None,
            code=None,
            min_gain=1.0,
            allow_regression=0.5,
            ratchet=False,
            context=None,
            verbose=False,
            llm_judge=None,
            max_rounds=3,
        )

        # Should stop after the first reverted round.
        assert len(calls) == 1

    def test_stop_on_regression_halts_on_score_drop(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(GOOD_SKILL_MD)

        config = load_config(DEFAULT_CONFIG)
        from skillprism.evaluate_skill_rubric import evaluate_skill

        report = evaluate_skill(skill_dir, config)
        save_baseline(skill_dir, report)

        calls: list[str] = []

        def fake_editor(prompt: str) -> str:
            calls.append(prompt)
            # Return a worse skill
            return "# Broken\n"

        editor = SkillEditor(caller=fake_editor)

        _run_auto_edit_rounds(
            skill_dir,
            config,
            editor,
            benchmark_registry=None,
            benchmark_output_dir=None,
            code=None,
            min_gain=1.0,
            allow_regression=0.0,
            stop_on_regression=True,
            ratchet=False,
            context=None,
            verbose=False,
            llm_judge=None,
            max_rounds=3,
        )

        # Should stop after the first regression round.
        assert len(calls) == 1

    def test_no_stop_on_regression_continues_rounds(self, tmp_path: Path) -> None:
        """--no-stop-on-regression: reverted edits should not stop remaining rounds."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(GOOD_SKILL_MD)

        config = load_config(DEFAULT_CONFIG)
        from skillprism.evaluate_skill_rubric import evaluate_skill

        report = evaluate_skill(skill_dir, config)
        save_baseline(skill_dir, report)

        calls: list[str] = []

        def fake_editor(prompt: str) -> str:
            calls.append(prompt)
            # Always return unchanged content, so every round is reverted.
            return GOOD_SKILL_MD

        editor = SkillEditor(caller=fake_editor)

        _run_auto_edit_rounds(
            skill_dir,
            config,
            editor,
            benchmark_registry=None,
            benchmark_output_dir=None,
            code=None,
            min_gain=1.0,
            allow_regression=0.0,
            stop_on_regression=False,
            ratchet=False,
            context=None,
            verbose=False,
            llm_judge=None,
            max_rounds=3,
        )

        # All rounds should run despite every edit being reverted.
        assert len(calls) == 3
