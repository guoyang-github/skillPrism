#!/usr/bin/env python3
"""Tests for evaluate-skill prompt/verification location and --all filtering.

Covers:
1. test-prompts.json defaults to ``artifacts/<skill>/`` (cwd-relative); the
   skill tree stays read-only unless passed explicitly as --prompts-dir.
2. Auto-generated template prompts carry a quality warning; authored prompts
   do not; missing prompts produce a creation hint.
3. prompts_verification.json is auto-discovered from ``artifacts/<skill>/``
   when --prompts-verification is not passed.
4. With --all, --prompts-dir is split per skill to avoid collisions.
5. evaluate-skill --all skips the skill-prism meta-skill.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from skillprism.evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    _resolve_skill_paths,
    _run_evaluations,
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


def test_prompts_default_written_to_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    skill_dir = _make_skill(tmp_path, "sample-skill")
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg)  # no prompts_dir -> artifacts/<skill>/
    assert (tmp_path / "artifacts" / "sample-skill" / "test-prompts.json").exists()
    assert not (skill_dir / "test-prompts.json").exists()
    # Auto-generated templates must be flagged as placeholders.
    assert "template prompts" in report.test_prompts_report


def test_prompts_dir_skill_tree_opt_in(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path, "sample-skill")
    cfg = load_config(DEFAULT_CONFIG)
    evaluate_skill(skill_dir, cfg, prompts_dir=skill_dir)
    assert (skill_dir / "test-prompts.json").exists()


def test_authored_prompts_no_warning(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path, "sample-skill")
    prompts_dir = tmp_path / "artifacts" / "sample-skill"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "test-prompts.json").write_text(
        json.dumps([{"id": 1, "scenario": "happy path", "prompt": "p", "expected": "e"}]),
        encoding="utf-8",
    )
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg, prompts_dir=prompts_dir)
    assert "1 prompt(s) ready" in report.test_prompts_report
    assert "⚠" not in report.test_prompts_report


def test_missing_prompts_hint(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path, "sample-skill")
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(
        skill_dir, cfg, auto_generate_prompts=False, prompts_dir=tmp_path / "empty"
    )
    assert "missing" in report.test_prompts_report
    assert "PROMPTS_VERIFICATION" in report.test_prompts_report
    assert not (tmp_path / "empty" / "test-prompts.json").exists()


def test_verification_auto_discovered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
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
    ver_path = tmp_path / "artifacts" / "sample-skill" / "prompts_verification.json"
    ver_path.parent.mkdir(parents=True)
    save_prompts_verification(ver_path, report_obj)

    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg, auto_generate_prompts=False)
    assert report.prompts_verification is not None
    assert report.prompts_verification.pass_rate == 1.0
    assert report.prompts_verification_report


def test_run_evaluations_all_splits_prompts_dir(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    alpha = _make_skill(skills_root, "alpha-skill")
    beta = _make_skill(skills_root, "beta-skill")
    prompts_dir = tmp_path / "artifacts"
    ns = Namespace(
        prompts_dir=str(prompts_dir),
        verbose=False,
        type=None,
        run_smoke=False,
        run_deps=False,
        allow_exec=False,
        no_generate_prompts=False,
    )
    cfg = load_config(DEFAULT_CONFIG)
    _run_evaluations([alpha, beta], cfg, ns, None, None, None)
    assert (prompts_dir / "alpha-skill" / "test-prompts.json").exists()
    assert (prompts_dir / "beta-skill" / "test-prompts.json").exists()
    assert not (prompts_dir / "test-prompts.json").exists()


def test_resolve_skill_paths_skips_skill_prism(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    _make_skill(skills_root, "skill-prism")
    _make_skill(skills_root, "alpha-skill")
    ns = Namespace(all=True, skills_dir=str(skills_root), skill=None)
    paths = _resolve_skill_paths(ns, tmp_path)
    names = [p.name for p in paths]
    assert names == ["alpha-skill"]
    assert "skill-prism" not in names


def test_llm_judgments_auto_discovered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    skill_dir = _make_skill(tmp_path, "sample-skill")
    judgments = {
        "judges": [
            {
                "dimension": "D2",
                "scores": [5, 5],
                "reasons": ["great", "great"],
                "aggregated_score": 5,
                "aggregate": "mean",
            }
        ]
    }
    jpath = tmp_path / "artifacts" / "sample-skill" / "llm_judgments.json"
    jpath.parent.mkdir(parents=True)
    jpath.write_text(json.dumps(judgments), encoding="utf-8")

    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg, auto_generate_prompts=False)
    assert report.llm_judgments is not None
    assert report.llm_judgments["D2"].aggregated_score == 5
    d2 = next(d for d in report.dimensions if d.code == "D2")
    assert any("LLM judges" in e for e in d2.evidence)
