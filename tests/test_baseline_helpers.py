#!/usr/bin/env python3
"""Tests for skillprism._baseline helpers."""

from __future__ import annotations

from pathlib import Path

from skillprism._baseline import (
    BASELINE_FILE,
    baseline_dir,
    clear_baseline,
    load_baseline,
    load_baseline_skill_md,
    save_baseline,
    snapshot_code_assets,
)
from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config

BASE_SKILL_MD = """---
name: helper-test-skill
description: A skill for testing baseline helpers.
keywords:
  - test
---

# Helper Test Skill

## Quick Start

```bash
echo hello
```
"""


def _make_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "helper-test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD, encoding="utf-8")
    return skill_dir


def test_save_and_load_baseline_roundtrip(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg)

    data = save_baseline(skill_dir, report)
    assert "score" in data
    assert "historical_best_score" in data

    loaded = load_baseline(skill_dir)
    assert loaded is not None
    assert loaded["score"] == data["score"]
    assert loaded["historical_best_score"] == data["historical_best_score"]


def test_load_baseline_skill_md_falls_back_to_head(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    assert load_baseline_skill_md(skill_dir) == ""


def test_clear_baseline(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg)
    save_baseline(skill_dir, report)
    baseline_file = baseline_dir(skill_dir) / BASELINE_FILE
    assert baseline_file.exists()

    clear_baseline(skill_dir)
    assert not baseline_file.exists()


def test_baseline_dir_created(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg)
    save_baseline(skill_dir, report)
    assert (baseline_dir(skill_dir) / "SKILL.md").exists()
    assert (baseline_dir(skill_dir) / "SKILL.md.bak").exists()


def test_snapshot_code_assets(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    examples = skill_dir / "examples"
    examples.mkdir()
    (examples / "demo.py").write_text("print('demo')", encoding="utf-8")
    snapshot = snapshot_code_assets(skill_dir)
    assert snapshot.exists()
    assert (snapshot / "examples" / "demo.py").exists()
