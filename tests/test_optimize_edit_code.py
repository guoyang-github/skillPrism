#!/usr/bin/env python3
"""Tests for improve-skill --edit-code support."""

from __future__ import annotations

from pathlib import Path

from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config
from skillprism.optimize_skill import (
    judge_candidate,
    load_baseline,
    restore_code_assets,
    save_baseline,
    snapshot_code_assets,
)

BASE_SKILL_MD = """---
name: edit-code-test-skill
description: A skill for edit-code tests.
keywords:
  - test
---

# Edit Code Test Skill

## When to Use

Use this skill to test code asset editing.
"""


def test_snapshot_and_restore_code_assets(tmp_path: Path) -> None:
    skill_dir = tmp_path / "edit_code_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD)
    examples_dir = skill_dir / "examples"
    examples_dir.mkdir()
    (examples_dir / "minimal_example.py").write_text("print('hello')\n")
    (skill_dir / "requirements.txt").write_text("pyyaml\n")

    snapshot_code_assets(skill_dir)

    # Modify assets
    (examples_dir / "minimal_example.py").write_text("print('broken')\n")
    (skill_dir / "requirements.txt").write_text("numpy\n")

    restore_code_assets(skill_dir)

    assert (examples_dir / "minimal_example.py").read_text() == "print('hello')\n"
    assert (skill_dir / "requirements.txt").read_text() == "pyyaml\n"


def test_edit_code_with_smoke_failure_is_reverted(tmp_path: Path) -> None:
    skill_dir = tmp_path / "edit_code_skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(BASE_SKILL_MD)
    examples_dir = skill_dir / "examples"
    examples_dir.mkdir()
    (examples_dir / "minimal_example.py").write_text("print('hello')\n")

    config = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, config)
    save_baseline(skill_dir, report)
    baseline = load_baseline(skill_dir)

    # Simulate an editor that makes SKILL.md worse and code invalid
    snapshot_code_assets(skill_dir)
    skill_md.write_text(BASE_SKILL_MD + "\n## Version\n\nPython 3.9+\n")
    (examples_dir / "minimal_example.py").write_text("print('hello'\n")  # syntax error

    result = judge_candidate(
        skill_dir,
        config,
        baseline,
        apply=True,
        min_gain=0.1,
        edit_code=True,
    )
    assert result.applied is True
    assert result.kept is False
    # Code asset should be restored
    assert (examples_dir / "minimal_example.py").read_text() == "print('hello')\n"
