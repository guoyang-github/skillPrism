#!/usr/bin/env python3
"""End-to-end tests for the improve-skill workflow."""

from __future__ import annotations

from pathlib import Path

from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config
from skillprism.optimize_skill import load_baseline, save_baseline

BASE_SKILL_MD = """---
name: e2e-test-skill
description: A skill for end-to-end optimizer testing.
keywords:
  - test
---

# E2E Test Skill

## When to Use

Use this skill to test the full optimize workflow.

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


def test_e2e_record_baseline_and_judge(tmp_path: Path) -> None:
    skill_dir = tmp_path / "e2e_skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(BASE_SKILL_MD)

    config = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, config)
    save_baseline(skill_dir, report)

    baseline = load_baseline(skill_dir)
    assert baseline is not None
    assert baseline["score"] > 0

    # Simulate an improvement: add dependency file + version compatibility notes.
    improved_md = BASE_SKILL_MD.replace(
        "## Outputs",
        "## Version Compatibility\n\nCompatible with Python 3.9+ and pyyaml>=6.0.\n\n## Outputs",
    )
    skill_md.write_text(improved_md, encoding="utf-8")
    (skill_dir / "requirements.txt").write_text("pyyaml>=6.0\n", encoding="utf-8")

    from skillprism.optimize_skill import judge_candidate

    result = judge_candidate(
        skill_dir,
        config,
        baseline,
        apply=True,
        min_gain=0.1,
    )
    assert result.applied is True
    # The edit should be kept because dependency reproducibility improved
    assert result.kept is True
    assert result.current_score > result.baseline_score
