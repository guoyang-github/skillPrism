#!/usr/bin/env python3
"""Tests for improve-skill diff rendering."""

from __future__ import annotations

from pathlib import Path

from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config
from skillprism.optimize_skill import judge_candidate, load_baseline, render_diff, save_baseline

BASE_SKILL_MD = """---
name: diff-test-skill
description: A skill for diff rendering tests.
keywords:
  - test
---

# Diff Test Skill

## When to Use

Use this skill to test diff rendering.
"""


def test_render_diff_uses_difflib_when_not_git(tmp_path: Path) -> None:
    diff = render_diff(tmp_path, BASE_SKILL_MD, BASE_SKILL_MD + "\n## New Section\n")
    assert "SKILL.md (baseline)" in diff
    assert "+## New Section" in diff


def test_render_diff_truncates_long_diff(tmp_path: Path) -> None:
    long_md = BASE_SKILL_MD + "\n".join(f"line {i}" for i in range(500))
    diff = render_diff(tmp_path, BASE_SKILL_MD, long_md, max_lines=10)
    assert "... (" in diff


def test_judge_result_includes_diff(tmp_path: Path) -> None:
    skill_dir = tmp_path / "diff_skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(BASE_SKILL_MD)

    config = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, config)
    save_baseline(skill_dir, report)
    baseline = load_baseline(skill_dir)

    skill_md.write_text(BASE_SKILL_MD + "\n## New Section\n")

    result = judge_candidate(
        skill_dir,
        config,
        baseline,
        apply=False,
        show_diff=True,
        diff_lines=200,
    )
    assert "+## New Section" in result.diff


def test_judge_result_diff_empty_when_disabled(tmp_path: Path) -> None:
    skill_dir = tmp_path / "diff_skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(BASE_SKILL_MD)

    config = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, config)
    save_baseline(skill_dir, report)
    baseline = load_baseline(skill_dir)

    skill_md.write_text(BASE_SKILL_MD + "\n## New Section\n")

    result = judge_candidate(
        skill_dir,
        config,
        baseline,
        apply=False,
        show_diff=False,
    )
    assert result.diff == ""
