#!/usr/bin/env python3
"""P0-4: bloat guard must respect dry-run (apply=False).

Previously ``check_bloat`` unconditionally called ``save_skill_md(baseline)``
on an error-severity bloat finding, overwriting SKILL.md even without ``--apply``
— violating the dry-run contract. It also never passed the baseline path to
``check_bloat``, so the guard silently never fired. Both are fixed here.
"""

from __future__ import annotations

from pathlib import Path

from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config
from skillprism.optimize_skill import judge_candidate, load_baseline, save_baseline

BASE_SKILL_MD = """---
name: bloat-test-skill
description: A skill for testing the bloat guard dry-run behavior.
keywords:
  - test
---

# Bloat Test Skill

## When to Use

Use this skill to test bloat guard dry-run.

## Quick Start

```bash
echo hello
```
"""

# Padding to force >150% of baseline size when appended.
PADDING = "\n" + ("x" * 4000) + "\n"


def _setup_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "bloat_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD, encoding="utf-8")
    config = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, config)
    save_baseline(skill_dir, report)
    return skill_dir


def test_bloat_guard_dry_run_does_not_overwrite(tmp_path: Path) -> None:
    skill_dir = _setup_skill(tmp_path)
    baseline = load_baseline(skill_dir)
    assert baseline is not None
    skill_md = skill_dir / "SKILL.md"

    # Candidate edit: bloat SKILL.md to >150% of baseline.
    bloated_md = BASE_SKILL_MD + PADDING
    skill_md.write_text(bloated_md, encoding="utf-8")

    config = load_config(DEFAULT_CONFIG)
    result = judge_candidate(skill_dir, config, baseline, apply=False, min_gain=0.1)

    assert result.kept is False, "bloat guard must reject"
    assert result.applied is False, "dry-run must not apply"
    assert "bloat" in result.decision_reason.lower()

    # SKILL.md must be untouched (still the bloated candidate, NOT reverted).
    assert skill_md.read_text(encoding="utf-8") == bloated_md


def test_bloat_guard_apply_reverts_to_baseline(tmp_path: Path) -> None:
    skill_dir = _setup_skill(tmp_path)
    baseline = load_baseline(skill_dir)
    assert baseline is not None
    skill_md = skill_dir / "SKILL.md"

    bloated_md = BASE_SKILL_MD + PADDING
    skill_md.write_text(bloated_md, encoding="utf-8")

    config = load_config(DEFAULT_CONFIG)
    result = judge_candidate(skill_dir, config, baseline, apply=True, min_gain=0.1)

    assert result.kept is False
    assert result.applied is True, "apply=True reverts the bloated edit"
    # SKILL.md restored to baseline content.
    assert skill_md.read_text(encoding="utf-8") == BASE_SKILL_MD
