#!/usr/bin/env python3
"""Tests for evaluate-skill prompt/verification location and --all filtering.

Covers three behaviors:
1. test-prompts.json defaults to the skill tree, and --prompts-dir redirects it
   (decoupled from --output).
2. .skillprism_prompts_verification.json is auto-discovered per skill when
   --prompts-verification is not passed.
3. evaluate-skill --all skips the skill-prism meta-skill.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from skillprism.evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    _resolve_skill_paths,
    evaluate_skill,
    load_config,
)
from skillprism.prompts_verification import (
    PromptsVerificationReport,
    PromptVerificationResult,
    save_prompts_verification,
)

SKILL_MD = """---
name: sample-skill
description: A minimal skill for location tests.
keywords:
  - test
---

# Sample Skill

## Quick Start

```bash
echo hello
```
"""


def _make_skill(root: Path, name: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    return skill_dir


def test_prompts_default_written_to_skill_tree(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path, "sample-skill")
    cfg = load_config(DEFAULT_CONFIG)
    evaluate_skill(skill_dir, cfg)  # no prompts_dir -> skill tree
    assert (skill_dir / "test-prompts.json").exists()


def test_prompts_dir_redirects_output(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path, "sample-skill")
    prompts_dir = tmp_path / "artifacts" / "sample-skill"
    cfg = load_config(DEFAULT_CONFIG)
    evaluate_skill(skill_dir, cfg, prompts_dir=prompts_dir)
    assert (prompts_dir / "test-prompts.json").exists()
    assert not (skill_dir / "test-prompts.json").exists()


def test_verification_auto_discovered(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path, "sample-skill")
    report_obj = PromptsVerificationReport(
        skill="sample-skill",
        results=[
            PromptVerificationResult(
                prompt_id=1,
                prompt="do the thing",
                without_skill_output="bad",
                with_skill_output="good",
                expected="good",
                improvement_score=1.0,
                passed=True,
            )
        ],
    )
    save_prompts_verification(skill_dir / ".skillprism_prompts_verification.json", report_obj)

    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg, auto_generate_prompts=False)
    assert report.prompts_verification is not None
    assert report.prompts_verification.pass_rate == 1.0
    assert report.prompts_verification_report


def test_resolve_skill_paths_skips_skill_prism(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    _make_skill(skills_root, "skill-prism")
    _make_skill(skills_root, "alpha-skill")
    ns = Namespace(all=True, skills_dir=str(skills_root), skill=None)
    paths = _resolve_skill_paths(ns, tmp_path)
    names = [p.name for p in paths]
    assert names == ["alpha-skill"]
    assert "skill-prism" not in names
