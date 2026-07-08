#!/usr/bin/env python3
"""P0-1: revert primitive must discard the uncommitted candidate edit.

The candidate edit is never committed before judging (it is committed only in
the KEEP branch). ``git revert HEAD`` would therefore undo the *previous*
baseline commit and silently move the repo to a state older than the baseline.
The correct primitive is ``git checkout HEAD -- SKILL.md`` (discard uncommitted
working-tree + index changes), which leaves HEAD unchanged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config
from skillprism.optimize_skill import git_revert, judge_candidate, load_baseline, save_baseline

BASE_SKILL_MD = """---
name: revert-test-skill
description: A skill for testing the revert primitive.
keywords:
  - test
---

# Revert Test Skill

## When to Use

Use this skill to test that reverting an uncommitted edit restores HEAD.

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


def _git(skill_dir: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(skill_dir), *args], check=True, capture_output=True)


def _init_repo(skill_dir: Path) -> None:
    _git(skill_dir, "init")
    _git(skill_dir, "config", "user.email", "test@example.com")
    _git(skill_dir, "config", "user.name", "Test")
    _git(skill_dir, "add", "SKILL.md")
    _git(skill_dir, "commit", "-m", "baseline")


def test_git_revert_discards_uncommitted_edit_without_new_commit(tmp_path: Path) -> None:
    """git_revert restores SKILL.md to HEAD and creates no new commit."""
    skill_dir = tmp_path / "revert_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD, encoding="utf-8")
    _init_repo(skill_dir)

    head_before = subprocess.run(
        ["git", "-C", str(skill_dir), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    # Uncommitted candidate edit (staged, like render_diff would do).
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD + "\nbad candidate edit\n", encoding="utf-8")
    _git(skill_dir, "add", "SKILL.md")

    git_revert(skill_dir)

    head_after = subprocess.run(
        ["git", "-C", str(skill_dir), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert head_before == head_after, "git_revert must not create a new commit"

    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == BASE_SKILL_MD
    status = subprocess.run(
        ["git", "-C", str(skill_dir), "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    assert "SKILL.md" not in status, "working tree must be clean after revert"


def test_judge_candidate_revert_restores_baseline_content(tmp_path: Path) -> None:
    """judge_candidate with apply=True REVERT decision restores SKILL.md to baseline."""
    skill_dir = tmp_path / "judge_revert_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD, encoding="utf-8")
    _init_repo(skill_dir)

    config = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, config)
    save_baseline(skill_dir, report)
    baseline = load_baseline(skill_dir)
    assert baseline is not None

    head_before = subprocess.run(
        ["git", "-C", str(skill_dir), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    # Candidate edit that does NOT improve enough → REVERT (min_gain impossible to meet).
    candidate_md = BASE_SKILL_MD.replace("# Revert Test Skill", "# Revert Test Skill (tweaked)")
    (skill_dir / "SKILL.md").write_text(candidate_md, encoding="utf-8")
    _git(skill_dir, "add", "SKILL.md")

    result = judge_candidate(
        skill_dir,
        config,
        baseline,
        apply=True,
        min_gain=9999.0,  # force REVERT: no edit can gain 9999 points
        show_diff=True,
    )

    assert result.applied is True
    assert result.kept is False, "min_gain=9999 must force a REVERT decision"

    # SKILL.md restored to baseline content (HEAD), not the candidate.
    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == BASE_SKILL_MD

    head_after = subprocess.run(
        ["git", "-C", str(skill_dir), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert head_before == head_after, "revert must not create a new commit"

    log = subprocess.run(
        ["git", "-C", str(skill_dir), "log", "--oneline"], capture_output=True, text=True
    ).stdout.strip()
    assert len(log.splitlines()) == 1, "no revert commit should be synthesized"
